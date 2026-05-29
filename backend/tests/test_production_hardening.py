from io import BytesIO

from fastapi.testclient import TestClient

import app.main as main_module


def test_ready_reporta_dependencias_operacionais():
    client = TestClient(main_module.app)

    resp = client.get("/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] is True
    assert body["checks"]["templates"] is True
    assert body["checks"]["directories"] is True


def test_upload_rejeita_extensao_nao_permitida():
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/validar/dre",
        files={"arquivo": ("relatorio.txt", BytesIO(b"conteudo"), "text/plain")},
    )

    assert resp.status_code == 400
    assert "Formato de arquivo não permitido" in resp.json()["detail"]


def test_upload_rejeita_arquivo_maior_que_limite(monkeypatch):
    monkeypatch.setattr(main_module.settings, "max_upload_size_mb", 0)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/validar/dre",
        files={
            "arquivo": (
                "relatorio.xlsx",
                BytesIO(b"conteudo"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert resp.status_code == 413
    assert "Arquivo excede o limite" in resp.json()["detail"]


def test_upload_lote_rejeita_quantidade_acima_do_limite(monkeypatch):
    monkeypatch.setattr(main_module.settings, "max_files_per_batch", 1)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/detectar-competencia/fluxo_caixa",
        files=[
            ("arquivos", ("a.xlsx", BytesIO(b"a"), "application/vnd.ms-excel")),
            ("arquivos", ("b.xlsx", BytesIO(b"b"), "application/vnd.ms-excel")),
        ],
    )

    assert resp.status_code == 400
    assert "Quantidade máxima de arquivos" in resp.json()["detail"]


def test_download_rejeita_path_traversal():
    client = TestClient(main_module.app)

    dre_resp = client.get("/api/dre/download/%2E%2E%2Faideal.db")
    fluxo_resp = client.get("/api/fluxo_caixa/download/%2E%2E%2Faideal.db")

    assert dre_resp.status_code == 400
    assert fluxo_resp.status_code == 400
