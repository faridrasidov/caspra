# app/api/device/endpoints/payment.py

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_payment import (
    DeviceCaptureRequest,
    DeviceChargeRequest,
    DevicePaymentOut,
    DevicePreauthRequest,
    DeviceRefundRequest,
    DeviceVoidRequest,
    HoldOut,
)
from app.services.device_payment import DevicePaymentService

router = APIRouter(prefix="/payment", tags=["device-payment"])


@router.post("/charge", response_model=DevicePaymentOut, status_code=status.HTTP_201_CREATED)
async def charge(
    payload: DeviceChargeRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DevicePaymentOut:
    """Debit a card's wallet (idempotent, balance-checked under a row lock)."""
    return await DevicePaymentService().charge(db, device, payload)


@router.post("/refund", response_model=DevicePaymentOut, status_code=status.HTTP_201_CREATED)
async def refund(
    payload: DeviceRefundRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DevicePaymentOut:
    """Refund a prior debit via a compensating credit entry (idempotent)."""
    return await DevicePaymentService().refund(db, device, payload)


@router.post("/preauth", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def preauth(
    payload: DevicePreauthRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> HoldOut:
    """Reserve funds on a wallet without moving money (creates a Hold)."""
    return await DevicePaymentService().preauth(db, device, payload)


@router.post("/capture", response_model=DevicePaymentOut, status_code=status.HTTP_201_CREATED)
async def capture(
    payload: DeviceCaptureRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DevicePaymentOut:
    """Capture a pre-auth hold: post the debit ledger entry."""
    return await DevicePaymentService().capture(db, device, payload)


@router.post("/void", response_model=HoldOut)
async def void(
    payload: DeviceVoidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> HoldOut:
    """Void a pre-auth hold and release the reserved funds."""
    return await DevicePaymentService().void(db, device, payload)
