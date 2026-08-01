# app/api/device/endpoints/settings.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_ops import (
    DeviceReloadOut,
    DeviceSettingsOut,
    DeviceSettingsUpdateRequest,
)
from app.services.device_ops import DeviceSettingsService

router = APIRouter(prefix="/settings", tags=["device-settings"])


@router.get("", response_model=DeviceSettingsOut)
async def get_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceSettingsOut:
    """Return the device's current settings/config."""
    try:
        return await DeviceSettingsService().get(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.put("", response_model=DeviceSettingsOut)
async def update_settings(
    payload: DeviceSettingsUpdateRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceSettingsOut:
    """Persist device config changes pulled by the device."""
    try:
        return await DeviceSettingsService().update(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/reload", response_model=DeviceReloadOut, status_code=status.HTTP_201_CREATED)
async def reload_settings(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceReloadOut:
    """Queue a reload command for the device."""
    try:
        command = await DeviceSettingsService().reload(db, device)
        return DeviceReloadOut(command_id=command.id, status=command.status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
