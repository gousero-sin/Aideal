#!/usr/bin/env python3
"""Enxuga o topo da aba DRE do template e cria a linha DIFAL ICMS em Fornecedores.

Alterações aprovadas para o DRE gerado:

- grava "DIFAL ICMS" na linha livre logo abaixo de "OUTROS MATERIAIS DE
  APLICAÇÃO", no bloco Fornecedores; o ICMS (17.9) passa a compor os Custos
  Variáveis por essa linha;
- remove "Faturamento"; a Receita Bruta já é a soma das notas 1.1.x;
- remove a linha "ISS" do bloco de impostos (a guia 17.8 ISS tem hoje linha
  própria em Despesas Administrativas: ver update_dre_template_iss.py);
- remove as linhas em branco do bloco de impostos (entre a Receita Bruta e a
  Receita Líquida), como a que sobrou da Tarifa de Antecipação.

As linhas são localizadas pelo rótulo e as de baixo sobem sem deixar buraco. O patch é feito nos fragmentos XML do
zip, como em update_dre_template_tarifa.py, porque bibliotecas de planilha
descartam slicers e extensões OOXML ao regravar o arquivo. Antes de remover,
as fórmulas compartilhadas da aba são expandidas (as mestres estão na linha 7);
depois, referências a linhas da própria aba, a tabela, a seleção, os
ignoredErrors e o calcChain são renumerados. O script é idempotente.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from html import escape, unescape
from pathlib import Path
from zipfile import ZipFile

from openpyxl.formula.tokenizer import Token, Tokenizer
from openpyxl.formula.translate import Translator
from openpyxl.utils.cell import coordinate_from_string

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from update_dre_template_tarifa import (  # noqa: E402
    _celula_texto_sst,
    _sheet_part,
    _shared_strings,
    _texto_celula,
)

DRE_SHEET = "DRE"
FATURAMENTO_ROTULO = "Faturamento"
FORNECEDORES_ROTULO = "Fornecedores"
OUTROS_MATERIAIS_ROTULO = "OUTROS MATERIAIS DE APLICAÇÃO"
DIFAL_ROTULO = "DIFAL ICMS"
RECEITA_BRUTA_ROTULO = "(=)Receita Bruta"
RECEITA_LIQUIDA_ROTULO = "(=)Receita Líquida"
ISS_ROTULO = "ISS"
# Rótulos removidos do bloco entre a Receita Bruta e a Receita Líquida.
_ROTULOS_REMOVIDOS_IMPOSTOS = frozenset((FATURAMENTO_ROTULO, ISS_ROTULO, ""))

_ROW_RE = re.compile(r'<row\b[^>]*\br="(?P<r>\d+)"[^>]*?(?:/>|>.*?</row>)', re.DOTALL)
_CELL_REF_RE = re.compile(r'(<c\b[^>]*?\br=")(?P<col>[A-Z]{1,3})(?P<row>\d+)(")')
_F_RE = re.compile(r"<f\b(?P<attrs>[^>]*?)(?:/>|>(?P<body>[^<]*)</f>)")
_REF_RE = re.compile(r"(?P<col>\$?[A-Z]{1,3})(?P<abs>\$?)(?P<row>\d+)")
_CELL_TAG_RE = re.compile(
    r'<c\b[^>]*?\br="(?P<ref>[A-Z]{1,3}\d+)"[^>]*?(?:/>|>.*?</c>)', re.DOTALL
)


class LinhaReferenciadaError(ValueError):
    """Fórmula aponta diretamente para a linha removida."""


# --------------------------------------------------------------------------- #
# Fórmulas                                                                    #
# --------------------------------------------------------------------------- #


def _ajustar_ref(ref: str, linha_removida: int, *, extremo: str | None) -> str:
    """Renumera uma referência de célula; extremo indica início/fim de intervalo."""
    match = _REF_RE.fullmatch(ref)
    if not match:
        return ref
    linha = int(match.group("row"))
    if linha > linha_removida:
        linha -= 1
    elif linha == linha_removida:
        if extremo == "inicio":
            pass  # a linha seguinte sobe e passa a ocupar a posição
        elif extremo == "fim":
            linha -= 1
        else:
            raise LinhaReferenciadaError(ref)
    return f"{match.group('col')}{match.group('abs')}{linha}"


def _ajustar_operando(valor: str, linha_removida: int) -> str:
    folha, sep, endereco = valor.rpartition("!")
    if sep and folha.strip("'") != DRE_SHEET:
        return valor
    partes = endereco.split(":")
    if len(partes) == 1:
        ajustado = _ajustar_ref(partes[0], linha_removida, extremo=None)
    elif len(partes) == 2 and all(_REF_RE.fullmatch(p) for p in partes):
        inicio = _ajustar_ref(partes[0], linha_removida, extremo="inicio")
        fim = _ajustar_ref(partes[1], linha_removida, extremo="fim")
        ajustado = f"{inicio}:{fim}"
    else:
        ajustado = endereco  # colunas inteiras (A:A) ou nomes definidos
    return f"{folha}{sep}{ajustado}"


def ajustar_formula(formula: str, linha_removida: int) -> str:
    """Renumera referências da própria aba numa fórmula (sem o '=' inicial)."""
    tokens = Tokenizer(f"={formula}").items
    partes = []
    for token in tokens:
        if token.type == Token.OPERAND and token.subtype == Token.RANGE:
            partes.append(_ajustar_operando(token.value, linha_removida))
        else:
            partes.append(token.value)
    return "".join(partes)


def _ajustar_f_xml(xml: str, linha_removida: int) -> str:
    def trocar(match: re.Match[str]) -> str:
        body = match.group("body")
        if body is None:
            return match.group(0)
        if 't="shared"' in match.group("attrs"):
            raise ValueError(
                "Fórmulas compartilhadas devem ser expandidas antes do ajuste"
            )
        novo = escape(ajustar_formula(unescape(body), linha_removida), quote=False)
        return f"<f{match.group('attrs')}>{novo}</f>"

    return _F_RE.sub(trocar, xml)


def expandir_formulas_compartilhadas(xml: str) -> str:
    """Troca cada fórmula compartilhada pela fórmula explícita da célula."""
    mestres: dict[str, tuple[str, str]] = {}
    for cell in _CELL_TAG_RE.finditer(xml):
        f = _F_RE.search(cell.group(0))
        if f and 't="shared"' in f.group("attrs") and f.group("body"):
            si = re.search(r'\bsi="(\d+)"', f.group("attrs")).group(1)
            mestres[si] = (cell.group("ref"), unescape(f.group("body")))

    def trocar_celula(cell: re.Match[str]) -> str:
        texto = cell.group(0)
        f = _F_RE.search(texto)
        if not f or 't="shared"' not in f.group("attrs"):
            return texto
        si = re.search(r'\bsi="(\d+)"', f.group("attrs")).group(1)
        origem, formula = mestres[si]
        traduzida = Translator(f"={formula}", origin=origem).translate_formula(
            cell.group("ref")
        )
        nova_f = f"<f>{escape(traduzida[1:], quote=False)}</f>"
        return f"{texto[: f.start()]}{nova_f}{texto[f.end() :]}"

    return _CELL_TAG_RE.sub(trocar_celula, xml)


# --------------------------------------------------------------------------- #
# Linhas e metadados da aba                                                   #
# --------------------------------------------------------------------------- #


def _renumerar_linha(row_xml: str, nova: int) -> str:
    row_xml = re.sub(
        r'(<row\b[^>]*?\br=")\d+(")', rf"\g<1>{nova}\g<2>", row_xml, count=1
    )
    return _CELL_REF_RE.sub(
        lambda m: f"{m.group(1)}{m.group('col')}{nova}{m.group(4)}", row_xml
    )


def _ajustar_sqref(sqref: str, linha_removida: int) -> str:
    """Renumera uma lista de intervalos; descarta os que só cobriam a linha removida."""
    saida = []
    for item in sqref.split():
        partes = item.split(":")
        try:
            if len(partes) == 1:
                saida.append(_ajustar_ref(partes[0], linha_removida, extremo=None))
            else:
                inicio = _ajustar_ref(partes[0], linha_removida, extremo="inicio")
                fim = _ajustar_ref(partes[1], linha_removida, extremo="fim")
                if int(_REF_RE.fullmatch(inicio).group("row")) <= int(
                    _REF_RE.fullmatch(fim).group("row")
                ):
                    saida.append(f"{inicio}:{fim}")
        except LinhaReferenciadaError:
            continue
    return " ".join(saida)


def remover_linha(xml: str, linha_removida: int) -> tuple[str, int]:
    """Remove a linha da aba e sobe as seguintes. Retorna (xml, células de texto removidas)."""
    textos_removidos = 0

    def trocar_linha(match: re.Match[str]) -> str:
        nonlocal textos_removidos
        linha = int(match.group("r"))
        if linha == linha_removida:
            textos_removidos += len(re.findall(r'<c\b[^>]*\bt="s"', match.group(0)))
            return ""
        if linha > linha_removida:
            return _renumerar_linha(match.group(0), linha - 1)
        return match.group(0)

    xml = _ROW_RE.sub(trocar_linha, xml)
    xml = _ajustar_f_xml(xml, linha_removida)
    xml = re.sub(
        r'(<dimension\b[^>]*\bref=")([^"]+)(")',
        lambda m: (
            f"{m.group(1)}{_ajustar_sqref(m.group(2), linha_removida)}{m.group(3)}"
        ),
        xml,
    )
    xml = re.sub(
        r'(\b(?:sqref|activeCell|topLeftCell)=")([^"]+)(")',
        lambda m: (
            f"{m.group(1)}{_ajustar_sqref(m.group(2), linha_removida) or 'A1'}{m.group(3)}"
        ),
        xml,
    )
    return xml, textos_removidos


def _remover_collapsed(xml: str, linha: int) -> str:
    return re.sub(
        rf'(<row\b[^>]*\br="{linha}"[^>]*?)\s+collapsed="1"',
        r"\g<1>",
        xml,
        count=1,
    )


def ajustar_tabela(xml: str, linha_removida: int) -> str:
    xml = re.sub(
        r'(<(?:table|autoFilter)\b[^>]*\bref=")([^"]+)(")',
        lambda m: (
            f"{m.group(1)}{_ajustar_sqref(m.group(2), linha_removida)}{m.group(3)}"
        ),
        xml,
    )
    return re.sub(
        r"(<calculatedColumnFormula>)([^<]*)(</calculatedColumnFormula>)",
        lambda m: (
            f"{m.group(1)}"
            f"{escape(ajustar_formula(unescape(m.group(2)), linha_removida), quote=False)}"
            f"{m.group(3)}"
        ),
        xml,
    )


def ajustar_calc_chain(xml: str, sheet_id: str, linha_removida: int) -> str:
    def trocar(match: re.Match[str]) -> str:
        col, linha = coordinate_from_string(match.group("ref"))
        if linha == linha_removida:
            return ""
        if linha > linha_removida:
            return match.group(0).replace(
                f'r="{col}{linha}"', f'r="{col}{linha - 1}"', 1
            )
        return match.group(0)

    return re.sub(
        rf'<c\b(?=[^>]*\bi="{sheet_id}")[^>]*\br="(?P<ref>[A-Z]{{1,3}}\d+)"[^>]*/>',
        trocar,
        xml,
    )


# --------------------------------------------------------------------------- #
# sharedStrings                                                               #
# --------------------------------------------------------------------------- #


def _indice_ou_novo_sst(xml: str, strings: list[str], texto: str) -> tuple[str, int]:
    if texto in strings:
        return xml, strings.index(texto)
    xml = xml.replace(
        "</sst>", f"<si><t>{escape(texto, quote=False)}</t></si></sst>", 1
    )
    return _ajustar_contagem_sst(xml, referencias=1, unicos=1), len(strings)


def _ajustar_contagem_sst(xml: str, *, referencias: int, unicos: int = 0) -> str:
    def somar(attr: str, delta: int, texto: str) -> str:
        return re.sub(
            rf'(<sst\b[^>]*\b{attr}=")(\d+)(")',
            lambda m: f"{m.group(1)}{int(m.group(2)) + delta}{m.group(3)}",
            texto,
            count=1,
        )

    return somar("uniqueCount", unicos, somar("count", referencias, xml))


# --------------------------------------------------------------------------- #
# Orquestração                                                                #
# --------------------------------------------------------------------------- #


def _sheet_id(workbook_xml: str, nome: str) -> str:
    match = re.search(
        rf'<sheet\b(?=[^>]*\bname="{re.escape(nome)}")[^>]*\bsheetId="(\d+)"',
        workbook_xml,
    )
    if not match:
        raise ValueError(f"Aba ausente no template: {nome}")
    return match.group(1)


def _tabela_da_aba(parts: dict[str, bytes], sheet_part: str) -> str | None:
    rels_part = sheet_part.replace("worksheets/", "worksheets/_rels/") + ".rels"
    rels = parts.get(rels_part, b"").decode("utf-8")
    match = re.search(r'Type="[^"]*/table"[^>]*Target="\.\./(?P<t>[^"]+)"', rels)
    return f"xl/{match.group('t')}" if match else None


def _rotulos_coluna_a(xml: str, strings: list[str]) -> dict[int, str]:
    rotulos: dict[int, str] = {}
    for row in _ROW_RE.finditer(xml):
        linha = int(row.group("r"))
        try:
            rotulos[linha] = _texto_celula(row.group(0), f"A{linha}", strings)
        except ValueError:
            rotulos[linha] = ""
    return rotulos


def _linha_unica(rotulos: dict[int, str], texto: str) -> int:
    linhas = [linha for linha, rotulo in rotulos.items() if rotulo == texto]
    if len(linhas) != 1:
        raise ValueError(f"Rótulo {texto!r} deve aparecer uma vez na aba DRE: {linhas}")
    return linhas[0]


def linhas_a_remover(rotulos: dict[int, str]) -> list[int]:
    """Linhas do bloco de impostos que saem: Faturamento, ISS e as em branco."""
    inicio = _linha_unica(rotulos, RECEITA_BRUTA_ROTULO)
    fim = _linha_unica(rotulos, RECEITA_LIQUIDA_ROTULO)
    return [
        linha
        for linha in range(inicio + 1, fim)
        if rotulos.get(linha, "") in _ROTULOS_REMOVIDOS_IMPOSTOS
    ]


def aplicar(parts: dict[str, bytes]) -> bool:
    """Aplica as alterações nas partes do zip. Retorna False se já aplicadas."""
    sheet_part = _sheet_part(parts, DRE_SHEET)
    xml = parts[sheet_part].decode("utf-8")
    sst = parts["xl/sharedStrings.xml"].decode("utf-8")
    strings = _shared_strings(sst)
    rotulos = _rotulos_coluna_a(xml, strings)

    remover = linhas_a_remover(rotulos)
    criar_difal = DIFAL_ROTULO not in rotulos.values()
    if not remover and not criar_difal:
        return False

    if criar_difal:
        linha_difal = _linha_unica(rotulos, OUTROS_MATERIAIS_ROTULO) + 1
        if rotulos.get(linha_difal, "") != "":
            raise ValueError(
                f"DRE!A{linha_difal} deveria estar livre para {DIFAL_ROTULO}"
            )
        if (
            rotulos.get(_linha_unica(rotulos, FORNECEDORES_ROTULO), "")
            != FORNECEDORES_ROTULO
        ):
            raise ValueError("Bloco Fornecedores ausente na aba DRE")
        sst, indice_difal = _indice_ou_novo_sst(sst, strings, DIFAL_ROTULO)
        if indice_difal < len(strings):
            sst = _ajustar_contagem_sst(sst, referencias=1)
        xml = _celula_texto_sst(xml, f"A{linha_difal}", indice_difal)

    xml = expandir_formulas_compartilhadas(xml)
    for linha in remover:
        if rotulos.get(linha) == FATURAMENTO_ROTULO:
            # A linha seguinte (Deduções) só marcava o grupo recolhido do Faturamento.
            xml = _remover_collapsed(xml, linha + 1)

    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    sheet_id = _sheet_id(workbook_xml, DRE_SHEET)
    tabela = _tabela_da_aba(parts, sheet_part)
    calc_chain = parts.get("xl/calcChain.xml", b"").decode("utf-8")
    tabela_xml = parts[tabela].decode("utf-8") if tabela else ""

    textos_removidos = 0
    for linha in sorted(remover, reverse=True):
        xml, removidos = remover_linha(xml, linha)
        textos_removidos += removidos
        if tabela:
            tabela_xml = ajustar_tabela(tabela_xml, linha)
        if calc_chain:
            calc_chain = ajustar_calc_chain(calc_chain, sheet_id, linha)

    parts[sheet_part] = xml.encode("utf-8")
    parts["xl/sharedStrings.xml"] = _ajustar_contagem_sst(
        sst, referencias=-textos_removidos
    ).encode("utf-8")
    if tabela:
        parts[tabela] = tabela_xml.encode("utf-8")
    if calc_chain:
        parts["xl/calcChain.xml"] = calc_chain.encode("utf-8")
    return True


def processar(template: Path) -> bool:
    with ZipFile(template) as zin:
        infos = zin.infolist()
        parts = {info.filename: zin.read(info.filename) for info in infos}

    if not aplicar(parts):
        return False

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    with ZipFile(tmp_path, "w") as zout:
        for info in infos:
            zout.writestr(info, parts[info.filename])
    shutil.move(tmp_path, template)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template", nargs="?", default=str(DEFAULT_TEMPLATE))
    args = parser.parse_args()
    alterado = processar(Path(args.template))
    print(
        "[ok] template atualizado" if alterado else "[ok] template já estava atualizado"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
