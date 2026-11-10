from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_device, get_db
from app.core.domain_errors import ForbiddenError
from app.models.device.device import Device
from app.schemas.arcade import PlayOut, PlayOutcome, PlayRequest
from app.services.arcade import ArcadeService

router = APIRouter(prefix="/plays", tags=["device-plays"])
DB = Annotated[AsyncSession, Depends(get_db)]


async def play_reader(
    request: Request,
    device: Annotated[Device, Depends(get_authenticated_device)],
) -> Device:
    if request.headers.get("X-Device-Signature-Version") != "2":
        raise ForbiddenError("Machine play requires HMAC v2")
    return device


Reader = Annotated[Device, Depends(play_reader)]


@router.post("", response_model=PlayOut, status_code=201)
async def authorize_play(payload: PlayRequest, db: DB, device: Reader):
    return await ArcadeService().authorize(db, device, payload)


@router.get("/{play_id}", response_model=PlayOut)
async def play_status(play_id: UUID, db: DB, device: Reader):
    return await ArcadeService().device_play(db, device, play_id)


@router.post("/{play_id}/outcome", response_model=PlayOut)
async def play_outcome(play_id: UUID, payload: PlayOutcome, db: DB, device: Reader):
    return await ArcadeService().outcome(
        db, device.tenant_id, play_id, payload.outcome, payload.reason, device=device
    )
