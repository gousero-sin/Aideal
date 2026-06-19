"""Repository para indicadores manuais do Fluxo de Caixa."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..contracts.persistence import FluxoIndicadoresManuais
from ..db.connection import DatabaseConnection


class FluxoIndicadoresManuaisRepository:
    """Persistência dos indicadores manuais anuais do Fluxo de Caixa."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_ano(
        self,
        ano: int,
        conn: Any | None = None,
    ) -> FluxoIndicadoresManuais | None:
        query = """
            SELECT *
            FROM fluxo_indicadores_manuais
            WHERE competencia_ano = ?
        """
        if conn is not None:
            row = conn.execute(query, (ano,)).fetchone()
        else:
            row = self.db.fetch_one(query, (ano,))
        return FluxoIndicadoresManuais.from_db_row(row) if row else None

    def upsert(self, indicadores: FluxoIndicadoresManuais) -> FluxoIndicadoresManuais:
        now = datetime.now()
        atualizados = indicadores.model_copy(
            update={
                "created_at": indicadores.created_at or now,
                "updated_at": now,
            }
        )
        sql = """
            INSERT INTO fluxo_indicadores_manuais
            (competencia_ano, saldo_ano_anterior, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(competencia_ano) DO UPDATE SET
                saldo_ano_anterior = excluded.saldo_ano_anterior,
                updated_at = excluded.updated_at
        """
        with self.db.transaction() as conn:
            existente = self.get_by_ano(atualizados.competencia_ano, conn)
            registro = atualizados
            if existente:
                registro = atualizados.model_copy(update={"created_at": existente.created_at})
            conn.execute(sql, registro.model_to_db())

        salvo = self.get_by_ano(indicadores.competencia_ano)
        if salvo is None:
            raise RuntimeError("Indicadores manuais do Fluxo não foram persistidos.")
        return salvo
