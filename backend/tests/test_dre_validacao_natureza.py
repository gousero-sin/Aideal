import pandas as pd

from app.contracts.common import ErrorSeverity
from app.config import settings
from app.ingestao.parser import ExcelParser
from app.validacao.validators import DREValidator


def _dados_dre(df: pd.DataFrame) -> dict:
    return {
        "arquivo": "teste.xls",
        "abas": ["Sheet1"],
        "dados": {"Sheet1": df},
        "formato": ".xls",
    }


def test_validacao_bloqueia_natureza_nao_mapeada():
    df = pd.DataFrame(
        {
            "Emissão": ["01/05/2025"],
            "Descri.": ["Lançamento teste"],
            "Vlr.bruto (R$)": [100.0],
            "CLASSIFICAÇÃO": ["9 - NAO MAPEADA"],
        }
    )

    validator = DREValidator()
    result = validator.validar(_dados_dre(df), competencia="05/2025")

    assert result.valido is False
    assert any(
        e.campo == "natureza" and e.severidade == ErrorSeverity.BLOQUEANTE
        for e in result.erros
    )


def test_validacao_aceita_natureza_mapeada():
    df = pd.DataFrame(
        {
            "Emissão": ["01/05/2025", "02/05/2025"],
            "Descri.": ["Entrada", "Saída"],
            "Vlr.bruto (R$)": [100.0, 50.0],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAÍDA"],
        }
    )

    validator = DREValidator()
    result = validator.validar(_dados_dre(df), competencia="05/2025")

    assert result.valido is False
    assert any(e.campo == "competencia" for e in result.erros)
    assert all(e.campo != "natureza" for e in result.erros)


def test_validacao_rejeita_template_de_saida():
    parser = ExcelParser("dre")
    arquivo_template = settings.base_dir / "templates" / "dre" / "DRE AIDEAL - 05 2025  - obra.xlsx"
    dados = parser.ler_arquivo(arquivo_template)

    validator = DREValidator()
    result = validator.validar(dados, competencia="05/2025")

    assert result.valido is False
    assert any(e.campo == "arquivo" for e in result.erros)


def test_validacao_cumulativa_aceita_janeiro_ate_competencia():
    df = pd.DataFrame(
        {
            "Emissão": [
                "01/01/2025",
                "01/02/2025",
                "01/03/2025",
                "01/04/2025",
                "01/05/2025",
            ],
            "Descri.": ["M1", "M2", "M3", "M4", "M5"],
            "Vlr.bruto (R$)": [100, 110, 120, 130, 140],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAÍDA", "1 - ENTRADA", "2 - SAIDA", "1 - ENTRADA"],
        }
    )

    validator = DREValidator()
    result = validator.validar(_dados_dre(df), competencia="05/2025")

    assert result.valido is True
    assert result.metadata["dre_periodo_meses_encontrados_ano_competencia"] == [1, 2, 3, 4, 5]
    assert result.metadata["dre_periodo_meses_faltantes_ano_competencia"] == []
