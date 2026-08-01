# app/api/public/endpoints/topup.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    ExternalTopupConfirmRequest,
    ExternalTopupSessionOut,
    ExternalTopupStartRequest,
)
from app.services.external_topup import ExternalTopupService

router = APIRouter(
    prefix="/topup",
    tags=["public-topup"],
    dependencies=[Depends(rate_limit_public)],
)


@router.post("/start", response_model=ExternalTopupSessionOut, status_code=status.HTTP_201_CREATED)
async def start_topup(
    payload: ExternalTopupStartRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TOPUP_WRITE))],
) -> ExternalTopupSessionOut:
    """Start an external/mobile top-up session (idempotent, replay-safe)."""
    try:
        return await ExternalTopupService().start(db, ctx.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{session_id}/confirm", response_model=ExternalTopupSessionOut)
async def confirm_topup(
    session_id: UUID,
    payload: ExternalTopupConfirmRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TOPUP_WRITE))],
) -> ExternalTopupSessionOut:
    """Confirm a top-up after external payment success (credits via the ledger)."""
    try:
        return await ExternalTopupService().confirm(db, ctx.tenant_id, session_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{session_id}/cancel", response_model=ExternalTopupSessionOut)
async def cancel_topup(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TOPUP_WRITE))],
) -> ExternalTopupSessionOut:
    """Cancel a started top-up session."""
    try:
        return await ExternalTopupService().cancel(db, ctx.tenant_id, session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{session_id}", response_model=ExternalTopupSessionOut)
async def get_topup(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TOPUP_WRITE))],
) -> ExternalTopupSessionOut:
    """Get a top-up session by id."""
    try:
        return await ExternalTopupService().get_session(db, ctx.tenant_id, session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
