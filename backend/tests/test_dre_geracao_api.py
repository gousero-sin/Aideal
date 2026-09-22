"""Testes de API para geração DRE a partir do banco."""

from pathlib import Path

from conftest import login_admin
from fastapi.testclient import TestClient

import app.main as main_module
from app.access_control import configure_identity_service
from app.identity import create_identity_service

SENHA_ADMIN = "senha-admin-teste"
SENHA_ANALISTA = "senha-analista-123"
SENHA_SEM_DRE = "senha-sem-dre-123"


class _FakeGeracaoCompletaService:
    def __init__(self):
        self.verificar_args = None
        self.gerar_args = None

    def verificar_dados(self, competencia, centro_custo=None, meses_incluir=None, ano_todo=False):
        self.verificar_args = {
            "competencia": competencia,
            "centro_custo": centro_custo,
            "meses_incluir": meses_incluir,
            "ano_todo": ano_todo,
        }
        return {
            "valido": True,
            "competencia": competencia,
            "meses_utilizados": meses_incluir or [1, 2, 3],
        }

    def gerar_arquivo(self, competencia, centro_custo=None, meses_incluir=None, ano_todo=False):
        self.gerar_args = {
            "competencia": competencia,
            "centro_custo": centro_custo,
            "meses_incluir": meses_incluir,
            "ano_todo": ano_todo,
        }
        return {
            "arquivo_saida": "DRE_AIDEAL_06-2025_teste.xlsx",
            "total_lancamentos": 12,
            "total_credito": 1000.0,
            "total_debito": 500.0,
            "saldo_liquido": 500.0,
            "fonte_dados": "db",
            "estrategia_meses": "meses_incluir" if meses_incluir else "competencia",
            "ano_todo": ano_todo,
            "meses_incluir": meses_incluir or [],
            "meses_disponiveis": [1, 2, 3, 4, 5, 6],
            "meses_utilizados": meses_incluir or [1, 2, 3, 4, 5, 6],
            "meses_solicitados": meses_incluir or [1, 2, 3, 4, 5, 6],
            "meses_ocultos": [7, 8, 9, 10, 11, 12],
            "colunas_dre_visiveis": ["B", "C", "D", "E", "N", "O", "AH", "AI"],
        }


def test_api_dre_gerar_recebe_flags_de_meses(monkeypatch):
    fake_service = _FakeGeracaoCompletaService()
    monkeypatch.setattr(main_module, "dre_geracao_completa_service", fake_service)
    client = TestClient(main_module.app)
    login_admin(client)

    resp = client.post(
        "/api/dre/gerar",
        data={
            "competencia": "06/2025",
            "meses_incluir": ["1", "2", "6"],
            "ano_todo": "false",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["registros_reais"] == 12
    assert body["estrategia_meses"] == "meses_incluir"
    assert body["meses_incluir"] == [1, 2, 6]
    assert body["meses_utilizados"] == [1, 2, 6]
    assert fake_service.verificar_args["meses_incluir"] == [1, 2, 6]
    assert fake_service.verificar_args["ano_todo"] is False
    assert fake_service.gerar_args["meses_incluir"] == [1, 2, 6]
    assert fake_service.gerar_args["ano_todo"] is False


def test_api_dre_gerar_modo_teste_nao_gera_arquivo(monkeypatch):
    fake_service = _FakeGeracaoCompletaService()
    monkeypatch.setattr(main_module, "dre_geracao_completa_service", fake_service)
    client = TestClient(main_module.app)
    login_admin(client)

    resp = client.post(
        "/api/dre/gerar",
        data={
            "competencia": "06/2025",
            "modo_teste": "true",
            "ano_todo": "true",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["modo_teste"] is True
    assert fake_service.verificar_args["ano_todo"] is True
    assert fake_service.gerar_args is None


def test_api_dre_exportar_baixa_arquivo_filtrado_por_uma_obra(monkeypatch, tmp_path):
    fake_service = _FakeGeracaoCompletaService()
    arquivo = tmp_path / "DRE_AIDEAL_06-2025_teste.xlsx"
    arquivo.write_bytes(b"xlsx filtrado")
    monkeypatch.setattr(main_module, "dre_geracao_completa_service", fake_service)
    monkeypatch.setattr(main_module.settings, "output_dir", Path(tmp_path))
    identity = create_identity_service(tmp_path / "identity-export.db")
    owner = identity.bootstrap_eduardo(password=SENHA_ADMIN)
    identity.create_user(
        username="analista-dre",
        display_name="Analista DRE",
        password=SENHA_ANALISTA,
        permissions=("dre.view",),
        must_change_password=False,
        actor_user_id=owner.id,
    )
    identity.create_user(
        username="sem-dre",
        display_name="Sem DRE",
        password=SENHA_SEM_DRE,
        permissions=(),
        must_change_password=False,
        actor_user_id=owner.id,
    )
    configure_identity_service(identity)
    client = TestClient(main_module.app)
    assert client.post(
        "/api/dre/exportar",
        data={"competencia": "06/2025", "centro_custo": "Obra Alpha"},
    ).status_code == 401
    session = client.post(
        "/api/auth/login",
        json={"username": "analista-dre", "password": "senha-analista-123"},
    )
    assert session.status_code == 200
    assert "admin_banco.use" not in session.json()["permissions"]
    assert client.post(
        "/api/dre/exportar",
        data={"competencia": "06/2025", "centro_custo": "Obra Alpha"},
    ).status_code == 403
    assert client.post(
        "/api/dre/exportar",
        data={"competencia": "06/2025", "centro_custo": "Obra Alpha"},
        headers={"X-CSRF-Token": "invalido"},
    ).status_code == 403
    client.headers.update({"X-CSRF-Token": session.json()["csrf_token"]})

    sem_dre = TestClient(main_module.app)
    sem_dre_session = sem_dre.post(
        "/api/auth/login",
        json={"username": "sem-dre", "password": "senha-sem-dre-123"},
    ).json()
    assert sem_dre.post(
        "/api/dre/exportar",
        data={"competencia": "06/2025", "centro_custo": "Obra Alpha"},
        headers={"X-CSRF-Token": sem_dre_session["csrf_token"]},
    ).status_code == 403

    resp = client.post(
        "/api/dre/exportar",
        data={
            "competencia": "06/2025",
            "centro_custo": "Obra Alpha",
            "meses_incluir": ["2", "6"],
        },
    )

    assert resp.status_code == 200
    assert resp.content == b"xlsx filtrado"
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "DRE_AIDEAL_06-2025_teste.xlsx" in resp.headers["content-disposition"]
    assert fake_service.verificar_args == {
        "competencia": "06/2025",
        "centro_custo": "Obra Alpha",
        "meses_incluir": [2, 6],
        "ano_todo": False,
    }
    assert fake_service.gerar_args == fake_service.verificar_args
    assert not arquivo.exists()
