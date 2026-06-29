# app/api/admin/endpoints/auth.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.auth import (
    LoginRequest,
    MeOut,
    PermissionsOut,
    RefreshRequest,
    TokenOut,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> TokenOut:
    """Authenticate an admin user and return access + refresh tokens."""
    try:
        return await AuthService().login(db, payload.email, payload.password)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {e}",
        ) from e


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> TokenOut:
    """Exchange a refresh token for a new token pair."""
    try:
        return await AuthService().refresh(db, payload.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {e}",
        ) from e


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Revoke the supplied refresh token."""
    try:
        await AuthService().logout(db, payload.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {e}",
        ) from e


@router.get("/me", response_model=MeOut)
async def get_me(
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> MeOut:
    """Return the authenticated admin user's profile."""
    return MeOut.model_validate(current_admin)


@router.get("/permissions", response_model=PermissionsOut)
async def get_permissions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> PermissionsOut:
    """Return the permission codes for the authenticated admin."""
    try:
        codes = await AuthService().get_permissions(db, current_admin)
        return PermissionsOut(permissions=codes)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch permissions: {e}",
        ) from e
