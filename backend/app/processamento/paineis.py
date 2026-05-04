"""Agregações analíticas para os painéis DRE e Fluxo de Caixa."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..db.connection import DatabaseConnection

MESES_LABEL = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _validar_ano(ano: int) -> None:
    if ano < 2000 or ano > 2100:
        raise ValueError("Ano deve estar entre 2000 e 2100.")


def _validar_meses(meses: list[int]) -> None:
    invalidos = [mes for mes in meses if mes < 1 or mes > 12]
    if invalidos:
        raise ValueError("Mês deve estar entre 1 e 12.")


def _normalizar_lista_texto(valores: list[str] | None) -> list[str]:
    return [valor.strip() for valor in valores or [] if valor and valor.strip()]


def _float(value: Any) -> float:
    return float(value or 0)


def _percent(numerador: float, denominador: float) -> float:
    return (numerador / denominador) * 100 if denominador else 0


def _placeholders(total: int) -> str:
    return ",".join("?" for _ in range(total))


def _append_in(
    where: list[str],
    params: list[Any],
    expression: str,
    values: list[Any],
) -> None:
    if not values:
        return
    where.append(f"{expression} IN ({_placeholders(len(values))})")
    params.extend(values)


class _PainelBaseService:
    def __init__(self, db: DatabaseConnection | None = None) -> None:
        self.db = db or DatabaseConnection()

    def _ano_mais_recente(self, table: str) -> int:
        with self.db.get_connection() as conn:
            row = conn.execute(f"SELECT MAX(competencia_ano) AS ano FROM {table}").fetchone()
        return int(row["ano"]) if row and row["ano"] is not None else date.today().year

    @staticmethod
    def _periodo_payload(
        ano: int,
        meses_aplicados: list[int],
        meses_disponiveis: list[int],
    ) -> dict[str, Any]:
        meses_periodo = meses_aplicados or meses_disponiveis
        if meses_periodo:
            primeiro_mes = MESES_LABEL[meses_periodo[0] - 1]
            ultimo_mes = MESES_LABEL[meses_periodo[-1] - 1]
            label = f"{primeiro_mes}-{ultimo_mes}/{ano}"
            if len(meses_periodo) == 1:
                label = f"{MESES_LABEL[meses_periodo[0] - 1]}/{ano}"
        else:
            label = str(ano)
        return {
            "ano": ano,
            "meses": meses_periodo,
            "meses_disponiveis": meses_disponiveis,
            "label": label,
        }

    @staticmethod
    def _series_rows(rows: list[Any], count_key: str) -> list[dict[str, Any]]:
        return [
            {
                "mes": int(row["mes"]),
                "mes_label": MESES_LABEL[int(row["mes"]) - 1],
                "credito": _float(row["credito"]),
                "debito": _float(row["debito"]),
                "saldo": _float(row["saldo"]),
                count_key: int(row["total"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _ranking_rows(rows: list[Any], count_key: str) -> list[dict[str, Any]]:
        return [
            {
                "nome": row["nome"],
                "credito": _float(row["credito"]),
                "debito": _float(row["debito"]),
                "saldo": _float(row["saldo"]),
                count_key: int(row["total"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _filter_option_rows(rows: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "value": row["value"],
                "label": row["value"],
                "total": int(row["total"] or 0),
                "saldo": _float(row["saldo"]),
            }
            for row in rows
            if row["value"]
        ]


class PainelDREService(_PainelBaseService):
    """Agrega KPIs, séries e slicers web para DRE."""

    CENTRO_CUSTO_EXPR = "COALESCE(NULLIF(TRIM(centro_custo), ''), 'Sem obra')"
    NATUREZA_EXPR = (
        "COALESCE(NULLIF(TRIM(natureza_norm), ''), NULLIF(TRIM(natureza_raw), ''), 'Sem natureza')"
    )

    def obter_painel(
        self,
        ano: int | None = None,
        meses: list[int] | None = None,
        centro_custo: list[str] | None = None,
        natureza: list[str] | None = None,
    ) -> dict[str, Any]:
        ano_ref = ano if ano is not None else self._ano_mais_recente("dre_lancamentos")
        meses_ref = sorted(set(meses or []))
        centro_custo_ref = _normalizar_lista_texto(centro_custo)
        natureza_ref = _normalizar_lista_texto(natureza)

        _validar_ano(ano_ref)
        _validar_meses(meses_ref)

        where = ["competencia_ano = ?"]
        params: list[Any] = [ano_ref]
        _append_in(where, params, "competencia_mes", meses_ref)
        _append_in(where, params, self.CENTRO_CUSTO_EXPR, centro_custo_ref)
        _append_in(where, params, self.NATUREZA_EXPR, natureza_ref)
        where_sql = " AND ".join(where)

        period_where = ["competencia_ano = ?"]
        period_params: list[Any] = [ano_ref]
        _append_in(period_where, period_params, "competencia_mes", meses_ref)
        period_where_sql = " AND ".join(period_where)

        with self.db.get_connection() as conn:
            meses_disponiveis = [
                int(row["competencia_mes"])
                for row in conn.execute(
                    """
                    SELECT DISTINCT competencia_mes
                    FROM dre_lancamentos
                    WHERE competencia_ano = ?
                    ORDER BY competencia_mes
                    """,
                    (ano_ref,),
                ).fetchall()
            ]

            kpis = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total_lancamentos,
                    SUM(credito) AS total_credito,
                    SUM(debito) AS total_debito,
                    SUM(credito - debito) AS saldo_liquido,
                    COUNT(DISTINCT {self.CENTRO_CUSTO_EXPR}) AS total_obras,
                    COUNT(DISTINCT {self.NATUREZA_EXPR}) AS total_naturezas
                FROM dre_lancamentos
                WHERE {where_sql}
                """,
                tuple(params),
            ).fetchone()
            series = conn.execute(
                f"""
                SELECT
                    competencia_mes AS mes,
                    SUM(credito) AS credito,
                    SUM(debito) AS debito,
                    SUM(credito - debito) AS saldo,
                    COUNT(*) AS total
                FROM dre_lancamentos
                WHERE {where_sql}
                GROUP BY competencia_mes
                ORDER BY competencia_mes
                """,
                tuple(params),
            ).fetchall()
            ranking_obras = self._ranking(conn, self.CENTRO_CUSTO_EXPR, where_sql, params, limit=14)
            ranking_naturezas = self._ranking(conn, self.NATUREZA_EXPR, where_sql, params, limit=14)
            ultimos = conn.execute(
                f"""
                SELECT
                    id,
                    data_lancamento AS data,
                    historico,
                    credito,
                    debito,
                    credito - debito AS saldo,
                    {self.CENTRO_CUSTO_EXPR} AS centro_custo,
                    {self.NATUREZA_EXPR} AS natureza
                FROM dre_lancamentos
                WHERE {where_sql}
                ORDER BY data_lancamento DESC, id DESC
                LIMIT 12
                """,
                tuple(params),
            ).fetchall()

            filtros = {
                "anos": [
                    int(row["competencia_ano"])
                    for row in conn.execute(
                        """
                        SELECT DISTINCT competencia_ano
                        FROM dre_lancamentos
                        ORDER BY competencia_ano DESC
                        """
                    ).fetchall()
                ],
                "meses": meses_disponiveis,
                "centro_custo": self._filter_options(
                    conn, self.CENTRO_CUSTO_EXPR, period_where_sql, period_params
                ),
                "natureza": self._filter_options(
                    conn, self.NATUREZA_EXPR, period_where_sql, period_params
                ),
            }

        total_lancamentos = int(kpis["total_lancamentos"] or 0)
        total_credito = _float(kpis["total_credito"])
        total_debito = _float(kpis["total_debito"])
        saldo_liquido = _float(kpis["saldo_liquido"])
        meses_analise = len(meses_ref or meses_disponiveis)
        media_saida_mensal = total_debito / meses_analise if meses_analise else 0
        saldo_medio_mensal = saldo_liquido / meses_analise if meses_analise else 0
        folego_caixa_meses = (
            max(saldo_liquido, 0) / media_saida_mensal if media_saida_mensal else 0
        )
        return {
            "success": True,
            "periodo": self._periodo_payload(ano_ref, meses_ref, meses_disponiveis),
            "filtros_disponiveis": filtros,
            "filtros_aplicados": {
                "ano": ano_ref,
                "meses": meses_ref,
                "centro_custo": centro_custo_ref,
                "natureza": natureza_ref,
            },
            "kpis": {
                "total_lancamentos": total_lancamentos,
                "total_credito": total_credito,
                "total_debito": total_debito,
                "saldo_liquido": saldo_liquido,
                "total_obras": int(kpis["total_obras"] or 0),
                "total_naturezas": int(kpis["total_naturezas"] or 0),
                "ticket_medio": saldo_liquido / total_lancamentos if total_lancamentos else 0,
                "media_saida_mensal": media_saida_mensal,
                "saldo_medio_mensal": saldo_medio_mensal,
                "folego_caixa_meses": folego_caixa_meses,
                "margem_resultado_percentual": _percent(saldo_liquido, total_credito),
                "pressao_saida_percentual": _percent(total_debito, total_credito),
                "meses_analise": meses_analise,
            },
            "series_mensais": self._series_rows(series, "lancamentos"),
            "ranking_obras": self._ranking_rows(ranking_obras, "lancamentos"),
            "ranking_naturezas": self._ranking_rows(ranking_naturezas, "lancamentos"),
            "ultimos_lancamentos": [
                {
                    "id": row["id"],
                    "data": row["data"],
                    "historico": row["historico"],
                    "credito": _float(row["credito"]),
                    "debito": _float(row["debito"]),
                    "saldo": _float(row["saldo"]),
                    "centro_custo": row["centro_custo"],
                    "natureza": row["natureza"],
                }
                for row in ultimos
            ],
        }

    def _ranking(
        self,
        conn: Any,
        expression: str,
        where_sql: str,
        params: list[Any],
        limit: int,
    ) -> list[Any]:
        return conn.execute(
            f"""
            SELECT
                {expression} AS nome,
                SUM(credito) AS credito,
                SUM(debito) AS debito,
                SUM(credito - debito) AS saldo,
                COUNT(*) AS total
            FROM dre_lancamentos
            WHERE {where_sql}
            GROUP BY nome
            ORDER BY ABS(SUM(credito - debito)) DESC, total DESC, nome ASC
            LIMIT ?
            """,
            tuple([*params, limit]),
        ).fetchall()

    def _filter_options(
        self,
        conn: Any,
        expression: str,
        where_sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"""
            SELECT
                {expression} AS value,
                COUNT(*) AS total,
                SUM(credito - debito) AS saldo
            FROM dre_lancamentos
            WHERE {where_sql}
            GROUP BY value
            ORDER BY total DESC, value ASC
            LIMIT 240
            """,
            tuple(params),
        ).fetchall()
        return self._filter_option_rows(rows)


class PainelFluxoCaixaService(_PainelBaseService):
    """Agrega KPIs, séries e slicers web para Fluxo de Caixa."""

    BANCO_EXPR = "COALESCE(NULLIF(TRIM(banco_origem), ''), 'Sem banco')"
    TIPO_EXPR = "COALESCE(NULLIF(TRIM(tipo), ''), 'sem_tipo')"
    CLASSIFICACAO_EXPR = (
        "COALESCE(NULLIF(TRIM(classificacao), ''), "
        "NULLIF(TRIM(conta_gerencial), ''), 'Sem classificação')"
    )
    CREDITO_EXPR = "CASE WHEN tipo = 'credito' THEN valor ELSE 0 END"
    DEBITO_EXPR = "CASE WHEN tipo = 'debito' THEN valor ELSE 0 END"
    SALDO_EXPR = (
        "CASE WHEN tipo = 'credito' THEN valor WHEN tipo = 'debito' THEN -valor ELSE valor END"
    )

    def obter_painel(
        self,
        ano: int | None = None,
        meses: list[int] | None = None,
        banco: list[str] | None = None,
        tipo: list[str] | None = None,
        classificacao: list[str] | None = None,
    ) -> dict[str, Any]:
        ano_ref = ano if ano is not None else self._ano_mais_recente("fluxo_movimentos")
        meses_ref = sorted(set(meses or []))
        banco_ref = _normalizar_lista_texto(banco)
        tipo_ref = _normalizar_lista_texto(tipo)
        classificacao_ref = _normalizar_lista_texto(classificacao)

        _validar_ano(ano_ref)
        _validar_meses(meses_ref)

        where = ["competencia_ano = ?"]
        params: list[Any] = [ano_ref]
        _append_in(where, params, "competencia_mes", meses_ref)
        _append_in(where, params, self.BANCO_EXPR, banco_ref)
        _append_in(where, params, self.TIPO_EXPR, tipo_ref)
        _append_in(where, params, self.CLASSIFICACAO_EXPR, classificacao_ref)
        where_sql = " AND ".join(where)

        period_where = ["competencia_ano = ?"]
        period_params: list[Any] = [ano_ref]
        _append_in(period_where, period_params, "competencia_mes", meses_ref)
        period_where_sql = " AND ".join(period_where)

        with self.db.get_connection() as conn:
            meses_disponiveis = [
                int(row["competencia_mes"])
                for row in conn.execute(
                    """
                    SELECT DISTINCT competencia_mes
                    FROM fluxo_movimentos
                    WHERE competencia_ano = ?
                    ORDER BY competencia_mes
                    """,
                    (ano_ref,),
                ).fetchall()
            ]

            kpis = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total_movimentos,
                    SUM({self.CREDITO_EXPR}) AS total_creditos,
                    SUM({self.DEBITO_EXPR}) AS total_debitos,
                    SUM({self.SALDO_EXPR}) AS saldo_liquido,
                    COUNT(DISTINCT {self.BANCO_EXPR}) AS total_bancos,
                    COUNT(DISTINCT {self.CLASSIFICACAO_EXPR}) AS total_classificacoes
                FROM fluxo_movimentos
                WHERE {where_sql}
                """,
                tuple(params),
            ).fetchone()
            series = conn.execute(
                f"""
                SELECT
                    competencia_mes AS mes,
                    SUM({self.CREDITO_EXPR}) AS credito,
                    SUM({self.DEBITO_EXPR}) AS debito,
                    SUM({self.SALDO_EXPR}) AS saldo,
                    COUNT(*) AS total
                FROM fluxo_movimentos
                WHERE {where_sql}
                GROUP BY competencia_mes
                ORDER BY competencia_mes
                """,
                tuple(params),
            ).fetchall()
            ranking_bancos = self._ranking(conn, self.BANCO_EXPR, where_sql, params, limit=14)
            ranking_classificacoes = self._ranking(
                conn, self.CLASSIFICACAO_EXPR, where_sql, params, limit=14
            )
            recentes = conn.execute(
                f"""
                SELECT
                    id,
                    data_movimento AS data,
                    descricao,
                    tipo,
                    valor,
                    {self.SALDO_EXPR} AS saldo_liquido,
                    {self.BANCO_EXPR} AS banco,
                    {self.CLASSIFICACAO_EXPR} AS classificacao
                FROM fluxo_movimentos
                WHERE {where_sql}
                ORDER BY data_movimento DESC, id DESC
                LIMIT 12
                """,
                tuple(params),
            ).fetchall()

            filtros = {
                "anos": [
                    int(row["competencia_ano"])
                    for row in conn.execute(
                        """
                        SELECT DISTINCT competencia_ano
                        FROM fluxo_movimentos
                        ORDER BY competencia_ano DESC
                        """
                    ).fetchall()
                ],
                "meses": meses_disponiveis,
                "banco": self._filter_options(
                    conn, self.BANCO_EXPR, period_where_sql, period_params
                ),
                "tipo": self._filter_options(conn, self.TIPO_EXPR, period_where_sql, period_params),
                "classificacao": self._filter_options(
                    conn, self.CLASSIFICACAO_EXPR, period_where_sql, period_params
                ),
            }

        total_movimentos = int(kpis["total_movimentos"] or 0)
        return {
            "success": True,
            "periodo": self._periodo_payload(ano_ref, meses_ref, meses_disponiveis),
            "filtros_disponiveis": filtros,
            "filtros_aplicados": {
                "ano": ano_ref,
                "meses": meses_ref,
                "banco": banco_ref,
                "tipo": tipo_ref,
                "classificacao": classificacao_ref,
            },
            "kpis": {
                "total_movimentos": total_movimentos,
                "total_creditos": _float(kpis["total_creditos"]),
                "total_debitos": _float(kpis["total_debitos"]),
                "saldo_liquido": _float(kpis["saldo_liquido"]),
                "total_bancos": int(kpis["total_bancos"] or 0),
                "total_classificacoes": int(kpis["total_classificacoes"] or 0),
                "ticket_medio": (
                    _float(kpis["saldo_liquido"]) / total_movimentos if total_movimentos else 0
                ),
            },
            "series_mensais": self._series_rows(series, "movimentos"),
            "ranking_bancos": self._ranking_rows(ranking_bancos, "movimentos"),
            "ranking_classificacoes": self._ranking_rows(ranking_classificacoes, "movimentos"),
            "movimentos_recentes": [
                {
                    "id": row["id"],
                    "data": row["data"],
                    "descricao": row["descricao"],
                    "tipo": row["tipo"],
                    "valor": _float(row["valor"]),
                    "saldo_liquido": _float(row["saldo_liquido"]),
                    "banco": row["banco"],
                    "classificacao": row["classificacao"],
                }
                for row in recentes
            ],
        }

    def _ranking(
        self,
        conn: Any,
        expression: str,
        where_sql: str,
        params: list[Any],
        limit: int,
    ) -> list[Any]:
        return conn.execute(
            f"""
            SELECT
                {expression} AS nome,
                SUM({self.CREDITO_EXPR}) AS credito,
                SUM({self.DEBITO_EXPR}) AS debito,
                SUM({self.SALDO_EXPR}) AS saldo,
                COUNT(*) AS total
            FROM fluxo_movimentos
            WHERE {where_sql}
            GROUP BY nome
            ORDER BY ABS(SUM({self.SALDO_EXPR})) DESC, total DESC, nome ASC
            LIMIT ?
            """,
            tuple([*params, limit]),
        ).fetchall()

    def _filter_options(
        self,
        conn: Any,
        expression: str,
        where_sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"""
            SELECT
                {expression} AS value,
                COUNT(*) AS total,
                SUM({self.SALDO_EXPR}) AS saldo
            FROM fluxo_movimentos
            WHERE {where_sql}
            GROUP BY value
            ORDER BY total DESC, value ASC
            LIMIT 240
            """,
            tuple(params),
        ).fetchall()
        return self._filter_option_rows(rows)
