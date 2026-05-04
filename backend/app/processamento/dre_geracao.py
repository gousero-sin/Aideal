"""Serviço de geração cumulativa de DRE a partir do banco de dados."""

import logging
from typing import Any

from ..contracts.dre import DRELancamento, DRELote
from ..contracts.persistence import DRECompetenciaQuery, DRELancamentoDB
from ..db.connection import DatabaseConnection
from ..repository.dre_repository import DRERepository

logger = logging.getLogger(__name__)


class DREGeracaoService:
    """Serviço para geração de DRE cumulativo a partir do banco."""

    def __init__(self, db: DatabaseConnection | None = None):
        self.db = db or DatabaseConnection()
        self.repository = DRERepository(self.db)

    def _parse_competencia(self, competencia: str) -> tuple[int, int]:
        """Converte 'MM/AAAA' para (ano, mes)."""
        parts = competencia.replace("-", "/").replace("\\", "/").split("/")
        if len(parts) != 2:
            raise ValueError(f"Competência deve estar no formato MM/AAAA: {competencia}")

        mes_str, ano_str = parts
        mes = int(mes_str)
        ano = int(ano_str)
        if mes < 1 or mes > 12:
            raise ValueError(f"Mês da competência inválido: {mes:02d}. Use valores entre 01 e 12.")
        return ano, mes

    def _db_to_lancamento(self, db_lanc: DRELancamentoDB) -> DRELancamento:
        """Converte lançamento do DB para domínio."""
        from datetime import date

        # Parse data_lancamento (ISO format)
        data_str = db_lanc.data_lancamento
        try:
            data = date.fromisoformat(data_str)
        except ValueError:
            # Tenta outros formatos
            from datetime import datetime

            try:
                data = datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError:
                data = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S").date()

        return DRELancamento(
            data=data,
            historico=db_lanc.historico,
            credito=db_lanc.credito,
            debito=db_lanc.debito,
            natureza=db_lanc.natureza_norm or db_lanc.natureza_raw or "",
            centro_custo=db_lanc.centro_custo or "",
            rubrica=db_lanc.rubrica or "",
            conta_pai=db_lanc.conta_pai or "",
            linha_origem=db_lanc.linha_origem,
        )

    def verificar_dados(self, competencia: str, centro_custo: str | None = None) -> dict[str, Any]:
        """Verifica se há dados suficientes para geração."""
        try:
            ano, mes = self._parse_competencia(competencia)
        except ValueError as e:
            return {"valido": False, "error": str(e)}

        # Busca resumo YTD
        resumo = self.repository.get_resumo_ytd(ano, mes)

        # Verifica meses faltantes
        meses_disponiveis = set()
        for m in range(1, mes + 1):
            # Verifica se existe upload para o mês
            uploads = self.repository.uploads.get_by_competencia(ano, m)
            if uploads and any(u.status == "completed" for u in uploads):
                meses_disponiveis.add(m)

        meses_faltantes = set(range(1, mes + 1)) - meses_disponiveis

        return {
            "valido": resumo["total_lancamentos"] > 0,
            "competencia": competencia,
            "ano": ano,
            "mes": mes,
            "meses_disponiveis": sorted(meses_disponiveis),
            "meses_faltantes": sorted(meses_faltantes),
            "total_lancamentos_acumulado": resumo["total_lancamentos"],
            "total_credito_acumulado": float(resumo["total_credito"]),
            "total_debito_acumulado": float(resumo["total_debito"]),
            "saldo_liquido_acumulado": float(resumo["saldo_liquido"]),
        }

    def gerar_lote_cumulativo(
        self,
        competencia: str,
        centro_custo: str | None = None,
    ) -> DRELote:
        """
        Gera lote cumulativo YTD (Year to Date).

        Args:
            competencia: Competência final no formato MM/AAAA
            centro_custo: Filtro opcional por obra/centro de custo

        Returns:
            DRELote com lançamentos acumulados
        """
        ano, mes = self._parse_competencia(competencia)

        # Busca lançamentos YTD
        query = None
        if centro_custo:
            query = DRECompetenciaQuery(ano=ano, mes=mes, centro_custo=centro_custo)

        lancamentos_db = self.repository.get_lancamentos_ytd(ano, mes, query)

        if not lancamentos_db:
            logger.warning("Nenhum lançamento encontrado para %s", competencia)
            return DRELote(
                competencia=competencia,
                arquivo_origem="banco_dados",
                lancamentos=[],
            )

        # Converte para domínio
        lancamentos = [self._db_to_lancamento(lancamento) for lancamento in lancamentos_db]

        logger.info("Gerado lote cumulativo para %s: %d lançamentos", competencia, len(lancamentos))

        return DRELote(
            competencia=competencia,
            arquivo_origem="banco_dados_cumulativo",
            lancamentos=lancamentos,
        )

    def get_agregado_apoio(self, competencia: str) -> list[dict[str, Any]]:
        """
        Retorna dados agregados por conta_pai x mês para aba APOIO.

        Args:
            competencia: Competência no formato MM/AAAA

        Returns:
            Lista de dicionários com agregação
        """
        ano, mes = self._parse_competencia(competencia)
        return self.repository.lancamentos.get_agregado_por_conta_mes(ano, mes)

    def get_resumo_mensal(self, ano: int, mes: int) -> dict[str, Any] | None:
        """Retorna resumo do mês específico."""
        resumo = self.repository.lancamentos.get_resumo_competencia(ano, mes)
        if resumo:
            return {
                "competencia": f"{resumo.competencia_mes:02d}/{resumo.competencia_ano}",
                "total_lancamentos": resumo.total_lancamentos,
                "total_credito": float(resumo.total_credito),
                "total_debito": float(resumo.total_debito),
                "saldo_liquido": float(resumo.saldo_liquido),
                "total_contas_pai": resumo.total_contas_pai,
                "total_centros_custo": resumo.total_centros_custo,
            }
        return None
