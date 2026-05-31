"""Catalogo canonico de contas gerenciais por codigo."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence

from ..contracts.persistence import DRELancamentoDB, FluxoMovimentoDB
from ..db.connection import DatabaseConnection
from ..validacao.codigos_gerenciais import (
    extrair_codigo_gerencial,
    normalizar_rotulos_gerenciais_texto,
    separar_conta_gerencial,
)


def _get_connection(db: DatabaseConnection, conn: sqlite3.Connection | None = None):
    if conn is not None:
        return conn, False
    new_conn = sqlite3.connect(str(db.db_path))
    new_conn.row_factory = sqlite3.Row
    return new_conn, True


class ContaGerencialRepository:
    """Mantem um rotulo unico por codigo gerencial e aplica no historico."""

    CAMPOS_DRE = ("natureza_raw", "rubrica")
    CAMPOS_FLUXO = ("conta_gerencial", "classificacao")

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def sincronizar_dre(
        self,
        lancamentos: Sequence[DRELancamentoDB],
        conn: sqlite3.Connection | None = None,
    ) -> tuple[list[DRELancamentoDB], set[str]]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            valores = [*self._valores_historicos(connection), *self._valores_dre(lancamentos)]
            codigos_alterados = self._sincronizar_valores(valores, connection)
            codigos_lote = {
                codigo
                for valor in self._valores_dre(lancamentos)
                if (codigo := extrair_codigo_gerencial(valor))
            }
            rotulos = self._rotulos_por_codigo(codigos_lote, connection)
            normalizados = [
                lanc.model_copy(
                    update={
                        "natureza_raw": self._normalizar_valor(lanc.natureza_raw, rotulos),
                        "rubrica": self._normalizar_valor(lanc.rubrica, rotulos),
                    }
                )
                for lanc in lancamentos
            ]
            if should_close:
                connection.commit()
            return normalizados, codigos_alterados
        finally:
            if should_close:
                connection.close()

    def sincronizar_fluxo(
        self,
        movimentos: Sequence[FluxoMovimentoDB],
        conn: sqlite3.Connection | None = None,
    ) -> tuple[list[FluxoMovimentoDB], set[str]]:
        connection, should_close = _get_connection(self.db, conn)
        try:
            valores = [*self._valores_historicos(connection), *self._valores_fluxo(movimentos)]
            codigos_alterados = self._sincronizar_valores(valores, connection)
            codigos_lote = {
                codigo
                for valor in self._valores_fluxo(movimentos)
                if (codigo := extrair_codigo_gerencial(valor))
            }
            rotulos = self._rotulos_por_codigo(codigos_lote, connection)
            normalizados = [
                mov.model_copy(
                    update={
                        "conta_gerencial": self._normalizar_valor(
                            mov.conta_gerencial,
                            rotulos,
                        ),
                        "classificacao": self._normalizar_valor(mov.classificacao, rotulos),
                    }
                )
                for mov in movimentos
            ]
            if should_close:
                connection.commit()
            return normalizados, codigos_alterados
        finally:
            if should_close:
                connection.close()

    def aplicar_rotulos_historicos(
        self,
        codigos: Iterable[str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        codigos_limpos = tuple(dict.fromkeys(codigo for codigo in codigos if codigo))
        if not codigos_limpos:
            return

        connection, should_close = _get_connection(self.db, conn)
        try:
            rotulos = self._rotulos_por_codigo(codigos_limpos, connection)
            self._atualizar_tabela_por_rotulos(
                connection,
                tabela="dre_lancamentos",
                campos=self.CAMPOS_DRE,
                rotulos=rotulos,
            )
            self._atualizar_tabela_por_rotulos(
                connection,
                tabela="fluxo_movimentos",
                campos=self.CAMPOS_FLUXO,
                rotulos=rotulos,
            )
            if should_close:
                connection.commit()
        finally:
            if should_close:
                connection.close()

    def _sincronizar_valores(
        self,
        valores: Iterable[object],
        conn: sqlite3.Connection,
    ) -> set[str]:
        codigos_alterados: set[str] = set()
        for valor in valores:
            conta = separar_conta_gerencial(valor)
            if conta is None:
                continue

            row = conn.execute(
                "SELECT nome, rotulo FROM contas_gerenciais WHERE codigo = ?",
                (conta.codigo,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO contas_gerenciais (codigo, nome, rotulo)
                    VALUES (?, ?, ?)
                    """,
                    (conta.codigo, conta.nome, conta.rotulo),
                )
                codigos_alterados.add(conta.codigo)
                continue

            if row["nome"] != conta.nome or row["rotulo"] != conta.rotulo:
                conn.execute(
                    """
                    UPDATE contas_gerenciais
                    SET nome = ?, rotulo = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE codigo = ?
                    """,
                    (conta.nome, conta.rotulo, conta.codigo),
                )
                codigos_alterados.add(conta.codigo)
        return codigos_alterados

    def _valores_historicos(self, conn: sqlite3.Connection) -> list[str]:
        rows = conn.execute(
            """
            SELECT valor
            FROM (
                SELECT created_at, id, natureza_raw AS valor FROM dre_lancamentos
                UNION ALL
                SELECT created_at, id, rubrica AS valor FROM dre_lancamentos
                UNION ALL
                SELECT created_at, id, conta_gerencial AS valor FROM fluxo_movimentos
                UNION ALL
                SELECT created_at, id, classificacao AS valor FROM fluxo_movimentos
            )
            WHERE valor IS NOT NULL AND TRIM(valor) <> ''
            ORDER BY created_at, id
            """
        ).fetchall()
        return [row["valor"] for row in rows]

    def _valores_dre(self, lancamentos: Sequence[DRELancamentoDB]) -> list[str | None]:
        valores: list[str | None] = []
        for lanc in lancamentos:
            valores.extend((lanc.natureza_raw, lanc.rubrica))
        return valores

    def _valores_fluxo(self, movimentos: Sequence[FluxoMovimentoDB]) -> list[str | None]:
        valores: list[str | None] = []
        for mov in movimentos:
            valores.extend((mov.conta_gerencial, mov.classificacao))
        return valores

    def _rotulos_por_codigo(
        self,
        codigos: Iterable[str],
        conn: sqlite3.Connection,
    ) -> dict[str, str]:
        codigos_limpos = tuple(dict.fromkeys(codigo for codigo in codigos if codigo))
        if not codigos_limpos:
            return {}

        placeholders = ",".join("?" for _ in codigos_limpos)
        rows = conn.execute(
            f"""
            SELECT codigo, rotulo
            FROM contas_gerenciais
            WHERE codigo IN ({placeholders})
            """,
            codigos_limpos,
        ).fetchall()
        return {row["codigo"]: row["rotulo"] for row in rows}

    @staticmethod
    def _normalizar_valor(valor: str | None, rotulos: dict[str, str]) -> str | None:
        return normalizar_rotulos_gerenciais_texto(valor, rotulos)

    def _atualizar_tabela_por_rotulos(
        self,
        conn: sqlite3.Connection,
        tabela: str,
        campos: Sequence[str],
        rotulos: dict[str, str],
    ) -> None:
        if not rotulos:
            return

        for campo in campos:
            rows = conn.execute(
                f"""
                SELECT id, {campo} AS valor
                FROM {tabela}
                WHERE {campo} IS NOT NULL AND TRIM({campo}) <> ''
                """
            ).fetchall()
            for row in rows:
                valor_normalizado = normalizar_rotulos_gerenciais_texto(row["valor"], rotulos)
                if valor_normalizado != row["valor"]:
                    conn.execute(
                        f"UPDATE {tabela} SET {campo} = ? WHERE id = ?",
                        (valor_normalizado, row["id"]),
                    )
