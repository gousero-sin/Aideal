"""Testes abrangentes para DREValidator (validacao/validators.py)."""

import pandas as pd
import pytest

from app.contracts.common import ErrorSeverity
from app.validacao.validators import DREValidator


def _dados(df, arquivo="teste.xls", formato=".xls"):
    return {
        "arquivo": arquivo,
        "abas": ["Sheet1"],
        "dados": {"Sheet1": df},
        "formato": formato,
    }


# ── Formato ──────────────────────────────────────────────────────────────────


class TestValidacaoFormato:
    def test_formato_xls_aceito(self):
        df = pd.DataFrame({"Emissão": ["01/05/2025"], "Descri.": ["x"], "Vlr.bruto (R$)": [1], "CLASSIFICAÇÃO": ["1 - ENTRADA"]})
        r = DREValidator().validar(_dados(df, formato=".xls"), competencia="05/2025")
        assert all(e.campo != "formato" for e in r.erros)

    def test_formato_xlsx_aceito(self):
        df = pd.DataFrame({"Emissão": ["01/05/2025"], "Descri.": ["x"], "Vlr.bruto (R$)": [1], "CLASSIFICAÇÃO": ["1 - ENTRADA"]})
        r = DREValidator().validar(_dados(df, formato=".xlsx"), competencia="05/2025")
        assert all(e.campo != "formato" for e in r.erros)

    def test_formato_csv_rejeitado(self):
        df = pd.DataFrame({"A": [1]})
        r = DREValidator().validar(_dados(df, formato=".csv"), competencia="05/2025")
        assert any(e.campo == "formato" and e.severidade == ErrorSeverity.BLOQUEANTE for e in r.erros)


# ── Abas ─────────────────────────────────────────────────────────────────────


class TestValidacaoAbas:
    def test_sem_abas_bloqueia(self):
        dados = {"arquivo": "t.xls", "abas": [], "dados": {}, "formato": ".xls"}
        r = DREValidator().validar(dados, competencia="05/2025")
        assert any(e.campo == "abas" for e in r.erros)


# ── Template Saída ───────────────────────────────────────────────────────────


class TestDeteccaoTemplateSaida:
    def test_rejeita_template_completo(self):
        dados = {
            "arquivo": "DRE AIDEAL.xlsx",
            "abas": ["Painel", "DRE", "BD_FLUXO", "PLANO_CONTAS", "APOIO"],
            "dados": {"Painel": pd.DataFrame()},
            "formato": ".xlsx",
        }
        r = DREValidator().validar(dados, competencia="05/2025")
        assert any(e.campo == "arquivo" for e in r.erros)

    def test_aceita_arquivo_sem_assinatura_template(self):
        df = pd.DataFrame({
            "Emissão": [f"15/{m:02d}/2025" for m in range(1, 6)],
            "Descri.": ["x"] * 5,
            "Vlr.bruto (R$)": [100] * 5,
            "CLASSIFICAÇÃO": ["1 - ENTRADA"] * 5,
        })
        dados = {
            "arquivo": "relatorio.xls",
            "abas": ["Sheet1"],
            "dados": {"Sheet1": df},
            "formato": ".xls",
        }
        r = DREValidator().validar(dados, competencia="05/2025")
        assert all(e.campo != "arquivo" for e in r.erros)


# ── Colunas Obrigatórias ────────────────────────────────────────────────────


class TestColunasObrigatorias:
    def test_coluna_data_ausente(self):
        df = pd.DataFrame({
            "Descri.": ["x"],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert any(e.campo == "data" for e in r.erros)

    def test_coluna_historico_ausente(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert any(e.campo == "historico" for e in r.erros)

    def test_coluna_credito_ausente(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": ["x"],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert any(e.campo == "credito" for e in r.erros)

    def test_todas_colunas_presentes(self):
        df = pd.DataFrame({
            "Emissão": [f"15/{m:02d}/2025" for m in range(1, 6)],
            "Descri.": ["x"] * 5,
            "Vlr.bruto (R$)": [100] * 5,
            "CLASSIFICAÇÃO": ["1 - ENTRADA"] * 5,
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert all(e.campo not in ("data", "historico", "credito", "natureza") for e in r.erros)


# ── Natureza / Classificação ────────────────────────────────────────────────


class TestValidacaoNatureza:
    def test_natureza_nao_mapeada_bloqueia(self):
        df = pd.DataFrame({
            "Emissão": ["01/05/2025"],
            "Descri.": ["x"],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["99 - INEXISTENTE"],
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert any(e.campo == "natureza" and e.severidade == ErrorSeverity.BLOQUEANTE for e in r.erros)

    @pytest.mark.parametrize("natureza", [
        "1 - ENTRADA",
        "ENTRADA",
        "1-ENTRADA",
        "2 - SAIDA",
        "2 - SAÍDA",
        "SAIDA",
        "SAÍDA",
    ])
    def test_naturezas_validas(self, natureza):
        df = pd.DataFrame({
            "Emissão": [f"15/{m:02d}/2025" for m in range(1, 6)],
            "Descri.": ["x"] * 5,
            "Vlr.bruto (R$)": [100] * 5,
            "CLASSIFICAÇÃO": [natureza] * 5,
        })
        r = DREValidator().validar(_dados(df), competencia="05/2025")
        assert all(e.campo != "natureza" for e in r.erros)


# ── Período Cumulativo ───────────────────────────────────────────────────────


class TestValidacaoPeriodoCumulativo:
    def test_jan_ate_mai_valido(self, df_cumulativo_valido, dados_dre_factory):
        r = DREValidator().validar(dados_dre_factory(df_cumulativo_valido), competencia="05/2025")
        assert r.valido is True
        assert r.metadata["dre_periodo_meses_faltantes_ano_competencia"] == []

    def test_mes_faltante_bloqueia(self, dados_dre_factory):
        # Jan, Mar, Mai → faltam Fev e Abr
        df = pd.DataFrame({
            "Emissão": ["15/01/2025", "15/03/2025", "15/05/2025"],
            "Descri.": ["A", "B", "C"],
            "Vlr.bruto (R$)": [100, 200, 300],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"] * 3,
        })
        r = DREValidator().validar(dados_dre_factory(df), competencia="05/2025")
        assert r.valido is False
        assert 2 in r.metadata["dre_periodo_meses_faltantes_ano_competencia"]
        assert 4 in r.metadata["dre_periodo_meses_faltantes_ano_competencia"]

    def test_mes_acima_competencia_bloqueia(self, dados_dre_factory):
        df = pd.DataFrame({
            "Emissão": [f"15/{m:02d}/2025" for m in range(1, 8)],
            "Descri.": ["x"] * 7,
            "Vlr.bruto (R$)": [100] * 7,
            "CLASSIFICAÇÃO": ["1 - ENTRADA"] * 7,
        })
        r = DREValidator().validar(dados_dre_factory(df), competencia="05/2025")
        assert r.valido is False
        assert 6 in r.metadata["dre_periodo_meses_acima_competencia"]

    def test_ano_divergente_bloqueia(self, dados_dre_factory):
        df = pd.DataFrame({
            "Emissão": ["15/01/2025", "15/02/2024"],
            "Descri.": ["A", "B"],
            "Vlr.bruto (R$)": [100, 200],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "1 - ENTRADA"],
        })
        r = DREValidator().validar(dados_dre_factory(df), competencia="02/2025")
        assert r.valido is False
        assert any(e.campo == "competencia" for e in r.erros)

    def test_competencia_invalida_bloqueia(self, dados_dre_factory):
        df = pd.DataFrame({
            "Emissão": ["01/01/2025"],
            "Descri.": ["x"],
            "Vlr.bruto (R$)": [100],
            "CLASSIFICAÇÃO": ["1 - ENTRADA"],
        })
        r = DREValidator().validar(dados_dre_factory(df), competencia="invalido")
        assert r.valido is False

    def test_modo_nao_cumulativo_bypassa(self, dados_dre_factory, df_mes_unico_mai):
        r = DREValidator().validar(
            dados_dre_factory(df_mes_unico_mai),
            competencia="05/2025",
            modo_cumulativo=False,
        )
        assert r.metadata["dre_periodo_modo_cumulativo"] is False
        # Sem erros de período cumulativo
        assert all("cumulativo" not in e.mensagem.lower() for e in r.erros)


# ── Dados Vazios ─────────────────────────────────────────────────────────────


class TestDadosVazios:
    def test_dataframe_vazio_bloqueia(self, dados_dre_factory):
        df = pd.DataFrame()
        r = DREValidator().validar(dados_dre_factory(df), competencia="05/2025")
        assert any(e.campo == "dados" for e in r.erros)


# ── Competência Parse ────────────────────────────────────────────────────────


class TestParseCompetencia:
    @pytest.mark.parametrize("comp,expected", [
        ("05/2025", (5, 2025)),
        ("1/2025", (1, 2025)),
        ("12/2025", (12, 2025)),
        ("01-2025", (1, 2025)),
    ])
    def test_formatos_validos(self, comp, expected):
        assert DREValidator._parse_competencia(comp) == expected

    @pytest.mark.parametrize("comp", [
        "invalido",
        "13/2025",
        "00/2025",
        "",
        None,
        "2025/05",
    ])
    def test_formatos_invalidos(self, comp):
        assert DREValidator._parse_competencia(comp) is None
