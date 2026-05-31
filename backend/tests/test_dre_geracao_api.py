"""Testes de API para geração DRE a partir do banco."""

from conftest import login_admin
from fastapi.testclient import TestClient

import app.main as main_module


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
