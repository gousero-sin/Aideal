"""Resumo executivo para o dashboard GoFlowOS."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class DashboardResumoService:
    """Agrega sinais operacionais de DRE, Fluxo de Caixa e logs recentes."""

    DRE_IMPOSTO_DEBITO_EXPR = (
        "CASE WHEN TRIM(rubrica) IN "
        "('IR','IR Retido','ISS','ISS Retido','INSS','INSS Retido','PIS','COFINS','CSLL',"
        "'Tarifa de Antecipação','Impostos sobre vendas','Deduções sobre vendas',"
        "'(-)Deduções sobre vendas','Descontos sobre vendas','Simples Nacional') "
        "THEN debito ELSE 0 END"
    )
    DRE_SAIDAS_LIQUIDAS_EXPR = f"(debito - ({DRE_IMPOSTO_DEBITO_EXPR}))"
    DRE_SALDO_EXPR = f"(credito - {DRE_SAIDAS_LIQUIDAS_EXPR})"
    FLUXO_TRANSFERENCIA_EXPR = (
        "(tipo = 'transferencia' OR UPPER(COALESCE(classificacao, '')) LIKE 'TRANSFER%')"
    )
    FLUXO_CREDITO_EXPR = (
        f"CASE WHEN NOT {FLUXO_TRANSFERENCIA_EXPR} AND tipo = 'credito' THEN valor ELSE 0 END"
    )
    FLUXO_DEBITO_EXPR = (
        f"CASE WHEN NOT {FLUXO_TRANSFERENCIA_EXPR} AND tipo = 'debito' THEN valor ELSE 0 END"
    )
    FLUXO_SALDO_EXPR = (
        f"CASE WHEN {FLUXO_TRANSFERENCIA_EXPR} THEN 0 "
        "WHEN tipo = 'credito' THEN valor WHEN tipo = 'debito' THEN -valor ELSE valor END"
    )

    def __init__(
        self,
        db: DatabaseConnection | None = None,
        logs_dir: Path | None = None,
    ) -> None:
        self.db = db or DatabaseConnection()
        self.logs_dir = logs_dir or settings.logs_dir

    @staticmethod
    def _validar_periodo(ano: int, mes: int) -> None:
        if ano < 2000 or ano > 2100:
            raise ValueError("Ano deve estar entre 2000 e 2100.")
        if mes < 1 or mes > 12:
            raise ValueError("Mês deve estar entre 1 e 12.")

    @staticmethod
    def _float(value: Any) -> float:
        return float(value or 0)

    @staticmethod
    def _ultimo_upload(row: Any, extra_key: str | None = None) -> dict[str, Any] | None:
        if not row:
            return None
        upload = {
            "upload_id": row["id"],
            "arquivo_nome": row["arquivo_nome"],
            "competencia": f"{int(row['competencia_mes']):02d}/{int(row['competencia_ano'])}",
            "status": row["status"],
            "created_at": row["created_at"],
            "total_linhas": int(row["total_linhas"] or 0),
            "linhas_validas": int(row["linhas_validas"] or 0),
        }
        if extra_key and row[extra_key] is not None:
            upload[extra_key] = row[extra_key]
        return upload

    def _logs_recentes(self, limit: int = 6) -> list[dict[str, Any]]:
        if not self.logs_dir.exists():
            return []

        eventos: list[dict[str, Any]] = []
        for path in sorted(self.logs_dir.glob("log_*.json"), reverse=True)[: max(limit * 3, limit)]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("Ignorando log inválido %s: %s", path, exc)
                continue

            eventos.append(
                {
                    "id": payload.get("id") or path.stem.replace("log_", ""),
                    "fluxo": payload.get("fluxo"),
                    "status": payload.get("status"),
                    "arquivo_saida": payload.get("arquivo_saida"),
                    "arquivos_entrada": payload.get("arquivos_entrada") or [],
                    "created_at": payload.get("data_processamento") or payload.get("created_at"),
                }
            )
            if len(eventos) >= limit:
                break

        return eventos

    def obter_periodo_padrao(self) -> tuple[int, int]:
        """Retorna a última competência com dados ou o período corrente."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT competencia_ano, competencia_mes
                FROM (
                    SELECT competencia_ano, competencia_mes
                    FROM dre_uploads
                    WHERE status = 'completed'
                    UNION ALL
                    SELECT competencia_ano, competencia_mes
                    FROM fluxo_uploads
                    WHERE status = 'completed'
                )
                ORDER BY competencia_ano DESC, competencia_mes DESC
                LIMIT 1
                """
            ).fetchone()
        if row:
            return int(row["competencia_ano"]), int(row["competencia_mes"])

        now = datetime.now()
        return now.year, now.month

    def obter_resumo(self, ano: int, mes: int) -> dict[str, Any]:
        self._validar_periodo(ano, mes)

        with self.db.get_connection() as conn:
            dre_uploads = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_uploads,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_uploads
                FROM dre_uploads
                WHERE competencia_ano = ? AND competencia_mes <= ?
                """,
                (ano, mes),
            ).fetchone()
            dre_totais = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total_lancamentos,
                    SUM(credito) AS total_credito,
                    SUM(debito) AS total_debito,
                    SUM({self.DRE_IMPOSTO_DEBITO_EXPR}) AS total_impostos,
                    SUM({self.DRE_SAIDAS_LIQUIDAS_EXPR}) AS total_saidas_liquidas,
                    SUM({self.DRE_SALDO_EXPR}) AS saldo_liquido,
                    COUNT(DISTINCT conta_pai) AS total_contas_pai,
                    COUNT(DISTINCT centro_custo) AS total_centros_custo
                FROM dre_lancamentos
                WHERE competencia_ano = ? AND competencia_mes <= ?
                """,
                (ano, mes),
            ).fetchone()
            dre_meses = conn.execute(
                """
                SELECT DISTINCT competencia_mes
                FROM dre_uploads
                WHERE competencia_ano = ? AND status = 'completed'
                ORDER BY competencia_mes
                """,
                (ano,),
            ).fetchall()
            dre_ultimo = conn.execute(
                """
                SELECT *
                FROM dre_uploads
                WHERE competencia_ano = ? AND competencia_mes <= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ano, mes),
            ).fetchone()

            fluxo_uploads = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_uploads,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_uploads
                FROM fluxo_uploads
                WHERE competencia_ano = ? AND competencia_mes <= ?
                """,
                (ano, mes),
            ).fetchone()
            fluxo_totais = conn.execute(
                f"""
                SELECT
                    SUM(CASE WHEN NOT {self.FLUXO_TRANSFERENCIA_EXPR} THEN 1 ELSE 0 END)
                        AS total_movimentos,
                    SUM({self.FLUXO_CREDITO_EXPR}) AS total_creditos,
                    SUM({self.FLUXO_DEBITO_EXPR}) AS total_debitos,
                    SUM({self.FLUXO_SALDO_EXPR}) AS saldo_liquido,
                    COUNT(DISTINCT banco_origem) AS total_bancos
                FROM fluxo_movimentos
                WHERE competencia_ano = ? AND competencia_mes <= ?
                """,
                (ano, mes),
            ).fetchone()
            fluxo_meses = conn.execute(
                """
                SELECT DISTINCT competencia_mes
                FROM fluxo_uploads
                WHERE competencia_ano = ? AND status = 'completed'
                ORDER BY competencia_mes
                """,
                (ano,),
            ).fetchall()
            fluxo_bancos = conn.execute(
                """
                SELECT DISTINCT banco_origem
                FROM fluxo_movimentos
                WHERE competencia_ano = ? AND competencia_mes <= ?
                ORDER BY banco_origem
                """,
                (ano, mes),
            ).fetchall()
            fluxo_ultimo = conn.execute(
                """
                SELECT *
                FROM fluxo_uploads
                WHERE competencia_ano = ? AND competencia_mes <= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ano, mes),
            ).fetchone()

        return {
            "success": True,
            "ano": ano,
            "mes": mes,
            "competencia": f"{mes:02d}/{ano}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health": {
                "api": "operacional",
                "database": "ok",
            },
            "dre": {
                "meses_disponiveis": [int(row["competencia_mes"]) for row in dre_meses],
                "uploads_total": int(dre_uploads["total_uploads"] or 0),
                "uploads_completed": int(dre_uploads["completed_uploads"] or 0),
                "total_lancamentos": int(dre_totais["total_lancamentos"] or 0),
                "total_credito": self._float(dre_totais["total_credito"]),
                "total_debito": self._float(dre_totais["total_debito"]),
                "total_impostos": self._float(dre_totais["total_impostos"]),
                "total_saidas_liquidas": self._float(dre_totais["total_saidas_liquidas"]),
                "saldo_liquido": self._float(dre_totais["saldo_liquido"]),
                "total_contas_pai": int(dre_totais["total_contas_pai"] or 0),
                "total_centros_custo": int(dre_totais["total_centros_custo"] or 0),
                "ultimo_upload": self._ultimo_upload(dre_ultimo),
            },
            "fluxo_caixa": {
                "meses_disponiveis": [int(row["competencia_mes"]) for row in fluxo_meses],
                "uploads_total": int(fluxo_uploads["total_uploads"] or 0),
                "uploads_completed": int(fluxo_uploads["completed_uploads"] or 0),
                "total_movimentos": int(fluxo_totais["total_movimentos"] or 0),
                "total_creditos": self._float(fluxo_totais["total_creditos"]),
                "total_debitos": self._float(fluxo_totais["total_debitos"]),
                "saldo_liquido": self._float(fluxo_totais["saldo_liquido"]),
                "total_bancos": int(fluxo_totais["total_bancos"] or 0),
                "bancos": [row["banco_origem"] for row in fluxo_bancos if row["banco_origem"]],
                "ultimo_upload": self._ultimo_upload(fluxo_ultimo, "banco"),
            },
            "logs_recentes": self._logs_recentes(),
        }
