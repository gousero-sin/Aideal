"""Testes para FluxoCaixaTransformer (transformacao/engine.py)."""

from datetime import date
from decimal import Decimal

import pandas as pd

from app.contracts.fluxo_caixa import FCLote, FCMovimento, TipoMovimento
from app.ingestao.parser import ExcelParser
from app.transformacao.engine import FluxoCaixaTransformer


def _dados_fluxo(df, aba="Sheet"):
    return {
        "arquivo": "fluxo_teste.xls",
        "abas": [aba],
        "dados": {aba: df},
        "formato": ".xls",
    }


def test_transferencia_com_banco_destino_preserva_tipo_neutro_e_direcao_emitida():
    df = pd.DataFrame(
        {
            "Data Mov.": ["07/05/2025"],
            "Tipo": ["Transferência - BANCO SAFRA"],
            "Desc. Mov.": ["TRANSFERÊNCIA ENTRE BANCOS ITAÚ X SAFRA"],
            "Valor (R$)": [25000.0],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="05/2025")

    assert lote.total_registros == 1
    mov = lote.movimentos[0]
    assert mov.tipo == TipoMovimento.TRANSFERENCIA
    assert mov.valor == Decimal("25000")
    assert mov.classificacao == "Transferência Emitida"


def test_transferencia_sem_banco_destino_preserva_tipo_neutro_e_direcao_recebida():
    df = pd.DataFrame(
        {
            "Data Mov.": ["07/05/2025"],
            "Tipo": ["Transferência - "],
            "Desc. Mov.": ["TRANSFERÊNCIA ENTRE BANCOS CEF X ITAÚ"],
            "Valor (R$)": [25000.0],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="05/2025")

    assert lote.total_registros == 1
    mov = lote.movimentos[0]
    assert mov.tipo == TipoMovimento.TRANSFERENCIA
    assert mov.valor == Decimal("25000")
    assert mov.classificacao == "Transferência Recebida"


def test_transferencia_itau_para_outro_banco_preserva_tipo_neutro_pela_descricao():
    df = pd.DataFrame(
        {
            "Data Mov.": ["22/07/2025"],
            "Tipo": ["Transferência"],
            "Desc. Mov.": ["TRANSFERÊNCIA ENTRE BANCOS ITAÚ X SAFRA"],
            "Valor (R$)": [79602.49],
            "Conta Gerencial Mov": ["Transferência entre Bancos"],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="07/2025")

    assert lote.total_registros == 1
    mov = lote.movimentos[0]
    assert mov.tipo == TipoMovimento.TRANSFERENCIA
    assert mov.valor == Decimal("79602.49")
    assert mov.classificacao == "Transferência Emitida"


def test_transferencia_outro_banco_para_itau_preserva_tipo_neutro_pela_descricao():
    df = pd.DataFrame(
        {
            "Data Mov.": ["25/07/2025"],
            "Tipo": ["Transferência"],
            "Desc. Mov.": ["TRANSFERÊNCIA ENTRE BANCOS SAFRA X ITAÚ"],
            "Valor (R$)": [50000.0],
            "Conta Gerencial Mov": ["Transferência entre Bancos"],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="07/2025")

    assert lote.total_registros == 1
    mov = lote.movimentos[0]
    assert mov.tipo == TipoMovimento.TRANSFERENCIA
    assert mov.valor == Decimal("50000")
    assert mov.classificacao == "Transferência Recebida"


def test_conta_gerencial_usa_codigo_separado_como_rotulo_canonico():
    df = pd.DataFrame(
        {
            "Data Mov.": ["16/06/2026"],
            "Tipo": ["Débito"],
            "Descrição": ["Pagamento parcelamento"],
            "Valor": [1029.44],
            "Saldo": [5000.0],
            "Cód. Conta Gerencial": ["17.1"],
            "Conta Gerencial": ["PARCELAMENTO"],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="06/2026")

    assert lote.total_registros == 1
    mov = lote.movimentos[0]
    assert mov.classificacao == "17.1 - PARCELAMENTO"
    assert mov.conta_gerencial == "17.1 - PARCELAMENTO"


def test_saldo_bancario_zero_e_preservado_como_fechamento_valido():
    df = pd.DataFrame(
        {
            "Data Mov.": ["16/06/2026"],
            "Tipo": ["Débito"],
            "Descrição": ["Quitação total"],
            "Valor": [100.0],
            "Saldo": [0.0],
            "Conta Gerencial": ["4.3 - OUTROS MATERIAIS"],
        }
    )

    transformer = FluxoCaixaTransformer()
    lote = transformer.transformar(_dados_fluxo(df), banco_origem="itau", periodo="06/2026")

    assert lote.movimentos[0].saldo == Decimal("0")


def test_totais_do_lote_usam_valor_absoluto_para_movimentos_com_sinal_de_origem():
    lote = FCLote(
        periodo="06/2026",
        movimentos=[
            FCMovimento(
                data_movimento=date(2026, 6, 1),
                tipo=TipoMovimento.CREDITO,
                descricao="Entrada com sinal bancário",
                valor=Decimal("-100"),
                banco_origem="itau",
            ),
            FCMovimento(
                data_movimento=date(2026, 6, 2),
                tipo=TipoMovimento.DEBITO,
                descricao="Saída com sinal bancário",
                valor=Decimal("-50"),
                banco_origem="itau",
            ),
        ],
    )

    assert lote.total_creditos == Decimal("100")
    assert lote.total_debitos == Decimal("50")


def test_detecta_itau_isolamento_antes_de_itau():
    parser = ExcelParser("fluxo")

    assert parser.detectar_banco("RELATORIO DE MOVIMENTO ITAU ISOLAMENTO.xls") == "itau_isolamento"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO BI ITAU.xlsx") == "itau"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO SIMPLES caix a.xls") == "cef"


def test_detecta_banco_prioriza_segmento_do_nome_padrao_de_movimentos():
    parser = ExcelParser("fluxo")

    assert parser.detectar_banco("movimentos_2026-01_safra_itau.xlsx") == "safra"
    assert parser.detectar_banco("movimentos_2026-01_cef.xlsx") == "cef"
