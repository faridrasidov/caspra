# app/api/admin/endpoints/cards.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.device.device import CardStatus
from app.models.identity.user import User
from app.schemas.card import (
    CardAssignRequest,
    CardCreate,
    CardOut,
    CardReplaceRequest,
    PaginatedCardOut,
)
from app.services.card import CardService

router = APIRouter(prefix="/cards", tags=["admin-cards"])


@router.get("", response_model=PaginatedCardOut)
async def list_cards(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedCardOut:
    """List cards for the caller's tenant."""
    result = await CardService().list_cards(db, current_admin.tenant_id, page, limit)
    return PaginatedCardOut(**result)


@router.post("", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def register_card(
    payload: CardCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Register a new card."""
    return await CardService().register_card(db, current_admin.tenant_id, payload)


@router.get("/{card_id}", response_model=CardOut)
async def get_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Get a single card."""
    return await CardService().get_card(db, current_admin.tenant_id, card_id)


@router.post("/{card_id}/assign", response_model=CardOut)
async def assign_card(
    card_id: UUID,
    payload: CardAssignRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Assign a card to a customer."""
    return await CardService().assign(db, current_admin.tenant_id, card_id, payload.customer_id)


@router.post("/{card_id}/unassign", response_model=CardOut)
async def unassign_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Unassign a card from its customer."""
    return await CardService().unassign(db, current_admin.tenant_id, card_id)


@router.post("/{card_id}/block", response_model=CardOut)
async def block_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Block a card."""
    return await CardService().set_status(db, current_admin.tenant_id, card_id, CardStatus.BLOCKED)


@router.post("/{card_id}/unblock", response_model=CardOut)
async def unblock_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Unblock a card (return to active)."""
    return await CardService().set_status(db, current_admin.tenant_id, card_id, CardStatus.ACTIVE)


@router.post("/{card_id}/reset", response_model=CardOut)
async def reset_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Reset a card to active and unassigned."""
    return await CardService().reset(db, current_admin.tenant_id, card_id)


@router.post("/{card_id}/replace", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def replace_card(
    card_id: UUID,
    payload: CardReplaceRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CardOut:
    """Replace a lost card with a new one, preserving the customer link."""
    return await CardService().replace(db, current_admin.tenant_id, card_id, payload.new_uid)
