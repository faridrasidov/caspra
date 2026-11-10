from __future__ import annotations

# app/services/wallet.py
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.domain_errors import ConflictError, NotFoundError
from app.models.ledger.wallet import Customer, Wallet
from app.services.base import TenantScopedService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.wallet import WalletCreate


class WalletService(TenantScopedService):
    """Manage wallet records. Money movement lives in ``LedgerService``."""

    model = Wallet
    resource_name = "Wallet"

    async def list_wallets(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int, q: str | None = None
    ) -> dict:
        return await self.paginate(
            db, tenant_id, page, limit, order_by=Wallet.created_at.desc(), q=q
        )

    async def create_wallet(
        self, db: AsyncSession, tenant_id: UUID, payload: WalletCreate
    ) -> Wallet:
        stmt = select(Customer.id).where(
            Customer.id == payload.customer_id, Customer.tenant_id == tenant_id
        )
        if (await db.execute(stmt)).first() is None:
            raise NotFoundError("Customer", str(payload.customer_id))

        wallet = Wallet(
            tenant_id=tenant_id,
            customer_id=payload.customer_id,
            currency=payload.currency,
            type=payload.type.value,
        )
        existing = select(Wallet.id).where(
            Wallet.tenant_id == tenant_id,
            Wallet.customer_id == payload.customer_id,
            Wallet.type == payload.type.value,
            Wallet.currency == payload.currency,
            Wallet.status != "closed",
        )
        if (await db.execute(existing)).first():
            raise ConflictError("Customer already has an open wallet of this type and currency")
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
        return wallet

    async def get_wallet(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> Wallet:
        return await self.get_owned(db, wallet_id, tenant_id)
