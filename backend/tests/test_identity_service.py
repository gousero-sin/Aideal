import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.identity import (
    DEFAULT_PERMISSIONS,
    InvalidCredentialsError,
    InvalidIdentityInputError,
    LastOwnerError,
    UnknownPermissionError,
    UsernameAlreadyExistsError,
    create_identity_service,
)


def _legacy_hash(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"

TEMPORARIA_SEGURA = "temporaria-segura"
SENHA_TEMPORARIA = "senha-temporaria-123"
SENHA_LONGA = "segredo-comprido"
NOVA_SENHA_SEGURA = "nova-senha-segura"


def test_bootstrap_eduardo_is_idempotent_and_grants_every_permission(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")

    first = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    second = service.bootstrap_eduardo(password_hash=_legacy_hash("outra-senha"))

    assert second == first
    assert first.username == "Eduardo"
    assert first.is_system_owner is True
    assert first.permissions == DEFAULT_PERMISSIONS
    assert len(service.list_users(actor_user_id=first.id)) == 1


def test_bootstrap_eduardo_is_idempotent_when_another_worker_wins_race(tmp_path, monkeypatch):
    database_path = tmp_path / "identity.db"
    service = create_identity_service(database_path)
    competing_service = create_identity_service(database_path)
    original_create_user = service.repository.create_user

    def create_after_competing_worker(**kwargs):
        competing_service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
        return original_create_user(**kwargs)

    monkeypatch.setattr(service.repository, "create_user", create_after_competing_worker)

    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    assert owner.is_system_owner is True
    assert len(service.repository.list_users()) == 1


def test_authenticate_upgrades_legacy_hash_when_argon2_is_available(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    user = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    old_hash = service.repository.password_hash_for(user.id)

    authenticated = service.authenticate(" eduardo ", "segredo")

    assert authenticated.id == user.id
    if service.password_hasher.available:
        assert service.repository.password_hash_for(user.id).startswith("$argon2id$")
        assert service.repository.password_hash_for(user.id) != old_hash


def test_authenticate_does_not_reveal_whether_username_or_password_is_wrong(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    with pytest.raises(InvalidCredentialsError, match="Credenciais inválidas"):
        service.authenticate("Eduardo", "incorreta")
    with pytest.raises(InvalidCredentialsError, match="Credenciais inválidas"):
        service.authenticate("Desconhecido", "incorreta")


def test_admin_can_create_update_and_replace_user_permissions(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    created = service.create_user(
        username="ana",
        display_name="Ana Souza",
        password=TEMPORARIA_SEGURA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )

    updated = service.update_user(
        created.id,
        display_name="Ana Silva",
        active=False,
        actor_user_id=owner.id,
    )
    replaced = service.replace_permissions(
        created.id,
        ("fluxo.view", "orcamento.view", "fluxo.view"),
        actor_user_id=owner.id,
    )

    assert updated.display_name == "Ana Silva"
    assert updated.active is False
    assert replaced.permissions == ("fluxo.view", "orcamento.view")
    assert service.list_users(actor_user_id=owner.id) == (owner, replaced)


def test_temporary_password_must_be_changed_and_revokes_previous_session(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    user = service.create_user(
        username="temporario",
        display_name="Usuário Temporário",
        password=SENHA_TEMPORARIA,
        permissions=("dre.view",),
        must_change_password=True,
        actor_user_id=owner.id,
    )
    credentials = service.create_session(user.id)

    assert user.must_change_password is True
    with pytest.raises(InvalidCredentialsError):
        service.change_own_password(
            user.id,
            current_password="senha-incorreta",
            new_password="senha-definitiva-123",
        )

    updated = service.change_own_password(
        user.id,
        current_password=SENHA_TEMPORARIA,
        new_password="senha-definitiva-123",
    )

    assert updated.must_change_password is False
    assert service.resolve_session(credentials.token) is None
    assert service.authenticate("temporario", "senha-definitiva-123").id == user.id
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("temporario", "senha-temporaria-123")


def test_username_uniqueness_is_case_insensitive(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    service.create_user(
        username="ana",
        display_name="Ana",
        password=TEMPORARIA_SEGURA,
        actor_user_id=owner.id,
    )

    with pytest.raises(UsernameAlreadyExistsError):
        service.create_user(
            username="ANA",
            display_name="Outra Ana",
            password=TEMPORARIA_SEGURA,
            actor_user_id=owner.id,
        )


def test_unknown_permissions_are_rejected(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    with pytest.raises(UnknownPermissionError):
        service.create_user(
            username="ana",
            display_name="Ana",
            password=TEMPORARIA_SEGURA,
            permissions=("financeiro.superuser",),
            actor_user_id=owner.id,
        )


def test_user_without_management_permission_cannot_manage_other_users(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    regular_user = service.create_user(
        username="ana",
        display_name="Ana",
        password=TEMPORARIA_SEGURA,
        permissions=("dre.view",),
        actor_user_id=owner.id,
    )

    with pytest.raises(InvalidCredentialsError, match="users.manage"):
        service.create_user(
            username="maria",
            display_name="Maria",
            password=TEMPORARIA_SEGURA,
            actor_user_id=regular_user.id,
        )
    with pytest.raises(InvalidCredentialsError, match="users.manage"):
        service.list_users(actor_user_id=regular_user.id)


def test_regular_user_creation_rejects_legacy_sha256_hashes(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    with pytest.raises(InvalidIdentityInputError, match="Formato de hash"):
        service.create_user(
            username="ana",
            display_name="Ana",
            password_hash=_legacy_hash("temporaria"),
            actor_user_id=owner.id,
        )


def test_plaintext_passwords_are_hashed_and_never_stored_verbatim(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password=SENHA_LONGA)

    stored_hash = service.repository.password_hash_for(owner.id)

    assert stored_hash.startswith("$argon2id$")
    assert SENHA_LONGA not in stored_hash


def test_system_owner_cannot_be_deactivated_or_lose_user_management(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    with pytest.raises(LastOwnerError):
        service.update_user(owner.id, active=False, actor_user_id=owner.id)
    with pytest.raises(LastOwnerError):
        service.replace_permissions(owner.id, ("dre.view",), actor_user_id=owner.id)


def test_sessions_are_opaque_resolvable_and_revocable(tmp_path):
    now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    service = create_identity_service(
        tmp_path / "identity.db",
        session_ttl=timedelta(hours=1),
        clock=lambda: now,
    )
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))

    credentials = service.create_session(owner.id)
    payload = service.resolve_session(credentials.token)

    assert len(credentials.token) >= 43
    assert credentials.csrf_token
    assert owner.username not in credentials.token
    assert payload is not None
    assert payload.user == owner
    assert payload.csrf_token == credentials.csrf_token
    assert service.verify_csrf(credentials.token, credentials.csrf_token) is True
    assert service.verify_csrf(credentials.token, "csrf-incorreto") is False

    service.revoke_session(credentials.token, actor_user_id=owner.id)

    assert service.resolve_session(credentials.token) is None


def test_expired_and_deactivated_user_sessions_are_rejected(tmp_path):
    current_time = [datetime(2026, 8, 27, 12, tzinfo=timezone.utc)]
    service = create_identity_service(
        tmp_path / "identity.db",
        session_ttl=timedelta(minutes=30),
        clock=lambda: current_time[0],
    )
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    user = service.create_user(
        username="ana",
        display_name="Ana",
        password=TEMPORARIA_SEGURA,
        actor_user_id=owner.id,
    )
    expired_session = service.create_session(user.id)
    current_time[0] += timedelta(minutes=31)

    assert service.resolve_session(expired_session.token) is None

    current_time[0] -= timedelta(minutes=31)
    active_session = service.create_session(user.id)
    service.update_user(user.id, active=False, actor_user_id=owner.id)

    assert service.resolve_session(active_session.token) is None


def test_password_change_revokes_existing_sessions(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    user = service.create_user(
        username="ana",
        display_name="Ana",
        password=TEMPORARIA_SEGURA,
        actor_user_id=owner.id,
    )
    credentials = service.create_session(user.id)

    service.update_user(
        user.id,
        password=NOVA_SENHA_SEGURA,
        actor_user_id=owner.id,
    )

    assert service.resolve_session(credentials.token) is None


def test_session_payload_is_safe_for_api_responses(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo"))
    credentials = service.create_session(owner.id)

    payload = service.session_payload(credentials.token)

    assert payload == {
        "user": owner.to_dict(),
        "permissions": list(DEFAULT_PERMISSIONS),
        "csrf_token": credentials.csrf_token,
        "expires_at": credentials.expires_at.isoformat(),
    }


def test_sensitive_values_never_appear_in_audit_events(tmp_path):
    service = create_identity_service(tmp_path / "identity.db")
    owner = service.bootstrap_eduardo(password_hash=_legacy_hash("segredo-super-secreto"))
    credentials = service.create_session(owner.id)
    service.authenticate("Eduardo", "segredo-super-secreto")
    service.revoke_session(credentials.token, actor_user_id=owner.id)

    serialized_events = repr(service.repository.list_audit_events())

    assert "segredo-super-secreto" not in serialized_events
    assert credentials.token not in serialized_events
    assert credentials.csrf_token not in serialized_events
