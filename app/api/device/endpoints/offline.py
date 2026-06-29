# app/api/device/endpoints/offline.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
    try:
        return await DeviceOfflineService().offline_config(db, device)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch offline config: {e}",
        ) from e


@router.post("/sync", response_model=OfflineSyncResultOut, status_code=status.HTTP_201_CREATED)
async def offline_sync(
    payload: OfflineQueueUploadRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineSyncResultOut:
    """Sync queued offline operations (replay-safe)."""
    try:
        return await DeviceOfflineService().apply_queue(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync offline queue: {e}",
        ) from e


@router.post("/queue", response_model=OfflineSyncResultOut, status_code=status.HTTP_201_CREATED)
async def offline_queue(
    payload: OfflineQueueUploadRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineSyncResultOut:
    """Upload the full offline queue (idempotent / replay-safe via OfflineTransaction)."""
    try:
        return await DeviceOfflineService().apply_queue(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload offline queue: {e}",
        ) from e
