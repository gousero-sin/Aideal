"""Desempenho e concorrência: event loop livre, cache de painéis, rate limit e migrações."""

import asyncio
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient as StarletteTestClient
from starlette.applications import Starlette
from starlette.routing import Mount
from test_paineis_api import (
    _LANCAMENTOS_RESULTADO_DRE,
    _client_com_db,
    _inserir_lancamentos_dre,
    _novo_db,
)

import app.main as main_module
from app.identity.service import create_identity_service
from app.processamento.paineis import PainelDREService
from app.processamento.painel_cache import PainelRespostaCache

BACKEND_DIR = Path(__file__).resolve().parents[1]


class _PainelLento:
    """Painel falso que bloqueia a thread, como um cálculo pesado de pandas."""

    def __init__(self, segundos: float) -> None:
        self.segundos = segundos
        self.iniciado = threading.Event()

    def obter_painel(self, **_kwargs):
        self.iniciado.set()
        time.sleep(self.segundos)
        return {"ok": True}

    def invalidar_cache(self) -> None:
        pass


async def test_health_responde_enquanto_painel_pesado_calcula(monkeypatch):
    lento = _PainelLento(1.5)
    monkeypatch.setattr(main_module, "dre_painel_service", lento)
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://teste") as client:
        login = await client.post(
            "/api/admin/login",
            json={"username": "Eduardo", "password": "senha-admin-teste"},
        )
        assert login.status_code == 200

        painel = asyncio.create_task(client.get("/api/dre/painel"))
        while not lento.iniciado.is_set():
            await asyncio.sleep(0.01)

        inicio = time.perf_counter()
        health = await client.get("/health")
        duracao_health = time.perf_counter() - inicio

        assert health.status_code == 200
        assert not painel.done(), "o painel lento deveria ainda estar calculando"
        assert duracao_health < 0.5
        assert (await painel).json() == {"ok": True}


def test_painel_repetido_e_servido_do_cache_com_copia_isolada():
    servico = PainelDREService(db=_novo_db())
    _inserir_lancamentos_dre(servico.db, "cache-1", 2026, 5, "Obra C", _LANCAMENTOS_RESULTADO_DRE)

    primeiro = servico.obter_painel(ano=2026)
    primeiro["kpis"] = "mutado pelo chamador"
    segundo = servico.obter_painel(ano=2026)

    assert servico._cache_respostas.falhas == 1
    assert servico._cache_respostas.acertos == 1
    assert segundo["kpis"] != "mutado pelo chamador"
    assert segundo == servico._calcular_painel(ano=2026)


def test_cache_do_painel_invalida_quando_outra_conexao_grava_no_banco():
    db = _novo_db()
    servico = PainelDREService(db=db)
    _inserir_lancamentos_dre(db, "versao-1", 2026, 5, "Obra V", _LANCAMENTOS_RESULTADO_DRE)
    antes = servico.obter_painel(ano=2026)

    # Escrita por outra conexão (equivale a outro worker do uvicorn) muda o
    # PRAGMA data_version e precisa derrubar o cache sem invalidação explícita.
    _inserir_lancamentos_dre(db, "versao-2", 2026, 6, "Obra V", _LANCAMENTOS_RESULTADO_DRE)
    depois = servico.obter_painel(ano=2026)

    assert depois != antes
    assert depois == servico._calcular_painel(ano=2026)
    assert servico._cache_respostas.acertos == 0


def test_rota_de_escrita_invalida_cache_dos_paineis():
    db = _novo_db()
    client = _client_com_db(db)
    servico = main_module.dre_painel_service
    assert client.get("/api/dre/painel", params={"ano": 2025}).status_code == 200
    geracao_antes = servico._cache_respostas.geracao

    salvo = client.post(
        "/api/dre/admin/indicadores",
        data={"ano": "2025", "mes": "5", "contas_pagar": "300", "confirmar": "true"},
    )

    assert salvo.status_code == 200
    assert servico._cache_respostas.geracao > geracao_antes
    assert main_module.fluxo_painel_service._cache_respostas.geracao > 0


def test_cache_calcula_uma_vez_para_requisicoes_simultaneas():
    cache = PainelRespostaCache()
    chamadas = []
    liberar = threading.Event()

    def calcular():
        chamadas.append(1)
        liberar.wait(2)
        return {"valor": [1, 2, 3]}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futuros = [pool.submit(cache.obter_ou_calcular, "chave", calcular) for _ in range(8)]
        time.sleep(0.1)
        liberar.set()
        resultados = [f.result(timeout=5) for f in futuros]

    assert len(chamadas) == 1
    assert all(r == {"valor": [1, 2, 3]} for r in resultados)
    assert len({id(r) for r in resultados}) == 8


def test_cache_descarta_resultado_calculado_durante_invalidacao():
    cache = PainelRespostaCache()

    def calcular_e_invalidar():
        cache.invalidar()
        return "velho"

    assert cache.obter_ou_calcular("k", calcular_e_invalidar) == "velho"
    assert cache.obter_ou_calcular("k", lambda: "novo") == "novo"


def test_cache_libera_espera_quando_calculo_falha():
    cache = PainelRespostaCache()

    def falhar():
        raise RuntimeError("erro de cálculo")

    with pytest.raises(RuntimeError):
        cache.obter_ou_calcular("k", falhar)
    assert cache.obter_ou_calcular("k", lambda: 42) == 42


def test_rate_limit_de_login_e_compartilhado_entre_instancias(tmp_path):
    db_path = tmp_path / "identity.db"
    worker_a = create_identity_service(db_path)
    worker_b = create_identity_service(db_path)
    kwargs = {"window_seconds": 60, "max_attempts": 3}

    assert worker_a.register_login_attempt("1.2.3.4:eduardo", now=1000, **kwargs)
    assert worker_b.register_login_attempt("1.2.3.4:eduardo", now=1001, **kwargs)
    assert worker_a.register_login_attempt("1.2.3.4:eduardo", now=1002, **kwargs)
    assert not worker_b.register_login_attempt("1.2.3.4:eduardo", now=1003, **kwargs)
    # Outra chave não é afetada; a janela expira; sucesso zera o contador.
    assert worker_b.register_login_attempt("5.6.7.8:eduardo", now=1003, **kwargs)
    assert worker_a.register_login_attempt("1.2.3.4:eduardo", now=1100, **kwargs)
    worker_b.clear_login_attempts("1.2.3.4:eduardo")
    for instante in (1101, 1102):
        assert worker_a.register_login_attempt("1.2.3.4:eduardo", now=instante, **kwargs)


def test_rate_limit_conta_tentativas_simultaneas_sem_perder_nenhuma(tmp_path):
    db_path = tmp_path / "identity.db"
    servicos = [create_identity_service(db_path) for _ in range(4)]

    def tentar(indice: int) -> bool:
        return servicos[indice % 4].register_login_attempt(
            "ip:usuario", window_seconds=60, max_attempts=5, now=2000 + indice / 100
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        permitidas = list(pool.map(tentar, range(20)))

    assert sum(permitidas) == 5


def test_migracoes_simultaneas_em_processos_distintos(tmp_path):
    codigo = (
        "import sys\n"
        "from app.db.connection import DatabaseConnection\n"
        "from app.db.manager import MigrationManager\n"
        "from app.identity.database import IdentityDatabase\n"
        "MigrationManager(DatabaseConnection(sys.argv[1])).migrate()\n"
        "IdentityDatabase(sys.argv[2]).migrate()\n"
    )
    aideal_db = tmp_path / "aideal.db"
    identity_db = tmp_path / "identity.db"
    processos = [
        subprocess.Popen(
            [sys.executable, "-c", codigo, str(aideal_db), str(identity_db)],
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    for processo in processos:
        _, erro = processo.communicate(timeout=60)
        assert processo.returncode == 0, erro

    assert create_identity_service(identity_db).register_login_attempt(
        "x", window_seconds=60, max_attempts=1
    )


def test_json_grande_sai_comprimido_com_gzip():
    client = _client_com_db(_novo_db())

    resp = client.get("/api/dre/painel", headers={"Accept-Encoding": "gzip"})

    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.json()["kpis"] is not None


def test_frontend_assets_imutaveis_e_html_revalidado(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html></html>")
    app = Starlette(
        routes=[
            Mount(
                "/",
                app=main_module.FrontendStaticFiles(directory=str(tmp_path), html=True),
            )
        ]
    )
    client = StarletteTestClient(app)

    asset = client.get("/assets/index-abc123.js")
    html = client.get("/")

    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert html.headers["cache-control"] == "no-cache"
