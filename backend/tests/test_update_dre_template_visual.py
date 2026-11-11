"""Testes do patch que remove as linhas sem rótulo da aba DRE do template."""

import importlib.util
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from app.config import settings

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = importlib.util.spec_from_file_location(
    "update_dre_template_visual", _SCRIPTS / "update_dre_template_visual.py"
)
script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(script)

_ROTULOS = ["(=)Receita Bruta", "Detalhe A", "(-)Gastos Fixos", "Detalhe B", "(=)Total"]


def _linha(r: int, rotulo: int | None, formula: str, attrs: str = "") -> str:
    a = (
        f'<c r="A{r}" s="35" t="s"><v>{rotulo}</v></c>'
        if rotulo is not None
        else f'<c r="A{r}" s="35"/>'
    )
    return f'<row r="{r}"{attrs}>{a}<c r="B{r}"><f>{formula}</f><v>1</v></c></row>'


def _template(pasta: Path, *, total: str = "SUM(B6,B9)") -> Path:
    """DRE com cabeçalho vazio (1-5) e duas linhas sem rótulo (7 e 10)."""
    cabecalho = "".join(f'<row r="{r}"><c r="A{r}"/></row>' for r in range(1, 6))
    lookup = "IFERROR(VLOOKUP($A{r},APOIO!$B:$N,2,FALSE),0)"
    linhas = (
        cabecalho
        + _linha(6, 0, lookup.format(r=6))
        + _linha(7, None, lookup.format(r=7), ' hidden="1" outlineLevel="1"')
        + _linha(8, 1, lookup.format(r=8), ' hidden="1" outlineLevel="1"')
        + _linha(9, 2, lookup.format(r=9), ' collapsed="1"')
        + _linha(10, None, lookup.format(r=10), ' hidden="1" outlineLevel="1"')
        + _linha(11, 3, "B6/B$6", ' collapsed="1"')
        + _linha(12, 4, total)
    )
    partes = {
        "xl/workbook.xml": (
            '<workbook xmlns:r="r"><sheets>'
            '<sheet name="DRE" sheetId="21" r:id="rId2"/>'
            '<sheet name="APOIO" sheetId="25" r:id="rId5"/></sheets><definedNames>'
            '<definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'
            "DRE!$A$5:$B$12</definedName></definedNames></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships><Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId5" Target="worksheets/sheet5.xml"/></Relationships>'
        ),
        "xl/sharedStrings.xml": (
            f'<sst count="{len(_ROTULOS)}" uniqueCount="{len(_ROTULOS)}">'
            + "".join(f"<si><t>{rotulo}</t></si>" for rotulo in _ROTULOS)
            + "</sst>"
        ),
        "xl/worksheets/sheet2.xml": (
            '<worksheet><dimension ref="A1:B12"/><sheetViews><sheetView>'
            '<selection activeCell="B11" sqref="B11:B12"/></sheetView></sheetViews>'
            f"<sheetData>{linhas}</sheetData>"
            '<ignoredErrors><ignoredError sqref="B6:B12 B10" formula="1"/></ignoredErrors>'
            "</worksheet>"
        ),
        "xl/worksheets/_rels/sheet2.xml.rels": (
            '<Relationships><Relationship Id="rId3" '
            'Type="http://x/table" Target="../tables/table1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet5.xml": (
            '<worksheet><sheetData><row r="1">'
            '<c r="A1"><f>DRE!B12*-1</f><v>1</v></c>'
            '<c r="B1"><f>SUM(DRE!B6:B11)+B9</f><v>1</v></c>'
            '<c r="C1"><f>VLOOKUP(B5,DRE!A:A,1,FALSE)</f><v>1</v></c>'
            "</row></sheetData></worksheet>"
        ),
        "xl/tables/table1.xml": '<table name="DRE" ref="A5:B12"><autoFilter ref="A5:B12"/></table>',
        "xl/calcChain.xml": (
            '<calcChain><c r="B12" i="21"/><c r="B10" i="21"/><c r="B9" i="21"/>'
            '<c r="A1" i="25"/></calcChain>'
        ),
    }
    caminho = pasta / "minimo.xlsx"
    with ZipFile(caminho, "w") as zout:
        for nome, conteudo in partes.items():
            zout.writestr(nome, conteudo)
    return caminho


def _ler(caminho: Path, parte: str) -> str:
    with ZipFile(caminho) as zin:
        return zin.read(parte).decode("utf-8")


def test_dry_run_lista_linhas_sem_rotulo_sem_alterar_o_arquivo(tmp_path):
    caminho = _template(tmp_path)
    conteudo = caminho.read_bytes()

    assert script.processar(caminho, dry_run=True) == [7, 10]
    assert caminho.read_bytes() == conteudo


def test_processar_remove_linhas_sem_rotulo_e_renumera_todas_as_partes(tmp_path):
    caminho = _template(tmp_path)
    caminho.chmod(0o644)

    assert script.processar(caminho) == [7, 10]
    assert caminho.stat().st_mode & 0o777 == 0o644

    dre = _ler(caminho, "xl/worksheets/sheet2.xml")
    assert '<row r="6"><c r="A6" s="35" t="s"><v>0</v></c>' in dre
    assert '<row r="7" hidden="1" outlineLevel="1"><c r="A7" s="35" t="s"><v>1</v></c>' in dre
    assert "VLOOKUP($A7,APOIO!$B:$N,2,FALSE)" in dre  # Detalhe A subiu para 7
    # Gastos Fixos (8) mantém o grupo de Detalhe A; o grupo de Detalhe B só tinha
    # a linha em branco, então o marcador collapsed sai junto.
    assert '<row r="8" collapsed="1"><c r="A8" s="35" t="s"><v>2</v></c>' in dre
    assert '<row r="9"><c r="A9" s="35" t="s"><v>3</v></c>' in dre
    assert "<f>B6/B$6</f>" in dre
    assert "<f>SUM(B6,B8)</f>" in dre  # total aponta para os mesmos rótulos
    assert '<row r="11"' not in dre
    assert '<dimension ref="A1:B10"/>' in dre
    assert 'activeCell="B9" sqref="B9:B10"' in dre
    assert 'sqref="B6:B10"' in dre
    assert 'ref="A5:B10"' in _ler(caminho, "xl/tables/table1.xml")
    assert "DRE!$A$5:$B$10" in _ler(caminho, "xl/workbook.xml")
    assert _ler(caminho, "xl/calcChain.xml") == (
        '<calcChain><c r="B10" i="21"/><c r="B8" i="21"/><c r="A1" i="25"/></calcChain>'
    )
    apoio = _ler(caminho, "xl/worksheets/sheet5.xml")
    assert "<f>DRE!B10*-1</f>" in apoio
    assert "<f>SUM(DRE!B6:B9)+B9</f>" in apoio  # B9 é da própria APOIO: intacta
    assert "<f>VLOOKUP(B5,DRE!A:A,1,FALSE)</f>" in apoio

    conteudo = caminho.read_bytes()
    assert script.processar(caminho) == []
    assert caminho.read_bytes() == conteudo


def test_formula_apontando_para_linha_sem_rotulo_aborta_o_patch(tmp_path):
    caminho = _template(tmp_path, total="SUM(B6,B7)")
    conteudo = caminho.read_bytes()

    with pytest.raises(script.LinhaReferenciadaError):
        script.processar(caminho)
    assert caminho.read_bytes() == conteudo


def test_normalizar_collapsed_remove_marcador_de_grupo_que_ficou_vazio():
    xml = (
        '<sheetData><row r="1"><c r="A1"/></row>'
        '<row r="2" collapsed="1"><c r="A2"/></row>'
        '<row r="3" hidden="1" outlineLevel="1"><c r="A3"/></row>'
        '<row r="4" collapsed="1"><c r="A4"/></row></sheetData>'
    )
    saida = script.normalizar_collapsed(xml)

    assert '<row r="2"><c r="A2"/></row>' in saida
    assert '<row r="4" collapsed="1">' in saida


def test_template_oficial_sem_linhas_em_branco_e_patch_idempotente(tmp_path):
    copia = tmp_path / "template.xlsx"
    shutil.copy2(settings.template_dre_path, copia)
    conteudo = copia.read_bytes()

    assert script.processar(copia) == []
    assert copia.read_bytes() == conteudo

    wb = load_workbook(copia)
    ws = wb["DRE"]
    rotulos = {
        r: str(ws.cell(row=r, column=1).value or "").strip() for r in range(1, ws.max_row + 1)
    }
    assert [r for r in range(6, ws.max_row + 1) if not rotulos[r]] == []

    def linha(rotulo: str) -> int:
        linhas = [r for r, texto in rotulos.items() if texto == rotulo]
        assert len(linhas) == 1, rotulo
        return linhas[0]

    receita_liquida = linha("(=)Receita Líquida")
    margem = linha("(=)Margem de Contribuição")
    operacional = linha("(=)RESULTADO OPERACIONAL")
    antes_ir = linha("(=)RESULTADO ANTES DO IR")
    liquido = linha("(=)RESULTADO LÍQUIDO")
    gerencial = linha("(=)RESULTADO GERENCIAL")
    assert ws.cell(margem, 2).value == f"=SUM(B{receita_liquida}:B{receita_liquida + 1})"
    assert rotulos[receita_liquida + 1] == "(-)Custos Variavéis"
    assert ws.cell(operacional, 2).value == f"=SUM(B{margem}:B{margem + 1})"
    assert rotulos[margem + 1] == "(-)Gastos Fixos"
    assert ws.cell(antes_ir, 2).value == (
        f"=SUM(B{operacional},B{operacional + 1},B{operacional + 2},"
        f"B{linha('(+/-)Despesas e Recebimentos Não Operacionais')})"
    )
    assert rotulos[operacional + 1] == "(-)Depreciação Imobilizado"
    assert rotulos[operacional + 2] == "(+/-)Despesas e Receitas Financeiras"
    assert ws.cell(liquido, 2).value == f"=SUM(B{antes_ir},B{antes_ir + 1})"
    assert rotulos[antes_ir + 1] == "(-)IRPJ/CSLL"
    assert ws.cell(gerencial, 2).value == f"=SUM(B{liquido}:B{liquido + 1})"
    assert rotulos[liquido + 1] == "(-)Investimentos"
    # Percentuais e linha 2 continuam sobre a Receita Bruta (6) e a Líquida.
    assert ws.cell(margem, 3).value == f"=IFERROR(B{margem}/B${receita_liquida},0)"
    assert ws["F2"].value == "=F6/$AH$6"
    assert ws.tables["DRE"].ref == f"A5:AI{ws.max_row}"

    apoio = wb["APOIO"]
    assert apoio["Y37"].value == f"=DRE!A{linha('(-)Gastos Fixos')}"
    assert apoio["Z28"].value == f"=DRE!AH{linha('Despesas com Pessoal')}*-1"
