"""Caixa alta e recuo hierárquico dos rótulos da aba DRE nos arquivos gerados."""

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from test_dre_geracao_completa_service import _build_service_com_receita_liquida_e_impostos

from app.config import settings
from app.processamento import dre_geracao_completa
from app.processamento.dre_apresentacao import (
    RECUO_DETALHE,
    aplicar_apresentacao_dre,
    nivel_recuo,
)


def test_nivel_recuo_vem_do_estilo_e_detalhe_sem_negrito_vai_para_o_ultimo_nivel():
    assert [nivel_recuo(recuo, True) for recuo in (0, 1, 2)] == [1, 2, 3]
    assert nivel_recuo(4, False) == RECUO_DETALHE
    # Rubricas que o template deixou sem recuo continuam sendo detalhe.
    assert nivel_recuo(0, False) == RECUO_DETALHE
    assert nivel_recuo(None, False) == RECUO_DETALHE


def _aba_dre_minima():
    ws = Workbook().active
    ws.title = "DRE"
    ws["A5"] = "Demonstrativo"
    linhas = [
        ("(=)Receita Bruta", True, 0),
        ("(-)Deduções sobre vendas", True, 1),
        ("Impostos sobre vendas", True, 2),
        ("FERIAS ", False, 4),
        ("Marketing", False, 0),
    ]
    for linha, (rotulo, negrito, recuo) in enumerate(linhas, start=6):
        celula = ws.cell(row=linha, column=1, value=rotulo)
        celula.font = Font(b=negrito)
        celula.alignment = Alignment(
            horizontal="left" if recuo else None, vertical="center", indent=recuo
        )
        ws.cell(row=linha, column=2, value=linha * 10)
    ws.cell(row=11, column=1, value=123)
    return ws


def test_aplicar_apresentacao_caixa_alta_sem_strip_e_recuo_por_alinhamento():
    ws = _aba_dre_minima()

    meta = aplicar_apresentacao_dre(ws)

    assert meta == {"rotulos_formatados": 5}
    assert [ws.cell(row=r, column=1).value for r in range(6, 11)] == [
        "(=)RECEITA BRUTA",
        "(-)DEDUÇÕES SOBRE VENDAS",
        "IMPOSTOS SOBRE VENDAS",
        "FERIAS ",  # espaço final preservado: a chave do VLOOKUP não muda
        "MARKETING",
    ]
    assert [ws.cell(row=r, column=1).alignment.indent for r in range(6, 11)] == [1, 2, 3, 5, 5]
    for linha in range(6, 11):
        alinhamento = ws.cell(row=linha, column=1).alignment
        assert alinhamento.horizontal == "left"
        assert alinhamento.vertical == "center"
        assert not ws.cell(row=linha, column=1).value.startswith(" ")
    # Cabeçalho, valores e células não textuais ficam como estavam.
    assert ws["A5"].value == "Demonstrativo"
    assert ws["A5"].alignment.indent == 0
    assert [ws.cell(row=r, column=2).value for r in range(6, 11)] == [60, 70, 80, 90, 100]
    assert ws["A11"].value == 123


def test_aplicar_apresentacao_duas_vezes_nao_soma_recuo():
    ws = _aba_dre_minima()
    aplicar_apresentacao_dre(ws)

    assert aplicar_apresentacao_dre(ws) == {"rotulos_formatados": 0}
    assert ws["A6"].alignment.indent == 1


def test_template_oficial_ganha_caixa_alta_e_recuo_em_todos_os_rotulos():
    ws = load_workbook(settings.template_dre_path)["DRE"]
    aplicar_apresentacao_dre(ws)

    for linha in range(6, ws.max_row + 1):
        celula = ws.cell(row=linha, column=1)
        assert isinstance(celula.value, str) and celula.value.strip(), linha
        assert celula.value == celula.value.upper(), linha
        assert celula.alignment.indent >= 1, linha
        negrito = bool(celula.font.b)
        assert (celula.alignment.indent == RECUO_DETALHE) is (not negrito), linha


def _valores_dre(caminho):
    ws = load_workbook(caminho, data_only=True)["DRE"]
    rotulos = {linha: ws.cell(row=linha, column=1).value for linha in range(1, ws.max_row + 1)}
    valores = {
        (linha, coluna): ws.cell(row=linha, column=coluna).value
        for linha in range(1, ws.max_row + 1)
        for coluna in range(2, 36)
    }
    return ws, rotulos, valores


def test_gerar_arquivo_aplica_apresentacao_sem_mudar_nenhum_valor(tmp_path, monkeypatch):
    service = _build_service_com_receita_liquida_e_impostos()
    com_apresentacao = tmp_path / "com.xlsx"
    service.gerar_arquivo(competencia="01/2026", output_path=com_apresentacao)

    monkeypatch.setattr(dre_geracao_completa, "aplicar_apresentacao_dre", lambda ws: {})
    sem_apresentacao = tmp_path / "sem.xlsx"
    service.gerar_arquivo(competencia="01/2026", output_path=sem_apresentacao)

    ws, rotulos, valores = _valores_dre(com_apresentacao)
    _, rotulos_originais, valores_originais = _valores_dre(sem_apresentacao)

    assert valores == valores_originais
    assert rotulos[5] == rotulos_originais[5]
    for linha in range(6, ws.max_row + 1):
        assert rotulos_originais[linha], f"linha {linha} sem rótulo no DRE gerado"
        assert rotulos[linha] == rotulos_originais[linha].upper()
        assert ws.cell(row=linha, column=1).alignment.indent >= 1
