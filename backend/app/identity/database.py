"""Conexão SQLite e migrações exclusivas do banco de identidade."""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..db.process_lock import migration_lock

MIGRATION_PATTERN = re.compile(r"^V(\d+)__[\w_]+\.sql$")


class IdentityDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        os.chmod(self.path, 0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Conexão de leitura que sempre é fechada ao sair do bloco."""
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> tuple[int, ...]:
        # Vários workers do uvicorn migram ao mesmo tempo no startup.
        with migration_lock(self.path):
            return self._migrate_locked()

    def _migrate_locked(self) -> tuple[int, ...]:
        migration_dir = Path(__file__).parent / "migrations"
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied_rows = connection.execute(
                "SELECT version, checksum FROM identity_migrations"
            ).fetchall()
            applied = {int(row["version"]): str(row["checksum"]) for row in applied_rows}

            for migration_path in sorted(migration_dir.glob("V*.sql")):
                match = MIGRATION_PATTERN.match(migration_path.name)
                if match is None:
                    continue
                version = int(match.group(1))
                sql = migration_path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise RuntimeError(f"Migração de identidade V{version} foi alterada")
                    continue
                # sqlite3.executescript faz commit implícito antes de executar.
                # O BEGIN no próprio script mantém schema + registro da versão
                # na mesma transação controlada pelo context manager.
                connection.executescript(f"BEGIN IMMEDIATE;\n{sql}")
                connection.execute(
                    """
                    INSERT INTO identity_migrations (version, name, checksum)
                    VALUES (?, ?, ?)
                    """,
                    (version, migration_path.stem, checksum),
                )

        return self.applied_migrations()

    def applied_migrations(self) -> tuple[int, ...]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT version FROM identity_migrations ORDER BY version"
            ).fetchall()
        return tuple(int(row["version"]) for row in rows)
