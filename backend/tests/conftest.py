"""Fixtures compartilhadas para toda a suíte de testes AIDEAL."""

import os
import shutil
import tempfile
from pathlib import Path

# Sem a manutenção periódica dos painéis: cada TestClient com lifespan criaria
# uma thread recalculando painéis em paralelo com a suíte.
os.environ["AIDEAL_PAINEL_REFRESH_SEGUNDOS"] = "0"

# O banco operacional precisa ser isolado ANTES de importar o app: os serviços
# de app.main são singletons criados no import e guardam settings.db_path.
# Sem isso, testes de API gravam em data/aideal.db e apagam lançamentos reais.
os.environ["AIDEAL_DB_PATH"] = str(
    Path(tempfile.mkdtemp(prefix="aideal-tests-")) / "aideal.db"
)

import pandas as pd
import pytest
from openpyxl import Workbook

from app.access_control import configure_identity_service, configure_orcamento_service
from app.config import settings
from app.db.connection import DatabaseConnection
from app.db.manager import run_migrations
from app.ingestao.parser import ExcelParser
from app.processamento.dre import DREProcessamentoService

# Trava contra regressão do isolamento e schema pronto para os singletons do app
# (o TestClient sem `with` não executa o startup que aplica as migrações).
assert settings.db_path == Path(os.environ["AIDEAL_DB_PATH"]), settings.db_path
run_migrations(DatabaseConnection(settings.db_path))

# ── Helpers ──────────────────────────────────────────────────────────────────

ADMIN_TEST_USERNAME = "Eduardo"
ADMIN_TEST_PASSWORD = "senha-admin-teste"


def login_admin(client) -> None:
    """Autentica o TestClient em endpoints operacionais protegidos."""
    resp = client.post(
        "/api/admin/login",
        json={"username": ADMIN_TEST_USERNAME, "password": ADMIN_TEST_PASSWORD},
    )
    assert resp.status_code == 200
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    client.headers.update({"X-CSRF-Token": session.json()["csrf_token"]})


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


@pytest.fixture(autouse=True)
def _admin_auth_settings(monkeypatch, tmp_path):
    """Configura auth admin para a suíte; cada teste decide se faz login."""
    configure_identity_service(None)
    configure_orcamento_service(None)
    monkeypatch.setattr(settings, "admin_username", ADMIN_TEST_USERNAME)
    monkeypatch.setattr(settings, "admin_password", ADMIN_TEST_PASSWORD)
    monkeypatch.setattr(settings, "admin_password_hash", "")
    monkeypatch.setattr(settings, "admin_session_secret", "segredo-testes")
    monkeypatch.setattr(settings, "admin_session_max_age_seconds", 3600)
    monkeypatch.setattr(settings, "admin_cookie_secure", False)
    monkeypatch.setattr(settings, "identity_db_path", tmp_path / "identity.db")
    monkeypatch.setattr(settings, "orcamento_db_path", tmp_path / "orcamento.db")
    monkeypatch.setattr(settings, "db_path", tmp_path / "aideal.db")
    yield
    configure_identity_service(None)
    configure_orcamento_service(None)


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
        ws.append(
            [
                f"01/{mes:02d}/2025",
                f"Lancamento {mes}",
                float(100 * mes),
                "1 - ENTRADA" if mes % 2 else "2 - SAIDA",
                "VLI PINTURA",
            ]
        )
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
        ws.append(
            [
                f"{dia:02d}/05/2025",
                f"Lancamento dia {dia}",
                float(1000 * dia),
                "1 - ENTRADA",
            ]
        )
    wb.save(path)
    return path


@pytest.fixture
def df_cumulativo_valido():
    """DataFrame com 5 meses cumulativos válidos."""
    return pd.DataFrame(
        {
            "Emissão": [f"15/{m:02d}/2025" for m in range(1, 6)],
            "Descri.": [f"Lancamento M{m}" for m in range(1, 6)],
            "Vlr.bruto (R$)": [100.0 * m for m in range(1, 6)],
            "CLASSIFICAÇÃO": [
                "1 - ENTRADA",
                "2 - SAÍDA",
                "1 - ENTRADA",
                "2 - SAIDA",
                "1 - ENTRADA",
            ],
        }
    )


@pytest.fixture
def df_mes_unico_mai():
    """DataFrame só com dados de maio."""
    return pd.DataFrame(
        {
            "Emissão": ["01/05/2025", "15/05/2025", "31/05/2025"],
            "Descri.": ["A", "B", "C"],
            "Vlr.bruto (R$)": [100.0, 200.0, 300.0],
            "CLASSIFICAÇÃO": ["1 - ENTRADA", "2 - SAÍDA", "1 - ENTRADA"],
        }
    )
