"""Testes das APIs analíticas dos painéis DRE e Fluxo de Caixa."""

import tempfile

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.processamento.paineis import PainelDREService, PainelFluxoCaixaService


def _novo_db() -> DatabaseConnection:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseConnection(tmp.name)
    MigrationManager(db).migrate()
    return db


def _client_com_db(db: DatabaseConnection) -> TestClient:
    main_module.dre_painel_service = PainelDREService(db=db)
    main_module.fluxo_painel_service = PainelFluxoCaixaService(db=db)
    return TestClient(main_module.app)


def test_painel_dre_vazio_retorna_kpis_zerados():
    db = _novo_db()
    client = _client_com_db(db)

    resp = client.get("/api/dre/painel?ano=2025")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["periodo"]["ano"] == 2025
    assert body["filtros_disponiveis"]["centro_custo"] == []
    assert "conta_pai" not in body["filtros_disponiveis"]
    assert body["kpis"]["total_lancamentos"] == 0
    assert body["kpis"]["saldo_liquido"] == 0
    assert body["kpis"]["folego_caixa_meses"] == 0
    assert body["kpis"]["margem_resultado_percentual"] == 0
    assert body["kpis"]["pressao_saida_percentual"] == 0
    assert body["series_mensais"] == []
    assert body["ranking_obras"] == []
    assert "ranking_contas" not in body


def test_painel_dre_filtra_por_obra_natureza_e_meses_sem_recorte_de_conta():
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
                5,
                5,
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
                    4,
                    "2025-04-10",
                    "Receita A",
                    900,
                    900,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "R1",
                    "Conta Receita",
                    1,
                    "dre-h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-10",
                    "Receita A",
                    1000,
                    1000,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "R1",
                    "Conta Receita",
                    2,
                    "dre-h2",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-11",
                    "Despesa B",
                    300,
                    0,
                    300,
                    "Despesa",
                    "SAIDA",
                    "Obra B",
                    "R2",
                    "Conta Despesa",
                    3,
                    "dre-h3",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-12",
                    "Despesa A",
                    250,
                    0,
                    250,
                    "Despesa",
                    "SAIDA",
                    "Obra A",
                    "R2",
                    "Conta Despesa",
                    4,
                    "dre-h4",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-1",
                    2025,
                    5,
                    "2025-05-13",
                    "Receita C",
                    200,
                    200,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "R1",
                    "Outra Conta",
                    5,
                    "dre-h5",
                    "2026-04-01T10:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get(
        "/api/dre/painel"
        "?ano=2025&meses=5&centro_custo=Obra%20A&conta_pai=Conta%20Receita"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["filtros_aplicados"]["meses"] == [5]
    assert body["filtros_aplicados"]["centro_custo"] == ["Obra A"]
    assert "conta_pai" not in body["filtros_aplicados"]
    assert body["kpis"]["total_lancamentos"] == 3
    assert body["kpis"]["total_credito"] == 1200
    assert body["kpis"]["total_debito"] == 250
    assert body["kpis"]["saldo_liquido"] == 950
    assert body["kpis"]["media_saida_mensal"] == 250
    assert body["kpis"]["saldo_medio_mensal"] == 950
    assert body["kpis"]["folego_caixa_meses"] == pytest.approx(3.8)
    assert body["kpis"]["margem_resultado_percentual"] == pytest.approx(79.1666666667)
    assert body["kpis"]["pressao_saida_percentual"] == pytest.approx(20.8333333333)
    assert body["ranking_obras"][0]["nome"] == "Obra A"
    assert body["ranking_naturezas"][0]["nome"] == "ENTRADA"
    assert "ranking_contas" not in body
    assert "conta_pai" not in body["ultimos_lancamentos"][0]


def test_painel_fluxo_vazio_retorna_kpis_zerados():
    db = _novo_db()
    client = _client_com_db(db)

    resp = client.get("/api/fluxo_caixa/painel?ano=2025")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["periodo"]["ano"] == 2025
    assert body["filtros_disponiveis"]["banco"] == []
    assert body["kpis"]["total_movimentos"] == 0
    assert body["kpis"]["saldo_liquido"] == 0
    assert body["series_mensais"] == []
    assert body["ranking_bancos"] == []


def test_painel_fluxo_filtra_por_banco_tipo_classificacao_e_meses():
    db = _novo_db()
    with db.transaction() as conn:
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
                3,
                3,
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
                    4,
                    "2025-04-02",
                    "credito",
                    "Entrada antiga",
                    400,
                    400,
                    "Receita",
                    "Receita",
                    "itau",
                    "fluxo.xlsx",
                    1,
                    "Sheet",
                    "fc-h1",
                    "2026-04-01T11:00:00",
                ),
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
                    "Receita",
                    "itau",
                    "fluxo.xlsx",
                    2,
                    "Sheet",
                    "fc-h2",
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
                    "Despesa",
                    "cef",
                    "fluxo.xlsx",
                    3,
                    "Sheet",
                    "fc-h3",
                    "2026-04-01T11:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get(
        "/api/fluxo_caixa/painel?ano=2025&meses=5&banco=itau&tipo=credito&classificacao=Receita"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["filtros_aplicados"]["meses"] == [5]
    assert body["filtros_aplicados"]["banco"] == ["itau"]
    assert body["kpis"]["total_movimentos"] == 1
    assert body["kpis"]["total_creditos"] == 700
    assert body["kpis"]["total_debitos"] == 0
    assert body["ranking_bancos"][0]["nome"] == "itau"
    assert body["ranking_classificacoes"][0]["nome"] == "Receita"


def test_paineis_rejeitam_periodo_invalido():
    db = _novo_db()
    client = _client_com_db(db)

    dre_resp = client.get("/api/dre/painel?ano=2025&meses=13")
    fluxo_resp = client.get("/api/fluxo_caixa/painel?ano=1999")

    assert dre_resp.status_code == 400
    assert "Mês deve estar entre 1 e 12" in dre_resp.json()["detail"]
    assert fluxo_resp.status_code == 400
    assert "Ano deve estar entre 2000 e 2100" in fluxo_resp.json()["detail"]
