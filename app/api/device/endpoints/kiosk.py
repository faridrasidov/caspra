# app/api/device/endpoints/kiosk.py

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_kiosk import (
    KioskTopupCancelRequest,
    KioskTopupConfirmRequest,
    KioskTopupRequestIn,
    KioskTopupSessionOut,
    PaymentMethodOut,
    PaymentMethodsOut,
)
from app.services.device_kiosk import DeviceKioskService

router = APIRouter(prefix="/kiosk", tags=["device-kiosk"])


@router.post(
    "/topup/request",
    response_model=KioskTopupSessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def topup_request(
    payload: KioskTopupRequestIn,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> KioskTopupSessionOut:
    """Open a kiosk top-up session (idempotent)."""
    session = await DeviceKioskService().request_topup(db, device, payload)
    return KioskTopupSessionOut.model_validate(session)


@router.post("/topup/confirm", response_model=KioskTopupSessionOut)
async def topup_confirm(
    payload: KioskTopupConfirmRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> KioskTopupSessionOut:
    """Confirm a top-up session, crediting the customer's wallet (idempotent)."""
    session = await DeviceKioskService().confirm_topup(db, device, payload)
    return KioskTopupSessionOut.model_validate(session)


@router.post("/topup/cancel", response_model=KioskTopupSessionOut)
async def topup_cancel(
    payload: KioskTopupCancelRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> KioskTopupSessionOut:
    """Cancel a pending top-up session."""
    session = await DeviceKioskService().cancel_topup(db, device, payload.session_id)
    return KioskTopupSessionOut.model_validate(session)


@router.get("/payment-methods", response_model=PaymentMethodsOut)
async def payment_methods(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> PaymentMethodsOut:
    """List active payment methods for the tenant."""
    methods = await DeviceKioskService().list_payment_methods(db, device)
    return PaymentMethodsOut(items=[PaymentMethodOut.model_validate(m) for m in methods])
