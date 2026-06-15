"""Testes da API de resumo executivo do dashboard."""

import tempfile

from fastapi.testclient import TestClient

import app.main as main_module
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.processamento.dashboard import DashboardResumoService


def _novo_db() -> DatabaseConnection:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return db


def test_dashboard_resumo_vazio(monkeypatch, tmp_path):
    db = _novo_db()
    monkeypatch.setattr(
        main_module,
        "dashboard_resumo_service",
        DashboardResumoService(db=db, logs_dir=tmp_path),
    )
    client = TestClient(main_module.app)

    resp = client.get("/api/dashboard/resumo?ano=2025&mes=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["competencia"] == "05/2025"
    assert body["dre"]["total_lancamentos"] == 0
    assert body["fluxo_caixa"]["total_movimentos"] == 0
    assert body["logs_recentes"] == []


def test_dashboard_resumo_com_dre_e_fluxo(monkeypatch, tmp_path):
    db = _novo_db()
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO dre_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dre-1",
                "2026-04-01T10:00:00",
                "dre.xls",
                "hash-dre",
                2025,
                5,
                "completed",
                2,
                2,
                0,
                None,
            ),
        )
        conn.executemany(
            """
            INSERT INTO dre_lancamentos
            (upload_id, competencia_ano, competencia_mes, data_lancamento, historico,
             valor_bruto, credito, debito, natureza_raw, natureza_norm, centro_custo,
             rubrica, conta_pai, linha_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-01",
                    "Receita",
                    1000,
                    1000,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "R1",
                    "Conta 1",
                    1,
                    "h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-02",
                    "Despesa",
                    200,
                    0,
                    200,
                    "Despesa",
                    "SAIDA",
                    "Obra A",
                    "R2",
                    "Conta 2",
                    2,
                    "h2",
                    "2026-04-01T10:00:00",
                ),
            ],
        )
        conn.execute(
            """
            INSERT INTO fluxo_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             banco, status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fc-1",
                "2026-04-01T11:00:00",
                "fluxo.xlsx",
                "hash-fc",
                2025,
                5,
                "itau",
                "completed",
                2,
                2,
                0,
                None,
            ),
        )
        conn.executemany(
            """
            INSERT INTO fluxo_movimentos
            (upload_id, competencia_ano, competencia_mes, data_movimento, tipo, descricao,
             valor, saldo, classificacao, conta_gerencial, banco_origem, arquivo_origem,
             linha_origem, aba_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "fc-1",
                    2025,
                    5,
                    "2025-05-03",
                    "credito",
                    "Entrada",
                    700,
                    700,
                    "Receita",
                    "Conta",
                    "itau",
                    "fluxo.xlsx",
                    1,
                    "Sheet",
                    "fh1",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-1",
                    2025,
                    5,
                    "2025-05-04",
                    "debito",
                    "Saída",
                    150,
                    550,
                    "Despesa",
                    "Conta",
                    "itau",
                    "fluxo.xlsx",
                    2,
                    "Sheet",
                    "fh2",
                    "2026-04-01T11:00:00",
                ),
            ],
        )

    monkeypatch.setattr(
        main_module,
        "dashboard_resumo_service",
        DashboardResumoService(db=db, logs_dir=tmp_path),
    )
    client = TestClient(main_module.app)

    resp = client.get("/api/dashboard/resumo?ano=2025&mes=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["dre"]["meses_disponiveis"] == [5]
    assert body["dre"]["total_lancamentos"] == 2
    assert body["dre"]["total_credito"] == 1000.0
    assert body["dre"]["total_debito"] == 200.0
    assert body["dre"]["saldo_liquido"] == 800.0
    assert body["fluxo_caixa"]["meses_disponiveis"] == [5]
    assert body["fluxo_caixa"]["total_movimentos"] == 2
    assert body["fluxo_caixa"]["total_creditos"] == 700.0
    assert body["fluxo_caixa"]["total_debitos"] == 150.0
    assert body["fluxo_caixa"]["saldo_liquido"] == 550.0
    assert body["fluxo_caixa"]["bancos"] == ["itau"]

    default_resp = client.get("/api/dashboard/resumo")
    assert default_resp.status_code == 200
    assert default_resp.json()["competencia"] == "05/2025"


def test_dashboard_resumo_dre_usa_receita_liquida_sem_descontar_impostos_duas_vezes(
    monkeypatch,
    tmp_path,
):
    db = _novo_db()
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO dre_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dre-liquida",
                "2026-06-01T10:00:00",
                "dre_liquida.xls",
                "hash-dre-liquida",
                2026,
                6,
                "completed",
                3,
                3,
                0,
                None,
            ),
        )
        conn.executemany(
            """
            INSERT INTO dre_lancamentos
            (upload_id, competencia_ano, competencia_mes, data_lancamento, historico,
             valor_bruto, credito, debito, natureza_raw, natureza_norm, centro_custo,
             rubrica, conta_pai, linha_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "dre-liquida",
                    2026,
                    6,
                    "2026-06-10",
                    "Receita líquida",
                    2818408,
                    2818408,
                    0,
                    "(=)Receita Líquida",
                    "ENTRADA",
                    "Obra Saldo",
                    "(=)Receita Líquida",
                    "(=)Receita Líquida",
                    1,
                    "liquida-h1",
                    "2026-06-01T10:00:00",
                ),
                (
                    "dre-liquida",
                    2026,
                    6,
                    "2026-06-11",
                    "Saídas operacionais",
                    2372883,
                    0,
                    2372883,
                    "Fornecedores",
                    "SAIDA",
                    "Obra Saldo",
                    "Fornecedores",
                    "(-)Custos Variavéis",
                    2,
                    "liquida-h2",
                    "2026-06-01T10:00:00",
                ),
                (
                    "dre-liquida",
                    2026,
                    6,
                    "2026-06-12",
                    "IR retido",
                    100000,
                    0,
                    100000,
                    "IR",
                    "SAIDA",
                    "Obra Saldo",
                    "IR",
                    "IR",
                    3,
                    "liquida-h3",
                    "2026-06-01T10:00:00",
                ),
            ],
        )

    monkeypatch.setattr(
        main_module,
        "dashboard_resumo_service",
        DashboardResumoService(db=db, logs_dir=tmp_path),
    )
    client = TestClient(main_module.app)

    resp = client.get("/api/dashboard/resumo?ano=2026&mes=6")

    assert resp.status_code == 200
    body = resp.json()
    assert body["dre"]["total_credito"] == 2818408.0
    assert body["dre"]["total_debito"] == 2472883.0
    assert body["dre"]["total_impostos"] == 100000.0
    assert body["dre"]["total_saidas_liquidas"] == 2372883.0
    assert body["dre"]["saldo_liquido"] == 445525.0


def test_dashboard_resumo_rejeita_periodo_invalido(monkeypatch, tmp_path):
    db = _novo_db()
    monkeypatch.setattr(
        main_module,
        "dashboard_resumo_service",
        DashboardResumoService(db=db, logs_dir=tmp_path),
    )
    client = TestClient(main_module.app)

    resp = client.get("/api/dashboard/resumo?ano=2025&mes=13")

    assert resp.status_code == 400
    assert "Mês deve estar entre 1 e 12" in resp.json()["detail"]
