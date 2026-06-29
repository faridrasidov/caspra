# app/api/admin/endpoints/devices.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.device import (
    DeviceConfigOut,
    DeviceConfigUpdate,
    DeviceCreate,
    DeviceOut,
    DeviceStatusUpdate,
    DeviceUpdate,
    PaginatedDeviceEventOut,
    PaginatedDeviceOut,
)
from app.services.device import DeviceService

router = APIRouter(prefix="/devices", tags=["admin-devices"])


@router.get("", response_model=PaginatedDeviceOut)
async def list_devices(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceOut:
    """List devices for the caller's tenant."""
    try:
        result = await DeviceService().list_devices(db, current_admin.tenant_id, page, limit)
        return PaginatedDeviceOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list devices: {e}",
        ) from e


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Register a new device."""
    try:
        return await DeviceService().register_device(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {e}",
        ) from e


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Get a single device."""
    try:
        return await DeviceService().get_device(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device: {e}",
        ) from e


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Update a device."""
    try:
        return await DeviceService().update_device(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update device: {e}",
        ) from e


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a device."""
    try:
        await DeviceService().delete_device(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete device: {e}",
        ) from e


@router.post("/{device_id}/status", response_model=DeviceOut)
async def set_device_status(
    device_id: UUID,
    payload: DeviceStatusUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Set a device's status."""
    try:
        return await DeviceService().set_status(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set device status: {e}",
        ) from e


@router.post("/{device_id}/reset", response_model=DeviceOut)
async def reset_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceOut:
    """Reset a device to active status."""
    try:
        return await DeviceService().reset(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset device: {e}",
        ) from e


@router.get("/{device_id}/config", response_model=DeviceConfigOut)
async def get_device_config(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceConfigOut:
    """Get a device's configuration."""
    try:
        return await DeviceService().get_config(db, current_admin.tenant_id, device_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch device config: {e}",
        ) from e


@router.put("/{device_id}/config", response_model=DeviceConfigOut)
async def update_device_config(
    device_id: UUID,
    payload: DeviceConfigUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> DeviceConfigOut:
    """Update a device's configuration."""
    try:
        return await DeviceService().update_config(db, current_admin.tenant_id, device_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update device config: {e}",
        ) from e


@router.get("/{device_id}/events", response_model=PaginatedDeviceEventOut)
async def list_device_events(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceEventOut:
    """List events emitted by a device."""
    try:
        result = await DeviceService().list_events(
            db, current_admin.tenant_id, device_id, page, limit
        )
        return PaginatedDeviceEventOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list device events: {e}",
        ) from e
