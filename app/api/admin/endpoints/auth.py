# app/api/admin/endpoints/auth.py

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.core.config import settings
from app.core.domain_errors import UnauthorizedError
from app.core.rate_limit import check_login_rate_limit, clear_login_rate_limit
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
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path=f"{settings.admin_api_prefix}/auth",
    )


def _get_refresh_token(payload: RefreshRequest | None, request: Request) -> str:
    token = payload.refresh_token if payload is not None else None
    token = token or request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise UnauthorizedError("Refresh token is required")
    return token


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
) -> TokenOut:
    client_ip = request.client.host if request.client else "unknown"
    limiter_key = await check_login_rate_limit(client_ip, payload.email)
    tokens = await AuthService().login(db, payload.email, payload.password)
    await clear_login_rate_limit(limiter_key)
    _set_refresh_cookie(response, tokens.refresh_token)
    return tokens


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    payload: RefreshRequest | None = None,
) -> TokenOut:
    tokens = await AuthService().refresh(db, _get_refresh_token(payload, request))
    _set_refresh_cookie(response, tokens.refresh_token)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    payload: RefreshRequest | None = None,
) -> None:
    await AuthService().logout(db, _get_refresh_token(payload, request))
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=f"{settings.admin_api_prefix}/auth",
    )


@router.post("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    await AuthService().revoke_all_sessions(db, current_admin.id)


@router.get("/me", response_model=MeOut)
async def get_me(
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> MeOut:
    return MeOut.model_validate(current_admin)


@router.get("/permissions", response_model=PermissionsOut)
async def get_permissions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> PermissionsOut:
    codes = await AuthService().get_permissions(db, current_admin)
    return PermissionsOut(permissions=codes)
