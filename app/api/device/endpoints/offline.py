# app/api/device/endpoints/offline.py

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_txn import (
    OfflineConfigOut,
    OfflineQueueUploadRequest,
    OfflineSyncResultOut,
)
from app.services.device_offline import DeviceOfflineService

router = APIRouter(prefix="/offline", tags=["device-offline"])


@router.get("/config", response_model=OfflineConfigOut)
async def offline_config(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineConfigOut:
    """Return the offline operating limits for this device's tenant."""
    return await DeviceOfflineService().offline_config(db, device)


@router.post("/sync", response_model=OfflineSyncResultOut, status_code=status.HTTP_201_CREATED)
async def offline_sync(
    payload: OfflineQueueUploadRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineSyncResultOut:
    """Sync queued offline operations (replay-safe)."""
    return await DeviceOfflineService().apply_queue(db, device, payload)


@router.post("/queue", response_model=OfflineSyncResultOut, status_code=status.HTTP_201_CREATED)
async def offline_queue(
    payload: OfflineQueueUploadRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineSyncResultOut:
    """Upload the full offline queue (idempotent / replay-safe via OfflineTransaction)."""
    return await DeviceOfflineService().apply_queue(db, device, payload)
