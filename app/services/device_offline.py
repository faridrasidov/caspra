# app/services/device_offline.py

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device.device import Device
from app.models.ledger.hold import OfflineTransaction, OfflineTransactionStatus
from app.models.ledger.wallet import WalletType
from app.models.tenant.organization import Organization
from app.schemas.device_txn import (
    OfflineConfigOut,
    OfflineItemResult,
    OfflineQueueItem,
    OfflineQueueUploadRequest,
    OfflineSyncResultOut,
)
from app.services.device_card import DeviceCardService
from app.services.ledger import LedgerService

# Conservative defaults a reader applies while disconnected from the server.
MAX_OFFLINE_AMOUNT_MINOR = 10_000
MAX_OFFLINE_QUEUE_SIZE = 500
OFFLINE_SYNC_INTERVAL_S = 60


class DeviceOfflineService:
    """Offline limits and replay-safe upload of a device's queued operations."""

    def __init__(self) -> None:
        self._cards = DeviceCardService()
        self._ledger = LedgerService()

    async def offline_config(self, db: AsyncSession, device: Device) -> OfflineConfigOut:
        org = await db.get(Organization, device.tenant_id)
        currency = org.default_currency if org is not None else "USD"
        return OfflineConfigOut(
            max_offline_amount_minor=MAX_OFFLINE_AMOUNT_MINOR,
            max_queue_size=MAX_OFFLINE_QUEUE_SIZE,
            sync_interval_s=OFFLINE_SYNC_INTERVAL_S,
            currency=currency,
        )

    async def apply_queue(
        self, db: AsyncSession, device: Device, payload: OfflineQueueUploadRequest
    ) -> OfflineSyncResultOut:
        """Apply each queued op exactly once, keyed by its idempotency_key."""
        results: list[OfflineItemResult] = []
        accepted = duplicates = rejected = 0

        for item in payload.items:
            existing = await self._existing(db, device, item.idempotency_key)
            if existing is not None:
                duplicates += 1
                results.append(
                    OfflineItemResult(
                        idempotency_key=item.idempotency_key,
                        status=OfflineTransactionStatus(existing.status),
                        transaction_id=existing.applied_transaction_id,
                        error=existing.error,
                    )
                )
                continue

            record = OfflineTransaction(
                tenant_id=device.tenant_id,
                device_id=device.id,
                idempotency_key=item.idempotency_key,
                payload=item.model_dump(mode="json"),
                status=OfflineTransactionStatus.PENDING.value,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)

            try:
                txn = await self._apply_item(db, device, item)
            except HTTPException as exc:
                record.status = OfflineTransactionStatus.REJECTED.value
                record.error = str(exc.detail)
                await db.commit()
                rejected += 1
                results.append(
                    OfflineItemResult(
                        idempotency_key=item.idempotency_key,
                        status=OfflineTransactionStatus.REJECTED,
                        error=str(exc.detail),
                    )
                )
                continue

            record.status = OfflineTransactionStatus.APPLIED.value
            record.applied_transaction_id = txn.id
            await db.commit()
            accepted += 1
            results.append(
                OfflineItemResult(
                    idempotency_key=item.idempotency_key,
                    status=OfflineTransactionStatus.APPLIED,
                    transaction_id=txn.id,
                )
            )

        return OfflineSyncResultOut(
            accepted=accepted, duplicates=duplicates, rejected=rejected, results=results
        )

    async def _apply_item(self, db: AsyncSession, device: Device, item: OfflineQueueItem):
        card = await self._cards.get_card_by_uid(db, device.tenant_id, item.card_uid)
        wallet = await self._cards.resolve_wallet(
            db, device.tenant_id, card, WalletType.CREDIT, item.currency
        )
        return await self._ledger.charge(
            db,
            device.tenant_id,
            wallet.id,
            amount_minor=item.amount_minor,
            currency=item.currency,
            idempotency_key=item.idempotency_key,
            device_id=device.id,
            description=item.description,
        )

    async def _existing(
        self, db: AsyncSession, device: Device, idempotency_key
    ) -> OfflineTransaction | None:
        stmt = select(OfflineTransaction).where(
            OfflineTransaction.tenant_id == device.tenant_id,
            OfflineTransaction.idempotency_key == idempotency_key,
        )
        return (await db.execute(stmt)).scalars().first()
