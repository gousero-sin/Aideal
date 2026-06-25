#!/usr/bin/env python3
"""Atualiza pontualmente o template DRE para as correções do Painel AIDEAL.

O template pode conter extensões OOXML legadas que não sobrevivem a uma
regravação completa por bibliotecas de planilha. Por isso este utilitário altera
somente os fragmentos XML necessários; a geração final continua em modo
Excel-safe, que remove slicers e outros artefatos não suportados.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"

_CELL_REF_RE = re.compile(r"(?P<column>\$?[A-Z]{1,3})(?P<row_absolute>\$?)(?P<row>\d+)")
_ROW_RE = re.compile(r'<row\b[^>]*\br="(?P<row>\d+)"[^>]*>.*?</row>', re.DOTALL)
_SHEET_DATA_RE = re.compile(
    r"(?P<open><sheetData\b[^>]*>)(?P<body>.*?)(?P<close></sheetData>)",
    re.DOTALL,
)
_CELL_XML_RE = re.compile(r'<c\b(?=[^>]*\br="(?P<ref>[A-Z]+\d+)")[^>]*(?:/>|>.*?</c>)', re.DOTALL)

# Inserções antes da linha original. As linhas novas ficam dentro dos blocos
# recolhidos correspondentes; a linha 67 já era reservada e sem rótulo.
_DRE_INSERTIONS = ((62, 2), (89, 2))
_DRE_NEW_ROWS = {
    62: (61, "AUXILIO MORADIA"),
    63: (61, "VALE TRANSPORTE"),
    69: (66, "Mão de Obra Terceirizada"),
    91: (88, "Manutenção da Sede"),
    92: (88, "Marketing"),
}
_EMPRESTIMO_ORIGINAL_ROWS = {152: 154, 153: 154}

_PLANO_UPDATES = {
    141: {
        "B": "Despesas Não Operacionais",
        "C": "(-) Despesas Não Operacionais",
        "D": "(+/-)Despesas e Recebimentos Não Operacionais",
        "E": 5,
    },
    163: {
        "A": "8.5 - MAQUINAS/EQUIPAMENTOS - IMOBILIZADO",
        "B": "Aquisição de Maquinas e Equipamentos",
        "C": "Investimentos",
        "D": "(-)Investimentos",
        "E": 8,
    },
    172: {
        "B": "Despesas Não Operacionais",
        "C": "(-) Despesas Não Operacionais",
        "D": "(+/-)Despesas e Recebimentos Não Operacionais",
        "E": 5,
    },
    181: {
        "B": "Manutenção da Sede",
        "C": "Despesas Administrativas",
        "D": "(-)Gastos Fixos",
        "E": 4,
    },
    183: {
        "A": "6.11 - COMPRA VENDA VEICULOS",
        "B": "Compra de veiculos",
        "C": "Investimentos",
        "D": "(-)Investimentos",
        "E": 8,
    },
    184: {
        "B": "Financiamento",
        "C": "(-) Despesas Financeiras",
        "D": "(+/-)Despesas e Receitas Financeiras",
        "E": 6,
    },
    194: {
        "B": "Despesas Não Operacionais",
        "C": "(-) Despesas Não Operacionais",
        "D": "(+/-)Despesas e Recebimentos Não Operacionais",
        "E": 5,
    },
}
_PLANO_NEW_ROWS = (
    (
        "3.20 - MÃO DE OBRA TERCEIRIZADA",
        "Mão de Obra Terceirizada",
        "Serviços de Terceiros",
        "(-)Gastos Fixos",
        4,
    ),
    ("3.21 - MARKETING", "Marketing", "Despesas Administrativas", "(-)Gastos Fixos", 4),
    (
        "11.17 - MANUTENÇÃO DA SEDE",
        "Manutenção da Sede",
        "Despesas Administrativas",
        "(-)Gastos Fixos",
        4,
    ),
    (
        "11.18 - DESPESA NÃO OPERACIONAL",
        "Despesas Não Operacionais",
        "(-) Despesas Não Operacionais",
        "(+/-)Despesas e Recebimentos Não Operacionais",
        5,
    ),
    ("12.19 - AUXILIO MORADIA", "AUXILIO MORADIA", "Despesas com Pessoal", "(-)Gastos Fixos", 4),
    ("12.20 - VALE TRANSPORTE", "VALE TRANSPORTE", "Despesas com Pessoal", "(-)Gastos Fixos", 4),
    (
        "15.5 - MANUTENÇÃO DA SEDE",
        "Manutenção da Sede",
        "Despesas Administrativas",
        "(-)Gastos Fixos",
        4,
    ),
)


def _sheet_part(parts: dict[str, bytes], sheet_name: str) -> str:
    workbook = parts["xl/workbook.xml"].decode("utf-8")
    rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    match = re.search(
        rf'<sheet\b(?=[^>]*\bname="{re.escape(sheet_name)}")[^>]*\br:id="(?P<rid>[^"]+)"[^>]*/>',
        workbook,
    )
    if not match:
        raise ValueError(f"Aba ausente no template: {sheet_name}")
    rel_match = re.search(
        rf'<Relationship\b(?=[^>]*\bId="{re.escape(match.group("rid"))}")[^>]*\bTarget="(?P<target>[^"]+)"[^>]*/>',
        rels,
    )
    if not rel_match:
        raise ValueError(f"Relacionamento ausente para a aba: {sheet_name}")
    return f"xl/{rel_match.group('target').lstrip('/')}"


def _shift_row(row: int) -> int:
    return row + sum(count for start, count in _DRE_INSERTIONS if row >= start)


def _shift_references(xml: str) -> str:
    def replace(match: re.Match[str]) -> str:
        coluna = match.group("column")
        linha_absoluta = match.group("row_absolute")
        linha = _shift_row(int(match.group("row")))
        return f"{coluna}{linha_absoluta}{linha}"

    return _CELL_REF_RE.sub(replace, xml)


def _translate_relative_references(xml: str, delta: int) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group("row_absolute"):
            return match.group(0)
        return f"{match.group('column')}{int(match.group('row')) + delta}"

    return _CELL_REF_RE.sub(replace, xml)


def _set_row_number(row_xml: str, row: int) -> str:
    return re.sub(r'(<row\b[^>]*\br=")\d+(")', rf"\g<1>{row}\2", row_xml, count=1)


def _inline_string_cell(column: str, row: int, value: str) -> str:
    return f'<c r="{column}{row}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _number_cell(column: str, row: int, value: int) -> str:
    return f'<c r="{column}{row}"><v>{value}</v></c>'


def _replace_cell(row_xml: str, column: str, row: int, value: str | int) -> str:
    cell = (
        _number_cell(column, row, value)
        if isinstance(value, int)
        else _inline_string_cell(column, row, value)
    )
    pattern = re.compile(rf'<c\b(?=[^>]*\br="{column}{row}")[^>]*(?:/>|>.*?</c>)', re.DOTALL)
    if pattern.search(row_xml):
        return pattern.sub(cell, row_xml, count=1)
    return re.sub(r"(<row\b[^>]*>)", rf"\1{cell}", row_xml, count=1)


def _copiar_celulas_calculadas(
    destino_xml: str,
    origem_xml: str,
    destino_linha: int,
    origem_linha: int,
) -> str:
    """Copia B:AI de uma linha de detalhe, preservando o rótulo da destino."""
    origem_ajustada = _translate_relative_references(origem_xml, destino_linha - origem_linha)
    cells_por_coluna = {}
    for match in _CELL_XML_RE.finditer(origem_ajustada):
        coluna = re.match(r"([A-Z]+)\d+", match.group("ref")).group(1)
        if coluna != "A":
            cells_por_coluna[coluna] = match.group(0)
    resultado = destino_xml
    for coluna, cell_xml in cells_por_coluna.items():
        pattern = re.compile(
            rf'<c\b(?=[^>]*\br="{coluna}{destino_linha}")[^>]*(?:/>|>.*?</c>)',
            re.DOTALL,
        )
        resultado = pattern.sub(cell_xml, resultado, count=1)
    return resultado


def _dre_sheet_xml(xml: str) -> str:
    match = _SHEET_DATA_RE.search(xml)
    if not match:
        raise ValueError("sheetData não encontrado na aba DRE")

    original_rows = {
        int(row_match.group("row")): row_match.group(0)
        for row_match in _ROW_RE.finditer(match.group("body"))
    }
    if not original_rows:
        raise ValueError("Linhas não encontradas na aba DRE")

    rendered_rows: list[str] = []
    for original_row in sorted(original_rows):
        if original_row == 62:
            novas_linhas_pessoal = ((62, _DRE_NEW_ROWS[62]), (63, _DRE_NEW_ROWS[63]))
            for target_row, (source_row, label) in novas_linhas_pessoal:
                clone = _translate_relative_references(
                    original_rows[source_row],
                    target_row - source_row,
                )
                clone = _set_row_number(clone, target_row)
                rendered_rows.append(_replace_cell(clone, "A", target_row, label))

        moved_row = _shift_row(original_row)
        if original_row == 67:
            source_row, label = _DRE_NEW_ROWS[moved_row]
            clone = _translate_relative_references(
                original_rows[source_row],
                moved_row - source_row,
            )
            clone = _set_row_number(clone, moved_row)
            rendered_rows.append(_replace_cell(clone, "A", moved_row, label))
            continue

        row_base = original_rows[original_row]
        if original_row in _EMPRESTIMO_ORIGINAL_ROWS:
            row_base = _copiar_celulas_calculadas(
                row_base,
                original_rows[_EMPRESTIMO_ORIGINAL_ROWS[original_row]],
                original_row,
                _EMPRESTIMO_ORIGINAL_ROWS[original_row],
            )
        row_xml = _shift_references(row_base)
        row_xml = _set_row_number(row_xml, moved_row)
        rendered_rows.append(row_xml)

        if original_row == 88:
            for target_row in (91, 92):
                source_row, label = _DRE_NEW_ROWS[target_row]
                clone = _translate_relative_references(
                    original_rows[source_row],
                    target_row - source_row,
                )
                clone = _set_row_number(clone, target_row)
                rendered_rows.append(_replace_cell(clone, "A", target_row, label))

    prefix = _shift_references(xml[: match.start("body")])
    suffix = _shift_references(xml[match.end("body") :])
    return f"{prefix}{''.join(rendered_rows)}{suffix}"


def _corrigir_linhas_emprestimo_aplicadas(xml: str) -> str:
    """Repara modelos já atualizados que mantinham valores cacheados no empréstimo."""
    match = _SHEET_DATA_RE.search(xml)
    if not match:
        raise ValueError("sheetData não encontrado na aba DRE")
    rows = {
        int(row_match.group("row")): row_match.group(0)
        for row_match in _ROW_RE.finditer(match.group("body"))
    }
    for destino in (156, 157):
        rows[destino] = _copiar_celulas_calculadas(rows[destino], rows[158], destino, 158)
    body = "".join(rows[row] for row in sorted(rows))
    return f"{xml[: match.start('body')]}{body}{xml[match.end('body') :]}"


def _plano_sheet_xml(xml: str) -> str:
    match = _SHEET_DATA_RE.search(xml)
    if not match:
        raise ValueError("sheetData não encontrado na aba PLANO_CONTAS")
    rows = {
        int(row_match.group("row")): row_match.group(0)
        for row_match in _ROW_RE.finditer(match.group("body"))
    }
    if 207 not in rows:
        raise ValueError("Linha modelo 207 ausente na aba PLANO_CONTAS")

    for row_number, values in _PLANO_UPDATES.items():
        row_xml = rows[row_number]
        for column, value in values.items():
            row_xml = _replace_cell(row_xml, column, row_number, value)
        rows[row_number] = row_xml

    model_row = rows[207]
    for index, values in enumerate(_PLANO_NEW_ROWS, start=208):
        row_xml = _translate_relative_references(model_row, index - 207)
        row_xml = _set_row_number(row_xml, index)
        for column, value in zip(("A", "B", "C", "D", "E"), values, strict=True):
            row_xml = _replace_cell(row_xml, column, index, value)
        rows[index] = row_xml

    body = "".join(rows[row] for row in sorted(rows))
    return f"{xml[: match.start('body')]}{body}{xml[match.end('body') :]}"


def _update_table_ref(xml: str, old_ref: str, new_ref: str) -> str:
    if old_ref not in xml:
        raise ValueError(f"Referência de tabela ausente: {old_ref}")
    return xml.replace(old_ref, new_ref)


def _update_defined_names(xml: str) -> str:
    def replace(match: re.Match[str]) -> str:
        content = match.group("content")
        if "DRE!" not in content and "'DRE'!" not in content:
            return match.group(0)
        return match.group("open") + _shift_references(content) + match.group("close")

    return re.sub(
        r"(?P<open><definedName\b[^>]*>)(?P<content>.*?)(?P<close></definedName>)",
        replace,
        xml,
        flags=re.DOTALL,
    )


def atualizar(template_path: Path) -> None:
    with ZipFile(template_path, "r") as source:
        parts = {name: source.read(name) for name in source.namelist()}

    dre_part = _sheet_part(parts, "DRE")
    plano_part = _sheet_part(parts, "PLANO_CONTAS")
    if b"AUXILIO MORADIA" in parts[dre_part]:
        dre_xml = _corrigir_linhas_emprestimo_aplicadas(parts[dre_part].decode("utf-8"))
        parts[dre_part] = dre_xml.encode("utf-8")
    else:
        parts[dre_part] = _dre_sheet_xml(parts[dre_part].decode("utf-8")).encode("utf-8")
        workbook_xml = _update_defined_names(parts["xl/workbook.xml"].decode("utf-8"))
        parts["xl/workbook.xml"] = workbook_xml.encode("utf-8")
    parts[plano_part] = _plano_sheet_xml(parts[plano_part].decode("utf-8")).encode("utf-8")

    for name, payload in list(parts.items()):
        if not name.startswith("xl/tables/") or not name.endswith(".xml"):
            continue
        xml = payload.decode("utf-8")
        if 'ref="A5:AI185"' in xml:
            parts[name] = _update_table_ref(xml, "A5:AI185", "A5:AI189").encode("utf-8")
        elif 'ref="A1:E207"' in xml:
            parts[name] = _update_table_ref(xml, "A1:E207", "A1:E214").encode("utf-8")

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx",
        delete=False,
        dir=template_path.parent,
    ) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        with ZipFile(temp_path, "w", ZIP_DEFLATED) as destination:
            for name, payload in parts.items():
                destination.writestr(name, payload)
        shutil.move(temp_path, template_path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()
    atualizar(args.template)
    print(f"[ok] template atualizado: {args.template}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
