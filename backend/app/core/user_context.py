"""Request-scoped user identity for multi-tenant data isolation."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
current_username: ContextVar[Optional[str]] = ContextVar("current_username", default=None)


def get_current_user_id() -> Optional[str]:
    return current_user_id.get()


def get_current_username() -> Optional[str]:
    return current_username.get()
