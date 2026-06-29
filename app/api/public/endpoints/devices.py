# app/api/public/endpoints/devices.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    PaginatedPublicDeviceOut,
    PaginatedPublicTransactionOut,
    PublicDeviceOut,
    PublicDeviceStatusOut,
)
from app.services.device import DeviceService
from app.services.transaction import TransactionService

router = APIRouter(
    prefix="/devices",
    tags=["public-devices"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("", response_model=PaginatedPublicDeviceOut)
async def list_devices(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.DEVICES_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicDeviceOut:
    """List devices for the API key's tenant (read-only)."""
    try:
        result = await DeviceService().list_devices(db, ctx.tenant_id, page, limit)
        return PaginatedPublicDeviceOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list devices: {e}",
        ) from e


@router.get("/{device_id}", response_model=PublicDeviceOut)
async def get_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.DEVICES_READ))],
) -> PublicDeviceOut:
    """Get device metadata."""
    try:
        return await DeviceService().get_device(db, ctx.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device: {e}",
        ) from e


@router.get("/{device_id}/status", response_model=PublicDeviceStatusOut)
async def get_device_status(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.DEVICES_READ))],
) -> PublicDeviceStatusOut:
    """Get a device's current status."""
    try:
        return await DeviceService().get_device(db, ctx.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device status: {e}",
        ) from e


@router.get("/{device_id}/transactions", response_model=PaginatedPublicTransactionOut)
async def get_device_transactions(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.DEVICES_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicTransactionOut:
    """List transactions posted by a device (limited fields)."""
    try:
        await DeviceService().get_device(db, ctx.tenant_id, device_id)
        result = await TransactionService().list_transactions(
            db, ctx.tenant_id, page, limit, device_id=device_id
        )
        return PaginatedPublicTransactionOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device transactions: {e}",
        ) from e
