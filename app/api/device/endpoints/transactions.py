# app/api/device/endpoints/transactions.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_txn import (
    DeviceTransactionOut,
    OfflineQueueUploadRequest,
    OfflineSyncResultOut,
    PaginatedDeviceTransactionOut,
)
from app.services.device_transaction import DeviceTransactionService

router = APIRouter(prefix="/transactions", tags=["device-transactions"])


@router.get("", response_model=PaginatedDeviceTransactionOut)
async def list_transactions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceTransactionOut:
    """List the device's own recent transactions."""
    result = await DeviceTransactionService().list_recent(db, device, page, limit)
    return PaginatedDeviceTransactionOut(**result)


@router.get("/pending", response_model=PaginatedDeviceTransactionOut)
async def list_pending(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedDeviceTransactionOut:
    """List the device's pending (unsynced) transactions."""
    result = await DeviceTransactionService().list_pending(db, device, page, limit)
    return PaginatedDeviceTransactionOut(**result)


@router.post("/upload", response_model=OfflineSyncResultOut, status_code=status.HTTP_201_CREATED)
async def upload_offline(
    payload: OfflineQueueUploadRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> OfflineSyncResultOut:
    """Upload an offline transaction queue (replay-safe via idempotency keys)."""
    return await DeviceTransactionService().upload(db, device, payload)


@router.get("/{transaction_id}", response_model=DeviceTransactionOut)
async def transaction_status(
    transaction_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DeviceTransactionOut:
    """Get the status of one of the device's transactions by id."""
    txn = await DeviceTransactionService().get_status(db, device, transaction_id)
    return DeviceTransactionOut.model_validate(txn)
