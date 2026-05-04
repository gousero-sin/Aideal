"""Merger de Fluxo de Caixa — consolida múltiplos lotes em base única."""

import logging

from ..contracts.fluxo_caixa import FCLote

logger = logging.getLogger(__name__)


class FluxoCaixaMerger:
    """Consolida múltiplos FCLotes de bancos diferentes em um lote unificado."""

    def consolidar(self, lotes: list[FCLote], periodo: str) -> FCLote:
        """Merge múltiplos FCLotes em um único lote consolidado.

        Args:
            lotes: lista de FCLotes individuais (um por arquivo/banco)
            periodo: período de referência da consolidação

        Returns:
            FCLote unificado com todos os movimentos e rastreabilidade
        """
        consolidado = FCLote(periodo=periodo)

        for lote in lotes:
            consolidado.arquivos_origem.extend(lote.arquivos_origem)
            consolidado.bancos.extend(lote.bancos)
            consolidado.movimentos.extend(lote.movimentos)

        # Ordenar por data e banco
        consolidado.movimentos.sort(key=lambda m: (m.data_movimento, m.banco_origem))

        # Deduplica bancos
        consolidado.bancos = list(set(consolidado.bancos))

        logger.info(
            f"Consolidação FC: {len(lotes)} arquivo(s), "
            f"{len(consolidado.bancos)} banco(s), "
            f"{consolidado.total_registros} movimento(s)"
        )

        return consolidado
