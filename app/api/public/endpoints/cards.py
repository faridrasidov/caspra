# app/api/public/endpoints/cards.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.domain_errors import NotFoundError
from app.core.scopes import PII_SCOPE, PublicScope
from app.schemas.public import (
    PaginatedPublicCardOut,
    PublicBalancesOut,
    PublicCardLinkRequest,
    PublicCardOut,
    PublicCustomerOut,
    PublicWalletBalanceOut,
)
from app.services.card import CardService
from app.services.customer import CustomerService

router = APIRouter(
    prefix="/cards",
    tags=["public-cards"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("", response_model=PaginatedPublicCardOut)
async def list_cards(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicCardOut:
    """List cards for the API key's tenant."""
    try:
        result = await CardService().list_cards(db, ctx.tenant_id, page, limit)
        return PaginatedPublicCardOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{card_id}", response_model=PublicCardOut)
async def get_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_READ))],
) -> PublicCardOut:
    """Get a single card."""
    try:
        return await CardService().get_card(db, ctx.tenant_id, card_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{card_id}/balances", response_model=PublicBalancesOut)
async def get_card_balances(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_READ))],
) -> PublicBalancesOut:
    """Return wallet balances for the customer linked to this card."""
    try:
        card = await CardService().get_card(db, ctx.tenant_id, card_id)
        if card.customer_id is None:
            return PublicBalancesOut(balances=[])
        wallets = await CustomerService().get_balances(db, ctx.tenant_id, card.customer_id)
        return PublicBalancesOut(
            balances=[
                PublicWalletBalanceOut(
                    wallet_id=w.id,
                    currency=w.currency,
                    balance_minor=w.balance_minor,
                    type=w.type,
                )
                for w in wallets
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{card_id}/customer", response_model=PublicCustomerOut)
async def get_card_customer(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_READ))],
) -> PublicCustomerOut:
    """Return the customer linked to this card (contact fields redacted)."""
    try:
        card = await CardService().get_card(db, ctx.tenant_id, card_id)
        if card.customer_id is None:
            raise NotFoundError("Card customer", str(card_id))
        customer = await CustomerService().get_customer(db, ctx.tenant_id, card.customer_id)
        show_pii = ctx.has_scope(PII_SCOPE)
        return PublicCustomerOut(
            id=customer.id,
            external_id=customer.external_id,
            full_name=customer.full_name,
            email=customer.email if show_pii else None,
            phone=customer.phone if show_pii else None,
            status=customer.status,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{card_id}/link", response_model=PublicCardOut)
async def link_card(
    card_id: UUID,
    payload: PublicCardLinkRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_WRITE))],
) -> PublicCardOut:
    """Link a card to a customer."""
    try:
        return await CardService().assign(db, ctx.tenant_id, card_id, payload.customer_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("/{card_id}/unlink", response_model=PublicCardOut)
async def unlink_card(
    card_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CARDS_WRITE))],
) -> PublicCardOut:
    """Unlink a card from its customer."""
    try:
        return await CardService().unassign(db, ctx.tenant_id, card_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
