"""Testes para FluxoCaixaTransformer (transformacao/engine.py)."""

from decimal import Decimal

import pandas as pd

from app.contracts.fluxo_caixa import TipoMovimento
from app.ingestao.parser import ExcelParser
from app.transformacao.engine import FluxoCaixaTransformer


def _dados_fluxo(df, aba="Sheet"):
    return {
        "arquivo": "fluxo_teste.xls",
        "abas": [aba],
        "dados": {aba: df},
        "formato": ".xls",
    }


def test_transferencia_com_banco_destino_vira_debito():
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
    assert mov.tipo == TipoMovimento.DEBITO
    assert mov.valor == Decimal("25000")


def test_transferencia_sem_banco_destino_vira_credito():
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
    assert mov.tipo == TipoMovimento.CREDITO
    assert mov.valor == Decimal("25000")


def test_transferencia_itau_para_outro_banco_vira_debito_pela_descricao():
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
    assert mov.tipo == TipoMovimento.DEBITO
    assert mov.valor == Decimal("79602.49")
    assert mov.classificacao == "Transferência Emitida"


def test_transferencia_outro_banco_para_itau_vira_credito_pela_descricao():
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
    assert mov.tipo == TipoMovimento.CREDITO
    assert mov.valor == Decimal("50000")
    assert mov.classificacao == "Transferência Recebida"


def test_detecta_itau_isolamento_antes_de_itau():
    parser = ExcelParser("fluxo")

    assert parser.detectar_banco("RELATORIO DE MOVIMENTO ITAU ISOLAMENTO.xls") == "itau_isolamento"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO BI ITAU.xlsx") == "itau"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO SIMPLES caix a.xls") == "cef"
