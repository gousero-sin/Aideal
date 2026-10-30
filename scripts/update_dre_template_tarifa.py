#!/usr/bin/env python3
"""Move a Tarifa de Antecipação das deduções para as Despesas Financeiras no template DRE.

A tarifa de antecipação é custo financeiro do recebível, não tributo sobre a
venda. No template legado ela aparece em "Impostos sobre vendas" (DRE!A15) e o
PLANO_CONTAS a classifica em "(-)Deduções sobre vendas". Este utilitário:

- move o rótulo de DRE!A15 para DRE!A165, a linha livre sob "(-) Despesas
  Financeiras", preservando o estilo das duas células;
- reclassifica a linha da tarifa no PLANO_CONTAS para "(-) Despesas
  Financeiras" / "(+/-)Despesas e Receitas Financeiras" / código 6.

As fórmulas VLOOKUP($A15/$A165, APOIO...) já existem nas duas linhas, então só o
rótulo muda de lugar. Como em update_dre_template_painel.py, o template é
alterado por patch dos fragmentos XML no zip: bibliotecas de planilha descartam
slicers e extensões OOXML ao regravar o arquivo. O script é idempotente.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from html import unescape
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"

TARIFA_ROTULO = "Tarifa de Antecipação"
DESPESAS_FINANCEIRAS_ROTULO = "(-) Despesas Financeiras"
FINANCEIRO_ROTULO = "(+/-)Despesas e Receitas Financeiras"
NAO_OPERACIONAL_ROTULO = "(+/-)Despesas e Recebimentos Não Operacionais"
FINANCEIRO_COD = 6

# Linha de origem (bloco Impostos sobre vendas) e linha livre de destino, entre
# os filhos de "(-) Despesas Financeiras" (159) e o bloco não operacional (167).
_DRE_LINHA_ORIGEM = 15
_DRE_LINHA_DESTINO = 165
_DRE_LINHA_DESPESAS_FINANCEIRAS = 159
_DRE_LINHA_NAO_OPERACIONAL = 167

_SI_RE = re.compile(r"<si>(?P<body>.*?)</si>", re.DOTALL)
_T_RE = re.compile(r"<t\b[^>]*>(?P<text>.*?)</t>", re.DOTALL)
_CELL_RE_TEMPLATE = (
    r'<c\b(?=[^>]*\br="{ref}")(?P<attrs>[^>]*?)(?:/>|>(?P<body>.*?)</c>)'
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


def _shared_strings(xml: str) -> list[str]:
    return [
        unescape("".join(t.group("text") for t in _T_RE.finditer(si.group("body"))))
        for si in _SI_RE.finditer(xml)
    ]


def _indice_sst(strings: list[str], texto: str) -> int:
    """Reutiliza a entrada existente; o patch não acrescenta textos ao sharedStrings."""
    try:
        return strings.index(texto)
    except ValueError as exc:
        raise ValueError(
            f"Texto ausente no sharedStrings do template: {texto}"
        ) from exc


def _cell_match(xml: str, ref: str) -> re.Match[str]:
    match = re.search(_CELL_RE_TEMPLATE.format(ref=ref), xml, re.DOTALL)
    if not match:
        raise ValueError(f"Célula ausente no template: {ref}")
    return match


def _texto_celula(xml: str, ref: str, strings: list[str]) -> str:
    match = _cell_match(xml, ref)
    body = match.group("body") or ""
    valor = re.search(r"<v>(?P<v>[^<]*)</v>", body)
    if not valor:
        inline = _T_RE.search(body)
        return unescape(inline.group("text")).strip() if inline else ""
    if 't="s"' in match.group("attrs"):
        return strings[int(valor.group("v"))].strip()
    return unescape(valor.group("v")).strip()


def _atributos_sem_tipo(attrs: str) -> str:
    return re.sub(r'\s+t="[^"]*"', "", attrs).rstrip()


def _celula_texto_sst(xml: str, ref: str, indice: int) -> str:
    """Grava a célula como referência ao sharedStrings, preservando r= e s=."""
    match = _cell_match(xml, ref)
    nova = f'<c{_atributos_sem_tipo(match.group("attrs"))} t="s"><v>{indice}</v></c>'
    return f"{xml[: match.start()]}{nova}{xml[match.end() :]}"


def _celula_vazia(xml: str, ref: str) -> str:
    """Remove o valor da célula, preservando r= e s= (mesmo formato de A166)."""
    match = _cell_match(xml, ref)
    nova = f"<c{_atributos_sem_tipo(match.group('attrs'))}/>"
    return f"{xml[: match.start()]}{nova}{xml[match.end() :]}"


def _celula_numero(xml: str, ref: str, valor: int) -> str:
    match = _cell_match(xml, ref)
    nova = f"<c{_atributos_sem_tipo(match.group('attrs'))}><v>{valor}</v></c>"
    return f"{xml[: match.start()]}{nova}{xml[match.end() :]}"


def _atributos_linha(xml: str, row: int) -> dict[str, str]:
    match = re.search(rf'<row\b[^>]*\br="{row}"[^>]*>', xml)
    if not match:
        raise ValueError(f"Linha ausente no template: {row}")
    return dict(re.findall(r'(\w+)="([^"]*)"', match.group(0)))


def _dre_sheet_xml(xml: str, strings: list[str]) -> str:
    def rotulo(row: int) -> str:
        return _texto_celula(xml, f"A{row}", strings)

    if rotulo(_DRE_LINHA_DESPESAS_FINANCEIRAS) != DESPESAS_FINANCEIRAS_ROTULO:
        raise ValueError(
            f"DRE!A{_DRE_LINHA_DESPESAS_FINANCEIRAS} não é {DESPESAS_FINANCEIRAS_ROTULO}"
        )
    if rotulo(_DRE_LINHA_NAO_OPERACIONAL) != NAO_OPERACIONAL_ROTULO:
        raise ValueError(
            f"DRE!A{_DRE_LINHA_NAO_OPERACIONAL} não é {NAO_OPERACIONAL_ROTULO}"
        )

    origem, destino = rotulo(_DRE_LINHA_ORIGEM), rotulo(_DRE_LINHA_DESTINO)
    if origem == "" and destino == TARIFA_ROTULO:
        return xml  # já aplicado
    if origem != TARIFA_ROTULO or destino != "":
        raise ValueError(
            f"Estado inesperado: A{_DRE_LINHA_ORIGEM}={origem!r}, A{_DRE_LINHA_DESTINO}={destino!r}"
        )

    # A linha de destino herda a mesma visibilidade/outline dos demais filhos
    # recolhidos de "(-) Despesas Financeiras"; a origem segue como as linhas
    # vazias reservadas do bloco (ex.: 29, 151, 166). Nada a alterar em <row>.
    for linha in (
        _DRE_LINHA_ORIGEM,
        _DRE_LINHA_DESTINO,
        _DRE_LINHA_DESPESAS_FINANCEIRAS + 1,
    ):
        atributos = _atributos_linha(xml, linha)
        if atributos.get("hidden") != "1" or atributos.get("outlineLevel") != "1":
            raise ValueError(
                f"DRE linha {linha} fora do nível recolhido esperado: {atributos}"
            )

    xml = _celula_vazia(xml, f"A{_DRE_LINHA_ORIGEM}")
    return _celula_texto_sst(
        xml, f"A{_DRE_LINHA_DESTINO}", _indice_sst(strings, TARIFA_ROTULO)
    )


def _plano_sheet_xml(xml: str, strings: list[str]) -> str:
    linhas = [
        int(row)
        for row in re.findall(r'<row\b[^>]*\br="(\d+)"', xml)
        if _texto_celula_opcional(xml, f"A{row}", strings) == TARIFA_ROTULO
    ]
    if len(linhas) != 1:
        raise ValueError(
            f"Esperada uma linha de {TARIFA_ROTULO} no PLANO_CONTAS: {linhas}"
        )
    linha = linhas[0]
    if _texto_celula(xml, f"B{linha}", strings) != TARIFA_ROTULO:
        raise ValueError(f"PLANO_CONTAS!B{linha} não é {TARIFA_ROTULO}")

    xml = _celula_texto_sst(
        xml, f"C{linha}", _indice_sst(strings, DESPESAS_FINANCEIRAS_ROTULO)
    )
    xml = _celula_texto_sst(xml, f"D{linha}", _indice_sst(strings, FINANCEIRO_ROTULO))
    return _celula_numero(xml, f"E{linha}", FINANCEIRO_COD)


def _texto_celula_opcional(xml: str, ref: str, strings: list[str]) -> str:
    if not re.search(_CELL_RE_TEMPLATE.format(ref=ref), xml, re.DOTALL):
        return ""
    return _texto_celula(xml, ref, strings)


def atualizar(template_path: Path) -> bool:
    """Aplica o patch. Retorna False quando o template já estava atualizado."""
    with ZipFile(template_path, "r") as source:
        infos = source.infolist()
        parts = {info.filename: source.read(info.filename) for info in infos}

    strings = _shared_strings(parts["xl/sharedStrings.xml"].decode("utf-8"))
    alterados: dict[str, bytes] = {}
    for sheet_name, patch in (
        ("DRE", _dre_sheet_xml),
        ("PLANO_CONTAS", _plano_sheet_xml),
    ):
        part = _sheet_part(parts, sheet_name)
        original = parts[part].decode("utf-8")
        atualizado = patch(original, strings)
        if atualizado != original:
            alterados[part] = atualizado.encode("utf-8")

    if not alterados:
        return False

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx",
        delete=False,
        dir=template_path.parent,
    ) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        # Mantém ordem, compressão e metadados de cada entrada do pacote.
        with ZipFile(temp_path, "w") as destination:
            for info in infos:
                destination.writestr(
                    info, alterados.get(info.filename, parts[info.filename])
                )
        # NamedTemporaryFile nasce 0600; preserva o modo original do template.
        shutil.copymode(template_path, temp_path)
        shutil.move(temp_path, template_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()
    if atualizar(args.template):
        print(f"[ok] template atualizado: {args.template}")
    else:
        print(f"[ok] template já estava atualizado: {args.template}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
