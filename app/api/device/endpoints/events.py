# app/api/device/endpoints/events.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_ops import (
    DeviceCommandOut,
    DeviceCommandPullOut,
    DeviceEventPushOut,
    DeviceEventPushRequest,
)
from app.services.device_ops import DeviceEventService

router = APIRouter(prefix="/events", tags=["device-events"])


@router.post("/push", response_model=DeviceEventPushOut, status_code=status.HTTP_201_CREATED)
async def push_events(
    payload: DeviceEventPushRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceEventPushOut:
    """Push device logs/events to the server."""
    try:
        accepted = await DeviceEventService().push(db, device, payload)
        return DeviceEventPushOut(accepted=accepted)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/pull", response_model=DeviceCommandPullOut)
async def pull_events(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceCommandPullOut:
    """Pull pending server messages/commands for the device."""
    try:
        commands = await DeviceEventService().pull(db, device)
        return DeviceCommandPullOut(commands=[DeviceCommandOut.model_validate(c) for c in commands])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
