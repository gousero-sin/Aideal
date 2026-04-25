"""Fixtures compartilhadas para toda a suíte de testes AIDEAL."""

import shutil
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from app.config import settings
from app.ingestao.parser import ExcelParser
from app.processamento.dre import DREProcessamentoService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _dados_dre_sintetico(
    df: pd.DataFrame,
    arquivo: str = "teste.xls",
    abas: list[str] | None = None,
    aba_dados: str = "Sheet1",
    formato: str = ".xls",
) -> dict:
    """Monta o dict padrão retornado por ExcelParser.ler_arquivo()."""
    return {
        "arquivo": arquivo,
        "abas": abas or [aba_dados],
        "dados": {aba_dados: df},
        "formato": formato,
    }


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def dados_dre_factory():
    """Factory para criar dict de dados DRE a partir de um DataFrame."""
    return _dados_dre_sintetico


@pytest.fixture
def parser_dre():
    return ExcelParser("dre")


@pytest.fixture
def dre_service(tmp_path):
    """DREProcessamentoService com diretórios temporários isolados."""
    return DREProcessamentoService(
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        temp_dir=tmp_path / "tmp",
    )


@pytest.fixture
def template_copy(tmp_path):
    """Cópia do template oficial em diretório temporário."""
    dest = tmp_path / "template_copy.xlsx"
    shutil.copyfile(settings.template_dre_path, dest)
    return dest


@pytest.fixture
def arquivo_dre_cumulativo(tmp_path) -> Path:
    """Arquivo .xlsx sintético com meses 01..05/2025 (modo cumulativo)."""
    path = tmp_path / "DRE_CUMULATIVO_01_A_05_2025.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "RELATORIO"
    ws.append(["metadata"])
    ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO", "Obra/Centro custo"])
    for mes in range(1, 6):
        ws.append([
            f"01/{mes:02d}/2025",
            f"Lancamento {mes}",
            float(100 * mes),
            "1 - ENTRADA" if mes % 2 else "2 - SAIDA",
            "VLI PINTURA",
        ])
    wb.save(path)
    return path


@pytest.fixture
def arquivo_dre_mes_unico(tmp_path) -> Path:
    """Arquivo .xlsx sintético com dados apenas do mês 05."""
    path = tmp_path / "DRE_MES_05_2025.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet"
    ws.append(["metadata"])
    ws.append(["Emissão", "Descri.", "Vlr.bruto (R$)", "CLASSIFICAÇÃO"])
    for dia in range(1, 4):
        ws.append([
            f"{dia:02d}/05/2025",
            f"Lancamento dia {dia}",
            float(1000 * dia),
            "1 - ENTRADA",
        ])
    wb.save(path)
    return path


@pytest.fixture
def df_cumulativo_valido():
    """DataFrame com 5 meses cumulativos válidos."""
    return pd.DataFrame({
        "Emissão": [f"15/{m:02d}/2025" for m in range(1, 6)],
        "Descri.": [f"Lancamento M{m}" for m in range(1, 6)],
        "Vlr.bruto (R$)": [100.0 * m for m in range(1, 6)],
        "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAÍDA", "1 - ENTRADA", "2 - SAIDA", "1 - ENTRADA"],
    })


@pytest.fixture
def df_mes_unico_mai():
    """DataFrame só com dados de maio."""
    return pd.DataFrame({
        "Emissão": ["01/05/2025", "15/05/2025", "31/05/2025"],
        "Descri.": ["A", "B", "C"],
        "Vlr.bruto (R$)": [100.0, 200.0, 300.0],
        "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAÍDA", "1 - ENTRADA"],
    })
