"""Gerenciamento de conexão com banco de dados."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ..config import settings


class DatabaseConnection:
    """Gerenciador de conexão SQLite com suporte futuro a D1."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else settings.db_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Garante que o diretório do banco existe."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager para conexão SQLite."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager para transação atômica."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        """Executa SQL simples."""
        with self.get_connection() as conn:
            return conn.execute(sql, params or ())

    def execute_many(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Executa SQL em lote."""
        with self.get_connection() as conn:
            return conn.executemany(sql, params_list)

    def fetch_one(self, sql: str, params: tuple | None = None) -> sqlite3.Row | None:
        """Retorna uma única linha."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchone()

    def fetch_all(self, sql: str, params: tuple | None = None) -> list[sqlite3.Row]:
        """Retorna todas as linhas."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchall()

    def fetch_val(self, sql: str, params: tuple | None = None) -> any:
        """Retorna o primeiro valor da primeira linha."""
        row = self.fetch_one(sql, params)
        if row:
            return row[0]
        return None


# Instância global
db = DatabaseConnection()
