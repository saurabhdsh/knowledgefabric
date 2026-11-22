"""Weave JWT authentication endpoints."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services.auth_service import auth_service

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=10, max_length=256)


class EntraExchangeRequest(BaseModel):
    """Exchange an Entra ID (Azure AD) ID token for a Weave session.

    Requires ``ENTRA_TENANT_ID`` and ``ENTRA_CLIENT_ID`` on the host. The
    browser obtains the ID token via MSAL; this endpoint verifies the issuer
    and audience, then maps ``preferred_username`` / ``email`` to a Weave user.
    """

    id_token: str = Field(..., min_length=20)


@router.post("/login", response_model=APIResponse)
async def login(request: LoginRequest):
    try:
        user = auth_service.authenticate(request.username, request.password)
    except ValueError as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = auth_service.create_access_token(user)
    return APIResponse(
        success=True,
        message="Signed in successfully",
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": auth_service.user_to_dict(user),
            "must_change_password": bool(getattr(user, "must_change_password", False)),
        },
    )


@router.post("/logout", response_model=APIResponse)
async def logout(request: Request):
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        auth_service.revoke_token(auth_header[7:].strip())
    return APIResponse(success=True, message="Signed out", data={"revoked": True})


@router.post("/change-password", response_model=APIResponse)
async def change_password(body: ChangePasswordRequest, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        user = auth_service.change_password(
            user_id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Old sessions stay valid until expiry; issue a fresh token without the flag.
    token = auth_service.create_access_token(user)
    return APIResponse(
        success=True,
        message="Password updated",
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": auth_service.user_to_dict(user),
        },
    )


@router.get("/me", response_model=APIResponse)
async def get_me(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return APIResponse(
        success=True,
        message="Profile retrieved",
        data=auth_service.user_to_dict(user),
    )


@router.get("/entra/config", response_model=APIResponse)
async def entra_config():
    """Public Entra settings for the login page. Empty when SSO is not configured."""
    tenant = (os.environ.get("ENTRA_TENANT_ID") or "").strip()
    client_id = (os.environ.get("ENTRA_CLIENT_ID") or "").strip()
    enabled = bool(tenant and client_id)
    return APIResponse(
        success=True,
        message="Entra config" if enabled else "Entra SSO is not configured",
        data={
            "enabled": enabled,
            "tenant_id": tenant or None,
            "client_id": client_id or None,
            "authority": f"https://login.microsoftonline.com/{tenant}" if tenant else None,
            "scopes": ["openid", "profile", "email"],
        },
    )


@router.post("/entra/exchange", response_model=APIResponse)
async def entra_exchange(body: EntraExchangeRequest):
    """Verify an Entra ID token and open a Weave session.

    Full JWKS verification is enabled when ``ENTRA_TENANT_ID`` and
    ``ENTRA_CLIENT_ID`` are set. Without them the endpoint refuses so a
    misconfigured host cannot be used as an open login.
    """
    tenant = (os.environ.get("ENTRA_TENANT_ID") or "").strip()
    client_id = (os.environ.get("ENTRA_CLIENT_ID") or "").strip()
    if not tenant or not client_id:
        raise HTTPException(
            status_code=501,
            detail="Entra SSO is not configured on this host (set ENTRA_TENANT_ID and ENTRA_CLIENT_ID).",
        )
    try:
        from jose import jwt as jose_jwt
        import urllib.request
        import json as _json

        jwks_url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
        with urllib.request.urlopen(jwks_url, timeout=10) as resp:  # nosec B310 - fixed Microsoft host
            jwks = _json.loads(resp.read().decode("utf-8"))
        header = jose_jwt.get_unverified_header(body.id_token)
        key = next((k for k in jwks.get("keys") or [] if k.get("kid") == header.get("kid")), None)
        if not key:
            raise ValueError("Signing key not found for this token.")
        claims = jose_jwt.decode(
            body.id_token,
            key,
            algorithms=[header.get("alg") or "RS256"],
            audience=client_id,
            issuer=f"https://login.microsoftonline.com/{tenant}/v2.0",
            options={"verify_at_hash": False},
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Entra token rejected: {exc}") from exc

    email = (claims.get("preferred_username") or claims.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=401, detail="Entra token has no email claim.")
    # Map by username = local-part or full email.
    user = auth_service.get_user_by_username(email) or auth_service.get_user_by_username(email.split("@")[0])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=f"No active Weave user is mapped for '{email}'. An admin must create the account first.",
        )
    token = auth_service.create_access_token(user)
    return APIResponse(
        success=True,
        message="Signed in with Entra",
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": auth_service.user_to_dict(user),
        },
    )
