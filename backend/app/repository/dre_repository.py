"""Repository para persistência de DRE (uploads e lançamentos)."""

import hashlib
import logging
import sqlite3
from decimal import Decimal
from typing import Any

from ..contracts.persistence import (
    DRECompetenciaQuery,
    DRELancamentoDB,
    DREResumoCompetencia,
    DREUpload,
)
from ..db.connection import DatabaseConnection
from .base import Repository

logger = logging.getLogger(__name__)


def _get_connection(db: DatabaseConnection, conn: sqlite3.Connection | None = None):
    """Helper para obter conexão (nova ou existente)."""
    if conn is not None:
        return conn, False  # conexão existente, não fechar
    new_conn = sqlite3.connect(str(db.db_path))
    new_conn.row_factory = sqlite3.Row
    return new_conn, True  # nova conexão, precisa fechar


class DREUploadRepository(Repository[DREUpload]):
    """Repository para uploads DRE."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_id(self, upload_id: str, conn: sqlite3.Connection | None = None) -> DREUpload | None:
        """Busca upload por ID."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                "SELECT * FROM dre_uploads WHERE id = ?", (upload_id,)
            ).fetchone()
            if row:
                return DREUpload.from_db_row(row)
            return None
        finally:
            if should_close:
                connection.close()

    def get_by_sha256(
        self, sha256: str, conn: sqlite3.Connection | None = None
    ) -> DREUpload | None:
        """Busca upload por hash do arquivo."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                "SELECT * FROM dre_uploads WHERE arquivo_sha256 = ?", (sha256,)
            ).fetchone()
            if row:
                return DREUpload.from_db_row(row)
            return None
        finally:
            if should_close:
                connection.close()

    def get_by_sha256_competencia(
        self,
        sha256: str,
        ano: int,
        mes: int,
        conn: sqlite3.Connection | None = None,
    ) -> DREUpload | None:
        """Busca upload por hash + competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                """
                SELECT * FROM dre_uploads
                WHERE arquivo_sha256 = ?
                  AND competencia_ano = ?
                  AND competencia_mes = ?
                LIMIT 1
                """,
                (sha256, ano, mes),
            ).fetchone()
            if row:
                return DREUpload.from_db_row(row)
            return None
        finally:
            if should_close:
                connection.close()

    def get_by_competencia(
        self, ano: int, mes: int, conn: sqlite3.Connection | None = None
    ) -> list[DREUpload]:
        """Busca uploads por competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM dre_uploads"
                " WHERE competencia_ano = ? AND competencia_mes = ?"
                " ORDER BY created_at DESC",
                (ano, mes),
            ).fetchall()
            return [DREUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_by_ano(self, ano: int, conn: sqlite3.Connection | None = None) -> list[DREUpload]:
        """Busca uploads por ano."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM dre_uploads"
                " WHERE competencia_ano = ?"
                " ORDER BY competencia_mes, created_at DESC",
                (ano,),
            ).fetchall()
            return [DREUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def create(self, upload: DREUpload, conn: sqlite3.Connection | None = None) -> DREUpload:
        """Cria novo registro de upload."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO dre_uploads
            (id, created_at, arquivo_nome, arquivo_sha256, competencia_ano, competencia_mes,
             status, total_linhas, linhas_validas, linhas_rejeitadas, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            connection.execute(sql, upload.model_to_db())
            if should_close:
                connection.commit()
            return upload
        finally:
            if should_close:
                connection.close()

    def update(self, upload: DREUpload, conn: sqlite3.Connection | None = None) -> DREUpload:
        """Atualiza status e métricas do upload."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            UPDATE dre_uploads SET
                status = ?, total_linhas = ?, linhas_validas = ?,
                linhas_rejeitadas = ?, observacao = ?
            WHERE id = ?
            """
            connection.execute(
                sql,
                (
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
        """Remove upload e seus lançamentos (cascata)."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute("DELETE FROM dre_uploads WHERE id = ?", (upload_id,))
            if should_close:
                connection.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                connection.close()

    def list_all(
        self, limit: int = 100, offset: int = 0, conn: sqlite3.Connection | None = None
    ) -> list[DREUpload]:
        """Lista uploads com paginação."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                "SELECT * FROM dre_uploads ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [DREUpload.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_meses_completos_por_ano(
        self, ano: int, conn: sqlite3.Connection | None = None
    ) -> list[int]:
        """Retorna meses com upload completed para o ano informado."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                """
                SELECT DISTINCT competencia_mes
                FROM dre_uploads
                WHERE competencia_ano = ? AND status = 'completed'
                ORDER BY competencia_mes
                """,
                (ano,),
            ).fetchall()
            return [int(row["competencia_mes"]) for row in rows]
        finally:
            if should_close:
                connection.close()


class DRELancamentoRepository(Repository[DRELancamentoDB]):
    """Repository para lançamentos DRE."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_id(
        self, lancamento_id: int, conn: sqlite3.Connection | None = None
    ) -> DRELancamentoDB | None:
        """Busca lançamento por ID."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                "SELECT * FROM dre_lancamentos WHERE id = ?", (lancamento_id,)
            ).fetchone()
            if row:
                return DRELancamentoDB.from_db_row(row)
            return None
        finally:
            if should_close:
                connection.close()

    def create(
        self, lancamento: DRELancamentoDB, conn: sqlite3.Connection | None = None
    ) -> DRELancamentoDB:
        """Cria novo lançamento."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO dre_lancamentos
            (upload_id, competencia_ano, competencia_mes, data_lancamento, historico,
             valor_bruto, credito, debito, natureza_raw, natureza_norm, centro_custo,
             rubrica, conta_pai, linha_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor = connection.execute(sql, lancamento.model_to_db())
            lancamento.id = cursor.lastrowid
            if should_close:
                connection.commit()
            return lancamento
        finally:
            if should_close:
                connection.close()

    def create_many(
        self, lancamentos: list[DRELancamentoDB], conn: sqlite3.Connection | None = None
    ) -> list[DRELancamentoDB]:
        """Cria múltiplos lançamentos em lote."""
        if not lancamentos:
            return []

        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            INSERT INTO dre_lancamentos
            (upload_id, competencia_ano, competencia_mes, data_lancamento, historico,
             valor_bruto, credito, debito, natureza_raw, natureza_norm, centro_custo,
             rubrica, conta_pai, linha_origem, hash_linha, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = [lanc.model_to_db() for lanc in lancamentos]
            connection.executemany(sql, params)
            if should_close:
                connection.commit()
            return lancamentos
        finally:
            if should_close:
                connection.close()

    def update(
        self, lancamento: DRELancamentoDB, conn: sqlite3.Connection | None = None
    ) -> DRELancamentoDB:
        """Atualiza lançamento existente."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            sql = """
            UPDATE dre_lancamentos SET
                data_lancamento = ?, historico = ?, valor_bruto = ?, credito = ?,
                debito = ?, natureza_raw = ?, natureza_norm = ?, centro_custo = ?,
                rubrica = ?, conta_pai = ?, linha_origem = ?
            WHERE id = ?
            """
            connection.execute(
                sql,
                (
                    lancamento.data_lancamento,
                    lancamento.historico,
                    float(lancamento.valor_bruto),
                    float(lancamento.credito),
                    float(lancamento.debito),
                    lancamento.natureza_raw,
                    lancamento.natureza_norm,
                    lancamento.centro_custo,
                    lancamento.rubrica,
                    lancamento.conta_pai,
                    lancamento.linha_origem,
                    lancamento.id,
                ),
            )
            if should_close:
                connection.commit()
            return lancamento
        finally:
            if should_close:
                connection.close()

    def delete(self, lancamento_id: int, conn: sqlite3.Connection | None = None) -> bool:
        """Remove lançamento por ID."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute(
                "DELETE FROM dre_lancamentos WHERE id = ?", (lancamento_id,)
            )
            if should_close:
                connection.commit()
            return cursor.rowcount > 0
        finally:
            if should_close:
                connection.close()

    def delete_by_upload(self, upload_id: str, conn: sqlite3.Connection | None = None) -> int:
        """Remove todos os lançamentos de um upload."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute(
                "DELETE FROM dre_lancamentos WHERE upload_id = ?", (upload_id,)
            )
            if should_close:
                connection.commit()
            return cursor.rowcount
        finally:
            if should_close:
                connection.close()

    def delete_by_competencia(
        self, ano: int, mes: int, conn: sqlite3.Connection | None = None
    ) -> int:
        """Remove todos os lançamentos de uma competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            cursor = connection.execute(
                "DELETE FROM dre_lancamentos WHERE competencia_ano = ? AND competencia_mes = ?",
                (ano, mes),
            )
            if should_close:
                connection.commit()
            return cursor.rowcount
        finally:
            if should_close:
                connection.close()

    def get_by_competencia(
        self,
        ano: int,
        mes: int,
        centro_custo: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[DRELancamentoDB]:
        """Busca lançamentos por competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            if centro_custo:
                rows = connection.execute(
                    """SELECT * FROM dre_lancamentos
                       WHERE competencia_ano = ? AND competencia_mes = ? AND centro_custo = ?
                       ORDER BY data_lancamento, id""",
                    (ano, mes, centro_custo),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM dre_lancamentos
                       WHERE competencia_ano = ? AND competencia_mes = ?
                       ORDER BY data_lancamento, id""",
                    (ano, mes),
                ).fetchall()
            return [DRELancamentoDB.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_ytd(
        self,
        ano: int,
        ate_mes: int,
        query: DRECompetenciaQuery | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[DRELancamentoDB]:
        """Busca lançamentos acumulados YTD (Year to Date)."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            base_sql = """SELECT * FROM dre_lancamentos
                          WHERE competencia_ano = ? AND competencia_mes <= ?"""
            params: list[Any] = [ano, ate_mes]

            if query:
                if query.centro_custo:
                    base_sql += " AND centro_custo = ?"
                    params.append(query.centro_custo)
                if query.conta_pai:
                    base_sql += " AND conta_pai = ?"
                    params.append(query.conta_pai)
                if query.natureza:
                    base_sql += " AND natureza_norm = ?"
                    params.append(query.natureza)

            base_sql += " ORDER BY data_lancamento, id"

            rows = connection.execute(base_sql, tuple(params)).fetchall()
            return [DRELancamentoDB.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_agregado_por_conta_mes(
        self, ano: int, ate_mes: int, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Retorna agregação por conta_pai x mês (para aba APOIO)."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            rows = connection.execute(
                """SELECT
                    conta_pai,
                    competencia_mes,
                    SUM(credito) as credito,
                    SUM(debito) as debito,
                    COUNT(*) as quantidade
                FROM dre_lancamentos
                WHERE competencia_ano = ? AND competencia_mes <= ?
                GROUP BY conta_pai, competencia_mes
                ORDER BY conta_pai, competencia_mes""",
                (ano, ate_mes),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_by_meses(
        self,
        ano: int,
        meses: list[int],
        centro_custo: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[DRELancamentoDB]:
        """Busca lançamentos de meses específicos no ano (para geração YTD disponível)."""
        if not meses:
            return []
        connection, should_close = _get_connection(self.db, conn)
        try:
            placeholders = ",".join("?" * len(meses))
            params: list[Any] = [ano] + list(meses)
            sql = f"""SELECT * FROM dre_lancamentos
                      WHERE competencia_ano = ? AND competencia_mes IN ({placeholders})"""
            if centro_custo:
                sql += " AND centro_custo = ?"
                params.append(centro_custo)
            sql += " ORDER BY competencia_mes, data_lancamento, id"
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [DRELancamentoDB.from_db_row(row) for row in rows]
        finally:
            if should_close:
                connection.close()

    def get_resumo_competencia(
        self, ano: int, mes: int, conn: sqlite3.Connection | None = None
    ) -> DREResumoCompetencia | None:
        """Retorna resumo da competência."""
        connection, should_close = _get_connection(self.db, conn)
        try:
            row = connection.execute(
                """SELECT
                    competencia_ano,
                    competencia_mes,
                    COUNT(*) as total_lancamentos,
                    SUM(credito) as total_credito,
                    SUM(debito) as total_debito,
                    SUM(credito - debito) as saldo_liquido,
                    COUNT(DISTINCT conta_pai) as total_contas_pai,
                    COUNT(DISTINCT centro_custo) as total_centros_custo
                FROM dre_lancamentos
                WHERE competencia_ano = ? AND competencia_mes = ?
                GROUP BY competencia_ano, competencia_mes""",
                (ano, mes),
            ).fetchone()
            if row and row["total_lancamentos"]:
                return DREResumoCompetencia(
                    competencia_ano=row["competencia_ano"],
                    competencia_mes=row["competencia_mes"],
                    total_lancamentos=row["total_lancamentos"],
                    total_credito=Decimal(str(row["total_credito"] or 0)),
                    total_debito=Decimal(str(row["total_debito"] or 0)),
                    saldo_liquido=Decimal(str(row["saldo_liquido"] or 0)),
                    total_contas_pai=row["total_contas_pai"],
                    total_centros_custo=row["total_centros_custo"],
                )
            return None
        finally:
            if should_close:
                connection.close()


class DRERepository:
    """Repository consolidado para operações DRE com transações."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.uploads = DREUploadRepository(db)
        self.lancamentos = DRELancamentoRepository(db)

    def _calcular_hash_linha(
        self,
        data: str,
        historico: str,
        credito: Decimal,
        debito: Decimal,
        natureza: str,
        centro_custo: str | None,
        linha_origem: int | None = None,
    ) -> str:
        """Calcula hash único para uma linha de lançamento."""
        content = (
            f"{data}|{historico}|{credito}|{debito}|{natureza}|"
            f"{centro_custo or ''}|{linha_origem or 0}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def upsert_competencia(
        self,
        upload: DREUpload,
        lancamentos: list[DRELancamentoDB],
    ) -> tuple[DREUpload, int, int]:
        """
        Realiza upsert transacional por competência.

        Regra:
        1. Remove lançamentos existentes do mês (se houver reupload)
        2. Insere novos lançamentos
        3. Atualiza status do upload

        Returns:
            Tuple de (upload_atualizado, removidos, inseridos)
        """
        connection = sqlite3.connect(str(self.db.db_path))
        connection.row_factory = sqlite3.Row
        try:
            # 1. Verifica se existe upload anterior para mesma competência
            uploads_anteriores = self.uploads.get_by_competencia(
                upload.competencia_ano, upload.competencia_mes, connection
            )

            removidos = 0
            for up_ant in uploads_anteriores:
                if up_ant.id != upload.id:
                    # Remove lançamentos do upload anterior
                    removidos += self.lancamentos.delete_by_upload(up_ant.id, connection)
                    # Remove o upload anterior
                    self.uploads.delete(up_ant.id, connection)
                    logger.info(
                        "Substituído upload anterior %s para %d/%d",
                        up_ant.id,
                        upload.competencia_mes,
                        upload.competencia_ano,
                    )

            # 2. Insere novo upload
            self.uploads.create(upload, connection)

            # 3. Prepara e insere lançamentos com hash
            lancamentos_validos = []
            for lanc in lancamentos:
                lanc.upload_id = upload.id
                lanc.hash_linha = self._calcular_hash_linha(
                    lanc.data_lancamento,
                    lanc.historico,
                    lanc.credito,
                    lanc.debito,
                    lanc.natureza_raw or "",
                    lanc.centro_custo,
                    lanc.linha_origem,
                )
                lancamentos_validos.append(lanc)

            if lancamentos_validos:
                self.lancamentos.create_many(lancamentos_validos, connection)

            # 4. Atualiza métricas do upload
            upload.total_linhas = len(lancamentos)
            upload.linhas_validas = len(lancamentos_validos)
            upload.linhas_rejeitadas = upload.total_linhas - upload.linhas_validas
            upload.status = "completed"
            self.uploads.update(upload, connection)

            connection.commit()
            inseridos = len(lancamentos_validos)
            return upload, removidos, inseridos
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_lancamentos_ytd(
        self, ano: int, ate_mes: int, query: DRECompetenciaQuery | None = None
    ) -> list[DRELancamentoDB]:
        """Retorna lançamentos acumulados YTD."""
        return self.lancamentos.get_ytd(ano, ate_mes, query)

    def get_meses_disponiveis(self, ano: int) -> list[int]:
        """Retorna meses disponíveis no ano com upload concluído."""
        return self.uploads.get_meses_completos_por_ano(ano)

    def get_resumo_ytd(self, ano: int, ate_mes: int) -> dict[str, Any]:
        """Retorna resumo acumulado YTD."""
        connection, should_close = _get_connection(self.db, None)
        try:
            row = connection.execute(
                """SELECT
                    COUNT(*) as total_lancamentos,
                    SUM(credito) as total_credito,
                    SUM(debito) as total_debito,
                    SUM(credito - debito) as saldo_liquido,
                    COUNT(DISTINCT conta_pai) as total_contas,
                    COUNT(DISTINCT centro_custo) as total_centros,
                    MIN(data_lancamento) as primeira_data,
                    MAX(data_lancamento) as ultima_data
                FROM dre_lancamentos
                WHERE competencia_ano = ? AND competencia_mes <= ?""",
                (ano, ate_mes),
            ).fetchone()
            if row:
                return {
                    "ano": ano,
                    "mes_final": ate_mes,
                    "total_lancamentos": row["total_lancamentos"],
                    "total_credito": Decimal(str(row["total_credito"] or 0)),
                    "total_debito": Decimal(str(row["total_debito"] or 0)),
                    "saldo_liquido": Decimal(str(row["saldo_liquido"] or 0)),
                    "total_contas_pai": row["total_contas"],
                    "total_centros_custo": row["total_centros"],
                    "primeira_data": row["primeira_data"],
                    "ultima_data": row["ultima_data"],
                }
            return {
                "ano": ano,
                "mes_final": ate_mes,
                "total_lancamentos": 0,
                "total_credito": Decimal("0"),
                "total_debito": Decimal("0"),
                "saldo_liquido": Decimal("0"),
                "total_contas_pai": 0,
                "total_centros_custo": 0,
            }
        finally:
            if should_close:
                connection.close()

    def limpar_dados(self, ano: int | None = None, mes: int | None = None) -> dict[str, int]:
        """Limpa dados DRE por escopo (global, ano, ou ano+mes) de forma transacional."""
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

            where = ""
            if filtros:
                where = " WHERE " + " AND ".join(filtros)

            upload_rows = connection.execute(
                f"SELECT id FROM dre_uploads{where}",
                tuple(params),
            ).fetchall()
            upload_ids = [row["id"] for row in upload_rows]

            if not upload_ids:
                connection.commit()
                return {"uploads_removidos": 0, "lancamentos_removidos": 0}

            placeholders = ",".join("?" for _ in upload_ids)
            lancamentos_removidos = connection.execute(
                f"DELETE FROM dre_lancamentos WHERE upload_id IN ({placeholders})",
                tuple(upload_ids),
            ).rowcount
            uploads_removidos = connection.execute(
                f"DELETE FROM dre_uploads WHERE id IN ({placeholders})",
                tuple(upload_ids),
            ).rowcount

            connection.commit()
            return {
                "uploads_removidos": int(uploads_removidos or 0),
                "lancamentos_removidos": int(lancamentos_removidos or 0),
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
