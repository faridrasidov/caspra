# app/api/device/endpoints/sync.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_ops import (
    DeviceCommandAckRequest,
    DeviceCommandOut,
    DeviceCommandPullOut,
    SyncStatusOut,
    TelemetryPushOut,
    TelemetryPushRequest,
)
from app.services.device_ops import DeviceSyncService

router = APIRouter(prefix="/sync", tags=["device-sync"])


@router.get("/status", response_model=SyncStatusOut)
async def sync_status(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> SyncStatusOut:
    """Return the device's sync status (pending commands, last seen)."""
    try:
        return await DeviceSyncService().status(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/push", response_model=TelemetryPushOut, status_code=status.HTTP_201_CREATED)
async def push_telemetry(
    payload: TelemetryPushRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> TelemetryPushOut:
    """Push device telemetry (CPU, temperature, uptime)."""
    try:
        telemetry = await DeviceSyncService().push_telemetry(db, device, payload)
        return TelemetryPushOut(id=telemetry.id, recorded=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/pull", response_model=DeviceCommandPullOut)
async def pull_commands(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceCommandPullOut:
    """Pull pending commands for the device."""
    try:
        commands = await DeviceSyncService().pull(db, device)
        return DeviceCommandPullOut(commands=[DeviceCommandOut.model_validate(c) for c in commands])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/commands/{command_id}/ack", response_model=DeviceCommandOut)
async def acknowledge_command(
    command_id: UUID,
    payload: DeviceCommandAckRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceCommandOut:
    command = await DeviceSyncService().acknowledge(db, device, command_id, payload)
    return DeviceCommandOut.model_validate(command)
