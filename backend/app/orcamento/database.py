"""Conexão SQLite e migrações exclusivas do banco de Orçamento."""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..db.process_lock import migration_lock

MIGRATION_PATTERN = re.compile(r"^V(\d+)__[\w_]+\.sql$")

# A primeira V3 chegou a ser aplicada em ambientes locais antes de sua ordem de
# reconstrução das FKs ser corrigida. O schema final é equivalente e validado
# por foreign_key_check; aceitar somente este hash conhecido preserva o
# histórico sem abrir mão da detecção de alterações arbitrárias.
LEGACY_MIGRATION_CHECKSUMS: dict[int, frozenset[str]] = {
    3: frozenset({"7da4eda253066d5a512f49026c47c7cddb3011f1dd13c11fae2b2d01cd23c9ef"}),
}


def _discover_migrations(migration_dir: Path) -> tuple[tuple[int, Path, str], ...]:
    """Descobre migrações em ordem numérica e rejeita versões ambíguas."""
    discovered: dict[int, tuple[Path, str]] = {}
    for migration_path in migration_dir.glob("V*.sql"):
        match = MIGRATION_PATTERN.match(migration_path.name)
        if match is None:
            continue
        version = int(match.group(1))
        if version in discovered:
            raise RuntimeError(f"Versão de migração de orçamento V{version} está duplicada")
        sql = migration_path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        discovered[version] = (migration_path, checksum)
    return tuple(
        (version, *discovered[version])
        for version in sorted(discovered)
    )


class OrcamentoDatabase:
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
        migrations = _discover_migrations(migration_dir)
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orcamento_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied_rows = connection.execute(
                "SELECT version, checksum FROM orcamento_migrations"
            ).fetchall()
            applied = {int(row["version"]): str(row["checksum"]) for row in applied_rows}

            available_versions = {version for version, _, _ in migrations}
            missing_files = sorted(set(applied) - available_versions)
            if missing_files:
                versions = ", ".join(f"V{version}" for version in missing_files)
                raise RuntimeError(
                    f"Migrações de orçamento aplicadas sem arquivo correspondente: {versions}"
                )

            for version, migration_path, checksum in migrations:
                sql = migration_path.read_text(encoding="utf-8")
                if version in applied:
                    accepted_checksums = LEGACY_MIGRATION_CHECKSUMS.get(version, frozenset())
                    if applied[version] != checksum and applied[version] not in accepted_checksums:
                        raise RuntimeError(f"Migração de orçamento V{version} foi alterada")
                    continue
                # sqlite3.executescript faz commit implícito antes de executar.
                # O BEGIN no próprio script mantém schema + registro da versão
                # na mesma transação controlada pelo context manager.
                connection.executescript(f"BEGIN IMMEDIATE;\n{sql}")
                connection.execute(
                    """
                    INSERT INTO orcamento_migrations (version, name, checksum)
                    VALUES (?, ?, ?)
                    """,
                    (version, migration_path.stem, checksum),
                )
                applied[version] = checksum

            foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise RuntimeError("Migrações de orçamento deixaram referências inválidas")

        return self.applied_migrations()

    def applied_migrations(self) -> tuple[int, ...]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT version FROM orcamento_migrations ORDER BY version"
            ).fetchall()
        return tuple(int(row["version"]) for row in rows)
