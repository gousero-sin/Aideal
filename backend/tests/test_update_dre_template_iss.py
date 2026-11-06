"""Testes do patch que cria a linha ISS em Despesas Administrativas no template DRE."""

import importlib.util
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

from app.config import settings

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = importlib.util.spec_from_file_location(
    "update_dre_template_iss", _SCRIPTS / "update_dre_template_iss.py"
)
script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(script)


def _sheet_xml(linhas: str) -> str:
    return (
        '<worksheet><dimension ref="A1:C4"/><sheetViews><sheetView>'
        '<selection activeCell="B3" sqref="B3:B4"/></sheetView></sheetViews>'
        f"<sheetData>{linhas}</sheetData>"
        '<ignoredErrors><ignoredError sqref="C1:C4 B2" formula="1"/></ignoredErrors></worksheet>'
    )


_LINHA_1 = '<row r="1"><c r="A1" s="35" t="s"><v>0</v></c></row>'
_LINHA_2 = (
    '<row r="2" hidden="1" outlineLevel="1"><c r="A2" t="inlineStr"><is><t>Marketing</t></is></c>'
    '<c r="B2" s="29"><f>IFERROR(VLOOKUP($A2,APOIO!$B:$N,MATCH(B$1,APOIO!$B$1:$N$1,0),FALSE),0)</f>'
    '<v>12</v></c><c r="C2" s="38"><f>IFERROR(B2/B$1,0)</f><v>0.5</v></c></row>'
)
_LINHA_3 = (
    '<row r="3" collapsed="1"><c r="A3" s="36" t="s"><v>1</v></c>'
    '<c r="B3"><f>SUM(B1:B4)+B4+B2+APOIO!B3</f><v>0</v></c></row>'
)
_LINHA_4 = '<row r="4"><c r="B4"><f>B3+B$3</f><v>0</v></c></row>'


def _inserir() -> tuple[str, str]:
    return script.inserir_linha(
        _sheet_xml(_LINHA_1 + _LINHA_2 + _LINHA_3 + _LINHA_4),
        2,
        indice_rotulo=7,
        estilo_rotulo="35",
    )


def test_deslocar_formula_so_move_referencias_da_propria_aba_na_linha_nova_ou_abaixo():
    assert script.deslocar_formula("SUM(B1:B4)+B4+B2+APOIO!B3", 3) == "SUM(B1:B5)+B5+B2+APOIO!B3"
    assert script.deslocar_formula("B3+B$3", 3) == "B4+B$4"
    assert script.deslocar_formula("VLOOKUP($A9,APOIO!$B:$N,1,FALSE)", 3) == (
        "VLOOKUP($A10,APOIO!$B:$N,1,FALSE)"
    )
    assert script.deslocar_formula("DRE!A5+DRE!A2", 3) == "DRE!A6+DRE!A2"


def test_inserir_linha_copia_modelo_com_rotulo_novo_e_formulas_traduzidas():
    xml, nova = _inserir()

    assert nova.startswith('<row r="3" hidden="1" outlineLevel="1">')
    assert '<c r="A3" s="35" t="s"><v>7</v></c>' in nova
    assert "IFERROR(VLOOKUP($A3,APOIO!$B:$N,MATCH(B$1,APOIO!$B$1:$N$1,0),FALSE),0)" in nova
    assert "IFERROR(B3/B$1,0)" in nova
    # Cache do modelo não vaza para a linha nova.
    assert "<v>12</v>" not in nova
    assert "<v>0.5</v>" not in nova
    assert xml.index('<row r="2"') < xml.index('<row r="3" hidden="1"') < xml.index('<row r="4"')


def test_inserir_linha_desce_as_de_baixo_e_renumera_metadados_da_aba():
    xml, _ = _inserir()

    # A linha seguinte mantém o marcador do grupo recolhido e sobe o número.
    assert '<row r="4" collapsed="1"><c r="A4" s="36" t="s"><v>1</v></c>' in xml
    assert "<f>SUM(B1:B5)+B5+B2+APOIO!B3</f>" in xml
    assert "<f>B4+B$4</f>" in xml
    assert '<dimension ref="A1:C5"/>' in xml
    assert 'activeCell="B4" sqref="B4:B5"' in xml
    assert 'sqref="C1:C5 B2"' in xml
    # Linhas acima da inserção ficam intactas.
    assert _LINHA_1 in xml


def test_deslocar_tabela_e_nome_definido_acompanham_a_insercao():
    formula = "<calculatedColumnFormula>{}</calculatedColumnFormula></table>"
    tabela = '<table name="DRE" ref="A5:AI186">' + formula.format("B90")
    assert script.deslocar_tabela(tabela, 90) == (
        '<table name="DRE" ref="A5:AI187">' + formula.format("B91")
    )
    workbook = (
        '<definedName name="_xlnm._FilterDatabase" localSheetId="1" hidden="1">'
        "DRE!$A$5:$AI$189</definedName>"
        '<definedName name="_xlnm._FilterDatabase" localSheetId="3" hidden="1">'
        "PLANO_CONTAS!$A$1:$D$175</definedName>"
    )
    saida = script.deslocar_nomes_definidos(workbook, 90)
    assert "DRE!$A$5:$AI$190" in saida
    assert "PLANO_CONTAS!$A$1:$D$175" in saida


def test_deslocar_calc_chain_so_mexe_na_aba_dre_e_acrescenta_a_linha_nova():
    cadeia = (
        '<calcChain><c r="B89" i="21"/><c r="B90" i="21" l="1"/>'
        '<c r="B90" i="25"/></calcChain>'
    )
    linha = '<row r="90"><c r="A90" t="s"><v>1</v></c><c r="B90"><f>1</f><v>0</v></c></row>'

    assert script.deslocar_calc_chain(cadeia, "21", 90, linha) == (
        '<calcChain><c r="B89" i="21"/><c r="B91" i="21" l="1"/>'
        '<c r="B90" i="25"/><c r="B90" i="21"/></calcChain>'
    )


_ROTULOS_DRE_MINIMA = [
    "(-)Gastos Fixos",
    "Despesas com Pessoal",
    "Despesas Administrativas",
    "Marketing",
    "Despesas com Veículos e Equipamentos",
    "Despesas com Locações",
    "Despesas com Máquinas e Equipamentos",
    "Despesas com Viagens e Hospedagens",
    "Despesas Financeiras",
    "Despesas com Infraestrutura",
    "Serviços de Terceiros",
]


def _template_minimo(pasta: Path) -> Path:
    """Monta um xlsx mínimo, sem a linha ISS, com todas as partes que o patch toca."""
    linhas = "".join(
        f'<row r="{linha}"><c r="A{linha}" s="35" t="s"><v>{indice}</v></c>'
        f'<c r="B{linha}" s="29"><f>IFERROR(VLOOKUP($A{linha},APOIO!$B:$N,2,FALSE),0)</f>'
        "<v>9</v></c></row>"
        for indice, linha in enumerate(range(6, 6 + len(_ROTULOS_DRE_MINIMA)))
    )
    partes = {
        "xl/workbook.xml": (
            '<workbook xmlns:r="r"><sheets>'
            '<sheet name="DRE" sheetId="21" r:id="rId2"/>'
            '<sheet name="APOIO" sheetId="25" r:id="rId5"/></sheets><definedNames>'
            '<definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'
            "DRE!$A$5:$B$16</definedName></definedNames></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships><Relationship Id="rId2" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId5" Target="worksheets/sheet5.xml"/></Relationships>'
        ),
        "xl/sharedStrings.xml": (
            f'<sst count="{len(_ROTULOS_DRE_MINIMA)}" uniqueCount="{len(_ROTULOS_DRE_MINIMA)}">'
            + "".join(f"<si><t>{rotulo}</t></si>" for rotulo in _ROTULOS_DRE_MINIMA)
            + "</sst>"
        ),
        "xl/worksheets/sheet2.xml": (
            f'<worksheet><dimension ref="A5:B16"/><sheetData>{linhas}</sheetData></worksheet>'
        ),
        "xl/worksheets/_rels/sheet2.xml.rels": (
            '<Relationships><Relationship Id="rId3" '
            'Type="http://x/table" Target="../tables/table1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet5.xml": (
            '<worksheet><sheetData><row r="28"><c r="Y28" t="str"><f>DRE!A36</f>'
            '<v>Despesas com Pessoal</v></c><c r="Z28"><f>DRE!AH36*-1</f><v>1</v></c>'
            '<c r="AA28"><f>DRE!A36</f><v>x</v></c></row><row r="37"><c r="Y37" t="str">'
            '<f>DRE!A35</f><v>G</v></c></row></sheetData></worksheet>'
        ),
        "xl/tables/table1.xml": '<table name="DRE" ref="A5:B16"/>',
        "xl/calcChain.xml": '<calcChain><c r="B9" i="21"/><c r="B10" i="21"/></calcChain>',
    }
    caminho = pasta / "minimo.xlsx"
    with ZipFile(caminho, "w") as zout:
        for nome, conteudo in partes.items():
            zout.writestr(nome, conteudo)
    return caminho


def _ler(caminho: Path, parte: str) -> str:
    with ZipFile(caminho) as zin:
        return zin.read(parte).decode("utf-8")


def test_processar_cria_iss_atualiza_todas_as_partes_e_a_segunda_execucao_nao_altera(tmp_path):
    caminho = _template_minimo(tmp_path)
    caminho.chmod(0o644)

    assert script.processar(caminho) is True
    assert caminho.stat().st_mode & 0o777 == 0o644

    dre = _ler(caminho, "xl/worksheets/sheet2.xml")
    sst = _ler(caminho, "xl/sharedStrings.xml")
    assert '<c r="A10" s="35" t="s"><v>11</v></c>' in dre  # ISS logo abaixo de Marketing (9)
    assert "VLOOKUP($A10,APOIO!$B:$N,2,FALSE)" in dre
    assert '<row r="11"><c r="A11" s="35" t="s"><v>4</v></c>' in dre  # Veículos desceu
    assert '<dimension ref="A5:B17"/>' in dre
    assert 'count="12" uniqueCount="12"' in sst
    assert sst.endswith("<si><t>ISS</t></si></sst>")
    assert 'ref="A5:B17"' in _ler(caminho, "xl/tables/table1.xml")
    assert "DRE!$A$5:$B$17" in _ler(caminho, "xl/workbook.xml")
    assert _ler(caminho, "xl/calcChain.xml") == (
        '<calcChain><c r="B9" i="21"/><c r="B11" i="21"/><c r="B10" i="21"/></calcChain>'
    )

    apoio = _ler(caminho, "xl/worksheets/sheet5.xml")
    assert "<f>DRE!A7</f><v>Despesas com Pessoal</v>" in apoio  # Pessoal na linha 7
    assert "<f>DRE!AH7*-1</f>" in apoio
    assert "<f>DRE!A6</f><v>G</v>" in apoio  # Gastos Fixos na linha 6
    assert '<c r="AA28"><f>DRE!A36</f>' in apoio  # fora do quadro PARETO: intacta

    conteudo = caminho.read_bytes()
    assert script.processar(caminho) is False
    assert caminho.read_bytes() == conteudo


def test_template_oficial_tem_iss_no_bloco_e_patch_e_idempotente(tmp_path):
    copia = tmp_path / "template.xlsx"
    shutil.copy2(settings.template_dre_path, copia)
    original = {}
    with ZipFile(copia) as zin:
        original = {nome: zin.read(nome) for nome in zin.namelist()}

    assert script.processar(copia) is False

    with ZipFile(copia) as zin:
        assert {nome: zin.read(nome) for nome in zin.namelist()} == original

    ws = load_workbook(copia)["DRE"]
    rotulos = {r: str(ws.cell(row=r, column=1).value or "").strip() for r in range(1, 200)}
    linha_iss = next(r for r, rotulo in rotulos.items() if rotulo == "ISS")
    assert rotulos[linha_iss - 1] == "Marketing"
    assert rotulos[linha_iss + 1] == "Despesas com Veículos e Equipamentos"
    assert ws.cell(row=linha_iss, column=2).value.startswith(f"=IFERROR(VLOOKUP($A{linha_iss},")
    assert ws.cell(row=linha_iss, column=3).value == f"=IFERROR(B{linha_iss}/B$16,0)"
    assert ws.cell(row=linha_iss, column=34).value.startswith(f"=SUM(B{linha_iss},D{linha_iss},")
