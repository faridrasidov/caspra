# app/api/admin/endpoints/wallets.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
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
    try:
        result = await WalletService().list_wallets(db, current_admin.tenant_id, page, limit)
        return PaginatedWalletOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list wallets: {e}",
        ) from e


@router.post("", response_model=WalletOut, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    payload: WalletCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletOut:
    """Create a wallet for a customer."""
    try:
        return await WalletService().create_wallet(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create wallet: {e}",
        ) from e


@router.post("/transfer", response_model=TransactionOut)
async def transfer(
    payload: WalletTransferRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TransactionOut:
    """Transfer value between two wallets (idempotent, double-entry)."""
    try:
        return await LedgerService().transfer(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer: {e}",
        ) from e


@router.get("/{wallet_id}", response_model=WalletOut)
async def get_wallet(
    wallet_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletOut:
    """Get a single wallet."""
    try:
        return await WalletService().get_wallet(db, current_admin.tenant_id, wallet_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch wallet: {e}",
        ) from e


@router.get("/{wallet_id}/balance", response_model=WalletBalanceOut)
async def get_balance(
    wallet_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WalletBalanceOut:
    """Get a wallet's current balance."""
    try:
        wallet = await LedgerService().get_balance(db, current_admin.tenant_id, wallet_id)
        return WalletBalanceOut(
            wallet_id=wallet.id,
            currency=wallet.currency,
            balance_minor=wallet.balance_minor,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch balance: {e}",
        ) from e


@router.post("/{wallet_id}/topup", response_model=TransactionOut)
async def topup(
    wallet_id: UUID,
    payload: WalletTopupRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TransactionOut:
    """Credit a wallet (idempotent)."""
    try:
        return await LedgerService().topup(db, current_admin.tenant_id, wallet_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to top up wallet: {e}",
        ) from e


@router.post("/{wallet_id}/deduct", response_model=TransactionOut)
async def deduct(
    wallet_id: UUID,
    payload: WalletDeductRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> TransactionOut:
    """Debit a wallet (idempotent, balance-checked under lock)."""
    try:
        return await LedgerService().deduct(db, current_admin.tenant_id, wallet_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deduct from wallet: {e}",
        ) from e
