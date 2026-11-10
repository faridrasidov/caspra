from __future__ import annotations

# app/services/device_offline.py
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.domain_errors import ForbiddenError, NotFoundError, ValidationError
from app.core.metrics import set_metric_gauge
from app.models.device.device import Device
from app.models.ledger.hold import OfflineTransaction, OfflineTransactionStatus
from app.models.ledger.wallet import Transaction, TransactionType, WalletType
from app.models.tenant.organization import OfflinePolicy, Organization
from app.schemas.device_txn import (
    OfflineConfigOut,
    OfflineItemResult,
    OfflinePolicyUpdate,
    OfflineQueueItem,
    OfflineQueueUploadRequest,
    OfflineReviewDecision,
    OfflineSyncResultOut,
)
from app.services.audit import AuditService
from app.services.device_capability import DeviceCapabilityService
from app.services.device_card import DeviceCardService
from app.services.ledger import LedgerService
from app.utils.idempotency import canonical_request_hash

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.identity.user import User


class DeviceOfflineService:
    """Bounded-risk, replay-safe upload of a device's queued operations."""

    def __init__(self) -> None:
        self._cards = DeviceCardService()
        self._ledger = LedgerService(commit=False)

    async def offline_config(self, db: AsyncSession, device: Device) -> OfflineConfigOut:
        org = await db.get(Organization, device.tenant_id)
        policy = await self.get_policy(db, device.tenant_id)
        return OfflineConfigOut(
            enabled=bool(policy and policy.enabled),
            uid_risk_accepted=bool(policy and policy.uid_risk_accepted),
            max_transaction_minor=policy.max_transaction_minor if policy else 0,
            max_card_total_minor=policy.max_card_total_minor if policy else 0,
            max_device_total_minor=policy.max_device_total_minor if policy else 0,
            max_outage_total_minor=policy.max_outage_total_minor if policy else 0,
            max_queue_age_seconds=policy.max_queue_age_seconds if policy else 3600,
            max_queue_size=policy.max_queue_size if policy else 100,
            sync_interval_s=policy.sync_interval_seconds if policy else 60,
            currency=org.default_currency if org is not None else "USD",
        )

    async def get_policy(self, db: AsyncSession, tenant_id: UUID) -> OfflinePolicy | None:
        stmt = select(OfflinePolicy).where(OfflinePolicy.tenant_id == tenant_id)
        return (await db.execute(stmt)).scalars().first()

    async def update_policy(
        self, db: AsyncSession, tenant_id: UUID, payload: OfflinePolicyUpdate
    ) -> OfflinePolicy:
        if payload.enabled:
            amount_limits = (
                payload.max_transaction_minor,
                payload.max_card_total_minor,
                payload.max_device_total_minor,
                payload.max_outage_total_minor,
            )
            if not payload.uid_risk_accepted or any(limit <= 0 for limit in amount_limits):
                raise ValidationError(
                    "Enabling UID-only offline spending requires explicit risk acceptance "
                    "and positive amount limits"
                )
        policy = await self.get_policy(db, tenant_id)
        if policy is None:
            policy = OfflinePolicy(tenant_id=tenant_id)
            db.add(policy)
        for key, value in payload.model_dump().items():
            setattr(policy, key, value)
        await db.commit()
        await db.refresh(policy)
        return policy

    async def apply_queue(
        self, db: AsyncSession, device: Device, payload: OfflineQueueUploadRequest
    ) -> OfflineSyncResultOut:
        tenant_id, device_id = device.tenant_id, device.id
        now = datetime.now(UTC)
        self._record_queue_metrics(device, payload, now)
        results = []
        counts = {"accepted": 0, "duplicates": 0, "rejected": 0, "manual_review": 0}
        for item in payload.items:
            policy = (
                await db.execute(
                    select(OfflinePolicy)
                    .where(OfflinePolicy.tenant_id == tenant_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if policy is None or not policy.enabled or not policy.uid_risk_accepted:
                raise ForbiddenError("Offline spending is disabled for this tenant")
            if len(payload.items) > policy.max_queue_size:
                raise ValidationError("Offline queue exceeds policy size limit")
            device = await db.get(Device, device_id)
            result, duplicate = await self._process_item(db, device, policy, item, now)
            await db.commit()
            results.append(result)
            category = (
                "duplicates"
                if duplicate
                else {
                    "applied": "accepted",
                    "rejected": "rejected",
                    "manual_review": "manual_review",
                }[result.status.value]
            )
            counts[category] += 1
        return OfflineSyncResultOut(**counts, results=results)

    async def _process_item(  # noqa: PLR0911 - explicit replay and validation dispositions
        self, db, device, policy, item, now
    ):
        request_hash = canonical_request_hash(
            "offline.charge",
            device_id=device.id,
            card_uid=item.card_uid,
            amount_minor=item.amount_minor,
            currency=item.currency.upper(),
            occurred_at=item.occurred_at.isoformat(),
            sequence_number=item.sequence_number,
            description=item.description,
        )
        record = await self._existing(db, device, item.idempotency_key)
        if record is not None:
            stored_hash = record.request_hash or canonical_request_hash(
                "offline.charge",
                device_id=record.device_id,
                card_uid=record.card_uid,
                amount_minor=record.amount_minor,
                currency=record.payload["currency"].upper(),
                occurred_at=OfflineQueueItem.model_validate(record.payload).occurred_at.isoformat(),
                sequence_number=record.sequence_number,
                description=record.payload.get("description"),
            )
            if stored_hash != request_hash or record.device_id != device.id:
                return self._result(
                    item,
                    OfflineTransactionStatus.REJECTED,
                    error="Idempotency key was reused for another operation",
                ), False
            if record.status != OfflineTransactionStatus.PENDING.value:
                return self._result(
                    item,
                    OfflineTransactionStatus(record.status),
                    transaction_id=record.applied_transaction_id,
                    error=record.error,
                ), True
            posted = (
                await db.execute(
                    select(Transaction.id).where(
                        Transaction.tenant_id == device.tenant_id,
                        Transaction.idempotency_key == item.idempotency_key,
                    )
                )
            ).first()
            if posted is None:
                window_start = now - timedelta(seconds=policy.max_queue_age_seconds)
                disposition, reason = self._validate_item(
                    item,
                    policy,
                    now,
                    window_start,
                    item.sequence_number,
                    await self._risk_total(db, device.tenant_id, window_start),
                    await self._risk_total(db, device.tenant_id, window_start, device_id=device.id),
                    await self._risk_total(
                        db, device.tenant_id, window_start, card_uid=item.card_uid
                    ),
                )
                if disposition is not None:
                    record.status, record.error = disposition.value, reason
                    return self._result(item, disposition, error=reason), False
        else:
            sequence_owner = await self._existing_sequence(db, device, item.sequence_number)
            if sequence_owner is not None:
                await AuditService().record(
                    db,
                    device.tenant_id,
                    None,
                    "offline.sequence_conflict",
                    "device",
                    str(device.id),
                    {
                        "idempotency_key": str(item.idempotency_key),
                        "sequence_number": item.sequence_number,
                        "original_operation": str(sequence_owner.id),
                    },
                )
                return self._result(
                    item,
                    OfflineTransactionStatus.REJECTED,
                    error=(
                        "Sequence belongs to another operation; "
                        "original preserved and conflict audited"
                    ),
                ), False
            window_start = now - timedelta(seconds=policy.max_queue_age_seconds)
            disposition, reason = self._validate_item(
                item,
                policy,
                now,
                window_start,
                await self._next_sequence(db, device),
                await self._risk_total(db, device.tenant_id, window_start),
                await self._risk_total(db, device.tenant_id, window_start, device_id=device.id),
                await self._risk_total(db, device.tenant_id, window_start, card_uid=item.card_uid),
            )
            if disposition is not None:
                return await self._record_without_applying(
                    db, device, item, request_hash, disposition, reason
                ), False
            record = await self._create_record(db, device, item, request_hash)
        try:
            async with db.begin_nested():
                txn = await self._apply_item(db, device, item)
                transaction_id = txn.id
        except HTTPException as exc:
            record.status = OfflineTransactionStatus.REJECTED.value
            record.error = str(exc.detail)
            return self._result(
                item, OfflineTransactionStatus.REJECTED, error=str(exc.detail)
            ), False
        record.status = OfflineTransactionStatus.APPLIED.value
        record.applied_transaction_id = transaction_id
        return self._result(
            item, OfflineTransactionStatus.APPLIED, transaction_id=transaction_id
        ), False

    @staticmethod
    def _record_queue_metrics(
        device: Device,
        payload: OfflineQueueUploadRequest,
        now: datetime,
    ) -> None:
        labels = {"device_id": str(device.id)}
        if payload.items:
            oldest = min(item.occurred_at for item in payload.items)
            set_metric_gauge(
                "offline_queue_age_seconds",
                max(0.0, (now - oldest).total_seconds()),
                **labels,
            )
        set_metric_gauge("offline_queue_size", len(payload.items), **labels)

    async def list_review(
        self, db: AsyncSession, tenant_id: UUID, status_filter: str | None = None
    ) -> list[OfflineTransaction]:
        stmt = select(OfflineTransaction).where(OfflineTransaction.tenant_id == tenant_id)
        if status_filter is not None:
            stmt = stmt.where(OfflineTransaction.status == status_filter)
        else:
            stmt = stmt.where(
                OfflineTransaction.status == OfflineTransactionStatus.MANUAL_REVIEW.value
            )
        stmt = stmt.order_by(OfflineTransaction.occurred_at.asc()).limit(500)
        return list((await db.execute(stmt)).scalars().all())

    async def review(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        offline_transaction_id: UUID,
        reviewer: User,
        payload: OfflineReviewDecision,
    ) -> OfflineTransaction:
        stmt = (
            select(OfflineTransaction)
            .where(
                OfflineTransaction.id == offline_transaction_id,
                OfflineTransaction.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        record = (await db.execute(stmt)).scalars().first()
        if record is None:
            raise NotFoundError("Offline transaction", str(offline_transaction_id))
        if record.status != OfflineTransactionStatus.MANUAL_REVIEW.value:
            raise ValidationError("Only operations awaiting manual review can be decided")

        record.reviewed_at = datetime.now(UTC)
        record.reviewed_by_user_id = reviewer.id
        record.error = payload.reason
        if payload.decision == "reject":
            record.status = OfflineTransactionStatus.REJECTED.value
            await db.commit()
            await db.refresh(record)
            return record

        device = await db.get(Device, record.device_id)
        if device is None or device.tenant_id != tenant_id:
            raise NotFoundError("Device", str(record.device_id))
        item = OfflineQueueItem.model_validate(record.payload)
        txn = await self._apply_item(db, device, item)
        record.status = OfflineTransactionStatus.APPLIED.value
        record.applied_transaction_id = txn.id
        await db.commit()
        await db.refresh(record)
        return record

    def _validate_item(  # noqa: PLR0911
        self,
        item: OfflineQueueItem,
        policy: OfflinePolicy,
        now: datetime,
        window_start: datetime,
        expected_sequence: int,
        tenant_total: int,
        device_total: int,
        card_total: int,
    ) -> tuple[OfflineTransactionStatus | None, str | None]:
        if item.type != TransactionType.DEBIT:
            return OfflineTransactionStatus.REJECTED, "Only debit operations are allowed offline"
        if item.occurred_at > now + timedelta(minutes=5):
            return OfflineTransactionStatus.MANUAL_REVIEW, "Device clock is ahead of server time"
        if item.occurred_at < window_start:
            return OfflineTransactionStatus.REJECTED, "Offline operation exceeds queue age limit"
        if item.sequence_number != expected_sequence:
            return (
                OfflineTransactionStatus.MANUAL_REVIEW,
                f"Expected sequence {expected_sequence}, received {item.sequence_number}",
            )
        if item.amount_minor > policy.max_transaction_minor:
            return OfflineTransactionStatus.REJECTED, "Per-transaction offline limit exceeded"
        if card_total + item.amount_minor > policy.max_card_total_minor:
            return OfflineTransactionStatus.MANUAL_REVIEW, "Per-card offline limit exceeded"
        if device_total + item.amount_minor > policy.max_device_total_minor:
            return OfflineTransactionStatus.MANUAL_REVIEW, "Per-device offline limit exceeded"
        if tenant_total + item.amount_minor > policy.max_outage_total_minor:
            return OfflineTransactionStatus.MANUAL_REVIEW, "Tenant outage limit exceeded"
        return None, None

    async def _create_record(
        self,
        db: AsyncSession,
        device: Device,
        item: OfflineQueueItem,
        request_hash: str,
        *,
        status: OfflineTransactionStatus = OfflineTransactionStatus.PENDING,
        error: str | None = None,
    ) -> OfflineTransaction:
        record = OfflineTransaction(
            tenant_id=device.tenant_id,
            device_id=device.id,
            idempotency_key=item.idempotency_key,
            request_hash=request_hash,
            occurred_at=item.occurred_at,
            sequence_number=item.sequence_number,
            card_uid=item.card_uid,
            amount_minor=item.amount_minor,
            payload=item.model_dump(mode="json"),
            status=status.value,
            error=error,
        )
        db.add(record)
        await db.flush()
        return record

    async def _record_without_applying(
        self,
        db: AsyncSession,
        device: Device,
        item: OfflineQueueItem,
        request_hash: str,
        status: OfflineTransactionStatus,
        reason: str | None,
    ) -> OfflineItemResult:
        record = await self._create_record(
            db,
            device,
            item,
            request_hash,
            status=status,
            error=reason,
        )
        return self._result(
            item,
            OfflineTransactionStatus(record.status),
            transaction_id=record.applied_transaction_id,
            error=record.error,
        )

    @staticmethod
    def _result(
        item: OfflineQueueItem,
        status: OfflineTransactionStatus,
        *,
        transaction_id: UUID | None = None,
        error: str | None = None,
    ) -> OfflineItemResult:
        return OfflineItemResult(
            idempotency_key=item.idempotency_key,
            status=status,
            transaction_id=transaction_id,
            error=error,
        )

    async def _apply_item(self, db: AsyncSession, device: Device, item: OfflineQueueItem):
        prior = (
            await db.execute(
                select(Transaction).where(
                    Transaction.tenant_id == device.tenant_id,
                    Transaction.idempotency_key == item.idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if prior is not None:
            if (
                prior.type != "debit"
                or prior.amount_minor != item.amount_minor
                or prior.currency != item.currency.upper()
                or prior.device_id != device.id
            ):
                raise ValidationError(
                    "Existing ledger transaction does not match offline operation"
                )
            return prior
        org = await db.get(Organization, device.tenant_id)
        if org is None or item.currency.upper() != org.default_currency.upper():
            raise ValidationError("Offline operation currency must match venue currency")
        await DeviceCapabilityService().assert_legacy_payments(db, device)
        card = await self._cards.get_card_by_uid(db, device.tenant_id, item.card_uid)
        wallet = await self._cards.resolve_wallet(
            db, device.tenant_id, card, WalletType.CREDIT, item.currency.upper()
        )
        return await self._ledger.charge(
            db,
            device.tenant_id,
            wallet.id,
            amount_minor=item.amount_minor,
            currency=item.currency.upper(),
            idempotency_key=item.idempotency_key,
            device_id=device.id,
            description=item.description,
        )

    async def _existing(
        self, db: AsyncSession, device: Device, idempotency_key: UUID
    ) -> OfflineTransaction | None:
        stmt = select(OfflineTransaction).where(
            OfflineTransaction.tenant_id == device.tenant_id,
            OfflineTransaction.idempotency_key == idempotency_key,
        )
        return (await db.execute(stmt)).scalars().first()

    async def _existing_sequence(
        self, db: AsyncSession, device: Device, sequence_number: int
    ) -> OfflineTransaction | None:
        stmt = select(OfflineTransaction).where(
            OfflineTransaction.tenant_id == device.tenant_id,
            OfflineTransaction.device_id == device.id,
            OfflineTransaction.sequence_number == sequence_number,
        )
        return (await db.execute(stmt)).scalars().first()

    async def _next_sequence(self, db: AsyncSession, device: Device) -> int:
        stmt = select(func.max(OfflineTransaction.sequence_number)).where(
            OfflineTransaction.tenant_id == device.tenant_id,
            OfflineTransaction.device_id == device.id,
        )
        return int((await db.execute(stmt)).scalar_one_or_none() or 0) + 1

    async def _risk_total(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        window_start: datetime,
        *,
        device_id: UUID | None = None,
        card_uid: str | None = None,
    ) -> int:
        stmt = select(func.coalesce(func.sum(OfflineTransaction.amount_minor), 0)).where(
            OfflineTransaction.tenant_id == tenant_id,
            OfflineTransaction.occurred_at >= window_start,
            OfflineTransaction.status == OfflineTransactionStatus.APPLIED.value,
        )
        if device_id is not None:
            stmt = stmt.where(OfflineTransaction.device_id == device_id)
        if card_uid is not None:
            stmt = stmt.where(OfflineTransaction.card_uid == card_uid)
        return int((await db.execute(stmt)).scalar_one())
