"""Repository para persistência de Fluxo de Caixa."""

import hashlib
import logging
import sqlite3
from decimal import Decimal
from typing import Any

from ..contracts.persistence import FluxoMovimentoDB, FluxoUpload
from ..db.connection import DatabaseConnection
from ..db.manager import run_migrations
from .base import Repository
from .contas_gerenciais import ContaGerencialRepository
from .dre_repository import _get_connection

logger = logging.getLogger(__name__)


class FluxoUploadRepository(Repository[FluxoUpload]):
    """Repository para uploads de Fluxo de Caixa."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_id(
        self, upload_id: str, conn: sqlite3.Connection | None = None
    ) -> FluxoUpload | None:
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                "SELECT * FROM fluxo_uploads WHERE id = ?", (upload_id,)
            ).fetchone()
            return FluxoUpload.from_db_row(row) if row else None
        finally:
            if should_close:
                connection.close()

    def get_by_competencia(
        self, ano: int, mes: int, conn: sqlite3.Connection | None = None
    ) -> list[FluxoUpload]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM fluxo_uploads"
                " WHERE competencia_ano = ? AND competencia_mes = ?"
                " ORDER BY created_at DESC",
                (ano, mes),
            ).fetchall()
            return [FluxoUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_by_ano(self, ano: int, conn: sqlite3.Connection | None = None) -> list[FluxoUpload]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM fluxo_uploads"
                " WHERE competencia_ano = ?"
                " ORDER BY competencia_mes, created_at DESC",
                (ano,),
            ).fetchall()
            return [FluxoUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def create(self, upload: FluxoUpload, conn: sqlite3.Connection | None = None) -> FluxoUpload:
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO fluxo_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             banco, status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            connection.execute(sql, upload.model_to_db())
            if should_close:
                connection.commit()
            return upload
        finally:
            if should_close:
                connection.close()

    def update(self, upload: FluxoUpload, conn: sqlite3.Connection | None = None) -> FluxoUpload:
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            UPDATE fluxo_uploads SET
                banco = ?, status = ?, total_linhas = ?, linhas_validas = ?,
                linhas_rejeitadas = ?, observacao = ?
            WHERE id = ?
            """
            connection.execute(
                sql,
                (
                    upload.banco,
                    upload.status,
                    upload.total_linhas,
                    upload.linhas_validas,
                    upload.linhas_rejeitadas,
                    upload.observacao,
                    upload.id,
                ),
            )
            if should_close:
                connection.commit()
            return upload
        finally:
            if should_close:
                connection.close()

    def delete(self, upload_id: str, conn: sqlite3.Connection | None = None) -> bool:
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute("DELETE FROM fluxo_uploads WHERE id = ?", (upload_id,))
            if should_close:
                connection.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                connection.close()

    def list_all(
        self, limit: int = 100, offset: int = 0, conn: sqlite3.Connection | None = None
    ) -> list[FluxoUpload]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM fluxo_uploads ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [FluxoUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_meses_completos_por_ano(
        self, ano: int, conn: sqlite3.Connection | None = None
    ) -> list[int]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                """
                SELECT DISTINCT competencia_mes
                FROM fluxo_uploads
                WHERE competencia_ano = ? AND status = 'completed'
                ORDER BY competencia_mes
                """,
                (ano,),
            ).fetchall()
            return [int(row["competencia_mes"]) for row in rows]
        finally:
            if should_close:
                connection.close()


class FluxoMovimentoRepository(Repository[FluxoMovimentoDB]):
    """Repository para movimentos de Fluxo de Caixa."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_id(
        self, movimento_id: int, conn: sqlite3.Connection | None = None
    ) -> FluxoMovimentoDB | None:
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                "SELECT * FROM fluxo_movimentos WHERE id = ?", (movimento_id,)
            ).fetchone()
            return FluxoMovimentoDB.from_db_row(row) if row else None
        finally:
            if should_close:
                connection.close()

    def create(
        self, movimento: FluxoMovimentoDB, conn: sqlite3.Connection | None = None
    ) -> FluxoMovimentoDB:
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO fluxo_movimentos
            (upload_id, competencia_ano, competencia_mes, data_movimento, tipo, descricao,
             valor, saldo, classificacao, conta_gerencial, banco_origem, arquivo_origem,
             linha_origem, aba_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = connection.execute(sql, movimento.model_to_db())
            movimento.id = cursor.lastrowid
            if should_close:
                connection.commit()
            return movimento
        finally:
            if should_close:
                connection.close()

    def create_many(
        self, movimentos: list[FluxoMovimentoDB], conn: sqlite3.Connection | None = None
    ) -> list[FluxoMovimentoDB]:
        if not movimentos:
            return []

        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO fluxo_movimentos
            (upload_id, competencia_ano, competencia_mes, data_movimento, tipo, descricao,
             valor, saldo, classificacao, conta_gerencial, banco_origem, arquivo_origem,
             linha_origem, aba_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = [mov.model_to_db() for mov in movimentos]
            connection.executemany(sql, params)
            if should_close:
                connection.commit()
            return movimentos
        finally:
            if should_close:
                connection.close()

    def delete(self, movimento_id: int, conn: sqlite3.Connection | None = None) -> bool:
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute(
                "DELETE FROM fluxo_movimentos WHERE id = ?", (movimento_id,)
            )
            if should_close:
                connection.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                connection.close()

    def update(
        self,
        movimento: FluxoMovimentoDB,
        conn: sqlite3.Connection | None = None,
    ) -> FluxoMovimentoDB:
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            UPDATE fluxo_movimentos SET
                data_movimento = ?, tipo = ?, descricao = ?, valor = ?, saldo = ?,
                classificacao = ?, conta_gerencial = ?, banco_origem = ?,
                arquivo_origem = ?, linha_origem = ?, aba_origem = ?
            WHERE id = ?
            """
            connection.execute(
                sql,
                (
                    movimento.data_movimento,
                    movimento.tipo,
                    movimento.descricao,
                    float(movimento.valor),
                    float(movimento.saldo) if movimento.saldo is not None else None,
                    movimento.classificacao,
                    movimento.conta_gerencial,
                    movimento.banco_origem,
                    movimento.arquivo_origem,
                    movimento.linha_origem,
                    movimento.aba_origem,
                    movimento.id,
                ),
            )
            if should_close:
                connection.commit()
            return movimento
        finally:
            if should_close:
                connection.close()

    def delete_by_upload(self, upload_id: str, conn: sqlite3.Connection | None = None) -> int:
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute(
                "DELETE FROM fluxo_movimentos WHERE upload_id = ?", (upload_id,)
            )
            if should_close:
                connection.commit()
            return int(cursor.rowcount or 0)
        finally:
            if should_close:
                connection.close()

    def get_by_meses(
        self,
        ano: int,
        meses: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> list[FluxoMovimentoDB]:
        if not meses:
            return []
        connection, should_close = _get_connection(self.db, conn)
        try:
            placeholders = ",".join("?" * len(meses))
            rows = connection.execute(
                f"""SELECT * FROM fluxo_movimentos
                    WHERE competencia_ano = ? AND competencia_mes IN ({placeholders})
                    ORDER BY competencia_mes, data_movimento, banco_origem, id""",
                tuple([ano, *meses]),
            ).fetchall()
            return [FluxoMovimentoDB.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_saldos_finais_anteriores(
        self,
        ano: int,
        mes: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Decimal]:
        """Retorna o último saldo informado por banco antes da competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                """
                SELECT banco_origem, saldo
                FROM fluxo_movimentos
                WHERE saldo IS NOT NULL
                  AND (competencia_ano < ? OR (competencia_ano = ? AND competencia_mes < ?))
                ORDER BY banco_origem, competencia_ano DESC, competencia_mes DESC,
                         data_movimento DESC, COALESCE(linha_origem, 0) DESC, id DESC
                """,
                (ano, ano, mes),
            ).fetchall()
            saldos: dict[str, Decimal] = {}
            for row in rows:
                banco = str(row["banco_origem"] or "").strip().lower()
                if banco and banco not in saldos:
                    saldos[banco] = Decimal(str(row["saldo"]))
            return saldos
        finally:
            if should_close:
                connection.close()


class FluxoCaixaRepository:
    """Repository consolidado para operações de Fluxo de Caixa."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.uploads = FluxoUploadRepository(db)
        self.movimentos = FluxoMovimentoRepository(db)
        self.contas_gerenciais = ContaGerencialRepository(db)

    def _calcular_hash_linha(self, movimento: FluxoMovimentoDB) -> str:
        content = (
            f"{movimento.data_movimento}|{movimento.tipo}|{movimento.descricao}|"
            f"{movimento.valor}|{movimento.saldo or Decimal('0')}|"
            f"{movimento.classificacao or ''}|{movimento.banco_origem}|"
            f"{movimento.arquivo_origem or ''}|{movimento.linha_origem or 0}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def upsert_competencia(
        self,
        uploads_movimentos: list[tuple[FluxoUpload, list[FluxoMovimentoDB]]],
    ) -> tuple[int, int]:
        """Substitui transacionalmente os dados de uma competência."""
        if not uploads_movimentos:
            return 0, 0

        ano = uploads_movimentos[0][0].competencia_ano
        mes = uploads_movimentos[0][0].competencia_mes
        # Garante que o schema (incl. contas_gerenciais) esteja íntegro mesmo se
        # a ingestão ocorrer antes do lifespan ou após uma migration nova.
        run_migrations(self.db)

        connection = sqlite3.connect(str(self.db.db_path))
        connection.row_factory = sqlite3.Row
        try:
            todos_movimentos = [mov for _, movimentos in uploads_movimentos for mov in movimentos]
            movimentos_normalizados, codigos_gerenciais_alterados = (
                self.contas_gerenciais.sincronizar_fluxo(todos_movimentos, connection)
            )
            uploads_movimentos_normalizados = []
            inicio = 0
            for upload, movimentos in uploads_movimentos:
                fim = inicio + len(movimentos)
                uploads_movimentos_normalizados.append(
                    (upload, movimentos_normalizados[inicio:fim])
                )
                inicio = fim
            uploads_movimentos = uploads_movimentos_normalizados

            uploads_anteriores = self.uploads.get_by_competencia(ano, mes, connection)
            removidos = 0
            for upload_ant in uploads_anteriores:
                removidos += self.movimentos.delete_by_upload(upload_ant.id, connection)
                self.uploads.delete(upload_ant.id, connection)

            inseridos = 0
            for upload, movimentos in uploads_movimentos:
                self.uploads.create(upload, connection)
                movimentos_validos = []
                for movimento in movimentos:
                    movimento.upload_id = upload.id
                    movimento.hash_linha = self._calcular_hash_linha(movimento)
                    movimentos_validos.append(movimento)

                self.movimentos.create_many(movimentos_validos, connection)
                self.contas_gerenciais.aplicar_rotulos_historicos(
                    codigos_gerenciais_alterados,
                    connection,
                )

                upload.total_linhas = upload.total_linhas or len(movimentos)
                upload.linhas_validas = len(movimentos_validos)
                upload.linhas_rejeitadas = max(upload.total_linhas - upload.linhas_validas, 0)
                upload.status = "completed"
                self.uploads.update(upload, connection)
                inseridos += len(movimentos_validos)

            connection.commit()
            return removidos, inseridos
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_meses_disponiveis(self, ano: int) -> list[int]:
        return self.uploads.get_meses_completos_por_ano(ano)

    def limpar_dados(self, ano: int | None = None, mes: int | None = None) -> dict[str, int]:
        connection = sqlite3.connect(str(self.db.db_path))
        connection.row_factory = sqlite3.Row
        try:
            filtros: list[str] = []
            params: list[Any] = []
            if ano is not None:
                filtros.append("competencia_ano = ?")
                params.append(ano)
            if mes is not None:
                filtros.append("competencia_mes = ?")
                params.append(mes)

            where = f" WHERE {' AND '.join(filtros)}" if filtros else ""
            upload_rows = connection.execute(
                f"SELECT id FROM fluxo_uploads{where}",
                tuple(params),
            ).fetchall()
            upload_ids = [row["id"] for row in upload_rows]
            if not upload_ids:
                connection.commit()
                return {"uploads_removidos": 0, "movimentos_removidos": 0}

            placeholders = ",".join("?" for _ in upload_ids)
            movimentos_removidos = connection.execute(
                f"DELETE FROM fluxo_movimentos WHERE upload_id IN ({placeholders})",
                tuple(upload_ids),
            ).rowcount
            uploads_removidos = connection.execute(
                f"DELETE FROM fluxo_uploads WHERE id IN ({placeholders})",
                tuple(upload_ids),
            ).rowcount
            connection.commit()
            return {
                "uploads_removidos": int(uploads_removidos or 0),
                "movimentos_removidos": int(movimentos_removidos or 0),
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
