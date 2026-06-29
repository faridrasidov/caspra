# app/api/device/endpoints/payment.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
    try:
        return await DevicePaymentService().charge(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to charge: {e}",
        ) from e


@router.post("/refund", response_model=DevicePaymentOut, status_code=status.HTTP_201_CREATED)
async def refund(
    payload: DeviceRefundRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DevicePaymentOut:
    """Refund a prior debit via a compensating credit entry (idempotent)."""
    try:
        return await DevicePaymentService().refund(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refund: {e}",
        ) from e


@router.post("/preauth", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
async def preauth(
    payload: DevicePreauthRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> HoldOut:
    """Reserve funds on a wallet without moving money (creates a Hold)."""
    try:
        return await DevicePaymentService().preauth(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pre-authorize: {e}",
        ) from e


@router.post("/capture", response_model=DevicePaymentOut, status_code=status.HTTP_201_CREATED)
async def capture(
    payload: DeviceCaptureRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> DevicePaymentOut:
    """Capture a pre-auth hold: post the debit ledger entry."""
    try:
        return await DevicePaymentService().capture(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture: {e}",
        ) from e


@router.post("/void", response_model=HoldOut)
async def void(
    payload: DeviceVoidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> HoldOut:
    """Void a pre-auth hold and release the reserved funds."""
    try:
        return await DevicePaymentService().void(db, device, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to void hold: {e}",
        ) from e
