"""Autenticação da aba administrativa do banco."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request, Response

from .config import settings

ADMIN_SESSION_COOKIE = "aideal_admin_session"


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _admin_username() -> str:
    return settings.admin_username.strip()


def _admin_secret() -> str:
    return settings.admin_session_secret.strip()


def admin_auth_configured() -> bool:
    """Retorna se a autenticação admin tem credenciais e segredo de sessão."""
    return bool(
        _admin_username()
        and (settings.admin_password or settings.admin_password_hash)
        and _admin_secret()
    )


def _raise_not_configured() -> None:
    raise HTTPException(
        status_code=503,
        detail="Autenticação admin não configurada.",
    )


def ensure_admin_auth_configured() -> None:
    if not admin_auth_configured():
        _raise_not_configured()


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verify_password_hash(password: str, configured_hash: str) -> bool:
    value = configured_hash.strip()
    if not value:
        return False

    if value.startswith("sha256:"):
        expected = value.removeprefix("sha256:")
    else:
        expected = value

    return hmac.compare_digest(_sha256_hex(password), expected)


def verify_admin_credentials(username: str, password: str) -> bool:
    """Valida usuário/senha admin usando comparação constante."""
    ensure_admin_auth_configured()
    user_ok = hmac.compare_digest(username.strip(), _admin_username())
    password_ok = False

    if settings.admin_password:
        password_ok = hmac.compare_digest(password, settings.admin_password)
    elif settings.admin_password_hash:
        password_ok = _verify_password_hash(password, settings.admin_password_hash)

    return user_ok and password_ok


def create_admin_session_token(username: str, now: int | None = None) -> str:
    """Cria token de sessão assinado via HMAC."""
    ensure_admin_auth_configured()
    issued_at = int(time.time() if now is None else now)
    max_age = max(60, int(settings.admin_session_max_age_seconds))
    payload = {
        "u": username,
        "iat": issued_at,
        "exp": issued_at + max_age,
    }
    encoded_payload = _b64_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        _admin_secret().encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_b64_encode(signature)}"


def verify_admin_session_token(token: str | None, now: int | None = None) -> dict[str, Any] | None:
    """Retorna o payload da sessão se o cookie estiver íntegro e vigente."""
    if not token or "." not in token or not admin_auth_configured():
        return None

    encoded_payload, encoded_signature = token.split(".", 1)
    expected_signature = _b64_encode(
        hmac.new(
            _admin_secret().encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(encoded_signature, expected_signature):
        return None

    try:
        payload = json.loads(_b64_decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    expires_at = int(payload.get("exp") or 0)
    current_time = int(time.time() if now is None else now)
    username = str(payload.get("u") or "")
    if expires_at < current_time or not hmac.compare_digest(username, _admin_username()):
        return None
    return payload


def set_admin_session_cookie(response: Response, username: str) -> None:
    token = create_admin_session_token(username)
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        max_age=max(60, int(settings.admin_session_max_age_seconds)),
        httponly=True,
        secure=bool(settings.admin_cookie_secure),
        samesite="strict",
        path="/",
    )


def clear_admin_session_cookie(response: Response) -> None:
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        httponly=True,
        secure=bool(settings.admin_cookie_secure),
        samesite="strict",
        path="/",
    )


def current_admin_username(request: Request) -> str | None:
    payload = verify_admin_session_token(request.cookies.get(ADMIN_SESSION_COOKIE))
    if not payload:
        return None
    return str(payload["u"])


def require_admin_session(request: Request) -> str:
    """Dependência FastAPI para endpoints operacionais."""
    ensure_admin_auth_configured()
    username = current_admin_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="Sessão admin obrigatória.")
    return username
