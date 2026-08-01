# app/api/admin/endpoints/kiosks.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.kiosk import (
    KioskCreate,
    KioskOut,
    KioskUpdate,
    PaginatedKioskLogOut,
    PaginatedKioskOut,
)
from app.services.kiosk import KioskService

router = APIRouter(prefix="/kiosks", tags=["admin-kiosks"])


@router.get("", response_model=PaginatedKioskOut)
async def list_kiosks(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedKioskOut:
    """List kiosks for the caller's tenant."""
    try:
        result = await KioskService().list_kiosks(db, current_admin.tenant_id, page, limit)
        return PaginatedKioskOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("", response_model=KioskOut, status_code=status.HTTP_201_CREATED)
async def create_kiosk(
    payload: KioskCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> KioskOut:
    """Create a kiosk."""
    try:
        return await KioskService().create_kiosk(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{kiosk_id}", response_model=KioskOut)
async def get_kiosk(
    kiosk_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> KioskOut:
    """Get a single kiosk."""
    try:
        return await KioskService().get_kiosk(db, current_admin.tenant_id, kiosk_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.patch("/{kiosk_id}", response_model=KioskOut)
async def update_kiosk(
    kiosk_id: UUID,
    payload: KioskUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> KioskOut:
    """Update a kiosk."""
    try:
        return await KioskService().update_kiosk(db, current_admin.tenant_id, kiosk_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{kiosk_id}/logs", response_model=PaginatedKioskLogOut)
async def list_kiosk_logs(
    kiosk_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedKioskLogOut:
    """List logs for a kiosk."""
    try:
        result = await KioskService().list_logs(db, current_admin.tenant_id, kiosk_id, page, limit)
        return PaginatedKioskLogOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
