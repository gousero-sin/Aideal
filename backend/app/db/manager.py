"""Executor de migrações SQL."""

import logging
import re
from pathlib import Path

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)

MIGRATION_PATTERN = re.compile(r"^V(\d+)__([\w_]+)\.sql$")


class MigrationManager:
    """Gerencia a execução de migrações SQL."""

    def __init__(self, db: DatabaseConnection, migrations_dir: Path | None = None):
        self.db = db
        self.migrations_dir = migrations_dir or Path(__file__).parent.parent / "migrations"

    def _ensure_migrations_table(self) -> None:
        """Cria tabela de controle de migrações se não existir."""
        sql = """
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT
        )
        """
        self.db.execute(sql)

    def _get_executed_migrations(self) -> set[int]:
        """Retorna versões já executadas."""
        try:
            rows = self.db.fetch_all("SELECT version FROM _migrations")
            return {row["version"] for row in rows}
        except Exception:
            return set()

    def _get_available_migrations(self) -> list[tuple[int, str, Path]]:
        """Lista migrações disponíveis no diretório."""
        migrations = []
        if not self.migrations_dir.exists():
            logger.warning("Diretório de migrações não encontrado: %s", self.migrations_dir)
            return migrations

        for file in sorted(self.migrations_dir.glob("V*.sql")):
            match = MIGRATION_PATTERN.match(file.name)
            if match:
                version = int(match.group(1))
                name = match.group(2)
                migrations.append((version, name, file))

        return sorted(migrations)

    def migrate(self) -> list[tuple[int, str]]:
        """Executa todas as migrações pendentes."""
        self._ensure_migrations_table()

        executed = self._get_executed_migrations()
        available = self._get_available_migrations()

        executed_migrations = []

        for version, name, file_path in available:
            if version in executed:
                logger.debug("Migração %d (%s) já executada, pulando", version, name)
                continue

            logger.info("Executando migração %d: %s", version, name)

            # Ler e executar SQL
            sql = file_path.read_text(encoding="utf-8")

            with self.db.transaction() as conn:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO _migrations (version, name, checksum) VALUES (?, ?, ?)",
                    (version, name, self._compute_checksum(sql)),
                )

            executed_migrations.append((version, name))
            logger.info("Migração %d executada com sucesso", version)

        return executed_migrations

    def _compute_checksum(self, content: str) -> str:
        """Calcula checksum simples do conteúdo."""
        import hashlib

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def status(self) -> dict:
        """Retorna status atual das migrações."""
        self._ensure_migrations_table()

        executed = self._get_executed_migrations()
        available = self._get_available_migrations()

        pending = [v for v, _, _ in available if v not in executed]

        return {
            "total_executed": len(executed),
            "total_available": len(available),
            "total_pending": len(pending),
            "executed_versions": sorted(executed),
            "pending_versions": pending,
            "is_up_to_date": len(pending) == 0,
        }


def run_migrations(db: DatabaseConnection | None = None) -> list[tuple[int, str]]:
    """Função utilitária para executar migrações."""
    if db is None:
        from .connection import db
    manager = MigrationManager(db)
    return manager.migrate()
