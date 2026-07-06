"""Weave JWT authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.models.knowledge import APIResponse
from app.services.auth_service import auth_service

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


@router.post("/login", response_model=APIResponse)
async def login(request: LoginRequest):
    user = auth_service.authenticate(request.username, request.password)
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
