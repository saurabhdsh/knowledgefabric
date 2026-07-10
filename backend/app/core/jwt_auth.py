"""JWT bearer middleware for Weave UI and API sessions."""
from __future__ import annotations

import logging
import os
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.user_context import current_user_id, current_username
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

AUTH_HEADER = "Authorization"

_JWT_DISABLED = os.environ.get("JWT_AUTH_DISABLED", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_PUBLIC_PREFIXES = (
    "/api/v1/auth/login",
)


def _matches_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


def _is_public_auth_path(path: str) -> bool:
    return _matches_any(path, _PUBLIC_PREFIXES)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid Bearer JWT on protected /api/v1 routes."""

    async def dispatch(self, request: Request, call_next):
        if _JWT_DISABLED:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/v1/") or _is_public_auth_path(path):
            return await call_next(request)

        auth_header = request.headers.get(AUTH_HEADER) or request.headers.get(AUTH_HEADER.lower())
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated. Sign in to Weave."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:].strip()
        payload = auth_service.decode_token(token)
        if not payload or not payload.get("sub"):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired session. Please sign in again."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = auth_service.get_user_by_id(str(payload["sub"]))
        if not user or not user.is_active:
            return JSONResponse(
                status_code=401,
                content={"detail": "User account is inactive or not found."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user_id = user.id
        request.state.username = user.username
        request.state.display_name = user.display_name
        request.state.role = user.role or "user"
        request.state.allowed_features = auth_service.effective_features(user)

        user_token = current_user_id.set(user.id)
        username_token = current_username.set(user.username)
        try:
            return await call_next(request)
        finally:
            current_user_id.reset(user_token)
            current_username.reset(username_token)
