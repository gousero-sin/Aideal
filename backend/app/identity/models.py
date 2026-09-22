"""Objetos imutáveis expostos pelo domínio de identidade."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class User:
    id: str
    username: str
    display_name: str
    active: bool
    is_system_owner: bool
    must_change_password: bool
    permissions: tuple[str, ...]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "active": self.active,
            "is_system_owner": self.is_system_owner,
            "must_change_password": self.must_change_password,
            "permissions": list(self.permissions),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    user: User
    csrf_token: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    event_type: str
    actor_user_id: str | None
    target_user_id: str | None
    metadata: dict[str, Any]
    created_at: datetime
