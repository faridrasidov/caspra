# app/api/device/endpoints/card.py

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_authenticated_device
from app.models.device.device import Device
from app.schemas.device_card import (
    CardBalanceOut,
    CardInfoOut,
    CardUidRequest,
    CardVerifyOut,
    TempAssignmentOut,
    TempAssignRequest,
)
from app.services.device_card import DeviceCardService

router = APIRouter(prefix="/card", tags=["device-card"])


@router.post("/verify", response_model=CardVerifyOut)
async def verify_card(
    payload: CardUidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> CardVerifyOut:
    """Verify a card's status (active/blocked/expired) within the device's tenant."""
    return await DeviceCardService().verify(db, device.tenant_id, payload.card_uid)


@router.post("/info", response_model=CardInfoOut)
async def card_info(
    payload: CardUidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> CardInfoOut:
    """Return minimal card info for a UID."""
    return await DeviceCardService().info(db, device.tenant_id, payload.card_uid)


@router.post("/balance", response_model=CardBalanceOut)
async def card_balance(
    payload: CardUidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> CardBalanceOut:
    """Return balances across all of the cardholder's wallets."""
    return await DeviceCardService().balance(db, device.tenant_id, payload.card_uid)


@router.post("/assign-temp", response_model=TempAssignmentOut, status_code=status.HTTP_201_CREATED)
async def assign_temp_card(
    payload: TempAssignRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> TempAssignmentOut:
    """Assign an anonymous temporary card to a session."""
    assignment = await DeviceCardService().assign_temp(
        db, device.tenant_id, payload.card_uid, payload.session_ref
    )
    return TempAssignmentOut.model_validate(assignment)


@router.post("/unassign-temp", response_model=TempAssignmentOut)
async def unassign_temp_card(
    payload: CardUidRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> TempAssignmentOut:
    """Release a temporary card assignment."""
    assignment = await DeviceCardService().unassign_temp(db, device.tenant_id, payload.card_uid)
    return TempAssignmentOut.model_validate(assignment)
