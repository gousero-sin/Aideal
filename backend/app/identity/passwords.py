"""Hash e verificação de senhas com migração segura do formato legado."""

import hashlib
import hmac
from dataclasses import dataclass

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError
    from argon2.low_level import Type
except ImportError:  # pragma: no cover - coberto pelo caminho sem dependência
    PasswordHasher = None  # type: ignore[assignment,misc]
    InvalidHashError = VerificationError = ValueError  # type: ignore[misc]
    Type = None  # type: ignore[assignment,misc]


class PasswordHashUnavailableError(RuntimeError):
    """Argon2id não está instalado; novos hashes não podem ser criados."""


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    valid: bool
    needs_rehash: bool = False


class Argon2PasswordHasher:
    """Produz Argon2id e reconhece SHA-256 apenas para migração legada."""

    def __init__(self) -> None:
        self._hasher = (
            PasswordHasher(
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                salt_len=16,
                type=Type.ID,
            )
            if PasswordHasher is not None
            else None
        )

    @property
    def available(self) -> bool:
        return self._hasher is not None

    def hash(self, password: str) -> str:
        if self._hasher is None:
            raise PasswordHashUnavailableError(
                "argon2-cffi é obrigatório para criar ou atualizar senhas"
            )
        return str(self._hasher.hash(password))

    def verify(self, password: str, encoded_hash: str) -> PasswordVerification:
        normalized_hash = encoded_hash.strip()
        if normalized_hash.startswith("$argon2"):
            return self._verify_argon2(password, normalized_hash)
        return self._verify_legacy_sha256(password, normalized_hash)

    def _verify_argon2(self, password: str, encoded_hash: str) -> PasswordVerification:
        if self._hasher is None:
            return PasswordVerification(valid=False)
        try:
            valid = bool(self._hasher.verify(encoded_hash, password))
        except (VerificationError, InvalidHashError, ValueError):
            return PasswordVerification(valid=False)
        return PasswordVerification(
            valid=valid,
            needs_rehash=valid and self._hasher.check_needs_rehash(encoded_hash),
        )

    @staticmethod
    def _verify_legacy_sha256(password: str, encoded_hash: str) -> PasswordVerification:
        expected = encoded_hash.removeprefix("sha256:")
        if len(expected) != 64:
            return PasswordVerification(valid=False)
        actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return PasswordVerification(
            valid=hmac.compare_digest(actual, expected.lower()),
            needs_rehash=True,
        )
