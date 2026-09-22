import sqlite3

from app.identity import create_identity_service


def test_factory_migrates_an_isolated_identity_database(tmp_path):
    database_path = tmp_path / "identity.db"

    create_identity_service(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        permissions = {
            row[0] for row in connection.execute("SELECT code FROM permissions").fetchall()
        }

    assert {
        "identity_migrations",
        "users",
        "permissions",
        "user_permissions",
        "sessions",
        "audit_events",
    }.issubset(tables)
    user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    assert "must_change_password" in user_columns
    assert permissions == {
        "dre.view",
        "fluxo.view",
        "admin_banco.use",
        "users.manage",
        "orcamento.view",
        "orcamento.edit",
        "orcamento.transition",
    }


def test_migrations_are_idempotent(tmp_path):
    database_path = tmp_path / "identity.db"

    first_service = create_identity_service(database_path)
    second_service = create_identity_service(database_path)

    assert first_service.repository.applied_migrations() == (1, 2, 3)
    assert second_service.repository.applied_migrations() == (1, 2, 3)


def test_identity_database_is_owner_read_write_only(tmp_path):
    database_path = tmp_path / "identity.db"

    create_identity_service(database_path)

    assert database_path.stat().st_mode & 0o777 == 0o600
