"""Erros de domínio do módulo de Orçamento."""


class OrcamentoError(Exception):
    """Base para erros esperados do domínio de orçamento."""


class InvalidOrcamentoInputError(OrcamentoError):
    """Entrada inválida em uma operação de orçamento."""


class OrcamentoNotFoundError(OrcamentoError):
    """Orçamento não encontrado."""


class RevisaoNotFoundError(OrcamentoError):
    """Revisão não encontrada."""


class CodigoAlreadyExistsError(OrcamentoError):
    """Código de orçamento já cadastrado."""


class InvalidSituacaoTransitionError(OrcamentoError):
    """Transição de situação não permitida pelo ciclo de vida documental."""
