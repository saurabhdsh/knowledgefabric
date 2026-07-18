"""
Inbound API-key middleware.

Behavior:
- All ``/api/v1/*`` routes require an ``X-API-Key`` header from EXTERNAL callers.
- Browser/UI requests with a JWT already validated by ``JWTAuthMiddleware`` are
  exempt; users must not need both a JWT and an integration API key.
- Local traffic (the React dev server on ``localhost:3000`` calling the backend
  on ``localhost:8000``) is automatically exempt, so the existing dev workflow
  keeps working unchanged.
- Tunnelled traffic (ngrok, Cloudflare Tunnel, reverse proxies) always requires
  a key: tunnels are detected by ``X-Forwarded-*`` / ``ngrok-*`` headers.
- Public endpoints (root, ``/health``, ``/docs``, ``/redoc``, OpenAPI JSON,
  ``/uploads/*``) are always open.
- CORS preflight (``OPTIONS``) requests pass through.

Escape hatches:
- Set ``INBOUND_AUTH_DISABLED=true`` to globally bypass (NOT recommended on
  tunneled / public hosts).
- Set ``INBOUND_AUTH_BYPASS_PATHS`` to a comma-separated list of additional
  path prefixes to exempt (rare; for quick demos).
"""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.inbound_api_key_service import inbound_api_key_service

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"

# Public routes (never require a key).
_PUBLIC_EXACT = {"/", "/health"}
_PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/openapi.json",
    "/api/v1/auth/",
    "/uploads/",
)

# Only routes under these prefixes are guarded. Anything else (static, etc.)
# falls through untouched.
_PROTECTED_PREFIXES = ("/api/v1/",)

_DISABLED = os.environ.get("INBOUND_AUTH_DISABLED", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_EXTRA_BYPASS = tuple(
    p.strip()
    for p in os.environ.get("INBOUND_AUTH_BYPASS_PATHS", "").split(",")
    if p.strip()
)

# Explicit LAN / private-network ranges treated as "local" (no API key).
# We do NOT use ipaddress.is_private because in newer Python it also covers
# TEST-NET / documentation ranges, which we want to require a key for.
_PRIVATE_LAN_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",       # RFC1918
        "172.16.0.0/12",    # RFC1918 (Docker bridges sit here)
        "192.168.0.0/16",   # RFC1918
        "169.254.0.0/16",   # IPv4 link-local
        "fc00::/7",         # IPv6 unique local
        "fe80::/10",        # IPv6 link-local
    )
)


def _is_local_origin(request: Request) -> bool:
    """A request is 'local' (no API key required) when:
      * the TCP client IP is loopback or in a private RFC1918 range
        (covers bare-metal localhost AND Docker bridge / LAN dev), AND
      * no proxy / tunnel forwarding header is present (ngrok, Cloudflare,
        reverse proxies always set one of these — tunnelled traffic must
        carry a key).
    """
    # Tunnels are NEVER local, regardless of source IP.
    headers_lower = {k.lower() for k in request.headers.keys()}
    forwarding = {"x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded"}
    if forwarding & headers_lower:
        return False
    if any(h.startswith("ngrok-") for h in headers_lower):
        return False

    client = request.client
    client_ip = client.host if client else None
    if not client_ip:
        return False
    if client_ip == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return any(ip in net for net in _PRIVATE_LAN_NETWORKS)


def _matches_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(p) for p in prefixes)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    if _matches_any(path, _PUBLIC_PREFIXES):
        return True
    if _EXTRA_BYPASS and _matches_any(path, _EXTRA_BYPASS):
        return True
    return False


def _is_protected(path: str) -> bool:
    return _matches_any(path, _PROTECTED_PREFIXES)


class InboundAPIKeyMiddleware(BaseHTTPMiddleware):
    """Enforces ``X-API-Key`` on protected routes for non-local callers."""

    async def dispatch(self, request: Request, call_next):
        if _DISABLED:
            return await call_next(request)
        if request.method == "OPTIONS":  # CORS preflight
            return await call_next(request)

        path = request.url.path

        if _is_public(path) or not _is_protected(path):
            return await call_next(request)

        if _is_local_origin(request):
            return await call_next(request)

        # JWTAuthMiddleware runs before this middleware and places the validated
        # UI user on request.state. A browser session uses JWT authentication;
        # X-API-Key is reserved for external/partner integrations.
        if getattr(request.state, "user_id", None):
            return await call_next(request)

        key = request.headers.get(API_KEY_HEADER) or request.headers.get(
            API_KEY_HEADER.lower()
        )
        if not key:
            logger.info("Rejecting %s %s — missing %s", request.method, path, API_KEY_HEADER)
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        f"Missing {API_KEY_HEADER} header. External callers must "
                        "supply an inbound API key issued via "
                        "scripts/issue_api_key.py."
                    )
                },
                headers={"WWW-Authenticate": API_KEY_HEADER},
            )

        record = inbound_api_key_service.validate(key)
        if not record:
            logger.info(
                "Rejecting %s %s — invalid/expired/revoked key (prefix %s)",
                request.method,
                path,
                (key[:12] + "…") if len(key) > 12 else key,
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid, expired, or revoked API key."},
                headers={"WWW-Authenticate": API_KEY_HEADER},
            )

        # Surface the authenticated consumer for downstream handlers / logging.
        request.state.consumer_id = record.id
        request.state.consumer_name = record.name
        request.state.consumer_scopes = record.scopes
        request.state.consumer_fabric_ids = record.fabric_ids

        return await call_next(request)
