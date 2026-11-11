"""Repositório transacional do domínio de identidade."""

import json
import sqlite3
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any
from uuid import uuid4

from .database import IdentityDatabase
from .exceptions import InvalidCredentialsError, UsernameAlreadyExistsError
from .models import AuditEvent, Session, User

SESSION_TOUCH_SECONDS = 60


def _serialize_time(value: datetime) -> str:
    return value.isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


class IdentityRepository:
    def __init__(self, database: IdentityDatabase, clock: Callable[[], datetime]):
        self.database = database
        self.clock = clock

    def applied_migrations(self) -> tuple[int, ...]:
        return self.database.applied_migrations()

    def all_permissions(self) -> tuple[str, ...]:
        with self.database.connection() as connection:
            rows = connection.execute("SELECT code FROM permissions ORDER BY position").fetchall()
        return tuple(str(row["code"]) for row in rows)

    def get_user(self, user_id: str) -> User | None:
        with self.database.connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(connection, row) if row is not None else None

    def get_user_by_username(self, username_key: str) -> User | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username_key = ?", (username_key,)
            ).fetchone()
            return self._row_to_user(connection, row) if row is not None else None

    def password_hash_for(self, user_id: str) -> str | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return str(row["password_hash"]) if row is not None else None

    def password_hash_by_username(self, username_key: str) -> tuple[str, str, bool] | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT id, password_hash, active FROM users WHERE username_key = ?",
                (username_key,),
            ).fetchone()
        if row is None:
            return None
        return str(row["id"]), str(row["password_hash"]), bool(row["active"])

    def list_users(self) -> tuple[User, ...]:
        with self.database.connection() as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY rowid").fetchall()
            return tuple(self._row_to_user(connection, row) for row in rows)

    def create_user(
        self,
        *,
        username: str,
        username_key: str,
        display_name: str,
        password_hash: str,
        active: bool,
        is_system_owner: bool,
        must_change_password: bool,
        permissions: tuple[str, ...],
        actor_user_id: str | None,
    ) -> User:
        user_id = str(uuid4())
        timestamp = _serialize_time(self.clock())
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        id, username, username_key, display_name, password_hash,
                        active, is_system_owner, must_change_password, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        username_key,
                        display_name,
                        password_hash,
                        int(active),
                        int(is_system_owner),
                        int(must_change_password),
                        timestamp,
                        timestamp,
                    ),
                )
                self._insert_permissions(connection, user_id, permissions, timestamp, actor_user_id)
                self._insert_audit(
                    connection,
                    "user.created",
                    actor_user_id,
                    user_id,
                    {"username": username, "permissions": list(permissions)},
                    timestamp,
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                return self._row_to_user(connection, row)
        except sqlite3.IntegrityError as error:
            if "users.username_key" in str(error):
                raise UsernameAlreadyExistsError("Nome de usuário já cadastrado") from error
            raise

    def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None,
        active: bool | None,
        password_hash: str | None,
        actor_user_id: str | None,
    ) -> User | None:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            existing = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if existing is None:
                return None
            next_display_name = (
                display_name if display_name is not None else existing["display_name"]
            )
            next_active = int(active) if active is not None else int(existing["active"])
            next_password_hash = (
                password_hash if password_hash is not None else existing["password_hash"]
            )
            connection.execute(
                """
                UPDATE users
                SET display_name = ?, active = ?, password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_display_name, next_active, next_password_hash, timestamp, user_id),
            )
            if active is False or password_hash is not None:
                connection.execute(
                    """
                    UPDATE sessions
                    SET revoked_at = ?, revoked_by_user_id = ?
                    WHERE user_id = ? AND revoked_at IS NULL
                    """,
                    (timestamp, actor_user_id, user_id),
                )
            changed_fields = [
                field
                for field, changed in (
                    ("display_name", display_name is not None),
                    ("active", active is not None),
                    ("password", password_hash is not None),
                )
                if changed
            ]
            self._insert_audit(
                connection,
                "user.updated",
                actor_user_id,
                user_id,
                {"changed_fields": changed_fields},
                timestamp,
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(connection, row)

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, timestamp, user_id),
            )
            self._insert_audit(connection, "password.rehashed", user_id, user_id, {}, timestamp)

    def delete_user(self, user_id: str, *, actor_user_id: str) -> bool:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            self._require_active_manager(connection, actor_user_id)
            existing = connection.execute(
                "SELECT username, is_system_owner FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if existing is None or existing["is_system_owner"] or user_id == actor_user_id:
                return False
            self._preserve_deleted_user_audit_ids(connection, user_id)
            self._insert_audit(
                connection,
                "user.deleted",
                actor_user_id,
                user_id,
                {"user_id": user_id, "username": str(existing["username"])},
                timestamp,
            )
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return True

    @staticmethod
    def _require_active_manager(connection: sqlite3.Connection, actor_user_id: str) -> None:
        row = connection.execute(
            """
            SELECT active, must_change_password,
                   EXISTS(
                       SELECT 1 FROM user_permissions
                       WHERE user_id = users.id AND permission_code = 'users.manage'
                   ) AS can_manage
            FROM users WHERE id = ?
            """,
            (actor_user_id,),
        ).fetchone()
        if row is None or not row["active"] or row["must_change_password"] or not row["can_manage"]:
            raise InvalidCredentialsError("Permissão users.manage obrigatória")

    @staticmethod
    def _preserve_deleted_user_audit_ids(
        connection: sqlite3.Connection, user_id: str
    ) -> None:
        rows = connection.execute(
            """
            SELECT id, actor_user_id, target_user_id, metadata_json
            FROM audit_events
            WHERE actor_user_id = ? OR target_user_id = ?
            """,
            (user_id, user_id),
        ).fetchall()
        for row in rows:
            metadata = json.loads(str(row["metadata_json"]))
            if row["actor_user_id"] == user_id:
                metadata["deleted_actor_user_id"] = user_id
            if row["target_user_id"] == user_id:
                metadata["deleted_target_user_id"] = user_id
            connection.execute(
                "UPDATE audit_events SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata, ensure_ascii=False), row["id"]),
            )

    def replace_permissions(
        self,
        user_id: str,
        permissions: tuple[str, ...],
        actor_user_id: str | None,
    ) -> User | None:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
            self._insert_permissions(connection, user_id, permissions, timestamp, actor_user_id)
            connection.execute("UPDATE users SET updated_at = ? WHERE id = ?", (timestamp, user_id))
            self._insert_audit(
                connection,
                "permissions.replaced",
                actor_user_id,
                user_id,
                {"permissions": list(permissions)},
                timestamp,
            )
            updated_row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return self._row_to_user(connection, updated_row)

    def update_user_access(
        self,
        user_id: str,
        *,
        display_name: str | None,
        active: bool | None,
        password_hash: str | None,
        permissions: tuple[str, ...] | None,
        must_change_password: bool | None,
        actor_user_id: str,
    ) -> User | None:
        """Atualiza perfil e acessos em uma única transação."""
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            self._require_active_manager(connection, actor_user_id)
            existing = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if existing is None:
                return None

            connection.execute(
                """
                UPDATE users
                SET display_name = ?, active = ?, password_hash = ?,
                    must_change_password = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name if display_name is not None else existing["display_name"],
                    int(active) if active is not None else int(existing["active"]),
                    password_hash if password_hash is not None else existing["password_hash"],
                    (
                        int(must_change_password)
                        if must_change_password is not None
                        else int(existing["must_change_password"])
                    ),
                    timestamp,
                    user_id,
                ),
            )
            if active is False or password_hash is not None:
                connection.execute(
                    """
                    UPDATE sessions
                    SET revoked_at = ?, revoked_by_user_id = ?
                    WHERE user_id = ? AND revoked_at IS NULL
                    """,
                    (timestamp, actor_user_id, user_id),
                )
            if permissions is not None:
                connection.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
                self._insert_permissions(connection, user_id, permissions, timestamp, actor_user_id)
                self._insert_audit(
                    connection,
                    "permissions.replaced",
                    actor_user_id,
                    user_id,
                    {"permissions": list(permissions)},
                    timestamp,
                )

            changed_fields = [
                field
                for field, changed in (
                    ("display_name", display_name is not None),
                    ("active", active is not None),
                    ("password", password_hash is not None),
                    ("permissions", permissions is not None),
                    ("must_change_password", must_change_password is not None),
                )
                if changed
            ]
            self._insert_audit(
                connection,
                "user.updated",
                actor_user_id,
                user_id,
                {"changed_fields": changed_fields},
                timestamp,
            )
            updated_row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return self._row_to_user(connection, updated_row)

    def change_password(
        self,
        user_id: str,
        *,
        password_hash: str,
        actor_user_id: str,
    ) -> User | None:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, must_change_password = 0, updated_at = ?
                WHERE id = ?
                """,
                (password_hash, timestamp, user_id),
            )
            connection.execute(
                """
                UPDATE sessions
                SET revoked_at = ?, revoked_by_user_id = ?
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (timestamp, actor_user_id, user_id),
            )
            self._insert_audit(
                connection,
                "password.changed",
                actor_user_id,
                user_id,
                {},
                timestamp,
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(connection, row)

    def create_session(
        self,
        *,
        user_id: str,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> tuple[str, datetime]:
        session_id = str(uuid4())
        created_at = self.clock()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    id, user_id, token_hash, csrf_token_hash, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    token_hash,
                    csrf_token_hash,
                    _serialize_time(created_at),
                    _serialize_time(expires_at),
                ),
            )
            self._insert_audit(
                connection, "session.created", user_id, user_id, {}, _serialize_time(created_at)
            )
        return session_id, created_at

    def resolve_session(self, token_hash: str, csrf_token: str) -> Session | None:
        now = self.clock()
        # Leitura sem trava de escrita: cada requisição autenticada resolve a
        # sessão (duas vezes quando há CSRF). BEGIN IMMEDIATE aqui serializava
        # todas as requisições de todos os workers no banco de identidade.
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT s.*, u.active
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                  AND s.revoked_at IS NULL
                  AND s.expires_at > ?
                  AND u.active = 1
                """,
                (token_hash, _serialize_time(now)),
            ).fetchone()
            if row is None:
                return None
            user_row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (row["user_id"],)
            ).fetchone()
            if self._session_touch_due(row["last_used_at"], now):
                connection.execute(
                    "UPDATE sessions SET last_used_at = ? WHERE id = ?",
                    (_serialize_time(now), row["id"]),
                )
                connection.commit()
            return Session(
                id=str(row["id"]),
                user=self._row_to_user(connection, user_row),
                csrf_token=csrf_token,
                created_at=_parse_time(str(row["created_at"])),
                expires_at=_parse_time(str(row["expires_at"])),
            )

    @staticmethod
    def _session_touch_due(last_used_at: str | None, now: datetime) -> bool:
        """`last_used_at` é informativo; gravá-lo no máximo uma vez por minuto."""
        if not last_used_at:
            return True
        try:
            return (now - _parse_time(str(last_used_at))).total_seconds() >= SESSION_TOUCH_SECONDS
        except (TypeError, ValueError):
            return True

    def register_login_attempt(
        self,
        attempt_key: str,
        *,
        now: float,
        window_seconds: float,
        max_attempts: int,
    ) -> bool:
        """Registra a tentativa se ainda houver cota; devolve False quando bloqueada.

        Contagem e inserção acontecem na mesma transação BEGIN IMMEDIATE, então
        workers concorrentes não conseguem ultrapassar o limite juntos.
        """
        cutoff = now - window_seconds
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM login_attempts
                WHERE attempt_key = ? AND attempted_at >= ?
                """,
                (attempt_key, cutoff),
            ).fetchone()
            if int(row["total"]) >= max_attempts:
                return False
            connection.execute(
                "INSERT INTO login_attempts (attempt_key, attempted_at) VALUES (?, ?)",
                (attempt_key, now),
            )
        return True

    def clear_login_attempts(self, attempt_key: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (attempt_key,))

    def clear_all_login_attempts(self) -> None:
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM login_attempts")

    def csrf_hash_for_session(self, token_hash: str) -> str | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT csrf_token_hash FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        return str(row["csrf_token_hash"]) if row is not None else None

    def revoke_session(self, token_hash: str, actor_user_id: str | None) -> bool:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT id, user_id, revoked_at FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is None:
                return False
            if row["revoked_at"] is None:
                connection.execute(
                    """
                    UPDATE sessions
                    SET revoked_at = ?, revoked_by_user_id = ?
                    WHERE id = ?
                    """,
                    (timestamp, actor_user_id, row["id"]),
                )
                self._insert_audit(
                    connection,
                    "session.revoked",
                    actor_user_id,
                    str(row["user_id"]),
                    {},
                    timestamp,
                )
            return True

    def list_audit_events(self) -> tuple[AuditEvent, ...]:
        with self.database.connection() as connection:
            rows = connection.execute("SELECT * FROM audit_events ORDER BY rowid").fetchall()
        return tuple(
            AuditEvent(
                id=str(row["id"]),
                event_type=str(row["event_type"]),
                actor_user_id=row["actor_user_id"],
                target_user_id=row["target_user_id"],
                metadata=json.loads(str(row["metadata_json"])),
                created_at=_parse_time(str(row["created_at"])),
            )
            for row in rows
        )

    def record_audit(
        self,
        event_type: str,
        *,
        actor_user_id: str | None,
        target_user_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        timestamp = _serialize_time(self.clock())
        with self.database.transaction() as connection:
            self._insert_audit(
                connection,
                event_type,
                actor_user_id,
                target_user_id,
                metadata or {},
                timestamp,
            )

    @staticmethod
    def _insert_permissions(
        connection: sqlite3.Connection,
        user_id: str,
        permissions: Iterable[str],
        granted_at: str,
        actor_user_id: str | None,
    ) -> None:
        connection.executemany(
            """
            INSERT INTO user_permissions (
                user_id, permission_code, granted_at, granted_by_user_id
            ) VALUES (?, ?, ?, ?)
            """,
            [(user_id, permission, granted_at, actor_user_id) for permission in permissions],
        )

    @staticmethod
    def _insert_audit(
        connection: sqlite3.Connection,
        event_type: str,
        actor_user_id: str | None,
        target_user_id: str | None,
        metadata: dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events (
                id, event_type, actor_user_id, target_user_id, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                event_type,
                actor_user_id,
                target_user_id,
                json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                created_at,
            ),
        )

    @staticmethod
    def _row_to_user(connection: sqlite3.Connection, row: sqlite3.Row) -> User:
        permission_rows = connection.execute(
            """
            SELECT p.code
            FROM user_permissions up
            JOIN permissions p ON p.code = up.permission_code
            WHERE up.user_id = ?
            ORDER BY p.position
            """,
            (row["id"],),
        ).fetchall()
        return User(
            id=str(row["id"]),
            username=str(row["username"]),
            display_name=str(row["display_name"]),
            active=bool(row["active"]),
            is_system_owner=bool(row["is_system_owner"]),
            must_change_password=bool(row["must_change_password"]),
            permissions=tuple(str(item["code"]) for item in permission_rows),
            created_at=_parse_time(str(row["created_at"])),
            updated_at=_parse_time(str(row["updated_at"])),
        )
