# app/services/wallet.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.models.ledger.wallet import Customer, Wallet
from app.schemas.wallet import WalletCreate
from app.services.base import TenantScopedService


class WalletService(TenantScopedService):
    """Manage wallet records. Money movement lives in ``LedgerService``."""

    model = Wallet
    resource_name = "Wallet"

    async def list_wallets(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Wallet.created_at.desc())

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
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
        return wallet

    async def get_wallet(self, db: AsyncSession, tenant_id: UUID, wallet_id: UUID) -> Wallet:
        return await self.get_owned(db, wallet_id, tenant_id)
