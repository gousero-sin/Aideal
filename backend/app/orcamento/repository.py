"""Persistência do domínio de Orçamento em banco próprio."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from typing import Any

from .database import OrcamentoDatabase
from .dfp import normalize_dfp_payload
from .exceptions import (
    CodigoAlreadyExistsError,
    InvalidSituacaoTransitionError,
    OrcamentoNotFoundError,
    RevisaoNotFoundError,
)
from .models import (
    SITUACAO_RASCUNHO,
    Orcamento,
    Revisao,
    SituacaoEvento,
    formatar_codigo,
)

CABECALHO_COLUNAS = (
    "escopo",
    "modalidade",
    "regiao",
    "prazo_execucao_dias",
    "saldo_mao_de_obra",
    "dados_contratante",
    "mobilizacao",
    "desmobilizacao",
    "area_unidade_base",
    "regime_tributario",
)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _row_to_revisao(row: sqlite3.Row) -> Revisao:
    return Revisao(
        id=str(row["id"]),
        orcamento_id=str(row["orcamento_id"]),
        numero=int(row["numero"]),
        situacao=str(row["situacao"]),
        escopo=str(row["escopo"]),
        modalidade=row["modalidade"],
        regiao=row["regiao"],
        prazo_execucao_dias=(
            int(row["prazo_execucao_dias"]) if row["prazo_execucao_dias"] is not None else None
        ),
        saldo_mao_de_obra=(
            float(row["saldo_mao_de_obra"]) if row["saldo_mao_de_obra"] is not None else None
        ),
        dados_contratante=row["dados_contratante"],
        mobilizacao=row["mobilizacao"],
        desmobilizacao=row["desmobilizacao"],
        area_unidade_base=row["area_unidade_base"],
        regime_tributario=row["regime_tributario"],
        dfp=normalize_dfp_payload(
            json.loads(row["dfp_payload"]) if row["dfp_payload"] else None,
            seed={
                "regiao": row["regiao"],
                "escopo": row["escopo"],
                "prazo_execucao_dias": row["prazo_execucao_dias"],
                "mobilizacao": row["mobilizacao"],
                "desmobilizacao": row["desmobilizacao"],
                "area_unidade_base": row["area_unidade_base"],
                "regime_tributario": row["regime_tributario"],
            },
        ),
        versao_regras=str(row["versao_regras"]),
        autor_user_id=str(row["autor_user_id"]),
        motivo=row["motivo"],
        emitido_em=_parse_datetime(str(row["emitido_em"])) if row["emitido_em"] else None,
        valido_ate=_parse_date(row["valido_ate"]),
        created_at=_parse_datetime(str(row["created_at"])),
    )


class OrcamentoRepository:
    def __init__(self, database: OrcamentoDatabase):
        self.database = database

    # -- leitura ---------------------------------------------------------

    def _revisoes_por_orcamento(
        self, connection: sqlite3.Connection, orcamento_ids: tuple[str, ...]
    ) -> dict[str, list[Revisao]]:
        if not orcamento_ids:
            return {}
        placeholders = ",".join("?" for _ in orcamento_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM orcamento_revisoes
            WHERE orcamento_id IN ({placeholders})
            ORDER BY numero
            """,
            orcamento_ids,
        ).fetchall()
        agrupadas: dict[str, list[Revisao]] = {}
        for row in rows:
            agrupadas.setdefault(str(row["orcamento_id"]), []).append(_row_to_revisao(row))
        return agrupadas

    def _montar(self, row: sqlite3.Row, revisoes: list[Revisao]) -> Orcamento:
        return Orcamento(
            id=str(row["id"]),
            sequencial=int(row["sequencial"]),
            codigo=str(row["codigo"]),
            contratante=str(row["contratante"]),
            criado_por_user_id=str(row["criado_por_user_id"]),
            revisoes=tuple(revisoes),
            created_at=_parse_datetime(str(row["created_at"])),
            updated_at=_parse_datetime(str(row["updated_at"])),
        )

    def list_orcamentos(self) -> tuple[Orcamento, ...]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM orcamentos ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
            revisoes = self._revisoes_por_orcamento(
                connection, tuple(str(row["id"]) for row in rows)
            )
        return tuple(self._montar(row, revisoes.get(str(row["id"]), [])) for row in rows)

    def get_orcamento(self, orcamento_id: str) -> Orcamento:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM orcamentos WHERE id = ?", (orcamento_id,)
            ).fetchone()
            if row is None:
                raise OrcamentoNotFoundError("Orçamento não encontrado")
            revisoes = self._revisoes_por_orcamento(connection, (orcamento_id,))
        return self._montar(row, revisoes.get(orcamento_id, []))

    def get_revisao(self, revisao_id: str) -> Revisao:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM orcamento_revisoes WHERE id = ?", (revisao_id,)
            ).fetchone()
        if row is None:
            raise RevisaoNotFoundError("Revisão não encontrada")
        return _row_to_revisao(row)

    def list_situacao_eventos(self, revisao_id: str) -> tuple[SituacaoEvento, ...]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM orcamento_situacao_eventos
                WHERE revisao_id = ? ORDER BY created_at
                """,
                (revisao_id,),
            ).fetchall()
        return tuple(
            SituacaoEvento(
                id=str(row["id"]),
                revisao_id=str(row["revisao_id"]),
                situacao=str(row["situacao"]),
                motivo=str(row["motivo"]),
                responsavel_user_id=str(row["responsavel_user_id"]),
                created_at=_parse_datetime(str(row["created_at"])),
            )
            for row in rows
        )

    # -- escrita ---------------------------------------------------------

    def create_orcamento(
        self,
        *,
        contratante: str,
        criado_por_user_id: str,
        revisao: dict[str, Any],
        agora: datetime,
    ) -> Orcamento:
        """O sequencial e o código são gerados aqui, dentro da transação."""
        orcamento_id = str(uuid.uuid4())
        timestamp = agora.isoformat()
        with self.database.transaction() as connection:
            # BEGIN IMMEDIATE serializa a escrita, então MAX+1 não corre risco de colisão.
            proximo = connection.execute(
                "SELECT COALESCE(MAX(sequencial), 0) + 1 AS sequencial FROM orcamentos"
            ).fetchone()
            sequencial = int(proximo["sequencial"])
            codigo = formatar_codigo(sequencial)
            try:
                connection.execute(
                    """
                    INSERT INTO orcamentos (
                        id, sequencial, codigo, codigo_key, contratante,
                        criado_por_user_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        orcamento_id,
                        sequencial,
                        codigo,
                        codigo.casefold(),
                        contratante,
                        criado_por_user_id,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                # Guarda defensiva: o índice único de sequencial não pode ser violado
                # silenciosamente nem gerar dois orçamentos com o mesmo código.
                raise CodigoAlreadyExistsError(
                    f"Código {codigo} já cadastrado; sequencial fora de sincronia"
                ) from exc
            self._inserir_revisao(
                connection, orcamento_id=orcamento_id, numero=0, revisao=revisao, agora=agora
            )
        return self.get_orcamento(orcamento_id)

    def create_revisao(
        self, *, orcamento_id: str, revisao: dict[str, Any], agora: datetime
    ) -> Revisao:
        with self.database.transaction() as connection:
            existe = connection.execute(
                "SELECT 1 FROM orcamentos WHERE id = ?", (orcamento_id,)
            ).fetchone()
            if existe is None:
                raise OrcamentoNotFoundError("Orçamento não encontrado")
            proximo = connection.execute(
                "SELECT COALESCE(MAX(numero), -1) + 1 AS numero FROM orcamento_revisoes"
                " WHERE orcamento_id = ?",
                (orcamento_id,),
            ).fetchone()
            revisao_id = self._inserir_revisao(
                connection,
                orcamento_id=orcamento_id,
                numero=int(proximo["numero"]),
                revisao=revisao,
                agora=agora,
            )
            connection.execute(
                "UPDATE orcamentos SET updated_at = ? WHERE id = ?",
                (agora.isoformat(), orcamento_id),
            )
        return self.get_revisao(revisao_id)

    def _inserir_revisao(
        self,
        connection: sqlite3.Connection,
        *,
        orcamento_id: str,
        numero: int,
        revisao: dict[str, Any],
        agora: datetime,
    ) -> str:
        revisao_id = str(uuid.uuid4())
        if revisao["dfp"].get("calculation_version") == 2:
            budget = connection.execute(
                "SELECT codigo FROM orcamentos WHERE id = ?", (orcamento_id,)
            ).fetchone()
            revisao = {**revisao, "dfp": {**revisao["dfp"], "metadata": {
                **revisao["dfp"].get("metadata", {}), "codigo_dfp": f"{budget['codigo']}-R{numero}",
            }}}
        colunas = (
            "situacao",
            "escopo",
            "modalidade",
            "regiao",
            "prazo_execucao_dias",
            "saldo_mao_de_obra",
            "dados_contratante",
            "mobilizacao",
            "desmobilizacao",
            "area_unidade_base",
            "regime_tributario",
            "dfp_payload",
            "versao_regras",
            "autor_user_id",
            "motivo",
        )
        campos = ", ".join(colunas)
        marcadores = ", ".join("?" for _ in colunas)
        connection.execute(
            f"""
            INSERT INTO orcamento_revisoes (
                id, orcamento_id, numero, {campos}, created_at
            ) VALUES (?, ?, ?, {marcadores}, ?)
            """,
            (
                revisao_id,
                orcamento_id,
                numero,
                revisao["situacao"],
                revisao["escopo"],
                revisao["modalidade"],
                revisao["regiao"],
                revisao["prazo_execucao_dias"],
                revisao["saldo_mao_de_obra"],
                revisao["dados_contratante"],
                revisao["mobilizacao"],
                revisao["desmobilizacao"],
                revisao["area_unidade_base"],
                revisao["regime_tributario"],
                json.dumps(revisao["dfp"], ensure_ascii=False),
                revisao["versao_regras"],
                revisao["autor_user_id"],
                revisao["motivo"],
                agora.isoformat(),
            ),
        )
        self._registrar_edicao(connection, revisao_id, "criacao", revisao["autor_user_id"],
                               {}, {**revisao, "numero": numero}, agora)
        return revisao_id

    def update_cabecalho(
        self,
        *,
        revisao_id: str,
        cabecalho: dict[str, Any],
        agora: datetime,
        responsavel_user_id: str = "sistema",
    ) -> Revisao:
        """Atualiza somente o conteúdo da revisão atual enquanto ela é rascunho."""
        with self.database.transaction() as connection:
            atual = connection.execute(
                """
                SELECT *
                FROM orcamento_revisoes WHERE id = ?
                """,
                (revisao_id,),
            ).fetchone()
            if atual is None:
                raise RevisaoNotFoundError("Revisão não encontrada")
            if str(atual["situacao"]) != SITUACAO_RASCUNHO:
                raise InvalidSituacaoTransitionError(
                    "Somente revisões em rascunho podem ter o cabeçalho editado"
                )

            numero_atual = connection.execute(
                """
                SELECT MAX(numero) AS numero
                FROM orcamento_revisoes WHERE orcamento_id = ?
                """,
                (atual["orcamento_id"],),
            ).fetchone()
            if int(numero_atual["numero"]) != int(atual["numero"]):
                raise InvalidSituacaoTransitionError(
                    "Somente a revisão atual pode ter o cabeçalho editado"
                )

            colunas_atualizaveis = (*CABECALHO_COLUNAS, "dfp_payload")
            if cabecalho["dfp"].get("calculation_version") == 2:
                budget = connection.execute(
                    "SELECT codigo FROM orcamentos WHERE id = ?", (atual["orcamento_id"],)
                ).fetchone()
                cabecalho = {**cabecalho, "dfp": {**cabecalho["dfp"], "metadata": {
                    **cabecalho["dfp"].get("metadata", {}),
                    "codigo_dfp": f"{budget['codigo']}-R{atual['numero']}",
                }}}
            self._registrar_edicao(connection, revisao_id, "edicao", responsavel_user_id,
                                   _row_to_revisao(atual).to_dict(), cabecalho, agora)
            atribuicoes = ", ".join(f"{coluna} = ?" for coluna in colunas_atualizaveis)
            connection.execute(
                f"UPDATE orcamento_revisoes SET {atribuicoes} WHERE id = ?",
                (
                    *(cabecalho[coluna] for coluna in CABECALHO_COLUNAS),
                    json.dumps(cabecalho["dfp"], ensure_ascii=False),
                    revisao_id,
                ),
            )
            connection.execute(
                "UPDATE orcamentos SET updated_at = ? WHERE id = ?",
                (agora.isoformat(), atual["orcamento_id"]),
            )
        return self.get_revisao(revisao_id)

    @staticmethod
    def _registrar_edicao(connection, revisao_id, tipo, responsavel, antes, depois, agora):
        connection.execute(
            "INSERT INTO orcamento_edicao_eventos VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                revisao_id,
                tipo,
                responsavel,
                json.dumps(antes, ensure_ascii=False),
                json.dumps(depois, ensure_ascii=False),
                agora.isoformat(),
            ),
        )

    def list_historico(self, orcamento_id: str) -> tuple[dict[str, Any], ...]:
        self.get_orcamento(orcamento_id)
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT e.* FROM orcamento_edicao_eventos e JOIN orcamento_revisoes r "
                "ON r.id=e.revisao_id WHERE r.orcamento_id=? ORDER BY e.created_at,e.rowid",
                (orcamento_id,),
            ).fetchall()
        return tuple(
            {
                **dict(row),
                "antes": json.loads(row["antes"]),
                "depois": json.loads(row["depois"]),
            }
            for row in rows
        )

    def get_catalogo(self) -> dict[str, Any]:
        with self.database.connection() as connection:
            row = connection.execute("SELECT payload FROM orcamento_catalogo WHERE id=1").fetchone()
        if row is None:
            return {"funcoes": [], "itens": [], "custo_administrativo_diario": 0}
        return json.loads(row["payload"])

    def save_catalogo(
        self, dados: dict[str, Any], *, responsavel_user_id: str, agora: datetime
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            timestamp = agora.isoformat()
            vigente = connection.execute(
                "SELECT id FROM orcamento_catalogo_historico WHERE vigente_ate IS NULL"
            ).fetchone()
            if vigente is not None:
                connection.execute(
                    "UPDATE orcamento_catalogo_historico SET vigente_ate = ? WHERE id = ?",
                    (timestamp, vigente["id"]),
                )
            proxima_versao = connection.execute(
                "SELECT COALESCE(MAX(versao), 0) + 1 AS versao FROM orcamento_catalogo_historico"
            ).fetchone()
            payload = json.dumps(dados, ensure_ascii=False)
            connection.execute(
                """
                INSERT INTO orcamento_catalogo_historico (
                    versao, payload, responsavel_user_id, vigente_desde, vigente_ate, created_at
                ) VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (
                    int(proxima_versao["versao"]),
                    payload,
                    responsavel_user_id,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO orcamento_catalogo VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE "
                "SET payload=excluded.payload,"
                "responsavel_user_id=excluded.responsavel_user_id,"
                "updated_at=excluded.updated_at",
                (payload, responsavel_user_id, timestamp),
            )
        return self.get_catalogo()

    def list_catalogo_historico(self) -> tuple[dict[str, Any], ...]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT versao, payload, responsavel_user_id, vigente_desde, vigente_ate, created_at
                FROM orcamento_catalogo_historico
                ORDER BY versao
                """
            ).fetchall()
        return tuple(
            {
                "versao": int(row["versao"]),
                "payload": json.loads(row["payload"]),
                "responsavel_user_id": str(row["responsavel_user_id"]),
                "vigente_desde": str(row["vigente_desde"]),
                "vigente_ate": str(row["vigente_ate"]) if row["vigente_ate"] else None,
                "created_at": str(row["created_at"]),
            }
            for row in rows
        )

    def registrar_situacao(
        self,
        *,
        revisao_id: str,
        situacao: str,
        situacao_esperada: str,
        motivo: str,
        responsavel_user_id: str,
        agora: datetime,
        emissao: tuple[datetime, date] | None = None,
    ) -> Revisao:
        """Aplica a situação e grava o evento na mesma transação, sem apagar nada."""
        with self.database.transaction() as connection:
            atual = connection.execute(
                """
                SELECT id, orcamento_id, numero, situacao
                FROM orcamento_revisoes WHERE id = ?
                """,
                (revisao_id,),
            ).fetchone()
            if atual is None:
                raise RevisaoNotFoundError("Revisão não encontrada")
            numero_atual = connection.execute(
                "SELECT MAX(numero) AS numero FROM orcamento_revisoes WHERE orcamento_id = ?",
                (atual["orcamento_id"],),
            ).fetchone()
            if int(numero_atual["numero"]) != int(atual["numero"]):
                raise InvalidSituacaoTransitionError(
                    "Somente a revisão atual pode mudar de situação"
                )
            if str(atual["situacao"]) != situacao_esperada:
                raise InvalidSituacaoTransitionError(
                    "A revisão foi alterada por outra operação; recarregue e tente novamente"
                )
            if emissao is None:
                atualizacao = connection.execute(
                    """
                    UPDATE orcamento_revisoes SET situacao = ?, motivo = ?
                    WHERE id = ? AND situacao = ?
                    """,
                    (situacao, motivo, revisao_id, situacao_esperada),
                )
            else:
                emitido_em, valido_ate = emissao
                atualizacao = connection.execute(
                    """
                    UPDATE orcamento_revisoes
                    SET situacao = ?, motivo = ?, emitido_em = ?, valido_ate = ?
                    WHERE id = ? AND situacao = ?
                    """,
                    (
                        situacao,
                        motivo,
                        emitido_em.isoformat(),
                        valido_ate.isoformat(),
                        revisao_id,
                        situacao_esperada,
                    ),
                )
            if atualizacao.rowcount != 1:
                raise InvalidSituacaoTransitionError(
                    "A revisão foi alterada por outra operação; recarregue e tente novamente"
                )
            connection.execute(
                """
                INSERT INTO orcamento_situacao_eventos (
                    id, revisao_id, situacao, motivo, responsavel_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    revisao_id,
                    situacao,
                    motivo,
                    responsavel_user_id,
                    agora.isoformat(),
                ),
            )
            self._registrar_edicao(connection, revisao_id, "situacao", responsavel_user_id,
                                   {"situacao": situacao_esperada},
                                   {"situacao": situacao, "motivo": motivo}, agora)
            connection.execute(
                "UPDATE orcamentos SET updated_at = ? WHERE id = ?",
                (agora.isoformat(), atual["orcamento_id"]),
            )
        return self.get_revisao(revisao_id)
