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


def test_transferencia_sem_descricao_e_saida_no_formato_operacional():
    df = pd.DataFrame(
        {
            "Data Mov.": ["19/01/2026"],
            "Tipo": ["Transferência"],
            "Desc. Mov.": [""],
            "Valor (R$)": [100000.0],
            "Cód. Conta Gerencial": ["2.1"],
            "Conta Gerencial Mov": ["Transferência entre Bancos"],
        }
    )

    lote = FluxoCaixaTransformer().transformar(
        _dados_fluxo(df),
        banco_origem="cef",
        periodo="01/2026",
    )

    assert lote.movimentos[0].tipo == TipoMovimento.TRANSFERENCIA
    assert lote.movimentos[0].classificacao == "Transferência Emitida"


def test_normalizacao_legada_recupera_direcao_pelo_saldo_e_contrapartida():
    movimento_base = {
        "data_movimento": date(2026, 1, 14),
        "tipo": TipoMovimento.TRANSFERENCIA,
        "descricao": "",
        "valor": Decimal("200000"),
        "classificacao": "Transferência Recebida",
        "conta_gerencial": "2.1 - Transferência entre Bancos",
        "linha_origem": 10,
    }
    movimentos = [
        FCMovimento(
            **movimento_base,
            saldo=Decimal("562294.94"),
            banco_origem="itau",
            arquivo_origem="movimentos_2026-01_itau_.xlsx",
        ),
        FCMovimento(
            data_movimento=date(2026, 1, 13),
            tipo=TipoMovimento.DEBITO,
            descricao="Movimento anterior",
            valor=Decimal("1"),
            saldo=Decimal("345605.81"),
            banco_origem="itau",
            arquivo_origem="movimentos_2026-01_itau_.xlsx",
            linha_origem=11,
        ),
        FCMovimento(
            **movimento_base,
            saldo=Decimal("203233.24"),
            banco_origem="desconhecido",
            arquivo_origem="movimentos_2026-01_mercantil_.xlsx",
        ),
        FCMovimento(
            data_movimento=date(2026, 1, 13),
            tipo=TipoMovimento.DEBITO,
            descricao="Movimento anterior",
            valor=Decimal("1"),
            saldo=Decimal("3233.24"),
            banco_origem="mercantil",
            arquivo_origem="movimentos_2026-01_mercantil_.xlsx",
            linha_origem=11,
        ),
    ]

    normalizados = FluxoCaixaTransformer().normalizar_movimentos_persistidos(
        movimentos
    )
    transferencia_itau = normalizados[0]
    transferencia_mercantil = normalizados[2]

    assert transferencia_itau.classificacao == "Transferência Emitida"
    assert transferencia_mercantil.classificacao == "Transferência Recebida"
    assert transferencia_mercantil.banco_origem == "mercantil"


def test_codigo_2_1_normaliza_novo_upload_como_transferencia_neutra():
    df = pd.DataFrame(
        {
            "Data Mov.": ["01/06/2026"],
            "Tipo": ["Crédito"],
            "Desc. Mov.": [""],
            "Valor (R$)": [100000.0],
            "Cód. Conta Gerencial": ["2.1"],
            "Conta Gerencial Mov": ["Nome da conta alterado"],
        }
    )

    lote = FluxoCaixaTransformer().transformar(
        _dados_fluxo(df),
        banco_origem="itau",
        periodo="06/2026",
    )

    assert lote.total_registros == 1
    assert lote.movimentos[0].tipo == TipoMovimento.TRANSFERENCIA
    assert lote.movimentos[0].classificacao == "Transferência Recebida"
    assert lote.total_creditos == Decimal("0")
    assert lote.total_debitos == Decimal("0")


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


def test_codigo_2_1_mantem_transferencias_neutras_mesmo_com_nome_alterado():
    recebida = FCMovimento(
        data_movimento=date(2026, 6, 1),
        tipo=TipoMovimento.CREDITO,
        descricao="",
        valor=Decimal("100"),
        classificacao="2.1 - Nome da conta alterado",
        conta_gerencial="2.1 - Nome da conta alterado",
        banco_origem="itau",
    )
    emitida = recebida.model_copy(
        update={
            "tipo": TipoMovimento.DEBITO,
            "valor": Decimal("40"),
        }
    )
    lote = FCLote(periodo="06/2026", movimentos=[recebida, emitida])

    assert recebida.eh_transferencia is True
    assert emitida.eh_transferencia is True
    assert emitida.transferencia_emitida is True
    assert lote.total_creditos == Decimal("0")
    assert lote.total_debitos == Decimal("0")


def test_detecta_itau_isolamento_antes_de_itau():
    parser = ExcelParser("fluxo")

    assert parser.detectar_banco("RELATORIO DE MOVIMENTO ITAU ISOLAMENTO.xls") == "itau_isolamento"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO BI ITAU.xlsx") == "itau"
    assert parser.detectar_banco("RELATORIO DE MOVIMENTO SIMPLES caix a.xls") == "cef"


def test_detecta_banco_prioriza_segmento_do_nome_padrao_de_movimentos():
    parser = ExcelParser("fluxo")

    assert parser.detectar_banco("movimentos_2026-01_safra_itau.xlsx") == "safra"
    assert parser.detectar_banco("movimentos_2026-01_cef.xlsx") == "cef"
    assert parser.detectar_banco("movimentos_2026-01_caixa_.xlsx") == "cef"
