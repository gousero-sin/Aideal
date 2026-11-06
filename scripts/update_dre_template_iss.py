#!/usr/bin/env python3
"""Cria a linha "ISS" no bloco Despesas Administrativas da aba DRE do template.

A guia 17.8 ISS deixou de compor "ISS Retido" (deduções sobre vendas) e passou a
ser despesa administrativa, em linha própria, depois da última rubrica do bloco.

A linha nova copia a última rubrica do bloco (altura, grupo recolhido, estilos e
fórmulas) e as de baixo descem uma posição. O patch é feito nos fragmentos XML do
zip, como em update_dre_template_linhas.py, porque bibliotecas de planilha
descartam slicers e extensões OOXML ao regravar o arquivo. Referências da própria
aba, tabela, seleção, ignoredErrors, nome definido e calcChain são renumerados, e
o quadro PARETO da aba APOIO, que aponta para linhas fixas da DRE, é realinhado
pelo rótulo. O script é idempotente.
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

from update_dre_template_linhas import (  # noqa: E402
    _CELL_TAG_RE,
    _F_RE,
    _REF_RE,
    _ROW_RE,
    DRE_SHEET,
    _ajustar_contagem_sst,
    _indice_ou_novo_sst,
    _linha_unica,
    _renumerar_linha,
    _rotulos_coluna_a,
    _sheet_id,
    _tabela_da_aba,
)
from update_dre_template_tarifa import _shared_strings, _sheet_part  # noqa: E402

DESPESAS_ADMINISTRATIVAS_ROTULO = "Despesas Administrativas"
PROXIMO_BLOCO_ROTULO = "Despesas com Veículos e Equipamentos"
ISS_ROTULO = "ISS"
APOIO_SHEET = "APOIO"
# Quadro PARETO da APOIO (Y28:Z37): aponta para linhas fixas dos subtotais de
# Gastos Fixos e ficou defasado com as alterações de linhas da DRE.
_PARETO_APOIO = {
    28: "Despesas com Pessoal",
    29: "Despesas com Locações",
    30: "Despesas com Infraestrutura",
    31: "Despesas com Máquinas e Equipamentos",
    32: "Despesas com Veículos e Equipamentos",
    33: "Despesas Administrativas",
    34: "Despesas Financeiras",
    35: "Serviços de Terceiros",
    36: "Despesas com Viagens e Hospedagens",
    37: "(-)Gastos Fixos",
}
_ROTULO_ESTILO_RE = re.compile(r'<c\b[^>]*\br="A\d+"[^>]*\bs="(?P<s>\d+)"')
_VALOR_RE = re.compile(r"<v>[^<]*</v>")


def _deslocar_ref(ref: str, linha_nova: int) -> str:
    """Desce uma referência de célula que está na linha nova ou abaixo dela."""
    match = _REF_RE.fullmatch(ref)
    if not match:
        return ref
    linha = int(match.group("row"))
    if linha >= linha_nova:
        linha += 1
    return f"{match.group('col')}{match.group('abs')}{linha}"


def _deslocar_operando(valor: str, linha_nova: int) -> str:
    folha, sep, endereco = valor.rpartition("!")
    if sep and folha.strip("'") != DRE_SHEET:
        return valor
    partes = endereco.split(":")
    if not all(_REF_RE.fullmatch(parte) for parte in partes):
        return valor  # colunas inteiras (A:A) ou nomes definidos
    return f"{folha}{sep}{':'.join(_deslocar_ref(p, linha_nova) for p in partes)}"


def deslocar_formula(formula: str, linha_nova: int) -> str:
    """Renumera referências da própria aba numa fórmula (sem o '=' inicial)."""
    partes = []
    for token in Tokenizer(f"={formula}").items:
        if token.type == Token.OPERAND and token.subtype == Token.RANGE:
            partes.append(_deslocar_operando(token.value, linha_nova))
        else:
            partes.append(token.value)
    return "".join(partes)


def _deslocar_sqref(sqref: str, linha_nova: int) -> str:
    return " ".join(
        ":".join(_deslocar_ref(parte, linha_nova) for parte in item.split(":"))
        for item in sqref.split()
    )


def _clonar_linha(
    modelo: str, linha_nova: int, *, indice_rotulo: int, estilo_rotulo: str
) -> str:
    """Copia a linha modelo, traduz as fórmulas e grava o novo rótulo em A."""

    def trocar_celula(cell: re.Match[str]) -> str:
        texto = cell.group(0)
        coluna = coordinate_from_string(cell.group("ref"))[0]
        if coluna == "A":
            return f'<c r="A{linha_nova}" s="{estilo_rotulo}" t="s"><v>{indice_rotulo}</v></c>'
        f = _F_RE.search(texto)
        if not f or not f.group("body"):
            return texto
        traduzida = Translator(f"={unescape(f.group('body'))}", origin=cell.group("ref"))
        nova_f = (
            f"<f>{escape(traduzida.translate_formula(f'{coluna}{linha_nova}')[1:], quote=False)}</f>"
        )
        return _VALOR_RE.sub("<v>0</v>", f"{texto[: f.start()]}{nova_f}{texto[f.end() :]}")

    copia = _CELL_TAG_RE.sub(trocar_celula, modelo)
    return _renumerar_linha(copia, linha_nova)


def inserir_linha(
    xml: str, linha_modelo: int, *, indice_rotulo: int, estilo_rotulo: str
) -> tuple[str, str]:
    """Insere uma cópia da linha modelo logo abaixo dela.

    Retorna (xml, linha nova). Fórmulas e metadados da aba são renumerados.
    """
    linha_nova = linha_modelo + 1
    modelos = [m.group(0) for m in _ROW_RE.finditer(xml) if int(m.group("r")) == linha_modelo]
    if len(modelos) != 1:
        raise ValueError(f"Linha modelo {linha_modelo} ausente na aba DRE")
    nova = _clonar_linha(
        modelos[0],
        linha_nova,
        indice_rotulo=indice_rotulo,
        estilo_rotulo=estilo_rotulo,
    )

    def descer_linha(match: re.Match[str]) -> str:
        linha = int(match.group("r"))
        if linha >= linha_nova:
            return _renumerar_linha(match.group(0), linha + 1)
        return match.group(0)

    def ajustar_f(match: re.Match[str]) -> str:
        body = match.group("body")
        if body is None:
            return match.group(0)
        if 't="shared"' in match.group("attrs"):
            raise ValueError("Fórmulas compartilhadas devem ser expandidas antes do ajuste")
        novo = escape(deslocar_formula(unescape(body), linha_nova), quote=False)
        return f"<f{match.group('attrs')}>{novo}</f>"

    xml = _F_RE.sub(ajustar_f, _ROW_RE.sub(descer_linha, xml))
    xml = re.sub(
        r'(<dimension\b[^>]*\bref=")([^"]+)(")',
        lambda m: f"{m.group(1)}{_deslocar_sqref(m.group(2), linha_nova)}{m.group(3)}",
        xml,
    )
    xml = re.sub(
        r'(\b(?:sqref|activeCell|topLeftCell)=")([^"]+)(")',
        lambda m: f"{m.group(1)}{_deslocar_sqref(m.group(2), linha_nova)}{m.group(3)}",
        xml,
    )
    # A cópia já vem com as referências certas: entra depois do ajuste das demais.
    fim_modelo = next(
        m.end() for m in _ROW_RE.finditer(xml) if int(m.group("r")) == linha_modelo
    )
    return f"{xml[:fim_modelo]}{nova}{xml[fim_modelo:]}", nova


def deslocar_tabela(xml: str, linha_nova: int) -> str:
    xml = re.sub(
        r'(<(?:table|autoFilter)\b[^>]*\bref=")([^"]+)(")',
        lambda m: f"{m.group(1)}{_deslocar_sqref(m.group(2), linha_nova)}{m.group(3)}",
        xml,
    )
    return re.sub(
        r"(<calculatedColumnFormula>)([^<]*)(</calculatedColumnFormula>)",
        lambda m: (
            f"{m.group(1)}"
            f"{escape(deslocar_formula(unescape(m.group(2)), linha_nova), quote=False)}"
            f"{m.group(3)}"
        ),
        xml,
    )


def deslocar_calc_chain(xml: str, sheet_id: str, linha_nova: int, linha_criada_xml: str) -> str:
    """Renumera a cadeia de cálculo da aba e acrescenta as células da linha nova."""

    def trocar(match: re.Match[str]) -> str:
        col, linha = coordinate_from_string(match.group("ref"))
        if linha < linha_nova:
            return match.group(0)
        return match.group(0).replace(f'r="{col}{linha}"', f'r="{col}{linha + 1}"', 1)

    xml = re.sub(
        rf'<c\b(?=[^>]*\bi="{sheet_id}")[^>]*\br="(?P<ref>[A-Z]{{1,3}}\d+)"[^>]*/>',
        trocar,
        xml,
    )
    novas = "".join(
        f'<c r="{cell.group("ref")}" i="{sheet_id}"/>'
        for cell in _CELL_TAG_RE.finditer(linha_criada_xml)
        if "<f>" in cell.group(0)
    )
    return xml.replace("</calcChain>", f"{novas}</calcChain>", 1)


def deslocar_nomes_definidos(xml: str, linha_nova: int) -> str:
    """Renumera nomes definidos que apontam para intervalos da aba DRE."""

    def trocar(match: re.Match[str]) -> str:
        return (
            f"{match.group(1)}{DRE_SHEET}!"
            f"{':'.join(_deslocar_ref(p, linha_nova) for p in match.group(2).split(':'))}"
            f"{match.group(3)}"
        )

    return re.sub(rf"(<definedName\b[^>]*>){DRE_SHEET}!([^<]+)(</definedName>)", trocar, xml)


def _linha_iss_no_bloco(rotulos: dict[int, str], inicio: int, fim: int) -> bool:
    return any(rotulos.get(linha) == ISS_ROTULO for linha in range(inicio + 1, fim))


def realinhar_pareto_apoio(xml: str, rotulos: dict[int, str]) -> str:
    """Aponta o quadro PARETO da APOIO para as linhas atuais dos subtotais da DRE."""

    def trocar_celula(cell: re.Match[str]) -> str:
        coluna, linha = coordinate_from_string(cell.group("ref"))
        rotulo = _PARETO_APOIO.get(linha)
        if coluna not in ("Y", "Z") or rotulo is None:
            return cell.group(0)
        linha_dre = _linha_unica(rotulos, rotulo)
        return re.sub(
            rf"(<f>{DRE_SHEET}!\$?[A-Z]{{1,3}}\$?)\d+",
            rf"\g<1>{linha_dre}",
            cell.group(0),
        )

    return _CELL_TAG_RE.sub(trocar_celula, xml)


def _inserir_linha_iss(parts: dict[str, bytes], sheet_part: str) -> None:
    """Cria a linha ISS no bloco e renumera tudo que depende das linhas da aba."""
    xml = parts[sheet_part].decode("utf-8")
    sst = parts["xl/sharedStrings.xml"].decode("utf-8")
    strings = _shared_strings(sst)
    rotulos = _rotulos_coluna_a(xml, strings)
    inicio = _linha_unica(rotulos, DESPESAS_ADMINISTRATIVAS_ROTULO)
    fim = _linha_unica(rotulos, PROXIMO_BLOCO_ROTULO)

    linha_modelo = fim - 1
    # O rótulo segue a formatação das demais rubricas do bloco.
    linhas_bloco = {
        int(m.group("r")): m.group(0)
        for m in _ROW_RE.finditer(xml)
        if inicio < int(m.group("r")) < fim
    }
    estilos = [
        estilo.group("s")
        for linha in sorted(linhas_bloco)
        if (estilo := _ROTULO_ESTILO_RE.search(linhas_bloco[linha]))
    ]
    if not estilos:
        raise ValueError("Bloco Despesas Administrativas sem rótulo formatado")

    total_antes = len(strings)
    sst, indice_iss = _indice_ou_novo_sst(sst, strings, ISS_ROTULO)
    if indice_iss < total_antes:
        sst = _ajustar_contagem_sst(sst, referencias=1)

    xml, linha_criada = inserir_linha(
        xml, linha_modelo, indice_rotulo=indice_iss, estilo_rotulo=estilos[-1]
    )

    linha_nova = linha_modelo + 1
    parts[sheet_part] = xml.encode("utf-8")
    parts["xl/sharedStrings.xml"] = sst.encode("utf-8")

    tabela = _tabela_da_aba(parts, sheet_part)
    if tabela:
        parts[tabela] = deslocar_tabela(parts[tabela].decode("utf-8"), linha_nova).encode("utf-8")

    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    parts["xl/workbook.xml"] = deslocar_nomes_definidos(workbook_xml, linha_nova).encode("utf-8")
    if "xl/calcChain.xml" in parts:
        parts["xl/calcChain.xml"] = deslocar_calc_chain(
            parts["xl/calcChain.xml"].decode("utf-8"),
            _sheet_id(workbook_xml, DRE_SHEET),
            linha_nova,
            linha_criada,
        ).encode("utf-8")


def aplicar(parts: dict[str, bytes]) -> bool:
    """Aplica as alterações nas partes do zip. Retorna False se já aplicadas."""
    sheet_part = _sheet_part(parts, DRE_SHEET)
    strings = _shared_strings(parts["xl/sharedStrings.xml"].decode("utf-8"))
    rotulos = _rotulos_coluna_a(parts[sheet_part].decode("utf-8"), strings)
    inicio = _linha_unica(rotulos, DESPESAS_ADMINISTRATIVAS_ROTULO)
    fim = _linha_unica(rotulos, PROXIMO_BLOCO_ROTULO)

    alterado = False
    if not _linha_iss_no_bloco(rotulos, inicio, fim):
        _inserir_linha_iss(parts, sheet_part)
        strings = _shared_strings(parts["xl/sharedStrings.xml"].decode("utf-8"))
        rotulos = _rotulos_coluna_a(parts[sheet_part].decode("utf-8"), strings)
        alterado = True

    apoio_part = _sheet_part(parts, APOIO_SHEET)
    apoio = parts[apoio_part].decode("utf-8")
    realinhado = realinhar_pareto_apoio(apoio, rotulos)
    if realinhado != apoio:
        parts[apoio_part] = realinhado.encode("utf-8")
        alterado = True
    return alterado


def processar(template: Path) -> bool:
    with ZipFile(template) as zin:
        infos = zin.infolist()
        parts = {info.filename: zin.read(info.filename) for info in infos}

    if not aplicar(parts):
        return False

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False, dir=template.parent) as tmp:
        tmp_path = Path(tmp.name)
    with ZipFile(tmp_path, "w") as zout:
        for info in infos:
            zout.writestr(info, parts[info.filename])
    shutil.copymode(template, tmp_path)
    tmp_path.replace(template)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template", nargs="?", default=str(DEFAULT_TEMPLATE))
    args = parser.parse_args()
    alterado = processar(Path(args.template))
    print("[ok] template atualizado" if alterado else "[ok] template já estava atualizado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
