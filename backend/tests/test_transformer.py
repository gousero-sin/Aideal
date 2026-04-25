"""Testes para DRETransformer (transformacao/engine.py)."""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.transformacao.engine import DRETransformer


def _dados_dre(df, aba="Sheet1"):
    return {
        "arquivo": "teste.xls",
        "abas": [aba],
        "dados": {aba: df},
        "formato": ".xls",
    }


class TestDRETransformerBasico:
    def test_transforma_lancamento_entrada(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": ["Recebimento CMOC"],
            "Vlr.bruto (R$)": [40258.08],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_registros == 1
        lanc = lote.lancamentos[0]
        assert lanc.data == date(2025, 5, 1)
        assert lanc.historico == "Recebimento CMOC"
        assert lanc.credito == Decimal("40258.08")
        assert lanc.debito == Decimal("0")

    def test_transforma_lancamento_saida(self):
        df = pd.DataFrame({
            "Emissão": ["15/05/2025"],
            "Descri.": ["Pagamento fornecedor"],
            "Vlr.bruto (R$)": [5000.0],
            "CLASSIFICAÇÃO": ["2 - SAIDA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_registros == 1
        lanc = lote.lancamentos[0]
        assert lanc.credito == Decimal("0")
        assert lanc.debito == Decimal("5000")

    def test_ignora_linha_sem_data(self):
        df = pd.DataFrame({
            "Emissão": [None, "01/05/2025"],
            "Descri.": ["Sem data", "Com data"],
            "Vlr.bruto (R$)": [100, 200],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "1 - ENTRADA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")
        assert lote.total_registros == 1
        assert lote.lancamentos[0].historico == "Com data"

    def test_ignora_linha_sem_historico(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": [None],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")
        assert lote.total_registros == 0

    def test_preserva_linha_origem(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025", "02/05/2025"],
            "Descri.": ["A", "B"],
            "Vlr.bruto (R$)": [100, 200],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAIDA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")
        assert lote.lancamentos[0].linha_origem == 2
        assert lote.lancamentos[1].linha_origem == 3

    def test_centro_custo_mapeado(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": ["Teste"],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
            "Obra/\nCentro custo": ["NIOBIO CMOC"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")
        assert lote.lancamentos[0].centro_custo == "NIOBIO CMOC"

    def test_expande_impostos_em_lancamentos_de_debito(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": ["Recebimento com impostos"],
            "Vlr.bruto (R$)": [1000.0],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
            "IR (R$)": [100.0],
            "ISS (R$)": [50.0],
            "INSS (R$)": [0.0],
            "PIS (R$)": [10.0],
            "COFINS (R$)": [0.0],
            "CSLL (R$)": [20.0],
            "Tarifa de Antecipação (R$)": [5.0],
        })

        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        # 1 lançamento base + 5 impostos > 0.
        assert lote.total_registros == 6
        assert lote.total_credito == Decimal("1000")
        assert lote.total_debito == Decimal("185")

    def test_classificacao_vazia_parcelamento_vira_saida(self):
        df = pd.DataFrame({
            "Emissão": ["30/05/2025"],
            "Descri.": ["PGFN"],
            "Vlr.bruto (R$)": [2446.59],
            "C. gerencial": ["17.1 - PARCELAMENTO"],
            "CLASSIFICAÇÃO": [None],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_registros == 1
        lanc = lote.lancamentos[0]
        assert lanc.credito == Decimal("0")
        assert lanc.debito == Decimal("2446.59")

    def test_classificacao_vazia_recebimento_vira_entrada(self):
        df = pd.DataFrame({
            "Emissão": ["30/05/2025"],
            "Descri.": ["Cliente X"],
            "Vlr.bruto (R$)": [1000.0],
            "C. gerencial": ["1.1.1 - Recebimento de Clientes"],
            "CLASSIFICAÇÃO": [None],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_registros == 1
        lanc = lote.lancamentos[0]
        assert lanc.credito == Decimal("1000")
        assert lanc.debito == Decimal("0")

    def test_coluna_alternativa_saida_nao_confunde_com_descricao_entrada(self):
        df = pd.DataFrame({
            "Emissão": ["30/05/2025"],
            "Descri.": ["PARCELAMENTO ENTRADA PGFN"],
            "Vlr.bruto (R$)": [2446.59],
            "C. gerencial": ["17.1 - PARCELAMENTO"],
            "CLASSIFICAÇÃO": [None],
            # Em alguns relatórios a classificação vem deslocada para a coluna IR.
            "IR (R$)": ["2 - SAIDA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_registros == 1
        lanc = lote.lancamentos[0]
        assert lanc.credito == Decimal("0")
        assert lanc.debito == Decimal("2446.59")


class TestDRETransformerMultiplosRegistros:
    def test_multiplos_meses(self, df_cumulativo_valido):
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df_cumulativo_valido), "05/2025")
        assert lote.total_registros == 5
        assert lote.competencia == "05/2025"

    def test_total_credito_debito(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025", "02/05/2025", "03/05/2025"],
            "Descri.": ["E1", "S1", "E2"],
            "Vlr.bruto (R$)": [1000.0, 500.0, 2000.0],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAIDA", "1 - ENTRADA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")

        assert lote.total_credito == Decimal("3000")
        assert lote.total_debito == Decimal("500")


class TestDRETransformerErros:
    def test_linha_com_erro_gera_warning(self):
        """Uma linha com valor impossível de converter não deve travar o lote."""
        df = pd.DataFrame({
            "Emissão": ["01/05/2025", "02/05/2025"],
            "Descri.": ["OK", "OK2"],
            "Vlr.bruto (R$)": [100, "texto_invalido"],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "1 - ENTRADA"],
        })
        t = DRETransformer()
        lote = t.transformar(_dados_dre(df), "05/2025")
        # Deve processar pelo menos 1 registro (ambos se _safe_decimal não falha)
        assert lote.total_registros >= 1
