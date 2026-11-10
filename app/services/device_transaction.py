from __future__ import annotations

# app/services/device_transaction.py
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.domain_errors import NotFoundError
from app.models.ledger.wallet import Transaction, TransactionStatus
from app.services.device_offline import DeviceOfflineService
from app.utils.pagination import paginate_async_query

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.device.device import Device
    from app.schemas.device_txn import (
        OfflineQueueUploadRequest,
        OfflineSyncResultOut,
    )


class DeviceTransactionService:
    """A device's view of its own transactions and offline upload entry point."""

    async def list_recent(self, db: AsyncSession, device: Device, page: int, limit: int) -> dict:
        stmt = (
            select(Transaction)
            .where(
                Transaction.tenant_id == device.tenant_id,
                Transaction.device_id == device.id,
            )
            .order_by(Transaction.created_at.desc())
        )
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )

    async def list_pending(self, db: AsyncSession, device: Device, page: int, limit: int) -> dict:
        stmt = (
            select(Transaction)
            .where(
                Transaction.tenant_id == device.tenant_id,
                Transaction.device_id == device.id,
                Transaction.status == TransactionStatus.PENDING.value,
            )
            .order_by(Transaction.created_at.desc())
        )
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )

    async def get_status(
        self, db: AsyncSession, device: Device, transaction_id: UUID
    ) -> Transaction:
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.tenant_id == device.tenant_id,
            Transaction.device_id == device.id,
        )
        txn = (await db.execute(stmt)).scalars().first()
        if txn is None:
            raise NotFoundError("Transaction", str(transaction_id))
        return txn

    async def upload(
        self, db: AsyncSession, device: Device, payload: OfflineQueueUploadRequest
    ) -> OfflineSyncResultOut:
        return await DeviceOfflineService().apply_queue(db, device, payload)
