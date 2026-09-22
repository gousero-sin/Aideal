"""API pública do módulo de Orçamento do GoFlow."""

from .dfp import compute_dfp_summary, get_dfp_window_schema, normalize_dfp_payload
from .exceptions import (
    CodigoAlreadyExistsError,
    InvalidOrcamentoInputError,
    InvalidSituacaoTransitionError,
    OrcamentoError,
    OrcamentoNotFoundError,
    RevisaoNotFoundError,
)
from .models import (
    MODALIDADES,
    SITUACAO_EM_REVISAO,
    SITUACAO_EMITIDO,
    SITUACAO_INATIVO,
    SITUACAO_PRONTO_PARA_PROPOSTA,
    SITUACAO_RASCUNHO,
    SITUACOES,
    VALIDADE_PADRAO_DIAS,
    VERSAO_REGRAS,
    Orcamento,
    Revisao,
    SituacaoEvento,
    calcular_validade,
    formatar_codigo,
)
from .service import OrcamentoService, create_orcamento_service

__all__ = [
    "MODALIDADES",
    "SITUACAO_EMITIDO",
    "SITUACAO_EM_REVISAO",
    "SITUACAO_INATIVO",
    "SITUACAO_PRONTO_PARA_PROPOSTA",
    "SITUACAO_RASCUNHO",
    "SITUACOES",
    "VALIDADE_PADRAO_DIAS",
    "VERSAO_REGRAS",
    "CodigoAlreadyExistsError",
    "InvalidOrcamentoInputError",
    "InvalidSituacaoTransitionError",
    "Orcamento",
    "OrcamentoError",
    "OrcamentoNotFoundError",
    "OrcamentoService",
    "Revisao",
    "RevisaoNotFoundError",
    "SituacaoEvento",
    "calcular_validade",
    "compute_dfp_summary",
    "create_orcamento_service",
    "formatar_codigo",
    "get_dfp_window_schema",
    "normalize_dfp_payload",
]
