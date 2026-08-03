"""Conciliação diagnóstica de transferências entre contas bancárias próprias."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ..contracts.fluxo_caixa import FCMovimento


def _detalhe_movimento(movimento: FCMovimento) -> dict:
    return {
        "data": movimento.data_movimento.isoformat(),
        "valor": float(abs(movimento.valor)),
        "banco": movimento.banco_origem,
        "direcao": "emitida" if movimento.transferencia_emitida else "recebida",
        "descricao": movimento.descricao,
        "arquivo": movimento.arquivo_origem,
        "linha": movimento.linha_origem,
    }


def conciliar_transferencias(
    movimentos: list[FCMovimento],
    tolerancia_dias: int = 1,
) -> dict:
    """Pareia transferências por valor, bancos distintos e data próxima.

    A conciliação é somente diagnóstica. Transferências permanecem neutras no
    caixa consolidado mesmo quando a exportação contém apenas um dos lados.
    """
    transferencias = [mov for mov in movimentos if mov.eh_transferencia]
    emitidas = sorted(
        (mov for mov in transferencias if mov.transferencia_emitida),
        key=lambda mov: (mov.data_movimento, abs(mov.valor), mov.banco_origem),
    )
    recebidas = sorted(
        (mov for mov in transferencias if not mov.transferencia_emitida),
        key=lambda mov: (mov.data_movimento, abs(mov.valor), mov.banco_origem),
    )
    recebidas_disponiveis = set(range(len(recebidas)))
    pares: list[dict] = []
    nao_pareadas: list[FCMovimento] = []
    tolerancia = timedelta(days=max(int(tolerancia_dias), 0))

    for emitida in emitidas:
        candidatos = [
            indice
            for indice in recebidas_disponiveis
            if abs(recebidas[indice].valor) == abs(emitida.valor)
            and recebidas[indice].banco_origem.strip().lower()
            != emitida.banco_origem.strip().lower()
            and abs(recebidas[indice].data_movimento - emitida.data_movimento) <= tolerancia
        ]
        if not candidatos:
            nao_pareadas.append(emitida)
            continue

        indice = min(
            candidatos,
            key=lambda item: (
                abs((recebidas[item].data_movimento - emitida.data_movimento).days),
                recebidas[item].data_movimento,
                recebidas[item].banco_origem,
            ),
        )
        recebidas_disponiveis.remove(indice)
        pares.append(
            {
                "emitida": _detalhe_movimento(emitida),
                "recebida": _detalhe_movimento(recebidas[indice]),
            }
        )

    nao_pareadas.extend(recebidas[indice] for indice in sorted(recebidas_disponiveis))
    total_emitidas = sum((abs(mov.valor) for mov in emitidas), Decimal("0"))
    total_recebidas = sum((abs(mov.valor) for mov in recebidas), Decimal("0"))

    return {
        "total_transferencias": len(transferencias),
        "pares": len(pares),
        "nao_pareadas": len(nao_pareadas),
        "total_emitidas": float(total_emitidas),
        "total_recebidas": float(total_recebidas),
        "diferenca_recebidas_emitidas": float(total_recebidas - total_emitidas),
        "impacta_saldo_financeiro": False,
        "tolerancia_dias": max(int(tolerancia_dias), 0),
        "detalhes_nao_pareadas": [_detalhe_movimento(mov) for mov in nao_pareadas],
    }
