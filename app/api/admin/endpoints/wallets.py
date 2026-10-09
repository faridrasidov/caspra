# app/api/admin/endpoints/wallets.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin, require_admin_permission
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.transaction import TransactionOut
from app.schemas.wallet import (
    PaginatedWalletOut,
    WalletBalanceOut,
    WalletCreate,
    WalletDeductRequest,
    WalletOut,
    WalletTopupRequest,
    WalletTransferRequest,
)
from app.services.ledger import LedgerService
from app.services.wallet import WalletService

router = APIRouter(prefix="/wallets", tags=["admin-wallets"])


@router.get("", response_model=PaginatedWalletOut)
async def list_wallets(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedWalletOut:
    """List wallets for the caller's tenant."""
    result = await WalletService().list_wallets(db, current_admin.tenant_id, page, limit)
    return PaginatedWalletOut(**result)


@router.post("", response_model=WalletOut, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    payload: WalletCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletOut:
    """Create a wallet for a customer."""
    return await WalletService().create_wallet(db, current_admin.tenant_id, payload)


@router.post("/transfer", response_model=TransactionOut)
async def transfer(
    payload: WalletTransferRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.WALLETS_ADJUST))
    ],
) -> TransactionOut:
    """Transfer value between two wallets (idempotent, double-entry)."""
    return await LedgerService().transfer(db, current_admin.tenant_id, payload)


@router.get("/{wallet_id}", response_model=WalletOut)
async def get_wallet(
    wallet_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletOut:
    """Get a single wallet."""
    return await WalletService().get_wallet(db, current_admin.tenant_id, wallet_id)


@router.get("/{wallet_id}/balance", response_model=WalletBalanceOut)
async def get_balance(
    wallet_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletBalanceOut:
    """Get a wallet's current balance."""
    wallet = await LedgerService().get_balance(db, current_admin.tenant_id, wallet_id)
    return WalletBalanceOut(
        wallet_id=wallet.id,
        currency=wallet.currency,
        balance_minor=wallet.balance_minor,
    )


@router.post("/{wallet_id}/topup", response_model=TransactionOut)
async def topup(
    wallet_id: UUID,
    payload: WalletTopupRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.WALLETS_ADJUST))
    ],
) -> TransactionOut:
    """Credit a wallet (idempotent)."""
    return await LedgerService().topup(db, current_admin.tenant_id, wallet_id, payload)


@router.post("/{wallet_id}/deduct", response_model=TransactionOut)
async def deduct(
    wallet_id: UUID,
    payload: WalletDeductRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(require_admin_permission(AdminPermission.WALLETS_ADJUST))
    ],
) -> TransactionOut:
    """Debit a wallet (idempotent, balance-checked under lock)."""
    return await LedgerService().deduct(db, current_admin.tenant_id, wallet_id, payload)
