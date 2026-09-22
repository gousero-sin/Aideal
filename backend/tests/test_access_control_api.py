from fastapi.testclient import TestClient

import app.main as main_module
from app.access_control import configure_identity_service
from app.identity import create_identity_service

ADMIN_PASSWORD = "senha-admin-teste"
SENHA_TEMPORARIA = "senha-temporaria-123"


def _configure_isolated_identity(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password=ADMIN_PASSWORD)
    configure_identity_service(service)
    return service, owner


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_global_login_exposes_only_safe_session_payload(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)

    body = _login(client, "Eduardo", ADMIN_PASSWORD)

    assert body["authenticated"] is True
    assert body["user"]["username"] == "Eduardo"
    assert body["user"]["is_system_owner"] is True
    assert set(body["permissions"]) == {
        "dre.view",
        "fluxo.view",
        "admin_banco.use",
        "users.manage",
        "orcamento.view",
        "orcamento.edit",
        "orcamento.transition",
    }
    assert {module["id"] for module in body["modules"]} == {
        "dre",
        "fluxo_caixa",
        "admin_banco",
        "usuarios",
        "orcamento",
    }
    assert body["csrf_token"]
    assert "password_hash" not in str(body).lower()
    assert "senha-admin-teste" not in str(body)
    assert (
        "aideal_session="
        in client.post(
            "/api/auth/login",
            json={"username": "Eduardo", "password": ADMIN_PASSWORD},
        ).headers["set-cookie"]
    )

    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["username"] == "Eduardo"


def test_panel_endpoints_require_authentication_and_permissions(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    owner_client = TestClient(main_module.app)
    anonymous_client = TestClient(main_module.app)

    assert anonymous_client.get("/api/dre/painel?ano=2025").status_code == 401
    assert anonymous_client.get("/api/fluxo_caixa/painel?ano=2025").status_code == 401

    user = service.create_user(
        username="ana",
        display_name="Ana",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )
    assert user.permissions == ("dre.view",)
    _login(owner_client, "ana", "senha-temporaria-123")

    assert owner_client.get("/api/dre/painel?ano=2025").status_code == 200
    assert owner_client.get("/api/fluxo_caixa/painel?ano=2025").status_code == 403
    assert owner_client.get("/api/admin/users").status_code == 403


def test_owner_creates_and_updates_user_with_csrf_and_audit(tmp_path):
    service, _owner = _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    session = _login(client, "Eduardo", ADMIN_PASSWORD)

    payload = {
        "username": "maria",
        "display_name": "Maria Souza",
        "password": "senha-temporaria-123",
        "permissions": ["dre.view"],
        "active": True,
    }
    without_csrf = client.post("/api/admin/users", json=payload)
    assert without_csrf.status_code == 403

    created = client.post(
        "/api/admin/users",
        json=payload,
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert created.status_code == 201
    user = created.json()
    assert user["username"] == "maria"
    assert user["permissions"] == ["dre.view"]

    updated = client.patch(
        f"/api/admin/users/{user['id']}",
        json={
            "display_name": "Maria Silva",
            "active": True,
            "permissions": ["fluxo.view"],
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Maria Silva"
    assert updated.json()["permissions"] == ["fluxo.view"]

    events = service.repository.list_audit_events()
    assert any(event.event_type == "user.created" for event in events)
    assert any(event.event_type == "permissions.replaced" for event in events)


def test_deactivation_revokes_active_user_session(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    user = service.create_user(
        username="carlos",
        display_name="Carlos",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )
    owner_client = TestClient(main_module.app)
    user_client = TestClient(main_module.app)
    owner_session = _login(owner_client, "Eduardo", ADMIN_PASSWORD)
    _login(user_client, "carlos", "senha-temporaria-123")

    response = owner_client.patch(
        f"/api/admin/users/{user.id}",
        json={"active": False},
        headers={"X-CSRF-Token": owner_session["csrf_token"]},
    )

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert user_client.get("/api/auth/session").status_code == 401
    assert user_client.get("/api/dre/painel?ano=2025").status_code == 401


def test_invalid_login_and_duplicate_username_use_safe_status_codes(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)

    invalid = client.post(
        "/api/auth/login",
        json={"username": "Eduardo", "password": "incorreta"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Credenciais inválidas."

    session = _login(client, "Eduardo", ADMIN_PASSWORD)
    duplicate_payload = {
        "username": "Eduardo",
        "display_name": "Outro Eduardo",
        "password": "senha-temporaria-123",
        "permissions": ["dre.view"],
    }
    duplicate = client.post(
        "/api/admin/users",
        json=duplicate_payload,
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert duplicate.status_code == 409


def test_login_rate_limit_blocks_repeated_guesses_and_success_resets_counter(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)

    for _ in range(2):
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "Eduardo", "password": "incorreta"},
            ).status_code
            == 401
        )

    assert _login(client, "Eduardo", ADMIN_PASSWORD)["authenticated"] is True

    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "Eduardo", "password": "incorreta"},
            ).status_code
            == 401
        )

    blocked = client.post(
        "/api/auth/login",
        json={"username": "Eduardo", "password": ADMIN_PASSWORD},
    )
    assert blocked.status_code == 429
    assert "senha" not in str(blocked.json()).casefold()


def test_logout_requires_csrf_and_revokes_server_session(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    session = _login(client, "Eduardo", ADMIN_PASSWORD)

    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/auth/session").status_code == 200

    logged_out = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert logged_out.status_code == 200
    assert client.get("/api/auth/session").status_code == 401


def test_user_api_rejects_mass_assignment_fields(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    session = _login(client, "Eduardo", ADMIN_PASSWORD)

    response = client.post(
        "/api/admin/users",
        json={
            "username": "invasor",
            "display_name": "Campo indevido",
            "password": "senha-temporaria-123",
            "permissions": ["dre.view"],
            "is_system_owner": True,
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )

    assert response.status_code == 422


def test_user_patch_is_atomic_when_permission_validation_fails(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    user = service.create_user(
        username="paula",
        display_name="Paula Original",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )
    client = TestClient(main_module.app)
    session = _login(client, "Eduardo", ADMIN_PASSWORD)

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={
            "display_name": "Paula Alterada",
            "permissions": ["permissao.inexistente"],
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )

    assert response.status_code == 422
    persisted = service.repository.get_user(user.id)
    assert persisted is not None
    assert persisted.display_name == "Paula Original"
    assert persisted.permissions == ("dre.view",)


def test_legacy_admin_session_requires_admin_bank_permission(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    service.create_user(
        username="somente.dre",
        display_name="Somente DRE",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )
    client = TestClient(main_module.app)
    _login(client, "somente.dre", "senha-temporaria-123")

    response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "username": None}


def test_temporary_password_blocks_panels_until_user_changes_it(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    service.create_user(
        username="primeiro.acesso",
        display_name="Primeiro Acesso",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        must_change_password=True,
        actor_user_id=owner.id,
    )
    client = TestClient(main_module.app)
    session = _login(client, "primeiro.acesso", "senha-temporaria-123")

    assert session["password_change_required"] is True
    assert client.get("/api/dre/painel?ano=2025").status_code == 403
    assert (
        client.post(
            "/api/auth/change-password",
            json={
                "current_password": "senha-temporaria-123",
                "new_password": "senha-definitiva-123",
            },
        ).status_code
        == 403
    )

    changed = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "senha-temporaria-123",
            "new_password": "senha-definitiva-123",
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )

    assert changed.status_code == 200
    assert changed.json()["password_change_required"] is False
    assert client.get("/api/dre/painel?ano=2025").status_code == 200


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/session").json()["csrf_token"]}


def test_rotas_de_orcamento_exigem_permissao_orcamento_view(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    owner_client = TestClient(main_module.app)
    sem_permissao = TestClient(main_module.app)
    anonimo = TestClient(main_module.app)

    service.create_user(
        username="ana",
        display_name="Ana",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        must_change_password=False,
        actor_user_id=owner.id,
    )
    _login(owner_client, "Eduardo", ADMIN_PASSWORD)
    _login(sem_permissao, "ana", "senha-temporaria-123")

    assert anonimo.get("/api/orcamento/orcamentos").status_code == 401

    # Usuária sem orcamento.view recebe 403 em toda rota do módulo.
    assert sem_permissao.get("/api/orcamento/orcamentos").status_code == 403
    assert (
        sem_permissao.post(
            "/api/orcamento/orcamentos",
            json={"contratante": "AIDEAL"},
            headers=_csrf(sem_permissao),
        ).status_code
        == 403
    )

    criado = owner_client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AIDEAL", "escopo": "Pintura"},
        headers=_csrf(owner_client),
    )
    assert criado.status_code == 201
    orcamento = criado.json()
    assert orcamento["codigo"] == "ORC-0001"
    assert orcamento["sequencial"] == 1
    assert orcamento["revisao_atual"]["numero"] == 0
    assert orcamento["revisao_atual"]["situacao"] == "rascunho"
    assert "criado_por_user_id" not in orcamento
    assert "autor_user_id" not in orcamento["revisao_atual"]
    assert "autor_user_id" not in orcamento["revisoes"][0]

    assert sem_permissao.get(f"/api/orcamento/orcamentos/{orcamento['id']}").status_code == 403
    assert owner_client.get(f"/api/orcamento/orcamentos/{orcamento['id']}").status_code == 200
    assert owner_client.get("/api/orcamento/orcamentos").status_code == 200


def test_patch_cabecalho_exige_autenticacao_permissao_e_csrf(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    owner_client = TestClient(main_module.app)
    sem_permissao = TestClient(main_module.app)
    anonimo = TestClient(main_module.app)
    service.create_user(
        username="ana",
        display_name="Ana",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        must_change_password=False,
        actor_user_id=owner.id,
    )
    _login(owner_client, "Eduardo", ADMIN_PASSWORD)
    _login(sem_permissao, "ana", "senha-temporaria-123")
    criado = owner_client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AIDEAL", **CABECALHO_COMPLETO},
        headers=_csrf(owner_client),
    ).json()
    endpoint = f"/api/orcamento/revisoes/{criado['revisao_atual']['id']}"

    assert anonimo.patch(endpoint, json={"escopo": "Outro"}).status_code == 401
    assert (
        sem_permissao.patch(
            endpoint,
            json={"escopo": "Outro"},
            headers=_csrf(sem_permissao),
        ).status_code
        == 403
    )
    assert owner_client.patch(endpoint, json={"escopo": "Outro"}).status_code == 403
    assert (
        owner_client.get(f"/api/orcamento/orcamentos/{criado['id']}").json()[
            "revisao_atual"
        ]["escopo"]
        == CABECALHO_COMPLETO["escopo"]
    )


def test_orcamento_view_permite_leitura_mas_nao_autoriza_escrita(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    owner_client = TestClient(main_module.app)
    leitor_client = TestClient(main_module.app)
    service.create_user(
        username="leitor.orcamento",
        display_name="Leitor Orçamento",
        password=SENHA_TEMPORARIA,
        permissions=("orcamento.view",),
        must_change_password=False,
        actor_user_id=owner.id,
    )
    _login(owner_client, "Eduardo", ADMIN_PASSWORD)
    _login(leitor_client, "leitor.orcamento", "senha-temporaria-123")
    criado = owner_client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AIDEAL", **CABECALHO_COMPLETO},
        headers=_csrf(owner_client),
    ).json()
    revisao_id = criado["revisao_atual"]["id"]

    assert leitor_client.get("/api/orcamento/orcamentos").status_code == 200
    assert (
        leitor_client.post(
            "/api/orcamento/orcamentos",
            json={"contratante": "Sem autorização"},
            headers=_csrf(leitor_client),
        ).status_code
        == 403
    )
    assert (
        leitor_client.patch(
            f"/api/orcamento/revisoes/{revisao_id}",
            json={"escopo": "Sem autorização"},
            headers=_csrf(leitor_client),
        ).status_code
        == 403
    )
    assert (
        leitor_client.post(
            f"/api/orcamento/revisoes/{revisao_id}/situacao",
            json={"situacao": "em_revisao", "motivo": "Sem autorização"},
            headers=_csrf(leitor_client),
        ).status_code
        == 403
    )


def test_patch_cabecalho_valida_payload_e_edita_somente_rascunho(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)
    criado = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AIDEAL", **CABECALHO_COMPLETO},
        headers=_csrf(client),
    ).json()
    revisao_id = criado["revisao_atual"]["id"]
    endpoint = f"/api/orcamento/revisoes/{revisao_id}"

    modalidade_invalida = client.patch(
        endpoint,
        json={"modalidade": "Empreitada"},
        headers=_csrf(client),
    )
    campo_desconhecido = client.patch(
        endpoint,
        json={"contratante": "Não pertence à revisão"},
        headers=_csrf(client),
    )
    assert modalidade_invalida.status_code == 422
    assert campo_desconhecido.status_code == 422

    editada = client.patch(
        endpoint,
        json={
            "escopo": "  Escopo editado  ",
            "modalidade": "HH",
            "saldo_mao_de_obra": 0,
        },
        headers=_csrf(client),
    )
    assert editada.status_code == 200
    assert editada.json()["escopo"] == "Escopo editado"
    assert editada.json()["modalidade"] == "HH"
    assert editada.json()["saldo_mao_de_obra"] == 0
    assert editada.json()["regiao"] == CABECALHO_COMPLETO["regiao"]

    avancada = client.post(
        f"/api/orcamento/revisoes/{revisao_id}/situacao",
        json={"situacao": "em_revisao", "motivo": "cabeçalho conferido"},
        headers=_csrf(client),
    )
    assert avancada.status_code == 200
    bloqueada = client.patch(
        endpoint,
        json={"escopo": "Sobrescrita indevida"},
        headers=_csrf(client),
    )
    assert bloqueada.status_code == 422
    assert "rascunho" in bloqueada.json()["detail"]


def test_nova_revisao_na_api_distingue_campos_omitidos_de_null_explicito(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)
    criado = client.post(
        "/api/orcamento/orcamentos",
        json={
            "contratante": "AIDEAL",
            **CABECALHO_COMPLETO,
            "mobilizacao": "Equipe mobilizada",
            "desmobilizacao": "Equipe desmobilizada",
            "area_unidade_base": "Área industrial",
            "regime_tributario": "Lucro presumido",
        },
        headers=_csrf(client),
    ).json()

    nova = client.post(
        f"/api/orcamento/orcamentos/{criado['id']}/revisoes",
        json={"modalidade": "HH", "mobilizacao": None},
        headers=_csrf(client),
    )

    assert nova.status_code == 201
    corpo = nova.json()
    assert corpo["escopo"] == CABECALHO_COMPLETO["escopo"]
    assert corpo["modalidade"] == "HH"
    assert corpo["regiao"] == CABECALHO_COMPLETO["regiao"]
    assert corpo["prazo_execucao_dias"] == CABECALHO_COMPLETO["prazo_execucao_dias"]
    assert corpo["saldo_mao_de_obra"] == CABECALHO_COMPLETO["saldo_mao_de_obra"]
    assert corpo["dados_contratante"] == CABECALHO_COMPLETO["dados_contratante"]
    assert corpo["mobilizacao"] is None
    assert corpo["desmobilizacao"] == "Equipe desmobilizada"
    assert corpo["area_unidade_base"] == "Área industrial"
    assert corpo["regime_tributario"] == "Lucro presumido"


def test_escrita_em_orcamento_exige_csrf_e_preserva_revisoes(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)

    sem_csrf = client.post("/api/orcamento/orcamentos", json={"contratante": "AIDEAL"})
    assert sem_csrf.status_code == 403

    orcamento = client.post(
        "/api/orcamento/orcamentos",
        json={
            "contratante": "AIDEAL",
            "escopo": "Original",
            "modalidade": "Spot",
            "regiao": "Anápolis/GO",
            "prazo_execucao_dias": 10,
            "saldo_mao_de_obra": 4,
            "dados_contratante": "AMBEV S.A.",
        },
        headers=_csrf(client),
    ).json()
    revisao_1 = orcamento["revisao_atual"]

    nova = client.post(
        f"/api/orcamento/orcamentos/{orcamento['id']}/revisoes",
        json={"escopo": "Revisado"},
        headers=_csrf(client),
    )
    assert nova.status_code == 201
    assert nova.json()["numero"] == 1
    assert nova.json()["modalidade"] == "Spot"
    assert nova.json()["regiao"] == "Anápolis/GO"
    assert nova.json()["prazo_execucao_dias"] == 10
    assert nova.json()["saldo_mao_de_obra"] == 4
    assert nova.json()["dados_contratante"] == "AMBEV S.A."

    detalhe = client.get(f"/api/orcamento/orcamentos/{orcamento['id']}").json()
    assert [item["escopo"] for item in detalhe["revisoes"]] == ["Original", "Revisado"]
    assert detalhe["revisoes"][0]["id"] == revisao_1["id"]


CABECALHO_COMPLETO = {
    "escopo": "Hidrojateamento e pintura",
    "modalidade": "Spot",
    "regiao": "Anápolis/GO",
    "prazo_execucao_dias": 10,
    "saldo_mao_de_obra": 4,
    "dados_contratante": "AMBEV S.A.",
}


def test_ciclo_de_situacao_completo_e_bloqueio_de_reativacao_pela_api(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)

    orcamento = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AMBEV", **CABECALHO_COMPLETO},
        headers=_csrf(client),
    ).json()
    revisao_id = orcamento["revisao_atual"]["id"]
    assert orcamento["cabecalho_pendente"] == []

    def situacao(valor, motivo):
        return client.post(
            f"/api/orcamento/revisoes/{revisao_id}/situacao",
            json={"situacao": valor, "motivo": motivo},
            headers=_csrf(client),
        )

    # Rascunho não salta direto para pronto.
    assert situacao("pronto_para_proposta", "tentativa").status_code == 422
    assert situacao("em_revisao", "início da revisão").status_code == 200
    assert situacao("pronto_para_proposta", "custos conferidos").status_code == 200

    emitido = situacao("emitido", "emissão ao cliente")
    assert emitido.status_code == 200
    corpo = emitido.json()
    assert corpo["situacao"] == "emitido"
    # A validade comercial só passa a existir na emissão.
    assert corpo["emitido_em"] is not None
    assert corpo["valido_ate"] is not None
    assert corpo["vencida"] is False

    assert situacao("em_revisao", "voltar").status_code == 422
    assert situacao("inativo", "substituída por nova revisão").status_code == 200

    reativar = situacao("em_revisao", "tentativa")
    assert reativar.status_code == 422
    assert "nova revisão" in reativar.json()["detail"]


def test_cabecalho_incompleto_bloqueia_avanco_e_e_reportado_na_api(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)

    orcamento = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AMBEV"},
        headers=_csrf(client),
    ).json()

    assert "Escopo do Serviço" in orcamento["cabecalho_pendente"]
    assert "Modalidade do Trabalho" in orcamento["cabecalho_pendente"]

    bloqueado_em_revisao = client.post(
        f"/api/orcamento/revisoes/{orcamento['revisao_atual']['id']}/situacao",
        json={"situacao": "em_revisao", "motivo": "início"},
        headers=_csrf(client),
    )
    assert bloqueado_em_revisao.status_code == 422
    assert "Cabeçalho incompleto" in bloqueado_em_revisao.json()["detail"]

    inativado = client.post(
        f"/api/orcamento/revisoes/{orcamento['revisao_atual']['id']}/situacao",
        json={"situacao": "inativo", "motivo": "cancelado"},
        headers=_csrf(client),
    )
    assert inativado.status_code == 200

    segundo = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AMBEV"},
        headers=_csrf(client),
    ).json()
    bloqueado = client.post(
        f"/api/orcamento/revisoes/{segundo['revisao_atual']['id']}/situacao",
        json={"situacao": "pronto_para_proposta", "motivo": "tentativa"},
        headers=_csrf(client),
    )
    assert bloqueado.status_code == 422
    assert "não é permitida" in bloqueado.json()["detail"]


def test_modalidade_fora_do_dominio_e_recusada_pela_api(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)

    resposta = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AMBEV", "modalidade": "Empreitada"},
        headers=_csrf(client),
    )
    assert resposta.status_code == 422


def test_codigo_e_sequencial_e_campo_desconhecido_e_recusado(tmp_path):
    _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)
    _login(client, "Eduardo", ADMIN_PASSWORD)

    primeiro = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "AIDEAL"},
        headers=_csrf(client),
    )
    segundo = client.post(
        "/api/orcamento/orcamentos",
        json={"contratante": "Outra"},
        headers=_csrf(client),
    )

    assert primeiro.status_code == 201
    assert segundo.status_code == 201
    assert primeiro.json()["codigo"] == "ORC-0001"
    assert segundo.json()["codigo"] == "ORC-0002"

    # O código é do sistema: tentar informá-lo é campo desconhecido.
    assert (
        client.post(
            "/api/orcamento/orcamentos",
            json={"contratante": "AIDEAL", "codigo": "LIVRE-01"},
            headers=_csrf(client),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/orcamento/orcamentos",
            json={"contratante": "AIDEAL", "situacao": "inativo"},
            headers=_csrf(client),
        ).status_code
        == 422
    )


def test_troca_de_senha_pendente_bloqueia_o_modulo_de_orcamento(tmp_path):
    service, owner = _configure_isolated_identity(tmp_path)
    client = TestClient(main_module.app)

    service.create_user(
        username="bruno",
        display_name="Bruno",
        password=SENHA_TEMPORARIA,
        permissions=("orcamento.view",),
        must_change_password=True,
        actor_user_id=owner.id,
    )
    body = _login(client, "bruno", "senha-temporaria-123")

    assert body["password_change_required"] is True
    assert body["modules"] == []
    assert client.get("/api/orcamento/orcamentos").status_code == 403
