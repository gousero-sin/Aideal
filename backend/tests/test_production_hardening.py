import tomllib
from io import BytesIO
from pathlib import Path

from conftest import login_admin
from fastapi.testclient import TestClient

import app.main as main_module
from app.runtime_compat import (
    EXCEL_RUNTIME_REQUIREMENTS,
    RuntimeDependencyMismatch,
    check_runtime_compatibility,
    require_runtime_compatibility,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_ready_reporta_dependencias_operacionais():
    client = TestClient(main_module.app)

    resp = client.get("/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] is True
    assert body["checks"]["templates"] is True
    assert body["checks"]["directories"] is True
    assert body["checks"]["excel_runtime"] is True


def test_pyproject_fixa_dependencias_sensiveis_do_excel():
    pyproject = tomllib.loads((ROOT_DIR / "backend" / "pyproject.toml").read_text())
    dependencies = {
        dependency.split("==", 1)[0]: dependency
        for dependency in pyproject["project"]["dependencies"]
        if "==" in dependency
    }

    for package, expected_version in EXCEL_RUNTIME_REQUIREMENTS.items():
        assert dependencies[package] == f"{package}=={expected_version}"


def test_runtime_compatibility_detecta_versao_divergente(monkeypatch):
    def fake_version(package_name: str) -> str:
        if package_name == "openpyxl":
            return "3.1.4"
        return EXCEL_RUNTIME_REQUIREMENTS[package_name]

    monkeypatch.setattr("app.runtime_compat._installed_version", fake_version)

    mismatches = check_runtime_compatibility()

    assert mismatches == [
        RuntimeDependencyMismatch(
            package="openpyxl",
            expected="3.1.5",
            installed="3.1.4",
        )
    ]


def test_runtime_compatibility_falha_com_mensagem_acionavel(monkeypatch):
    def fake_version(package_name: str) -> str:
        if package_name == "et_xmlfile":
            return "2.1.0"
        return EXCEL_RUNTIME_REQUIREMENTS[package_name]

    monkeypatch.setattr("app.runtime_compat._installed_version", fake_version)

    try:
        require_runtime_compatibility()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("require_runtime_compatibility deveria falhar")

    assert "Runtime Python incompatível com geração Excel do DRE" in message
    assert "et_xmlfile instalado=2.1.0 esperado=2.0.0" in message
    assert "pip install -r backend/requirements.txt" in message


def test_ready_reporta_detalhes_de_runtime_excel_incompativel(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "check_runtime_compatibility",
        lambda: [
            RuntimeDependencyMismatch(
                package="openpyxl",
                expected="3.1.5",
                installed="3.1.4",
            )
        ],
    )
    client = TestClient(main_module.app)

    resp = client.get("/ready")

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["checks"]["excel_runtime"] is False
    assert detail["excel_runtime_mismatches"] == [
        {
            "package": "openpyxl",
            "expected": "3.1.5",
            "installed": "3.1.4",
        }
    ]


def test_upload_rejeita_extensao_nao_permitida():
    client = TestClient(main_module.app)
    login_admin(client)

    resp = client.post(
        "/api/validar/dre",
        files={"arquivo": ("relatorio.txt", BytesIO(b"conteudo"), "text/plain")},
    )

    assert resp.status_code == 400
    assert "Formato de arquivo não permitido" in resp.json()["detail"]


def test_upload_rejeita_arquivo_maior_que_limite(monkeypatch):
    monkeypatch.setattr(main_module.settings, "max_upload_size_mb", 0)
    client = TestClient(main_module.app)
    login_admin(client)

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
    login_admin(client)

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
    login_admin(client)

    dre_resp = client.get("/api/dre/download/%2E%2E%2Faideal.db")
    fluxo_resp = client.get("/api/fluxo_caixa/download/%2E%2E%2Faideal.db")

    assert dre_resp.status_code == 400
    assert fluxo_resp.status_code == 400
