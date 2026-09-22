"""Erros de domínio do controle de identidade."""


class IdentityError(Exception):
    """Base para erros esperados do domínio de identidade."""


class InvalidCredentialsError(IdentityError):
    """Credenciais inválidas sem revelar qual campo falhou."""


class InvalidIdentityInputError(IdentityError):
    """Entrada inválida em uma operação de identidade."""


class UserNotFoundError(IdentityError):
    """Usuário não encontrado."""


class UsernameAlreadyExistsError(IdentityError):
    """Nome de usuário já cadastrado."""


class UnknownPermissionError(IdentityError):
    """Uma ou mais permissões não existem no catálogo."""


class LastOwnerError(IdentityError):
    """Operação removeria uma proteção obrigatória do proprietário do sistema."""
