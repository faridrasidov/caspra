# app/api/admin/endpoints/transactions.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin, require_admin_permission
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.transaction import (
    PaginatedTransactionOut,
    RefundOut,
    RefundRequest,
    TransactionExportOut,
    TransactionOut,
    TransactionStatsOut,
)
from app.services.ledger import LedgerService
from app.services.transaction import TransactionService

router = APIRouter(prefix="/transactions", tags=["admin-transactions"])


@router.get("", response_model=PaginatedTransactionOut)
async def list_transactions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    wallet_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
) -> PaginatedTransactionOut:
    """List transactions for the caller's tenant."""
    result = await TransactionService().list_transactions(
        db, current_admin.tenant_id, page, limit, type, wallet_id, customer_id
    )
    return PaginatedTransactionOut(**result)


@router.get("/stats", response_model=TransactionStatsOut)
async def get_stats(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TransactionStatsOut:
    """Aggregate transaction statistics for the caller's tenant."""
    return await TransactionService().get_stats(db, current_admin.tenant_id)


@router.get("/export", response_model=TransactionExportOut)
async def export_transactions(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    format: str = Query("json"),
) -> TransactionExportOut:
    """Export transactions for the caller's tenant."""
    return await TransactionService().export(db, current_admin.tenant_id, format)


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TransactionOut:
    """Get a single transaction."""
    return await TransactionService().get_transaction(db, current_admin.tenant_id, transaction_id)


@router.post(
    "/{transaction_id}/refund", response_model=RefundOut, status_code=status.HTTP_201_CREATED
)
async def refund_transaction(
    transaction_id: UUID,
    payload: RefundRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.TRANSACTIONS_REFUND))
    ],
) -> RefundOut:
    """Refund a debit transaction (idempotent compensating entry)."""
    return await LedgerService().refund(
        db,
        current_admin.tenant_id,
        transaction_id,
        payload.idempotency_key,
        payload.amount_minor,
        payload.reason,
    )
