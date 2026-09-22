"""Integração HTTP do controle de identidade e autorização do GoFlow."""

from __future__ import annotations

from datetime import timedelta
from threading import RLock
from time import monotonic
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Response, status

from .config import settings
from .identity import IdentityService, InvalidIdentityInputError, Session, create_identity_service
from .orcamento import OrcamentoService, create_orcamento_service

SESSION_COOKIE = "aideal_session"
LEGACY_ADMIN_COOKIE = "aideal_admin_session"
CSRF_HEADER = "X-CSRF-Token"

MODULE_CATALOG: tuple[dict[str, str], ...] = (
    {"id": "dre", "label": "DRE", "permission": "dre.view"},
    {"id": "fluxo_caixa", "label": "Fluxo de Caixa", "permission": "fluxo.view"},
    {"id": "admin_banco", "label": "Admin Banco", "permission": "admin_banco.use"},
    {"id": "usuarios", "label": "Controle de Acessos", "permission": "users.manage"},
    {"id": "orcamento", "label": "Orçamento", "permission": "orcamento.view"},
)

_service_lock = RLock()
_identity_service: IdentityService | None = None
_orcamento_service: OrcamentoService | None = None
_login_attempts: dict[str, tuple[float, ...]] = {}


def configure_identity_service(service: IdentityService | None) -> None:
    """Substitui o serviço global; usado para isolamento da suíte de testes."""
    global _identity_service
    with _service_lock:
        _identity_service = service
        _login_attempts.clear()


def _login_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().casefold()}"


def enforce_login_rate_limit(request: Request, username: str) -> None:
    """Bloqueia tentativas repetidas por combinação IP + usuário."""
    now = monotonic()
    cutoff = now - settings.login_window_seconds
    key = _login_key(request, username)
    with _service_lock:
        recent = tuple(item for item in _login_attempts.get(key, ()) if item >= cutoff)
        if len(recent) >= settings.login_max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas de login. Aguarde e tente novamente.",
            )
        _login_attempts[key] = recent


def record_login_result(request: Request, username: str, *, authenticated: bool) -> None:
    key = _login_key(request, username)
    with _service_lock:
        if authenticated:
            _login_attempts.pop(key, None)
            return
        _login_attempts[key] = (*_login_attempts.get(key, ()), monotonic())


def _bootstrap_service(service: IdentityService) -> IdentityService:
    try:
        if settings.admin_password:
            service.bootstrap_eduardo(
                password=settings.admin_password,
                username=settings.admin_username or "Eduardo",
                display_name=settings.admin_username or "Eduardo",
            )
        elif settings.admin_password_hash:
            service.bootstrap_eduardo(
                password_hash=settings.admin_password_hash,
                username=settings.admin_username or "Eduardo",
                display_name=settings.admin_username or "Eduardo",
            )
        else:
            # Em uma base já inicializada, a chamada apenas recupera o owner.
            service.bootstrap_eduardo(
                username=settings.admin_username or "Eduardo",
                display_name=settings.admin_username or "Eduardo",
            )
    except InvalidIdentityInputError as exc:
        raise RuntimeError(
            "Controle de acesso não inicializado. Configure AIDEAL_ADMIN_PASSWORD."
        ) from exc
    return service


def get_identity_service() -> IdentityService:
    global _identity_service
    with _service_lock:
        if _identity_service is None:
            service = create_identity_service(
                settings.identity_db_path,
                session_ttl=timedelta(seconds=settings.admin_session_max_age_seconds),
            )
            _identity_service = _bootstrap_service(service)
        return _identity_service


def configure_orcamento_service(service: OrcamentoService | None) -> None:
    """Substitui o serviço global; usado para isolamento da suíte de testes."""
    global _orcamento_service
    with _service_lock:
        _orcamento_service = service


def get_orcamento_service() -> OrcamentoService:
    global _orcamento_service
    with _service_lock:
        if _orcamento_service is None:
            _orcamento_service = create_orcamento_service(settings.orcamento_db_path)
        return _orcamento_service


def _session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE) or request.cookies.get(LEGACY_ADMIN_COOKIE)


def set_session_cookie(response: Response, token: str, *, include_legacy: bool = False) -> None:
    cookie_options = {
        "httponly": True,
        "secure": settings.admin_cookie_secure,
        "samesite": "strict",
        "max_age": settings.admin_session_max_age_seconds,
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, token, **cookie_options)
    if include_legacy:
        response.set_cookie(LEGACY_ADMIN_COOKIE, token, **cookie_options)


def clear_session_cookies(response: Response) -> None:
    for cookie_name in (SESSION_COOKIE, LEGACY_ADMIN_COOKIE):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=settings.admin_cookie_secure,
            httponly=True,
            samesite="strict",
        )


def modules_for_permissions(permissions: tuple[str, ...] | list[str]) -> list[dict[str, str]]:
    granted = frozenset(permissions)
    return [dict(module) for module in MODULE_CATALOG if module["permission"] in granted]


def session_payload(service: IdentityService, token: str) -> dict[str, Any]:
    payload = service.session_payload(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão obrigatória.")
    permissions = list(payload["permissions"])
    password_change_required = bool(payload["user"]["must_change_password"])
    return {
        "authenticated": True,
        **payload,
        "password_change_required": password_change_required,
        "modules": [] if password_change_required else modules_for_permissions(permissions),
    }


def require_authenticated_user(request: Request) -> Session:
    try:
        service = get_identity_service()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    session = service.resolve_session(_session_token(request))
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão obrigatória.")
    return session


AuthenticatedSession = Annotated[Session, Depends(require_authenticated_user)]


def require_permission(permission: str):
    def dependency(session: AuthenticatedSession) -> Session:
        if session.user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Troca de senha obrigatória.",
            )
        if permission not in session.user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão {permission} obrigatória.",
            )
        return session

    return dependency


def require_permissions(*permissions: str):
    def dependency(session: AuthenticatedSession) -> Session:
        if session.user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Troca de senha obrigatória.",
            )
        missing = [item for item in permissions if item not in session.user.permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissões obrigatórias ausentes.",
            )
        return session

    return dependency


def require_permission_with_csrf(permission: str):
    """Exige autorização e CSRF para operações que alteram estado."""

    def dependency(session: CsrfSession) -> Session:
        if session.user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Troca de senha obrigatória.",
            )
        if permission not in session.user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão {permission} obrigatória.",
            )
        return session

    return dependency


def require_permissions_with_csrf(*permissions: str):
    """Exige todas as permissões informadas e CSRF em operações de escrita."""

    def dependency(session: CsrfSession) -> Session:
        if session.user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Troca de senha obrigatória.",
            )
        if any(permission not in session.user.permissions for permission in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissões obrigatórias ausentes.",
            )
        return session

    return dependency


def require_csrf(request: Request, session: AuthenticatedSession) -> Session:
    csrf_token = request.headers.get(CSRF_HEADER)
    if not get_identity_service().verify_csrf(_session_token(request), csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido.")
    return session


CsrfSession = Annotated[Session, Depends(require_csrf)]


def token_from_request(request: Request) -> str | None:
    return _session_token(request)
