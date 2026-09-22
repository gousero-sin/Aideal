import hashlib

import pytest

from app.identity.passwords import Argon2PasswordHasher, PasswordHashUnavailableError


def test_legacy_sha256_password_is_verified_and_flagged_for_upgrade():
    senha = "senha-legada"
    encoded = hashlib.sha256(senha.encode("utf-8")).hexdigest()
    hasher = Argon2PasswordHasher()

    result = hasher.verify(senha, f"sha256:{encoded}")

    assert result.valid is True
    assert result.needs_rehash is True


def test_legacy_sha256_rejects_an_invalid_password():
    encoded = hashlib.sha256(b"senha-correta").hexdigest()
    hasher = Argon2PasswordHasher()

    result = hasher.verify("senha-incorreta", encoded)

    assert result.valid is False


def test_new_passwords_use_argon2id_when_dependency_is_available():
    hasher = Argon2PasswordHasher()
    if not hasher.available:
        with pytest.raises(PasswordHashUnavailableError):
            hasher.hash("uma-senha-segura")
        return

    encoded = hasher.hash("uma-senha-segura")

    assert encoded.startswith("$argon2id$")
    assert hasher.verify("uma-senha-segura", encoded).valid is True
    assert hasher.verify("senha-errada", encoded).valid is False
