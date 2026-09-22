"""Migrações do banco de Orçamento preservam revisões e eventos existentes."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.orcamento.database import OrcamentoDatabase, _discover_migrations

CHECKSUM_V3_LEGADO = "7da4eda253066d5a512f49026c47c7cddb3011f1dd13c11fae2b2d01cd23c9ef"


def _aplicar_migracao_legada(connection: sqlite3.Connection, version: int) -> None:
    migration_dir = Path(__file__).parents[1] / "app" / "orcamento" / "migrations"
    migration_path = next(migration_dir.glob(f"V{version}__*.sql"))
    sql = migration_path.read_text(encoding="utf-8")
    connection.executescript(sql)
    connection.execute(
        "INSERT INTO orcamento_migrations (version, name, checksum) VALUES (?, ?, ?)",
        (
            version,
            migration_path.stem,
            hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        ),
    )


def test_v3_migra_base_v2_com_revisao_e_evento(tmp_path):
    database_path = tmp_path / "orcamento.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE orcamento_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _aplicar_migracao_legada(connection, 1)
        _aplicar_migracao_legada(connection, 2)
        connection.execute(
            """
            INSERT INTO orcamentos (
                id, codigo, codigo_key, contratante, criado_por_user_id,
                created_at, updated_at, sequencial
            ) VALUES ('o1', 'ORC-0001', 'orc-0001', 'AIDEAL', 'u1', '2026-08-27',
                      '2026-08-27', 1)
            """
        )
        connection.execute(
            """
            INSERT INTO orcamento_revisoes (
                id, orcamento_id, numero, situacao, escopo, versao_regras,
                autor_user_id, valido_ate, created_at
            ) VALUES ('r1', 'o1', 1, 'em_elaboracao', 'Escopo', 'v1', 'u1',
                      '2026-09-26', '2026-08-27')
            """
        )
        connection.execute(
            """
            INSERT INTO orcamento_situacao_eventos (
                id, revisao_id, situacao, motivo, responsavel_user_id, created_at
            ) VALUES ('e1', 'r1', 'em_elaboracao', 'criação', 'u1', '2026-08-27')
            """
        )

    database = OrcamentoDatabase(database_path)
    assert database.migrate() == (1, 2, 3, 4, 5, 6)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        revisao = connection.execute(
            "SELECT situacao, dfp_payload FROM orcamento_revisoes WHERE id = 'r1'"
        ).fetchone()
        evento = connection.execute(
            "SELECT situacao FROM orcamento_situacao_eventos WHERE id = 'e1'"
        ).fetchone()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert revisao == ("rascunho", "{}")
    assert evento == ("rascunho",)
    assert foreign_key_errors == []


def test_v3_aceita_checksum_legado_conhecido_sem_reescrever_historico(tmp_path):
    database_path = tmp_path / "orcamento.db"
    database = OrcamentoDatabase(database_path)
    assert database.migrate() == (1, 2, 3, 4, 5, 6)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE orcamento_migrations SET checksum = ? WHERE version = 3",
            (CHECKSUM_V3_LEGADO,),
        )

    assert database.migrate() == (1, 2, 3, 4, 5, 6)
    with sqlite3.connect(database_path) as connection:
        checksum = connection.execute(
            "SELECT checksum FROM orcamento_migrations WHERE version = 3"
        ).fetchone()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert checksum == (CHECKSUM_V3_LEGADO,)
    assert foreign_key_errors == []


def test_descoberta_de_migracoes_ordena_numericamente_e_rejeita_duplicidade(tmp_path):
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "V10__dez.sql").write_text("SELECT 10;", encoding="utf-8")
    (migration_dir / "V2__dois.sql").write_text("SELECT 2;", encoding="utf-8")
    assert [version for version, _, _ in _discover_migrations(migration_dir)] == [2, 10]

    (migration_dir / "V2__duplicada.sql").write_text("SELECT 22;", encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicada"):
        _discover_migrations(migration_dir)


def test_migrate_rejeita_versao_aplicada_sem_arquivo_correspondente(tmp_path):
    database_path = tmp_path / "orcamento.db"
    database = OrcamentoDatabase(database_path)
    database.migrate()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO orcamento_migrations(version, name, checksum) VALUES (99, 'apagada', 'x')"
        )

    with pytest.raises(RuntimeError, match="sem arquivo correspondente"):
        database.migrate()


def test_v6_preserva_catalogo_atual_como_primeira_versao_historica(tmp_path):
    database_path = tmp_path / "orcamento.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE orcamento_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for version in range(1, 6):
            _aplicar_migracao_legada(connection, version)
        connection.execute(
            """
            INSERT INTO orcamento_catalogo (
                id, payload, responsavel_user_id, updated_at
            ) VALUES (1, ?, 'u1', '2026-09-14T12:00:00+00:00')
            """,
            ('{"funcoes":[{"nome":"Pintor","salario_real":2200}],"itens":[],"custo_administrativo_diario":100}',),
        )

    database = OrcamentoDatabase(database_path)
    assert database.migrate() == (1, 2, 3, 4, 5, 6)
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT versao, payload, responsavel_user_id, vigente_desde, vigente_ate, created_at
            FROM orcamento_catalogo_historico
            """
        ).fetchone()
    assert row == (
        1,
        '{"funcoes":[{"nome":"Pintor","salario_real":2200}],"itens":[],"custo_administrativo_diario":100}',
        "u1",
        "2026-09-14T12:00:00+00:00",
        None,
        "2026-09-14T12:00:00+00:00",
    )
