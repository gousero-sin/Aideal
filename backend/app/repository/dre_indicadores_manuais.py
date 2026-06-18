"""Repository para indicadores DRE informados manualmente na ADM."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from ..contracts.persistence import DREIndicadoresManuais
from ..db.connection import DatabaseConnection


class DREIndicadoresManuaisRepository:
    """Persistência dos indicadores manuais por competência DRE."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def get_by_competencia(
        self,
        ano: int,
        mes: int,
        conn: Any | None = None,
    ) -> DREIndicadoresManuais | None:
        query = """
            SELECT *
            FROM dre_indicadores_manuais
            WHERE competencia_ano = ? AND competencia_mes = ?
        """
        if conn is not None:
            row = conn.execute(query, (ano, mes)).fetchone()
        else:
            row = self.db.fetch_one(query, (ano, mes))
        return DREIndicadoresManuais.from_db_row(row) if row else None

    def upsert(self, indicadores: DREIndicadoresManuais) -> DREIndicadoresManuais:
        now = datetime.now()
        atualizados = indicadores.model_copy(
            update={
                "created_at": indicadores.created_at or now,
                "updated_at": now,
            }
        )
        sql = """
            INSERT INTO dre_indicadores_manuais
            (competencia_ano, competencia_mes, contas_pagar, contas_receber,
             total_impostos_retidos_acima_meta, total_impostos_retidos, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(competencia_ano, competencia_mes) DO UPDATE SET
                contas_pagar = excluded.contas_pagar,
                contas_receber = excluded.contas_receber,
                total_impostos_retidos_acima_meta = excluded.total_impostos_retidos_acima_meta,
                total_impostos_retidos = excluded.total_impostos_retidos,
                updated_at = excluded.updated_at
        """
        with self.db.transaction() as conn:
            existente = self.get_by_competencia(
                atualizados.competencia_ano,
                atualizados.competencia_mes,
                conn,
            )
            registro = atualizados
            if existente:
                registro = atualizados.model_copy(update={"created_at": existente.created_at})
            conn.execute(sql, registro.model_to_db())

        salvo = self.get_by_competencia(indicadores.competencia_ano, indicadores.competencia_mes)
        if salvo is None:
            raise RuntimeError("Indicadores manuais não foram persistidos.")
        return salvo

    def somar_periodo(self, ano: int, meses: list[int] | None = None) -> dict[str, Any]:
        where = ["competencia_ano = ?"]
        params: list[Any] = [ano]
        meses_ref = sorted({int(mes) for mes in meses or []})
        if meses_ref:
            placeholders = ",".join("?" for _ in meses_ref)
            where.append(f"competencia_mes IN ({placeholders})")
            params.extend(meses_ref)

        row = self.db.fetch_one(
            f"""
            SELECT
                COUNT(*) AS total_registros,
                SUM(contas_pagar) AS contas_pagar,
                SUM(contas_receber) AS contas_receber,
                SUM(total_impostos_retidos_acima_meta) AS total_impostos_retidos_acima_meta,
                SUM(total_impostos_retidos) AS total_impostos_retidos
            FROM dre_indicadores_manuais
            WHERE {" AND ".join(where)}
            """,
            tuple(params),
        )

        total_registros = int(row["total_registros"] or 0) if row else 0
        return {
            "existe": total_registros > 0,
            "ano": ano,
            "meses": meses_ref,
            "competencias": [
                {"ano": ano, "mes": mes, "periodo": f"{ano}-{mes:02d}"}
                for mes in meses_ref
            ],
            "total_registros": total_registros,
            "contas_pagar": Decimal(str(row["contas_pagar"] or 0)) if row else Decimal("0"),
            "contas_receber": Decimal(str(row["contas_receber"] or 0)) if row else Decimal("0"),
            "total_impostos_retidos_acima_meta": (
                Decimal(str(row["total_impostos_retidos_acima_meta"] or 0))
                if row
                else Decimal("0")
            ),
            "total_impostos_retidos": (
                Decimal(str(row["total_impostos_retidos"] or 0)) if row else Decimal("0")
            ),
        }

    def somar_competencias(self, competencias: list[tuple[int, int]]) -> dict[str, Any]:
        competencias_ref = sorted({(int(ano), int(mes)) for ano, mes in competencias})
        if not competencias_ref:
            return self._soma_vazia([])

        where = " OR ".join(
            "(competencia_ano = ? AND competencia_mes = ?)" for _ in competencias_ref
        )
        params: list[Any] = []
        for ano, mes in competencias_ref:
            params.extend([ano, mes])

        row = self.db.fetch_one(
            f"""
            SELECT
                COUNT(*) AS total_registros,
                SUM(contas_pagar) AS contas_pagar,
                SUM(contas_receber) AS contas_receber,
                SUM(total_impostos_retidos_acima_meta) AS total_impostos_retidos_acima_meta,
                SUM(total_impostos_retidos) AS total_impostos_retidos
            FROM dre_indicadores_manuais
            WHERE {where}
            """,
            tuple(params),
        )
        return self._soma_payload(row, competencias_ref)

    @classmethod
    def _soma_vazia(cls, competencias: list[tuple[int, int]]) -> dict[str, Any]:
        return cls._soma_payload(None, competencias)

    @staticmethod
    def _soma_payload(row: Any | None, competencias: list[tuple[int, int]]) -> dict[str, Any]:
        total_registros = int(row["total_registros"] or 0) if row else 0
        anos = {ano for ano, _mes in competencias}
        return {
            "existe": total_registros > 0,
            "ano": next(iter(anos)) if len(anos) == 1 else None,
            "meses": [mes for _ano, mes in competencias] if len(anos) == 1 else [],
            "competencias": [
                {"ano": ano, "mes": mes, "periodo": f"{ano}-{mes:02d}"}
                for ano, mes in competencias
            ],
            "total_registros": total_registros,
            "contas_pagar": Decimal(str(row["contas_pagar"] or 0)) if row else Decimal("0"),
            "contas_receber": Decimal(str(row["contas_receber"] or 0)) if row else Decimal("0"),
            "total_impostos_retidos_acima_meta": (
                Decimal(str(row["total_impostos_retidos_acima_meta"] or 0))
                if row
                else Decimal("0")
            ),
            "total_impostos_retidos": (
                Decimal(str(row["total_impostos_retidos"] or 0)) if row else Decimal("0")
            ),
        }
