"""Admin user management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services.auth_service import (
    FEATURE_USER_MANAGEMENT,
    ROLE_ADMIN,
    ROLE_USER,
    auth_service,
)

router = APIRouter()


def _require_admin(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user = auth_service.get_user_by_id(user_id)
    if not user or not auth_service.is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    if not auth_service.user_has_feature(user, FEATURE_USER_MANAGEMENT):
        raise HTTPException(status_code=403, detail="User management is not allowed.")
    return user


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=256)
    role: str = Field(default=ROLE_USER, pattern="^(admin|user)$")
    allowed_features: Optional[List[str]] = None


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    password: Optional[str] = Field(default=None, min_length=6, max_length=256)
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    allowed_features: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.get("/features", response_model=APIResponse)
async def list_features(request: Request):
    _require_admin(request)
    return APIResponse(
        success=True,
        message="Feature catalog",
        data={"features": auth_service.feature_catalog(for_admin_ui=True)},
    )


@router.get("", response_model=APIResponse)
@router.get("/", response_model=APIResponse)
async def list_users(request: Request):
    _require_admin(request)
    return APIResponse(
        success=True,
        message="Users retrieved",
        data={"users": auth_service.list_users()},
    )


@router.post("", response_model=APIResponse)
@router.post("/", response_model=APIResponse)
async def create_user(request: Request, body: CreateUserRequest):
    _require_admin(request)
    role = ROLE_ADMIN if body.role == ROLE_ADMIN else ROLE_USER
    try:
        user = auth_service.create_user(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            role=role,
            allowed_features=body.allowed_features,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(
        success=True,
        message="User created",
        data=auth_service.user_to_dict(user, include_admin_fields=True),
    )


@router.patch("/{user_id}", response_model=APIResponse)
async def update_user(user_id: str, request: Request, body: UpdateUserRequest):
    actor = _require_admin(request)
    try:
        user = auth_service.update_user(
            user_id,
            actor_id=actor.id,
            display_name=body.display_name,
            password=body.password,
            role=body.role,
            allowed_features=body.allowed_features,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(
        success=True,
        message="User updated",
        data=auth_service.user_to_dict(user, include_admin_fields=True),
    )


async def _delete_user_impl(user_id: str, request: Request):
    actor = _require_admin(request)
    try:
        deleted = auth_service.delete_user(user_id, actor_id=actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return APIResponse(
        success=True,
        message="User deleted",
        data=deleted,
    )


@router.post("/{user_id}/delete", response_model=APIResponse)
async def delete_user_post(user_id: str, request: Request):
    """Preferred delete path (works even when DELETE is blocked by proxies)."""
    return await _delete_user_impl(user_id, request)


@router.delete("/{user_id}", response_model=APIResponse)
async def delete_user(user_id: str, request: Request):
    return await _delete_user_impl(user_id, request)
