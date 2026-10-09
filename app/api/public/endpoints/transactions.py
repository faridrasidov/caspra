# app/api/public/endpoints/transactions.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    PaginatedPublicTransactionOut,
    PublicRefundOut,
    PublicRefundRequest,
    PublicTopupRequest,
    PublicTransactionOut,
)
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService
from app.services.transaction import TransactionService

router = APIRouter(
    prefix="/transactions",
    tags=["public-transactions"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("", response_model=PaginatedPublicTransactionOut)
async def list_transactions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TRANSACTIONS_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    wallet_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
    device_id: UUID | None = Query(None),
) -> PaginatedPublicTransactionOut:
    """List/search transactions for the API key's tenant.

    Supports filtering by wallet, customer, or device.
    """
    result = await TransactionService().list_transactions(
        db,
        ctx.tenant_id,
        page,
        limit,
        wallet_id=wallet_id,
        customer_id=customer_id,
        device_id=device_id,
    )
    return PaginatedPublicTransactionOut(**result)


@router.post("/topup", response_model=PublicTransactionOut, status_code=status.HTTP_201_CREATED)
async def topup(
    payload: PublicTopupRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TOPUP_WRITE))],
) -> PublicTransactionOut:
    """Credit a wallet (idempotent, routed through the ledger)."""
    return await LedgerService().topup(
        db,
        ctx.tenant_id,
        payload.wallet_id,
        WalletTopupRequest(
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
            description=payload.description,
        ),
    )


@router.post(
    "/{transaction_id}/refund",
    response_model=PublicRefundOut,
    status_code=status.HTTP_201_CREATED,
)
async def refund_transaction(
    transaction_id: UUID,
    payload: PublicRefundRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TRANSACTIONS_WRITE))],
) -> PublicRefundOut:
    """Refund a debit transaction (idempotent compensating entry)."""
    return await LedgerService().refund(
        db,
        ctx.tenant_id,
        transaction_id,
        payload.idempotency_key,
        payload.amount_minor,
        payload.reason,
    )


@router.get("/{transaction_id}", response_model=PublicTransactionOut)
async def get_transaction(
    transaction_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.TRANSACTIONS_READ))],
) -> PublicTransactionOut:
    """Get a single transaction."""
    return await TransactionService().get_transaction(db, ctx.tenant_id, transaction_id)
