"""Testes das APIs analíticas dos painéis DRE e Fluxo de Caixa."""

import tempfile

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.ingestao.fluxo_caixa_ingestao import FluxoCaixaIngestaoService
from app.processamento.dre_geracao import DREGeracaoService
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


def _patch_admin_services(db: DatabaseConnection) -> None:
    main_module.dre_geracao_service = DREGeracaoService(db=db)
    main_module.fluxo_ingestao_service = FluxoCaixaIngestaoService(db=db)


def _configurar_admin(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "admin_username", "Eduardo", raising=False)
    monkeypatch.setattr(main_module.settings, "admin_password", "senha-admin-teste", raising=False)
    monkeypatch.setattr(main_module.settings, "admin_password_hash", "", raising=False)
    monkeypatch.setattr(
        main_module.settings,
        "admin_session_secret",
        "segredo-testes",
        raising=False,
    )
    monkeypatch.setattr(main_module.settings, "admin_session_max_age_seconds", 3600, raising=False)
    monkeypatch.setattr(main_module.settings, "admin_cookie_secure", False, raising=False)


def _login_admin(client: TestClient) -> None:
    resp = client.post(
        "/api/admin/login",
        json={"username": "Eduardo", "password": "senha-admin-teste"},
    )
    assert resp.status_code == 200


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


def test_painel_dre_obra_usa_ciclo_completo_do_projeto_e_indicadores():
    db = _novo_db()
    with db.transaction() as conn:
        conn.executemany(
            """
            INSERT INTO dre_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "dre-alpha-2025-11",
                    "2026-04-01T10:00:00",
                    "dre_11_2025.xls",
                    "hash-dre-alpha-2025-11",
                    2025,
                    11,
                    "completed",
                    3,
                    3,
                    0,
                    None,
                ),
                (
                    "dre-alpha-2026-05",
                    "2026-04-01T10:00:00",
                    "dre_05_2026.xls",
                    "hash-dre-alpha-2026-05",
                    2026,
                    5,
                    "completed",
                    6,
                    6,
                    0,
                    None,
                ),
            ],
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
                    "dre-alpha-2025-11",
                    2025,
                    11,
                    "2025-11-10",
                    "Receita Alpha",
                    1000,
                    1000,
                    0,
                    "Faturamento",
                    "ENTRADA",
                    "Obra Alpha",
                    "Faturamento",
                    "(=)Receita Bruta",
                    1,
                    "alpha-h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2025-11",
                    2025,
                    11,
                    "2025-11-11",
                    "Fornecedores Alpha",
                    400,
                    0,
                    400,
                    "Fornecedores",
                    "SAIDA",
                    "Obra Alpha",
                    "Fornecedores",
                    "(-)Custos Variavéis",
                    2,
                    "alpha-h2",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2025-11",
                    2025,
                    11,
                    "2025-11-12",
                    "Fixos Alpha",
                    100,
                    0,
                    100,
                    "Despesas com Pessoal",
                    "SAIDA",
                    "Obra Alpha",
                    "Despesas com Pessoal",
                    "(-)Gastos Fixos",
                    3,
                    "alpha-h3",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-10",
                    "Receita Alpha 2",
                    2000,
                    2000,
                    0,
                    "Faturamento",
                    "ENTRADA",
                    "Obra Alpha",
                    "Faturamento",
                    "(=)Receita Bruta",
                    4,
                    "alpha-h4",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-11",
                    "Impostos Alpha",
                    200,
                    0,
                    200,
                    "Impostos sobre vendas",
                    "SAIDA",
                    "Obra Alpha",
                    "Impostos sobre vendas",
                    "(-)Deduções sobre vendas",
                    5,
                    "alpha-h5",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-12",
                    "Fornecedores Alpha 2",
                    600,
                    0,
                    600,
                    "Fornecedores",
                    "SAIDA",
                    "Obra Alpha",
                    "Fornecedores",
                    "(-)Custos Variavéis",
                    6,
                    "alpha-h6",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-13",
                    "Fixos Alpha 2",
                    300,
                    0,
                    300,
                    "Despesas com Pessoal",
                    "SAIDA",
                    "Obra Alpha",
                    "Despesas com Pessoal",
                    "(-)Gastos Fixos",
                    7,
                    "alpha-h7",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-14",
                    "Depreciacao Alpha",
                    50,
                    0,
                    50,
                    "Depreciação Imobilizado",
                    "SAIDA",
                    "Obra Alpha",
                    "Depreciação Imobilizado",
                    "(-)Depreciação Imobilizado",
                    8,
                    "alpha-h8",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-15",
                    "Investimento Alpha",
                    200,
                    0,
                    200,
                    "Investimentos",
                    "SAIDA",
                    "Obra Alpha",
                    "Investimentos",
                    "(-)Investimentos",
                    9,
                    "alpha-h9",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alpha-2026-05",
                    2026,
                    5,
                    "2026-05-16",
                    "Receita Beta",
                    9999,
                    9999,
                    0,
                    "Faturamento",
                    "ENTRADA",
                    "Obra Beta",
                    "Faturamento",
                    "(=)Receita Bruta",
                    10,
                    "beta-h1",
                    "2026-04-01T10:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get(
        "/api/dre/painel"
        "?ano=2026&meses=5&centro_custo=Obra%20Alpha&escopo_periodo=projeto_completo"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["filtros_aplicados"]["escopo_periodo"] == "projeto_completo"
    assert body["periodo"]["label"] == "Nov/25-Mai/26"
    assert body["series_mensais"] == [
        {
            "ano": 2025,
            "mes": 11,
            "periodo": "2025-11",
            "mes_label": "Nov/25",
            "credito": 1000.0,
            "debito": 500.0,
            "saldo": 500.0,
            "lancamentos": 3,
        },
        {
            "ano": 2026,
            "mes": 5,
            "periodo": "2026-05",
            "mes_label": "Mai/26",
            "credito": 2000.0,
            "debito": 1350.0,
            "saldo": 650.0,
            "lancamentos": 6,
        },
    ]
    assert body["saldos_projeto"]["primeira_competencia"] == "11/2025"
    assert body["saldos_projeto"]["ultima_competencia"] == "05/2026"
    assert body["saldos_projeto"]["saldo"] == 1150.0

    indicadores = {item["id"]: item for item in body["indicadores_viabilidade"]}
    assert set(indicadores) == {"mcl", "pel", "ebitda", "fcl", "roi", "ncg"}
    assert indicadores["mcl"]["valor"] == pytest.approx(1800.0)
    assert indicadores["mcl"]["percentual"] == pytest.approx(64.2857142857)
    assert indicadores["mcl"]["ideal"] is None
    assert "meta" not in indicadores["mcl"]
    assert "meta_status" not in indicadores["mcl"]
    assert indicadores["pel"]["valor"] == pytest.approx(622.2222222222)
    assert indicadores["pel"]["ideal"] is None
    assert indicadores["ebitda"]["valor"] == pytest.approx(1400.0)
    assert indicadores["ebitda"]["percentual"] == pytest.approx(50.0)
    assert indicadores["ebitda"]["ideal"] is None
    assert indicadores["fcl"]["ideal"] is None
    assert indicadores["roi"]["ideal"] is None
    assert indicadores["ncg"]["status"] == "indisponivel"
    assert indicadores["ncg"]["ideal"] is None
    assert set(indicadores["ncg"]["componentes_faltantes"]) == {
        "Contas a Receber",
        "Contas a Pagar",
    }


def test_painel_dre_indicadores_usam_contas_filhas_do_template_e_gasto_total_para_roi():
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
                "dre-leaf",
                "2026-04-01T10:00:00",
                "dre_leaf.xls",
                "hash-dre-leaf",
                2025,
                5,
                "completed",
                4,
                4,
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
                    "dre-leaf",
                    2025,
                    5,
                    "2025-05-10",
                    "Receita",
                    1000,
                    1000,
                    0,
                    "Faturamento",
                    "ENTRADA",
                    "Obra Leaf",
                    "Faturamento",
                    "1.1.1 - Recebimento de Clientes",
                    1,
                    "leaf-h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-leaf",
                    2025,
                    5,
                    "2025-05-11",
                    "Imposto",
                    100,
                    0,
                    100,
                    "IR",
                    "SAIDA",
                    "Obra Leaf",
                    "IR",
                    "IR",
                    2,
                    "leaf-h2",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-leaf",
                    2025,
                    5,
                    "2025-05-12",
                    "Tinta",
                    300,
                    0,
                    300,
                    "4.1 - TINTAS E SOLVENTES",
                    "SAIDA",
                    "Obra Leaf",
                    "4.1 - TINTAS E SOLVENTES",
                    "4.1 - TINTAS E SOLVENTES",
                    3,
                    "leaf-h3",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-leaf",
                    2025,
                    5,
                    "2025-05-13",
                    "Salario",
                    200,
                    0,
                    200,
                    "12.1 - SALARIO",
                    "SAIDA",
                    "Obra Leaf",
                    "12.1 - SALARIO",
                    "12.1 - SALARIO",
                    4,
                    "leaf-h4",
                    "2026-04-01T10:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get(
        "/api/dre/painel"
        "?ano=2025&centro_custo=Obra%20Leaf&escopo_periodo=projeto_completo"
    )

    assert resp.status_code == 200
    indicadores = {item["id"]: item for item in resp.json()["indicadores_viabilidade"]}
    assert indicadores["mcl"]["valor"] == pytest.approx(600.0)
    assert indicadores["pel"]["status"] == "calculado"
    assert indicadores["pel"]["valor"] == pytest.approx(300.0)
    assert indicadores["ebitda"]["percentual"] == pytest.approx(400 / 900 * 100)
    assert indicadores["roi"]["status"] == "indisponivel"
    assert indicadores["roi"]["componentes_faltantes"] == ["Investimento Total"]

    objetivos = {item["id"]: item for item in resp.json()["objetivos_estrategicos"]}
    assert objetivos["ifsrl"]["valor"] == pytest.approx(200 / 900 * 100)
    assert objetivos["ifsrl"]["meta_status"] == "ok"
    assert objetivos["iefp"]["valor"] == pytest.approx(900 / 200)
    assert objetivos["iefp"]["meta_status"] == "ok"
    assert objetivos["iirrl"]["status"] == "indisponivel"
    assert objetivos["itmir"]["componentes_faltantes"] == ["Total de Imposto Retido"]


def test_painel_dre_indicadores_viabilidade_nao_expoem_metas():
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
                "dre-alerta",
                "2026-04-01T10:00:00",
                "dre_alerta.xls",
                "hash-dre-alerta",
                2025,
                5,
                "completed",
                9,
                9,
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
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-10",
                    "Receita líquida",
                    1000,
                    1000,
                    0,
                    "(=)Receita Líquida",
                    "ENTRADA",
                    "Obra Alerta",
                    "(=)Receita Líquida",
                    "(=)Receita Líquida",
                    1,
                    "alerta-h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-11",
                    "Margem baixa",
                    200,
                    200,
                    0,
                    "(=)MARGEM DE CONTRIBUIÇÃO",
                    "ENTRADA",
                    "Obra Alerta",
                    "(=)MARGEM DE CONTRIBUIÇÃO",
                    "(=)MARGEM DE CONTRIBUIÇÃO",
                    2,
                    "alerta-h2",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-12",
                    "Fixos altos",
                    500,
                    0,
                    500,
                    "Despesas com Pessoal",
                    "SAIDA",
                    "Obra Alerta",
                    "Despesas com Pessoal",
                    "Despesas com Pessoal",
                    3,
                    "alerta-h3",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-13",
                    "Resultado operacional",
                    100,
                    100,
                    0,
                    "(=)RESULTADO OPERACIONAL",
                    "ENTRADA",
                    "Obra Alerta",
                    "(=)RESULTADO OPERACIONAL",
                    "(=)RESULTADO OPERACIONAL",
                    4,
                    "alerta-h4",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-14",
                    "Resultado gerencial",
                    100,
                    100,
                    0,
                    "(=)RESULTADO GERENCIAL",
                    "ENTRADA",
                    "Obra Alerta",
                    "(=)RESULTADO GERENCIAL",
                    "(=)RESULTADO GERENCIAL",
                    5,
                    "alerta-h5",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-15",
                    "Resultado líquido negativo",
                    50,
                    0,
                    50,
                    "RESULTADO LÍQUIDO",
                    "SAIDA",
                    "Obra Alerta",
                    "RESULTADO LÍQUIDO",
                    "RESULTADO LÍQUIDO",
                    6,
                    "alerta-h6",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-16",
                    "Investimento",
                    1000,
                    0,
                    1000,
                    "Aquisição de Maquinas e Equipamentos",
                    "SAIDA",
                    "Obra Alerta",
                    "Aquisição de Maquinas e Equipamentos",
                    "Aquisição de Maquinas e Equipamentos",
                    7,
                    "alerta-h7",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-17",
                    "Contas a receber",
                    300,
                    300,
                    0,
                    "Contas a Receber",
                    "ENTRADA",
                    "Obra Alerta",
                    "Contas a Receber",
                    "Contas a Receber",
                    8,
                    "alerta-h8",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-alerta",
                    2025,
                    5,
                    "2025-05-18",
                    "Contas a pagar",
                    100,
                    0,
                    100,
                    "Contas a Pagar",
                    "SAIDA",
                    "Obra Alerta",
                    "Contas a Pagar",
                    "Contas a Pagar",
                    9,
                    "alerta-h9",
                    "2026-04-01T10:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get("/api/dre/painel?ano=2025&meses=5&centro_custo=Obra%20Alerta")

    assert resp.status_code == 200
    indicadores = {item["id"]: item for item in resp.json()["indicadores_viabilidade"]}
    assert indicadores["mcl"]["percentual"] == pytest.approx(20.0)
    assert indicadores["pel"]["valor"] == pytest.approx(2500.0)
    assert indicadores["roi"]["valor"] == pytest.approx(-5.0)
    assert indicadores["ncg"]["valor"] == pytest.approx(200.0)
    assert all("meta" not in indicador for indicador in indicadores.values())
    assert all("meta_status" not in indicador for indicador in indicadores.values())


def test_painel_dre_objetivos_estrategicos_calculam_metas_com_imposto_retido():
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
                "dre-kpi",
                "2026-04-01T10:00:00",
                "dre_kpi.xls",
                "hash-dre-kpi",
                2025,
                5,
                "completed",
                4,
                4,
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
                    "dre-kpi",
                    2025,
                    5,
                    "2025-05-10",
                    "Receita Liquida",
                    1000,
                    1000,
                    0,
                    "(=)Receita Líquida",
                    "ENTRADA",
                    "Obra KPI",
                    "(=)Receita Líquida",
                    "(=)Receita Líquida",
                    1,
                    "kpi-h1",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-kpi",
                    2025,
                    5,
                    "2025-05-11",
                    "Salario",
                    200,
                    0,
                    200,
                    "12.1 - SALARIO",
                    "SAIDA",
                    "Obra KPI",
                    "12.1 - SALARIO",
                    "12.1 - SALARIO",
                    2,
                    "kpi-h2",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-kpi",
                    2025,
                    5,
                    "2025-05-12",
                    "FGTS",
                    40,
                    0,
                    40,
                    "12.14 - FGTS FUNCIONARIOS",
                    "SAIDA",
                    "Obra KPI",
                    "12.14 - FGTS FUNCIONARIOS",
                    "12.14 - FGTS FUNCIONARIOS",
                    3,
                    "kpi-h3",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-kpi",
                    2025,
                    5,
                    "2025-05-13",
                    "Imposto retido",
                    80,
                    0,
                    80,
                    "TOTAL DE IMPOSTO RETIDO",
                    "SAIDA",
                    "Obra KPI",
                    "TOTAL DE IMPOSTO RETIDO",
                    "TOTAL DE IMPOSTO RETIDO",
                    4,
                    "kpi-h4",
                    "2026-04-01T10:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get("/api/dre/painel?ano=2025&meses=5&centro_custo=Obra%20KPI")

    assert resp.status_code == 200
    objetivos = {item["id"]: item for item in resp.json()["objetivos_estrategicos"]}
    assert set(objetivos) == {"ifsrl", "iefp", "iirrl", "itmir"}
    assert objetivos["ifsrl"]["valor"] == pytest.approx(24.0)
    assert objetivos["ifsrl"]["unidade"] == "%"
    assert objetivos["ifsrl"]["meta"] == "≤ 30%"
    assert objetivos["ifsrl"]["meta_status"] == "ok"
    assert objetivos["iefp"]["valor"] == pytest.approx(1000 / 240)
    assert objetivos["iefp"]["meta"] == "> 2,5"
    assert objetivos["iefp"]["meta_status"] == "ok"
    assert objetivos["iirrl"]["valor"] == pytest.approx(8.0)
    assert objetivos["iirrl"]["meta"] == "≤ 10%"
    assert objetivos["iirrl"]["meta_status"] == "ok"
    assert objetivos["itmir"]["valor"] == pytest.approx(80.0)
    assert objetivos["itmir"]["unidade"] == "R$"
    assert objetivos["itmir"]["meta"] == "< 7 MM"
    assert objetivos["itmir"]["meta_status"] == "ok"


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


def test_painel_fluxo_retorna_cinco_contas_em_destaque_com_aliases():
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
                "fc-destaques",
                "2026-04-01T11:00:00",
                "fluxo.xlsx",
                "hash-fc-destaques",
                2025,
                5,
                "itau",
                "completed",
                10,
                10,
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
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-02",
                    "debito",
                    "Parcelamento",
                    70,
                    None,
                    "17.1 - Parcelamento (100,00%);",
                    "17.1 - Parcelamento (100,00%);",
                    "itau",
                    "fluxo.xlsx",
                    1,
                    "Sheet",
                    "destaque-h1",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-03",
                    "debito",
                    "Folha",
                    120,
                    None,
                    "12.1 - SALÁRIO",
                    "12.1 - SALÁRIO",
                    "itau",
                    "fluxo.xlsx",
                    2,
                    "Sheet",
                    "destaque-h2",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-04",
                    "debito",
                    "FGTS",
                    30,
                    None,
                    "12.14 - FGTS funcionários",
                    "12.14 - FGTS funcionários",
                    "itau",
                    "fluxo.xlsx",
                    3,
                    "Sheet",
                    "destaque-h3",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-05",
                    "debito",
                    "Locação",
                    50,
                    None,
                    "7.1 LOCAÇÃO MUNCK / GUINDASTES",
                    "7.1 LOCAÇÃO MUNCK / GUINDASTES",
                    "itau",
                    "fluxo.xlsx",
                    4,
                    "Sheet",
                    "destaque-h4",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-06",
                    "debito",
                    "Fornecedor",
                    80,
                    None,
                    "4.1 - Tintas e solventes",
                    "4.1 - Tintas e solventes",
                    "itau",
                    "fluxo.xlsx",
                    5,
                    "Sheet",
                    "destaque-h5",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-07",
                    "debito",
                    "Manutenção",
                    40,
                    None,
                    "6.3 - MANUTENÇÃO/PEÇAS  VEICULOS",
                    "6.3 - MANUTENÇÃO/PEÇAS  VEICULOS",
                    "itau",
                    "fluxo.xlsx",
                    6,
                    "Sheet",
                    "destaque-h6",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-08",
                    "debito",
                    "Rateio locação e folha",
                    100,
                    None,
                    "LOCAÇÃO COMPRESSORES (40,00%);\n\nSALARIO (60,00%);",
                    "LOCAÇÃO COMPRESSORES (40,00%);\n\nSALARIO (60,00%);",
                    "itau",
                    "fluxo.xlsx",
                    7,
                    "Sheet",
                    "destaque-h7",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-09",
                    "debito",
                    "Rateio fornecedores",
                    200,
                    None,
                    "EPIS (25,00%);\n\nMATERIAIS DE CONSUMO EM OBRAS  (75,00%);",
                    "EPIS (25,00%);\n\nMATERIAIS DE CONSUMO EM OBRAS  (75,00%);",
                    "itau",
                    "fluxo.xlsx",
                    8,
                    "Sheet",
                    "destaque-h8",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-10",
                    "debito",
                    "Outro",
                    100,
                    None,
                    "Outra saída",
                    "Outra saída",
                    "itau",
                    "fluxo.xlsx",
                    9,
                    "Sheet",
                    "destaque-h9",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-destaques",
                    2025,
                    5,
                    "2025-05-11",
                    "credito",
                    "Crédito ignorado nas saídas",
                    999,
                    None,
                    "12.1 - SALÁRIO",
                    "12.1 - SALÁRIO",
                    "itau",
                    "fluxo.xlsx",
                    10,
                    "Sheet",
                    "destaque-h10",
                    "2026-04-01T11:00:00",
                ),
            ],
        )

    client = _client_com_db(db)
    resp = client.get("/api/fluxo_caixa/painel?ano=2025&meses=5")

    assert resp.status_code == 200
    body = resp.json()
    destaques = {item["id"]: item for item in body["contas_destaque"]}
    assert set(destaques) == {
        "parcelamento",
        "folha_pessoal",
        "locacoes",
        "fornecedores",
        "gastos_manutencao",
    }
    assert destaques["parcelamento"]["total"] == 70.0
    assert destaques["folha_pessoal"]["total"] == 210.0
    assert destaques["locacoes"]["total"] == 90.0
    assert destaques["fornecedores"]["total"] == 280.0
    assert destaques["gastos_manutencao"]["total"] == 40.0
    assert destaques["folha_pessoal"]["participacao_saidas_percentual"] == pytest.approx(
        210 / 790 * 100
    )
    assert "12.1 salário" in destaques["folha_pessoal"]["contas_encontradas"]
    assert "12.14 FGTS funcionários" in destaques["folha_pessoal"]["contas_encontradas"]
    assert "8.9 materiais de consumo em obras" in destaques["fornecedores"]["contas_encontradas"]

    equilibrio = body["equilibrio_contas_destaque"]
    assert equilibrio["total_contas_destaque"] == pytest.approx(690.0)
    assert equilibrio["outras_saidas"] == pytest.approx(100.0)
    assert equilibrio["participacao_saidas_percentual"] == pytest.approx(690 / 790 * 100)
    assert equilibrio["cobertura_entradas_percentual"] == pytest.approx(999 / 690 * 100)
    assert equilibrio["saldo_liquido"] == pytest.approx(209.0)
    assert equilibrio["saldo_apos_contas_destaque"] == pytest.approx(309.0)
    assert equilibrio["status"] == "equilibrado"


def test_admin_limpar_remove_somente_competencia_informada(monkeypatch):
    _configurar_admin(monkeypatch)
    db = _novo_db()
    with db.transaction() as conn:
        conn.executemany(
            """
            INSERT INTO dre_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "dre-mai",
                    "2026-04-01T10:00:00",
                    "dre_05.xls",
                    "hash-dre-mai",
                    2025,
                    5,
                    "completed",
                    1,
                    1,
                    0,
                    None,
                ),
                (
                    "dre-jun",
                    "2026-04-01T10:00:00",
                    "dre_06.xls",
                    "hash-dre-jun",
                    2025,
                    6,
                    "completed",
                    1,
                    1,
                    0,
                    None,
                ),
            ],
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
                    "dre-mai",
                    2025,
                    5,
                    "2025-05-10",
                    "Maio",
                    100,
                    100,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "Faturamento",
                    "(=)Receita Bruta",
                    1,
                    "dre-mai-h",
                    "2026-04-01T10:00:00",
                ),
                (
                    "dre-jun",
                    2025,
                    6,
                    "2025-06-10",
                    "Junho",
                    200,
                    200,
                    0,
                    "Receita",
                    "ENTRADA",
                    "Obra A",
                    "Faturamento",
                    "(=)Receita Bruta",
                    2,
                    "dre-jun-h",
                    "2026-04-01T10:00:00",
                ),
            ],
        )
        conn.executemany(
            """
            INSERT INTO fluxo_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             banco, status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "fc-mai",
                    "2026-04-01T11:00:00",
                    "fc_05.xlsx",
                    "hash-fc-mai",
                    2025,
                    5,
                    "itau",
                    "completed",
                    1,
                    1,
                    0,
                    None,
                ),
                (
                    "fc-jun",
                    "2026-04-01T11:00:00",
                    "fc_06.xlsx",
                    "hash-fc-jun",
                    2025,
                    6,
                    "itau",
                    "completed",
                    1,
                    1,
                    0,
                    None,
                ),
            ],
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
                    "fc-mai",
                    2025,
                    5,
                    "2025-05-10",
                    "debito",
                    "Maio",
                    100,
                    None,
                    "SALARIO",
                    "SALARIO",
                    "itau",
                    "fc_05.xlsx",
                    1,
                    "Sheet",
                    "fc-mai-h",
                    "2026-04-01T11:00:00",
                ),
                (
                    "fc-jun",
                    2025,
                    6,
                    "2025-06-10",
                    "debito",
                    "Junho",
                    200,
                    None,
                    "SALARIO",
                    "SALARIO",
                    "itau",
                    "fc_06.xlsx",
                    2,
                    "Sheet",
                    "fc-jun-h",
                    "2026-04-01T11:00:00",
                ),
            ],
        )

    _patch_admin_services(db)
    client = _client_com_db(db)

    dre_sem_sessao = client.post(
        "/api/dre/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )
    fluxo_sem_sessao = client.post(
        "/api/fluxo_caixa/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )
    assert dre_sem_sessao.status_code == 401
    assert fluxo_sem_sessao.status_code == 401

    _login_admin(client)
    dre_sem_confirmar = client.post("/api/dre/admin/limpar", data={"ano": "2025", "mes": "5"})
    fluxo_sem_confirmar = client.post(
        "/api/fluxo_caixa/admin/limpar",
        data={"ano": "2025", "mes": "5"},
    )
    assert dre_sem_confirmar.status_code == 400
    assert fluxo_sem_confirmar.status_code == 400

    dre_resp = client.post(
        "/api/dre/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )
    fluxo_resp = client.post(
        "/api/fluxo_caixa/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )

    assert dre_resp.status_code == 200
    assert dre_resp.json()["lancamentos_removidos"] == 1
    assert fluxo_resp.status_code == 200
    assert fluxo_resp.json()["movimentos_removidos"] == 1

    with db.get_connection() as conn:
        dre_restantes = conn.execute("SELECT competencia_mes FROM dre_lancamentos").fetchall()
        fluxo_restantes = conn.execute("SELECT competencia_mes FROM fluxo_movimentos").fetchall()
    assert [row["competencia_mes"] for row in dre_restantes] == [6]
    assert [row["competencia_mes"] for row in fluxo_restantes] == [6]


def test_paineis_rejeitam_periodo_invalido():
    db = _novo_db()
    client = _client_com_db(db)

    dre_resp = client.get("/api/dre/painel?ano=2025&meses=13")
    fluxo_resp = client.get("/api/fluxo_caixa/painel?ano=1999")

    assert dre_resp.status_code == 400
    assert "Mês deve estar entre 1 e 12" in dre_resp.json()["detail"]
    assert fluxo_resp.status_code == 400
    assert "Ano deve estar entre 2000 e 2100" in fluxo_resp.json()["detail"]
