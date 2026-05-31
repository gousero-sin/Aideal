from fastapi.testclient import TestClient

import app.main as main_module


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


def test_admin_login_cria_sessao_http_only(monkeypatch):
    _configurar_admin(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/admin/login",
        json={"username": "Eduardo", "password": "senha-admin-teste"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"authenticated": True, "username": "Eduardo"}
    set_cookie = resp.headers["set-cookie"]
    assert "aideal_admin_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "senha-admin-teste" not in resp.text

    session_resp = client.get("/api/admin/session")
    assert session_resp.status_code == 200
    assert session_resp.json() == {"authenticated": True, "username": "Eduardo"}


def test_admin_login_rejeita_credenciais_invalidas(monkeypatch):
    _configurar_admin(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/admin/login",
        json={"username": "Eduardo", "password": "senha-errada"},
    )

    assert resp.status_code == 401
    assert "aideal_admin_session=" not in resp.headers.get("set-cookie", "")
    assert resp.json()["detail"] == "Credenciais inválidas."


def test_admin_logout_invalida_sessao(monkeypatch):
    _configurar_admin(monkeypatch)
    client = TestClient(main_module.app)
    client.post(
        "/api/admin/login",
        json={"username": "Eduardo", "password": "senha-admin-teste"},
    )

    resp = client.post("/api/admin/logout")

    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}
    assert "Max-Age=0" in resp.headers["set-cookie"]
    assert client.get("/api/admin/session").json() == {"authenticated": False, "username": None}


def test_admin_auth_nao_configurada_bloqueia_login_e_operacoes(monkeypatch):
    monkeypatch.setattr(main_module.settings, "admin_username", "", raising=False)
    monkeypatch.setattr(main_module.settings, "admin_password", "", raising=False)
    monkeypatch.setattr(main_module.settings, "admin_password_hash", "", raising=False)
    monkeypatch.setattr(main_module.settings, "admin_session_secret", "", raising=False)
    client = TestClient(main_module.app)

    login_resp = client.post(
        "/api/admin/login",
        json={"username": "Eduardo", "password": "senha-admin-teste"},
    )
    limpar_resp = client.post(
        "/api/dre/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )

    assert login_resp.status_code == 503
    assert limpar_resp.status_code == 503


def test_operacao_admin_exige_sessao(monkeypatch):
    _configurar_admin(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/dre/admin/limpar",
        data={"ano": "2025", "mes": "5", "confirmar": "true"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Sessão admin obrigatória."
