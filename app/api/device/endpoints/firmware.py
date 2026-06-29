# app/api/device/endpoints/firmware.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_ops import (
    FirmwareCheckOut,
    FirmwareDownloadOut,
    FirmwareUpdateOut,
    FirmwareUpdateStatusRequest,
)
from app.services.device_ops import DeviceFirmwareService

router = APIRouter(prefix="/firmware", tags=["device-firmware"])


@router.get("/check", response_model=FirmwareCheckOut)
async def check_firmware(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> FirmwareCheckOut:
    """Check whether a firmware update is available for this device type."""
    try:
        return await DeviceFirmwareService().check(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check firmware: {e}",
        ) from e


@router.get("/download/{firmware_id}", response_model=FirmwareDownloadOut)
async def download_firmware(
    firmware_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> FirmwareDownloadOut:
    """Return signed-URL-style download metadata for a firmware image."""
    try:
        return await DeviceFirmwareService().download(db, device, firmware_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch firmware download: {e}",
        ) from e


@router.post("/update-status", response_model=FirmwareUpdateOut)
async def update_status(
    payload: FirmwareUpdateStatusRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> FirmwareUpdateOut:
    """Report firmware update progress for a device."""
    try:
        update = await DeviceFirmwareService().update_status(db, device, payload)
        return FirmwareUpdateOut.model_validate(update)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to report firmware status: {e}",
        ) from e
