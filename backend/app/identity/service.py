"""Casos de uso de usuários, permissões e sessões."""

import base64
import hashlib
import hmac
import re
import secrets
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .database import IdentityDatabase
from .exceptions import (
    InvalidCredentialsError,
    InvalidIdentityInputError,
    LastOwnerError,
    UnknownPermissionError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from .models import Session, SessionCredentials, User
from .passwords import Argon2PasswordHasher
from .repository import IdentityRepository

DEFAULT_PERMISSIONS = (
    "dre.view",
    "fluxo.view",
    "admin_banco.use",
    "users.manage",
    "orcamento.view",
    "orcamento.edit",
    "orcamento.transition",
)
USERNAME_PATTERN = re.compile(r"^[\w.@+-]{3,64}$", re.UNICODE)
MINIMUM_PASSWORD_LENGTH = 10
CSRF_DOMAIN = b"aideal.identity.csrf.v1"
DUMMY_ARGON2_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$JoyNy3Efo+J97ZPrKbK05Q$"
    "GLUxUtwpP6nNHBefkSIEL9DdOOpP/PAGrwVAPn+Bh9w"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IdentityService:
    """Interface de integração para identidade e autorização do GoFlow."""

    def __init__(
        self,
        repository: IdentityRepository,
        *,
        password_hasher: Argon2PasswordHasher | None = None,
        session_ttl: timedelta = timedelta(hours=8),
        clock: Callable[[], datetime] = _utc_now,
    ):
        if session_ttl <= timedelta(0):
            raise ValueError("session_ttl deve ser positivo")
        self.repository = repository
        self.password_hasher = password_hasher or Argon2PasswordHasher()
        self.session_ttl = session_ttl
        self.clock = clock

    def bootstrap_eduardo(
        self,
        *,
        password: str | None = None,
        password_hash: str | None = None,
        username: str = "Eduardo",
        display_name: str = "Eduardo",
    ) -> User:
        """Cria uma única vez o proprietário inicial com todas as permissões."""
        normalized_username, username_key = self._validate_username(username)
        existing = self.repository.get_user_by_username(username_key)
        if existing is not None:
            if not existing.is_system_owner:
                raise LastOwnerError("O usuário de bootstrap já existe sem ser proprietário")
            return existing
        encoded_password = self._encode_password(password, password_hash, allow_legacy=True)
        try:
            return self.repository.create_user(
                username=normalized_username,
                username_key=username_key,
                display_name=self._validate_display_name(display_name),
                password_hash=encoded_password,
                active=True,
                is_system_owner=True,
                must_change_password=False,
                permissions=self._normalize_permissions(DEFAULT_PERMISSIONS),
                actor_user_id=None,
            )
        except UsernameAlreadyExistsError:
            concurrent_owner = self.repository.get_user_by_username(username_key)
            if concurrent_owner is not None and concurrent_owner.is_system_owner:
                return concurrent_owner
            raise

    def authenticate(self, username: str, password: str) -> User:
        """Autentica sem diferenciar usuário inexistente, inativo ou senha errada."""
        username_key = username.strip().casefold()
        credentials = self.repository.password_hash_by_username(username_key)
        if credentials is None:
            self._consume_failed_authentication_cost(password)
            self.repository.record_audit(
                "authentication.failed",
                actor_user_id=None,
                target_user_id=None,
                metadata={"reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError("Credenciais inválidas")

        user_id, password_hash, active = credentials
        verification = self.password_hasher.verify(password, password_hash)
        if not verification.valid or not active:
            if not password_hash.startswith("$argon2"):
                self._consume_failed_authentication_cost(password)
            self.repository.record_audit(
                "authentication.failed",
                actor_user_id=user_id,
                target_user_id=user_id,
                metadata={"reason": "invalid_credentials"},
            )
            raise InvalidCredentialsError("Credenciais inválidas")

        if verification.needs_rehash and self.password_hasher.available:
            self.repository.update_password_hash(user_id, self.password_hasher.hash(password))
        user = self._require_user(user_id)
        self.repository.record_audit(
            "authentication.succeeded",
            actor_user_id=user.id,
            target_user_id=user.id,
        )
        return user

    def list_users(self, *, actor_user_id: str) -> tuple[User, ...]:
        self._require_manager(actor_user_id)
        return self.repository.list_users()

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        password: str | None = None,
        password_hash: str | None = None,
        permissions: Iterable[str] = (),
        active: bool = True,
        must_change_password: bool = False,
        actor_user_id: str,
    ) -> User:
        self._require_manager(actor_user_id)
        normalized_username, username_key = self._validate_username(username)
        return self.repository.create_user(
            username=normalized_username,
            username_key=username_key,
            display_name=self._validate_display_name(display_name),
            password_hash=self._encode_password(password, password_hash, allow_legacy=False),
            active=bool(active),
            is_system_owner=False,
            must_change_password=bool(must_change_password),
            permissions=self._normalize_permissions(permissions),
            actor_user_id=actor_user_id,
        )

    def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        active: bool | None = None,
        password: str | None = None,
        password_hash: str | None = None,
        actor_user_id: str,
    ) -> User:
        self._require_manager(actor_user_id)
        existing = self._require_user(user_id)
        if existing.is_system_owner and active is False:
            raise LastOwnerError("O proprietário do sistema não pode ser desativado")
        next_password_hash = None
        if password is not None or password_hash is not None:
            next_password_hash = self._encode_password(password, password_hash, allow_legacy=False)
        updated = self.repository.update_user(
            user_id,
            display_name=(
                self._validate_display_name(display_name) if display_name is not None else None
            ),
            active=active,
            password_hash=next_password_hash,
            actor_user_id=actor_user_id,
        )
        if updated is None:  # proteção contra exclusão concorrente
            raise UserNotFoundError("Usuário não encontrado")
        return updated

    def replace_permissions(
        self,
        user_id: str,
        permissions: Iterable[str],
        *,
        actor_user_id: str,
    ) -> User:
        self._require_manager(actor_user_id)
        existing = self._require_user(user_id)
        normalized_permissions = self._normalize_permissions(permissions)
        if existing.is_system_owner and "users.manage" not in normalized_permissions:
            raise LastOwnerError("O proprietário deve manter users.manage")
        updated = self.repository.replace_permissions(
            user_id, normalized_permissions, actor_user_id
        )
        if updated is None:
            raise UserNotFoundError("Usuário não encontrado")
        return updated

    def update_user_access(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        active: bool | None = None,
        password: str | None = None,
        permissions: Iterable[str] | None = None,
        actor_user_id: str,
    ) -> User:
        """Valida e aplica perfil/permissões atomicamente."""
        self._require_manager(actor_user_id)
        existing = self._require_user(user_id)
        normalized_permissions = (
            self._normalize_permissions(permissions) if permissions is not None else None
        )
        if existing.is_system_owner:
            if active is False:
                raise LastOwnerError("O proprietário do sistema não pode ser desativado")
            if normalized_permissions is not None and "users.manage" not in normalized_permissions:
                raise LastOwnerError("O proprietário deve manter users.manage")
        normalized_display_name = (
            self._validate_display_name(display_name) if display_name is not None else None
        )
        password_hash = (
            self._encode_password(password, None, allow_legacy=False)
            if password is not None
            else None
        )
        updated = self.repository.update_user_access(
            user_id,
            display_name=normalized_display_name,
            active=active,
            password_hash=password_hash,
            permissions=normalized_permissions,
            must_change_password=True if password is not None else None,
            actor_user_id=actor_user_id,
        )
        if updated is None:
            raise UserNotFoundError("Usuário não encontrado")
        return updated

    def change_own_password(
        self,
        user_id: str,
        *,
        current_password: str,
        new_password: str,
    ) -> User:
        user = self._require_user(user_id)
        self.authenticate(user.username, current_password)
        if hmac.compare_digest(current_password, new_password):
            raise InvalidIdentityInputError("A nova senha deve ser diferente da senha atual")
        password_hash = self._encode_password(new_password, None, allow_legacy=False)
        updated = self.repository.change_password(
            user_id,
            password_hash=password_hash,
            actor_user_id=user_id,
        )
        if updated is None:
            raise UserNotFoundError("Usuário não encontrado")
        return updated

    def create_session(self, user_id: str) -> SessionCredentials:
        user = self._require_user(user_id)
        if not user.active:
            raise InvalidCredentialsError("Credenciais inválidas")
        token = secrets.token_urlsafe(32)
        csrf_token = self._derive_csrf_token(token)
        expires_at = self.clock() + self.session_ttl
        self.repository.create_session(
            user_id=user.id,
            token_hash=self._hash_token(token),
            csrf_token_hash=self._hash_token(csrf_token),
            expires_at=expires_at,
        )
        return SessionCredentials(token=token, csrf_token=csrf_token, expires_at=expires_at)

    def resolve_session(self, token: str | None) -> Session | None:
        if not token:
            return None
        token_hash = self._hash_token(token)
        csrf_token = self._derive_csrf_token(token)
        stored_csrf_hash = self.repository.csrf_hash_for_session(token_hash)
        if stored_csrf_hash is None or not hmac.compare_digest(
            stored_csrf_hash, self._hash_token(csrf_token)
        ):
            return None
        return self.repository.resolve_session(token_hash, csrf_token)

    def revoke_session(self, token: str | None, *, actor_user_id: str | None = None) -> bool:
        if not token:
            return False
        return self.repository.revoke_session(self._hash_token(token), actor_user_id)

    def verify_csrf(self, token: str | None, csrf_token: str | None) -> bool:
        if not token or not csrf_token or self.resolve_session(token) is None:
            return False
        return hmac.compare_digest(self._derive_csrf_token(token), csrf_token)

    def session_payload(self, token: str | None) -> dict[str, object] | None:
        session = self.resolve_session(token)
        if session is None:
            return None
        return {
            "user": session.user.to_dict(),
            "permissions": list(session.user.permissions),
            "csrf_token": session.csrf_token,
            "expires_at": session.expires_at.isoformat(),
        }

    def _require_manager(self, actor_user_id: str) -> User:
        actor = self._require_user(actor_user_id)
        if not actor.active or "users.manage" not in actor.permissions:
            raise InvalidCredentialsError("Permissão users.manage obrigatória")
        return actor

    def _require_user(self, user_id: str) -> User:
        user = self.repository.get_user(user_id)
        if user is None:
            raise UserNotFoundError("Usuário não encontrado")
        return user

    def _normalize_permissions(self, permissions: Iterable[str]) -> tuple[str, ...]:
        requested = {str(permission).strip() for permission in permissions}
        catalog = self.repository.all_permissions()
        unknown = requested.difference(catalog)
        if unknown:
            raise UnknownPermissionError(f"Permissões desconhecidas: {', '.join(sorted(unknown))}")
        return tuple(permission for permission in catalog if permission in requested)

    @staticmethod
    def _validate_username(username: str) -> tuple[str, str]:
        normalized = username.strip()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise InvalidIdentityInputError("Usuário deve ter de 3 a 64 caracteres válidos")
        return normalized, normalized.casefold()

    @staticmethod
    def _validate_display_name(display_name: str) -> str:
        normalized = display_name.strip()
        if not 1 <= len(normalized) <= 100:
            raise InvalidIdentityInputError("Nome de exibição deve ter de 1 a 100 caracteres")
        return normalized

    def _encode_password(
        self,
        password: str | None,
        password_hash: str | None,
        *,
        allow_legacy: bool,
    ) -> str:
        if (password is None) == (password_hash is None):
            raise InvalidIdentityInputError("Informe password ou password_hash, exclusivamente")
        if password is not None:
            if len(password) < MINIMUM_PASSWORD_LENGTH:
                raise InvalidIdentityInputError(
                    f"A senha deve ter pelo menos {MINIMUM_PASSWORD_LENGTH} caracteres"
                )
            return self.password_hasher.hash(password)
        normalized_hash = str(password_hash).strip()
        is_legacy = normalized_hash.startswith("sha256:") or bool(
            re.fullmatch(r"[0-9a-fA-F]{64}", normalized_hash)
        )
        if not normalized_hash.startswith("$argon2id$") and not (allow_legacy and is_legacy):
            raise InvalidIdentityInputError("Formato de hash de senha inválido")
        return normalized_hash

    def _consume_failed_authentication_cost(self, password: str) -> None:
        dummy_hash = DUMMY_ARGON2_HASH if self.password_hasher.available else "sha256:" + ("0" * 64)
        self.password_hasher.verify(password, dummy_hash)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _derive_csrf_token(token: str) -> str:
        digest = hmac.new(token.encode("utf-8"), CSRF_DOMAIN, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_identity_service(
    db_path: Path | str,
    *,
    session_ttl: timedelta = timedelta(hours=8),
    clock: Callable[[], datetime] = _utc_now,
    password_hasher: Argon2PasswordHasher | None = None,
) -> IdentityService:
    """Cria, migra e devolve um serviço isolado para integração pela API."""
    database = IdentityDatabase(db_path)
    database.migrate()
    repository = IdentityRepository(database, clock)
    return IdentityService(
        repository,
        password_hasher=password_hasher,
        session_ttl=session_ttl,
        clock=clock,
    )
