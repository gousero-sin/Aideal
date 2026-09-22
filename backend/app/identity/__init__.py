"""API pública do controle de acesso do GoFlow."""

from .exceptions import (
    IdentityError,
    InvalidCredentialsError,
    InvalidIdentityInputError,
    LastOwnerError,
    UnknownPermissionError,
    UsernameAlreadyExistsError,
    UserNotFoundError,
)
from .models import AuditEvent, Session, SessionCredentials, User
from .passwords import Argon2PasswordHasher, PasswordHashUnavailableError
from .service import DEFAULT_PERMISSIONS, IdentityService, create_identity_service

__all__ = [
    "DEFAULT_PERMISSIONS",
    "Argon2PasswordHasher",
    "AuditEvent",
    "IdentityError",
    "IdentityService",
    "InvalidCredentialsError",
    "InvalidIdentityInputError",
    "LastOwnerError",
    "PasswordHashUnavailableError",
    "Session",
    "SessionCredentials",
    "UnknownPermissionError",
    "User",
    "UserNotFoundError",
    "UsernameAlreadyExistsError",
    "create_identity_service",
]
