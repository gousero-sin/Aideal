#!/usr/bin/env python3
"""Remove as linhas sem rótulo da aba DRE do template oficial.

Critério: toda linha da aba DRE a partir da linha 6 (abaixo do cabeçalho) cuja
coluna A está vazia. São linhas de detalhe ocultas que sobraram de rubricas
antigas: só carregam o VLOOKUP padrão e aparecem como buracos quando o grupo é
expandido. As linhas 1 a 5 (cabeçalho, logo e títulos) nunca são tocadas.

O patch é feito nos fragmentos XML do zip, como em update_dre_template_linhas.py,
porque bibliotecas de planilha descartam slicers e extensões OOXML ao regravar o
arquivo. As fórmulas compartilhadas da aba são expandidas e as linhas saem de
baixo para cima; a cada remoção são renumerados:

- as fórmulas da própria aba (ex.: =SUM(B31:B32), percentuais sobre B$16);
- dimension, seleção, painel congelado e ignoredErrors;
- a tabela DRE e seu autoFilter;
- o nome definido _FilterDatabase da aba;
- a cadeia de cálculo (calcChain);
- fórmulas de outras abas que apontam para linhas da DRE (quadro PARETO da
  APOIO), que depois são conferidas pelo rótulo.

Fórmulas que apontem diretamente para uma linha removida abortam o patch. O
script é idempotente e aceita --dry-run para listar o que sairia.

Contas futuras: a DRE deixa de ter linhas reservas em branco. Uma rubrica nova
no PLANO_CONTAS exige inserir uma linha no bloco correspondente, como faz
update_dre_template_iss.py (inserir_linha copia a última rubrica do bloco e
renumera tudo que depende das linhas da aba).
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from html import escape, unescape
from pathlib import Path
from zipfile import ZipFile

from openpyxl.formula.tokenizer import Token, Tokenizer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from update_dre_template_iss import APOIO_SHEET, realinhar_pareto_apoio  # noqa: E402
from update_dre_template_linhas import (  # noqa: E402
    _F_RE,
    _ROW_RE,
    DRE_SHEET,
    LinhaReferenciadaError,
    _ajustar_contagem_sst,
    _ajustar_operando,
    _ajustar_sqref,
    _rotulos_coluna_a,
    _sheet_id,
    _tabela_da_aba,
    ajustar_calc_chain,
    ajustar_tabela,
    expandir_formulas_compartilhadas,
    remover_linha,
)
from update_dre_template_tarifa import _shared_strings, _sheet_part  # noqa: E402

__all__ = ["LinhaReferenciadaError", "aplicar", "linhas_sem_rotulo", "processar"]

PRIMEIRA_LINHA_DADOS = 6
_REF_DRE_COM_LINHA_RE = re.compile(r"'?DRE'?!\$?[A-Z]{1,3}\$?\d")
_COLLAPSED_RE = re.compile(r'\s+collapsed="1"')
_OUTLINE_RE = re.compile(r'\boutlineLevel="(\d+)"')
_ROW_TAG_RE = re.compile(r"<row\b[^>]*>")


def linhas_sem_rotulo(rotulos: dict[int, str]) -> list[int]:
    """Linhas de dados (>= 6) sem texto na coluna A, em ordem crescente."""
    return sorted(
        linha
        for linha, rotulo in rotulos.items()
        if linha >= PRIMEIRA_LINHA_DADOS and not rotulo.strip()
    )


# --------------------------------------------------------------------------- #
# Referências de outras partes do pacote para linhas da DRE                   #
# --------------------------------------------------------------------------- #


def ajustar_formula_externa(formula: str, linha_removida: int) -> str:
    """Renumera só os operandos com prefixo DRE! de uma fórmula de outra aba."""
    partes = []
    for token in Tokenizer(f"={formula}").items:
        valor = token.value
        if token.type == Token.OPERAND and token.subtype == Token.RANGE and "!" in valor:
            folha = valor.rpartition("!")[0].strip("'")
            if folha == DRE_SHEET:
                valor = _ajustar_operando(valor, linha_removida)
        partes.append(valor)
    return "".join(partes)


def ajustar_aba_externa(xml: str, linha_removida: int) -> str:
    def trocar(match: re.Match[str]) -> str:
        body = match.group("body")
        if body is None or not _REF_DRE_COM_LINHA_RE.search(unescape(body)):
            return match.group(0)
        if 't="shared"' in match.group("attrs"):
            raise ValueError("Fórmula compartilhada fora da DRE aponta para linha da DRE")
        novo = escape(ajustar_formula_externa(unescape(body), linha_removida), quote=False)
        return f"<f{match.group('attrs')}>{novo}</f>"

    return _F_RE.sub(trocar, xml)


def ajustar_nomes_definidos(xml: str, linha_removida: int) -> str:
    """Renumera nomes definidos que apontam para um intervalo da aba DRE."""

    def trocar(match: re.Match[str]) -> str:
        ajustado = _ajustar_sqref(match.group(3), linha_removida)
        if not ajustado:
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}{ajustado}{match.group(4)}"

    return re.sub(
        rf"(<definedName\b[^>]*>)('?{DRE_SHEET}'?!)([^<!,]+)(</definedName>)",
        trocar,
        xml,
    )


def _partes_planilha(parts: dict[str, bytes]) -> list[str]:
    return sorted(
        nome for nome in parts if nome.startswith("xl/worksheets/sheet") and nome.endswith(".xml")
    )


def _verificar_dependencias_nao_tratadas(parts: dict[str, bytes]) -> None:
    """Gráficos, pivôs e conexões apontando para linhas da DRE não são renumerados."""
    for nome, conteudo in parts.items():
        if not nome.endswith(".xml") or nome.startswith("xl/worksheets/"):
            continue
        if nome == "xl/workbook.xml":
            continue
        texto = conteudo.decode("utf-8", errors="ignore")
        if _REF_DRE_COM_LINHA_RE.search(unescape(texto)):
            raise ValueError(f"{nome} aponta para linhas da DRE; ajuste manual necessário")


# --------------------------------------------------------------------------- #
# Agrupamento (outline)                                                       #
# --------------------------------------------------------------------------- #


def normalizar_collapsed(xml: str) -> str:
    """Tira collapsed="1" de linhas cujo grupo de detalhe ficou vazio."""
    anterior_nivel = 0
    saida: list[str] = []
    pos = 0
    for row in _ROW_RE.finditer(xml):
        tag = _ROW_TAG_RE.match(row.group(0)).group(0)
        nivel_match = _OUTLINE_RE.search(tag)
        nivel = int(nivel_match.group(1)) if nivel_match else 0
        texto = row.group(0)
        if 'collapsed="1"' in tag and anterior_nivel <= nivel:
            texto = _COLLAPSED_RE.sub("", tag, count=1) + texto[len(tag) :]
        saida.append(xml[pos : row.start()])
        saida.append(texto)
        pos = row.end()
        anterior_nivel = nivel
    saida.append(xml[pos:])
    return "".join(saida)


# --------------------------------------------------------------------------- #
# Orquestração                                                                #
# --------------------------------------------------------------------------- #


def _rotulos(parts: dict[str, bytes], sheet_part: str) -> dict[int, str]:
    strings = _shared_strings(parts["xl/sharedStrings.xml"].decode("utf-8"))
    return _rotulos_coluna_a(parts[sheet_part].decode("utf-8"), strings)


def aplicar(parts: dict[str, bytes]) -> list[int]:
    """Remove as linhas sem rótulo nas partes do zip. Retorna as linhas removidas."""
    sheet_part = _sheet_part(parts, DRE_SHEET)
    remover = linhas_sem_rotulo(_rotulos(parts, sheet_part))
    if not remover:
        return []
    _verificar_dependencias_nao_tratadas(parts)

    xml = expandir_formulas_compartilhadas(parts[sheet_part].decode("utf-8"))
    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    sheet_id = _sheet_id(workbook_xml, DRE_SHEET)
    tabela = _tabela_da_aba(parts, sheet_part)
    tabela_xml = parts[tabela].decode("utf-8") if tabela else ""
    calc_chain = parts.get("xl/calcChain.xml", b"").decode("utf-8")
    externas = {
        nome: parts[nome].decode("utf-8") for nome in _partes_planilha(parts) if nome != sheet_part
    }

    textos_removidos = 0
    for linha in sorted(remover, reverse=True):
        xml, removidos = remover_linha(xml, linha)
        textos_removidos += removidos
        if tabela:
            tabela_xml = ajustar_tabela(tabela_xml, linha)
        if calc_chain:
            calc_chain = ajustar_calc_chain(calc_chain, sheet_id, linha)
        workbook_xml = ajustar_nomes_definidos(workbook_xml, linha)
        externas = {nome: ajustar_aba_externa(texto, linha) for nome, texto in externas.items()}

    parts[sheet_part] = normalizar_collapsed(xml).encode("utf-8")
    parts["xl/workbook.xml"] = workbook_xml.encode("utf-8")
    if textos_removidos:
        sst = parts["xl/sharedStrings.xml"].decode("utf-8")
        parts["xl/sharedStrings.xml"] = _ajustar_contagem_sst(
            sst, referencias=-textos_removidos
        ).encode("utf-8")
    if tabela:
        parts[tabela] = tabela_xml.encode("utf-8")
    if calc_chain:
        parts["xl/calcChain.xml"] = calc_chain.encode("utf-8")

    rotulos = _rotulos(parts, sheet_part)
    apoio_part = _sheet_part(parts, APOIO_SHEET) if APOIO_SHEET in workbook_xml else None
    for nome, texto in externas.items():
        if nome == apoio_part:
            texto = realinhar_pareto_apoio(texto, rotulos)
        parts[nome] = texto.encode("utf-8")
    return remover


def processar(template: Path, *, dry_run: bool = False) -> list[int]:
    with ZipFile(template) as zin:
        infos = zin.infolist()
        parts = {info.filename: zin.read(info.filename) for info in infos}

    if dry_run:
        return linhas_sem_rotulo(_rotulos(parts, _sheet_part(parts, DRE_SHEET)))

    removidas = aplicar(parts)
    if not removidas:
        return []

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False, dir=template.parent) as tmp:
        tmp_path = Path(tmp.name)
    with ZipFile(tmp_path, "w") as zout:
        for info in infos:
            zout.writestr(info, parts[info.filename])
    tmp_path.chmod(template.stat().st_mode & 0o777)
    tmp_path.replace(template)
    return removidas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template", nargs="?", default=str(DEFAULT_TEMPLATE))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="lista as linhas sem rótulo sem alterar o arquivo",
    )
    args = parser.parse_args()
    linhas = processar(Path(args.template), dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] linhas sem rótulo: {linhas or 'nenhuma'}")
    elif linhas:
        print(f"[ok] template atualizado; linhas removidas: {linhas}")
    else:
        print("[ok] template já estava sem linhas em branco")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
