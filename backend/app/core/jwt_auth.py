"""JWT bearer middleware for Weave UI and API sessions.

Partner integrations may authenticate with ``X-API-Key`` instead of a JWT.
When a key is present and valid, the request continues without a Bearer token;
fabric and scope limits on the key are enforced here so a key issued for one
fabric cannot read another.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Iterable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.user_context import current_user_id, current_username
from app.services.auth_service import auth_service
from app.services.inbound_api_key_service import inbound_api_key_service

logger = logging.getLogger(__name__)

AUTH_HEADER = "Authorization"
API_KEY_HEADER = "X-API-Key"

_PUBLIC_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/entra",
)


def _jwt_disabled() -> bool:
    return os.environ.get("JWT_AUTH_DISABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

# Paths that look like they act on a single fabric. Used to enforce fabric_ids.
_FABRIC_PATH = re.compile(
    r"/api/v1/(?:knowledge|query|agent|graph|governance|ontology)/"
    r"(?:fabrics/)?(?P<fid>[A-Za-z0-9_\-]+)"
)

# Map HTTP method + path fragment → required scope.
_SCOPE_RULES = (
    ("POST", "/query", "query"),
    ("POST", "/ask", "query"),
    ("GET", "/knowledge", "read"),
    ("POST", "/knowledge", "write"),
)


def _matches_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


def _is_public_auth_path(path: str) -> bool:
    return _matches_any(path, _PUBLIC_PREFIXES)


def _required_scope(method: str, path: str) -> Optional[str]:
    method = method.upper()
    for m, fragment, scope in _SCOPE_RULES:
        if method == m and fragment in path:
            return scope
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"
    return "read"


def _fabric_id_from_path(path: str) -> Optional[str]:
    match = _FABRIC_PATH.search(path)
    if not match:
        return None
    fid = match.group("fid")
    # Skip known non-id path segments.
    if fid in {
        "sources", "stats", "create", "upload", "export", "models",
        "train-ml-models", "distribute-model", "create-servicenow-fabric",
        "create-knowledge-fabric", "enrichment", "feedback", "sessions",
    }:
        return None
    return fid


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid Bearer JWT, or a valid inbound API key, on /api/v1 routes."""

    async def dispatch(self, request: Request, call_next):
        if _jwt_disabled():
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/v1/") or _is_public_auth_path(path):
            return await call_next(request)

        # Partner key path — validate before requiring a JWT.
        api_key = request.headers.get(API_KEY_HEADER) or request.headers.get(API_KEY_HEADER.lower())
        if api_key and not (request.headers.get(AUTH_HEADER) or "").lower().startswith("bearer "):
            record = inbound_api_key_service.validate(api_key)
            if not record:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid, expired, or revoked API key."},
                    headers={"WWW-Authenticate": API_KEY_HEADER},
                )
            scopes = set(record.scopes or [])
            needed = _required_scope(request.method, path)
            if needed and scopes and needed not in scopes and "admin" not in scopes:
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"API key is missing the '{needed}' scope."},
                )
            allowed_fabrics = record.fabric_ids
            fabric_id = _fabric_id_from_path(path)
            if allowed_fabrics is not None and fabric_id and fabric_id not in allowed_fabrics:
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"API key is not allowed to access fabric '{fabric_id}'."},
                )
            request.state.consumer_id = record.id
            request.state.consumer_name = record.name
            request.state.consumer_scopes = record.scopes
            request.state.consumer_fabric_ids = record.fabric_ids
            request.state.auth_via = "api_key"
            return await call_next(request)

        auth_header = request.headers.get(AUTH_HEADER) or request.headers.get(AUTH_HEADER.lower())
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated. Sign in to Weave, or supply an X-API-Key."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:].strip()
        if auth_service.is_token_revoked(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Session has been revoked. Please sign in again."},
                headers={"WWW-Authenticate": "Bearer"},
            )
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
        request.state.must_change_password = bool(getattr(user, "must_change_password", False))
        request.state.auth_via = "jwt"
        request.state.token_jti = payload.get("jti")

        user_token = current_user_id.set(user.id)
        username_token = current_username.set(user.username)
        try:
            return await call_next(request)
        finally:
            current_user_id.reset(user_token)
            current_username.reset(username_token)
