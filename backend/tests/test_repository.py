"""Testes unitários para camada de persistência DRE."""

import tempfile
from decimal import Decimal
from uuid import uuid4

import pytest

from app.contracts.persistence import (
    DRELancamentoDB,
    DREUpload,
)
from app.db.connection import DatabaseConnection
from app.db.manager import MigrationManager
from app.repository.dre_repository import DRERepository


@pytest.fixture
def temp_db():
    """Cria banco temporário para testes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = DatabaseConnection(db_path)

    # Executa migrações
    manager = MigrationManager(db)
    manager.migrate()

    yield db

    # Cleanup
    db.db_path.unlink(missing_ok=True)


@pytest.fixture
def repo(temp_db):
    """Repository inicializado."""
    return DRERepository(temp_db)


class TestDREUploadRepository:
    """Testes para operações de upload."""

    def test_create_upload(self, repo):
        """Testa criação de upload."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="teste.xls",
            arquivo_sha256="abc123",
            competencia_ano=2025,
            competencia_mes=5,
            status="pending",
            total_linhas=100,
        )

        created = repo.uploads.create(upload)
        assert created.id == upload.id

        # Busca e verifica
        found = repo.uploads.get_by_id(upload.id)
        assert found is not None
        assert found.arquivo_nome == "teste.xls"
        assert found.competencia_ano == 2025

    def test_get_by_sha256(self, repo):
        """Testa busca por hash."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="teste.xls",
            arquivo_sha256="hash_unico_123",
            competencia_ano=2025,
            competencia_mes=5,
        )
        repo.uploads.create(upload)

        found = repo.uploads.get_by_sha256("hash_unico_123")
        assert found is not None
        assert found.id == upload.id

    def test_get_by_sha256_competencia(self, repo):
        """Testa busca por hash + competência."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="teste.xls",
            arquivo_sha256="hash_comp_123",
            competencia_ano=2025,
            competencia_mes=6,
        )
        repo.uploads.create(upload)

        found = repo.uploads.get_by_sha256_competencia("hash_comp_123", 2025, 6)
        assert found is not None
        assert found.id == upload.id

    def test_create_upload_mesmo_hash_em_competencias_diferentes(self, repo):
        """Testa que o mesmo hash pode existir em competências diferentes."""
        upload_jan = DREUpload(
            id=str(uuid4()),
            arquivo_nome="relatorio_jan.xls",
            arquivo_sha256="hash_igual",
            competencia_ano=2025,
            competencia_mes=1,
        )
        upload_fev = DREUpload(
            id=str(uuid4()),
            arquivo_nome="relatorio_fev.xls",
            arquivo_sha256="hash_igual",
            competencia_ano=2025,
            competencia_mes=2,
        )

        repo.uploads.create(upload_jan)
        repo.uploads.create(upload_fev)

        jan = repo.uploads.get_by_sha256_competencia("hash_igual", 2025, 1)
        fev = repo.uploads.get_by_sha256_competencia("hash_igual", 2025, 2)
        assert jan is not None
        assert fev is not None
        assert jan.id != fev.id

    def test_get_by_competencia(self, repo):
        """Testa busca por competência."""
        # Cria uploads para diferentes meses
        for mes in [1, 2, 3]:
            upload = DREUpload(
                id=str(uuid4()),
                arquivo_nome=f"2025_{mes:02d}.xls",
                arquivo_sha256=f"hash_{mes}",
                competencia_ano=2025,
                competencia_mes=mes,
            )
            repo.uploads.create(upload)

        # Busca competência 2
        found = repo.uploads.get_by_competencia(2025, 2)
        assert len(found) == 1
        assert found[0].competencia_mes == 2

    def test_get_by_ano(self, repo):
        """Testa busca de uploads por ano."""
        upload_2024 = DREUpload(
            id=str(uuid4()),
            arquivo_nome="2024_12.xls",
            arquivo_sha256="hash_2024",
            competencia_ano=2024,
            competencia_mes=12,
        )
        upload_2025 = DREUpload(
            id=str(uuid4()),
            arquivo_nome="2025_01.xls",
            arquivo_sha256="hash_2025",
            competencia_ano=2025,
            competencia_mes=1,
        )
        repo.uploads.create(upload_2024)
        repo.uploads.create(upload_2025)

        found = repo.uploads.get_by_ano(2025)
        assert len(found) == 1
        assert found[0].competencia_ano == 2025
        assert found[0].id == upload_2025.id

    def test_update_status(self, repo):
        """Testa atualização de status."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="teste.xls",
            arquivo_sha256="abc",
            competencia_ano=2025,
            competencia_mes=5,
            status="pending",
        )
        repo.uploads.create(upload)

        # Atualiza
        upload.status = "completed"
        upload.linhas_validas = 50
        repo.uploads.update(upload)

        # Verifica
        found = repo.uploads.get_by_id(upload.id)
        assert found.status == "completed"
        assert found.linhas_validas == 50

    def test_delete_upload(self, repo):
        """Testa remoção de upload."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="teste.xls",
            arquivo_sha256="abc",
            competencia_ano=2025,
            competencia_mes=5,
        )
        repo.uploads.create(upload)

        # Deleta
        result = repo.uploads.delete(upload.id)
        assert result is True

        # Verifica que não existe mais
        found = repo.uploads.get_by_id(upload.id)
        assert found is None


class TestDRELancamentoRepository:
    """Testes para operações de lançamentos."""

    def test_create_lancamento(self, repo):
        """Testa criação de lançamento."""
        lanc = DRELancamentoDB(
            upload_id="upload_123",
            competencia_ano=2025,
            competencia_mes=5,
            data_lancamento="2025-05-15",
            historico="Teste",
            credito=Decimal("1000.00"),
            debito=Decimal("0"),
            hash_linha="hash123",
        )

        created = repo.lancamentos.create(lanc)
        assert created.id is not None
        assert created.historico == "Teste"

    def test_create_many(self, repo):
        """Testa criação em lote."""
        lancamentos = [
            DRELancamentoDB(
                upload_id="upload_123",
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento=f"2025-05-{i:02d}",
                historico=f"Lançamento {i}",
                credito=Decimal(f"{i * 100}.00"),
                debito=Decimal("0"),
                hash_linha=f"hash_{i}",
            )
            for i in range(1, 6)
        ]

        created = repo.lancamentos.create_many(lancamentos)
        assert len(created) == 5

    def test_get_by_competencia(self, repo):
        """Testa busca por competência."""
        # Cria lançamentos para mês 5
        for i in range(3):
            lanc = DRELancamentoDB(
                upload_id="upload_1",
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-15",
                historico=f"Lançamento {i}",
                credito=Decimal("100.00"),
                debito=Decimal("0"),
                hash_linha=f"hash_{i}",
            )
            repo.lancamentos.create(lanc)

        found = repo.lancamentos.get_by_competencia(2025, 5)
        assert len(found) == 3

    def test_get_ytd(self, repo):
        """Testa busca YTD."""
        # Cria lançamentos para meses 1, 2, 3
        for mes in [1, 2, 3]:
            for i in range(2):
                lanc = DRELancamentoDB(
                    upload_id=f"upload_{mes}",
                    competencia_ano=2025,
                    competencia_mes=mes,
                    data_lancamento=f"2025-{mes:02d}-15",
                    historico=f"Lançamento {mes}-{i}",
                    credito=Decimal(f"{mes * 100}.00"),
                    debito=Decimal("0"),
                    hash_linha=f"hash_{mes}_{i}",
                )
                repo.lancamentos.create(lanc)

        # Busca YTD até mês 2
        ytd = repo.lancamentos.get_ytd(2025, 2)
        assert len(ytd) == 4  # 2 lançamentos x 2 meses

    def test_get_agregado_por_conta_mes(self, repo):
        """Testa agregação para aba APOIO."""
        # Cria lançamentos com diferentes contas
        contas = ["Receitas", "Despesas", "Receitas"]
        for i, conta in enumerate(contas):
            lanc = DRELancamentoDB(
                upload_id="upload_1",
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-15",
                historico=f"Lançamento {i}",
                credito=Decimal("1000.00") if conta == "Receitas" else Decimal("0"),
                debito=Decimal("500.00") if conta == "Despesas" else Decimal("0"),
                conta_pai=conta,
                hash_linha=f"hash_{i}",
            )
            repo.lancamentos.create(lanc)

        agregado = repo.lancamentos.get_agregado_por_conta_mes(2025, 5)
        assert len(agregado) == 2  # 2 contas distintas

        receitas = next(a for a in agregado if a["conta_pai"] == "Receitas")
        assert receitas["credito"] == 2000.0  # 2 lançamentos de 1000


class TestDRERepositoryUpsert:
    """Testes para upsert transacional."""

    def test_upsert_nova_competencia(self, repo):
        """Testa upsert de nova competência."""
        upload = DREUpload(
            id=str(uuid4()),
            arquivo_nome="05_2025.xls",
            arquivo_sha256="hash_05",
            competencia_ano=2025,
            competencia_mes=5,
        )

        lancamentos = [
            DRELancamentoDB(
                upload_id=upload.id,
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-15",
                historico="Lançamento 1",
                credito=Decimal("1000.00"),
                debito=Decimal("0"),
                hash_linha="hash_001",
            ),
            DRELancamentoDB(
                upload_id=upload.id,
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-16",
                historico="Lançamento 2",
                credito=Decimal("0"),
                debito=Decimal("500.00"),
                hash_linha="hash_002",
            ),
        ]

        upload_atualizado, removidos, inseridos = repo.upsert_competencia(upload, lancamentos)

        assert upload_atualizado.status == "completed"
        assert upload_atualizado.total_linhas == 2
        assert removidos == 0
        assert inseridos == 2

    def test_upsert_substitui_competencia(self, repo):
        """Testa que upsert substitui competência existente."""
        # Primeiro upload
        upload1 = DREUpload(
            id=str(uuid4()),
            arquivo_nome="05_2025_v1.xls",
            arquivo_sha256="hash_v1",
            competencia_ano=2025,
            competencia_mes=5,
        )
        lancamentos1 = [
            DRELancamentoDB(
                upload_id=upload1.id,
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-15",
                historico="Lançamento antigo",
                credito=Decimal("100.00"),
                debito=Decimal("0"),
                hash_linha="hash_v1_001",
            )
        ]
        repo.upsert_competencia(upload1, lancamentos1)

        # Segundo upload (substitui)
        upload2 = DREUpload(
            id=str(uuid4()),
            arquivo_nome="05_2025_v2.xls",
            arquivo_sha256="hash_v2",
            competencia_ano=2025,
            competencia_mes=5,
        )
        lancamentos2 = [
            DRELancamentoDB(
                upload_id=upload2.id,
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-20",
                historico="Lançamento novo",
                credito=Decimal("200.00"),
                debito=Decimal("0"),
                hash_linha="hash_v2_001",
            )
        ]

        upload_atualizado, removidos, inseridos = repo.upsert_competencia(upload2, lancamentos2)

        assert removidos == 1  # Removeu o lançamento antigo
        assert inseridos == 1  # Inseriu o novo

        # Verifica que só existe o novo
        all_lancs = repo.lancamentos.get_by_competencia(2025, 5)
        assert len(all_lancs) == 1
        assert all_lancs[0].historico == "Lançamento novo"

    def test_get_resumo_ytd(self, repo):
        """Testa resumo YTD."""
        # Cria lançamentos para meses 1-3
        for mes in [1, 2, 3]:
            for i in range(mes):  # mês 1 = 1 lanç, mês 2 = 2 lanç, etc.
                lanc = DRELancamentoDB(
                    upload_id=f"upload_{mes}",
                    competencia_ano=2025,
                    competencia_mes=mes,
                    data_lancamento=f"2025-{mes:02d}-15",
                    historico=f"Lançamento {mes}-{i}",
                    credito=Decimal("100.00"),
                    debito=Decimal("0"),
                    hash_linha=f"hash_{mes}_{i}",
                )
                repo.lancamentos.create(lanc)

        resumo = repo.get_resumo_ytd(2025, 3)

        assert resumo["total_lancamentos"] == 6  # 1 + 2 + 3
        assert resumo["total_credito"] == Decimal("600.00")  # 6 x 100
        assert resumo["ano"] == 2025
        assert resumo["mes_final"] == 3

    def test_limpar_dados_por_competencia(self, repo):
        """Testa limpeza transacional por ano+mês."""
        upload_mai = DREUpload(
            id=str(uuid4()),
            arquivo_nome="05_2025.xls",
            arquivo_sha256="hash_05",
            competencia_ano=2025,
            competencia_mes=5,
            status="completed",
        )
        upload_jun = DREUpload(
            id=str(uuid4()),
            arquivo_nome="06_2025.xls",
            arquivo_sha256="hash_06",
            competencia_ano=2025,
            competencia_mes=6,
            status="completed",
        )
        repo.uploads.create(upload_mai)
        repo.uploads.create(upload_jun)

        repo.lancamentos.create(
            DRELancamentoDB(
                upload_id=upload_mai.id,
                competencia_ano=2025,
                competencia_mes=5,
                data_lancamento="2025-05-15",
                historico="Mai",
                credito=Decimal("100.00"),
                debito=Decimal("0"),
                hash_linha="hash_mai",
            )
        )
        repo.lancamentos.create(
            DRELancamentoDB(
                upload_id=upload_jun.id,
                competencia_ano=2025,
                competencia_mes=6,
                data_lancamento="2025-06-15",
                historico="Jun",
                credito=Decimal("200.00"),
                debito=Decimal("0"),
                hash_linha="hash_jun",
            )
        )

        resultado = repo.limpar_dados(ano=2025, mes=6)
        assert resultado["uploads_removidos"] == 1
        assert resultado["lancamentos_removidos"] == 1

        uploads_2025_06 = repo.uploads.get_by_competencia(2025, 6)
        lancs_2025_06 = repo.lancamentos.get_by_competencia(2025, 6)
        assert uploads_2025_06 == []
        assert lancs_2025_06 == []

        # Dados de maio devem permanecer
        uploads_2025_05 = repo.uploads.get_by_competencia(2025, 5)
        lancs_2025_05 = repo.lancamentos.get_by_competencia(2025, 5)
        assert len(uploads_2025_05) == 1
        assert len(lancs_2025_05) == 1


class TestMigrationManager:
    """Testes para gerenciador de migrações."""

    def test_migrate_creates_tables(self, temp_db):
        """Testa que migrações criam tabelas."""
        # Verifica que tabelas existem
        rows = temp_db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dre_%'"
        )
        table_names = {row["name"] for row in rows}

        assert "dre_uploads" in table_names
        assert "dre_lancamentos" in table_names

    def test_migrate_idempotent(self, temp_db):
        """Testa que migrações são idempotentes."""
        manager = MigrationManager(temp_db)

        # Executa duas vezes
        manager.migrate()
        result2 = manager.migrate()

        # Segunda vez não deve executar nada novo
        assert len(result2) == 0

    def test_migration_status(self, temp_db):
        """Testa status de migrações."""
        manager = MigrationManager(temp_db)
        manager.migrate()

        status = manager.status()
        assert status["is_up_to_date"] is True
        assert status["total_pending"] == 0
        assert status["total_executed"] >= 1
