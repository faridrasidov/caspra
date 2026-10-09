# app/services/transaction.py

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.models.ledger.wallet import Transaction, TransactionType
from app.schemas.transaction import (
    TransactionExportOut,
    TransactionOut,
    TransactionStatsOut,
)
from app.services.base import TenantScopedService
from app.utils.pagination import Page


class TransactionService(TenantScopedService[Transaction]):
    """Read-side access to the transaction history (writes go via LedgerService)."""

    model = Transaction
    resource_name = "Transaction"

    async def list_transactions(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        page: int,
        limit: int,
        txn_type: str | None = None,
        wallet_id: UUID | None = None,
        customer_id: UUID | None = None,
        device_id: UUID | None = None,
    ) -> Page[Transaction]:
        filters = []
        if txn_type is not None:
            filters.append(Transaction.type == txn_type)
        if wallet_id is not None:
            filters.append(Transaction.wallet_id == wallet_id)
        if customer_id is not None:
            filters.append(Transaction.customer_id == customer_id)
        if device_id is not None:
            filters.append(Transaction.device_id == device_id)
        return await self.paginate(
            db, tenant_id, page, limit, *filters, order_by=Transaction.created_at.desc()
        )

    async def get_transaction(
        self, db: AsyncSession, tenant_id: UUID, transaction_id: UUID
    ) -> Transaction:
        return await self.get_owned(db, transaction_id, tenant_id)

    async def get_stats(self, db: AsyncSession, tenant_id: UUID) -> TransactionStatsOut:
        count_stmt = (
            select(func.count()).select_from(Transaction).where(Transaction.tenant_id == tenant_id)
        )
        total_count = (await db.execute(count_stmt)).scalar_one()

        sum_stmt = (
            select(
                Transaction.type,
                func.coalesce(func.sum(Transaction.amount_minor), 0),
            )
            .where(Transaction.tenant_id == tenant_id)
            .group_by(Transaction.type)
        )
        totals = {row[0]: int(row[1]) for row in (await db.execute(sum_stmt)).all()}
        credit_like = totals.get(TransactionType.CREDIT.value, 0) + totals.get(
            TransactionType.REFUND.value, 0
        )
        debit_like = totals.get(TransactionType.DEBIT.value, 0)
        return TransactionStatsOut(
            total_count=total_count,
            total_credit_minor=credit_like,
            total_debit_minor=debit_like,
        )

    async def export(
        self, db: AsyncSession, tenant_id: UUID, fmt: str = "json"
    ) -> TransactionExportOut:
        stmt = (
            select(Transaction)
            .where(Transaction.tenant_id == tenant_id)
            .order_by(Transaction.created_at.desc())
            .limit(10000)
        )
        result = await db.execute(stmt)
        rows = [TransactionOut.model_validate(t) for t in result.scalars().all()]
        return TransactionExportOut(format=fmt, rows=rows)

    async def ensure_exists(self, db: AsyncSession, tenant_id: UUID, transaction_id: UUID) -> None:
        stmt = select(Transaction.id).where(
            Transaction.id == transaction_id, Transaction.tenant_id == tenant_id
        )
        if (await db.execute(stmt)).first() is None:
            raise NotFoundError("Transaction", str(transaction_id))
