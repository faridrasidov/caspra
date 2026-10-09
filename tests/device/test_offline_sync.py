# tests/device/test_offline_sync.py

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.domain_errors import ForbiddenError, ValidationError
from app.models.device.device import Device
from app.models.identity.user import User
from app.models.ledger.wallet import Wallet
from app.models.tenant.organization import OfflinePolicy
from app.schemas.device_txn import (
    OfflineQueueItem,
    OfflineQueueUploadRequest,
    OfflineReviewDecision,
)
from app.services.device_offline import DeviceOfflineService

pytestmark = pytest.mark.asyncio


def _item(card_uid: str, sequence_number: int, amount_minor: int = 500, **overrides):
    data = {
        "idempotency_key": uuid4(),
        "card_uid": card_uid,
        "amount_minor": amount_minor,
        "currency": "USD",
        "occurred_at": datetime.now(UTC) - timedelta(minutes=1),
        "sequence_number": sequence_number,
    }
    data.update(overrides)
    return OfflineQueueItem(**data)


async def _device(db_session, seeded: dict[str, str]) -> Device:
    return await db_session.get(Device, UUID(seeded["device_id"]))


async def _balance(db_session, seeded: dict[str, str]) -> int:
    db_session.expire_all()
    stmt = select(Wallet.balance_minor).where(Wallet.id == UUID(seeded["wallet_id"]))
    return (await db_session.execute(stmt)).scalar_one()


async def _sync(db_session, seeded, *items: OfflineQueueItem):
    device = await _device(db_session, seeded)
    payload = OfflineQueueUploadRequest(items=list(items))
    return await DeviceOfflineService().apply_queue(db_session, device, payload)


class TestOfflineSyncApply:
    """Queued offline debits are applied to the ledger exactly once."""

    async def test_in_order_items_are_applied(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        result = await _sync(db_session, seeded_device, _item(uid, 1), _item(uid, 2, 700))

        assert (result.accepted, result.rejected, result.manual_review) == (2, 0, 0)
        assert all(r.transaction_id is not None for r in result.results)
        assert await _balance(db_session, seeded_device) == 10_000 - 1_200

    async def test_replayed_queue_is_reported_as_duplicates(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        items = [_item(uid, 1), _item(uid, 2)]
        first = await _sync(db_session, seeded_device, *items)
        replay = await _sync(db_session, seeded_device, *items)

        assert first.accepted == 2
        assert (replay.accepted, replay.duplicates) == (0, 2)
        assert [r.transaction_id for r in replay.results] == [
            r.transaction_id for r in first.results
        ]
        assert await _balance(db_session, seeded_device) == 10_000 - 1_000

    async def test_reused_key_with_different_request_is_rejected(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        original = _item(uid, 1)
        await _sync(db_session, seeded_device, original)

        tampered = original.model_copy(update={"amount_minor": 1_900})
        result = await _sync(db_session, seeded_device, tampered)

        assert result.rejected == 1
        assert "different request" in result.results[0].error
        assert await _balance(db_session, seeded_device) == 10_000 - 500

    async def test_unknown_card_is_rejected_without_charging(self, db_session, seeded_device):
        result = await _sync(db_session, seeded_device, _item("NO-SUCH-CARD", 1))

        assert result.rejected == 1
        assert await _balance(db_session, seeded_device) == 10_000


class TestOfflineSyncPolicy:
    """Risk limits from the tenant's offline policy (see conftest seed values)."""

    async def test_disabled_policy_refuses_upload(self, db_session, seeded_device):
        policy = (
            await db_session.execute(
                select(OfflinePolicy).where(
                    OfflinePolicy.tenant_id == UUID(seeded_device["tenant_id"])
                )
            )
        ).scalar_one()
        policy.enabled = False
        await db_session.commit()

        with pytest.raises(ForbiddenError, match="disabled"):
            await _sync(db_session, seeded_device, _item(seeded_device["card_uid"], 1))

    async def test_queue_size_limit(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        items = [_item(uid, n) for n in range(1, 102)]
        with pytest.raises(ValidationError, match="item limit"):
            await _sync(db_session, seeded_device, *items)

    async def test_per_transaction_limit_rejects(self, db_session, seeded_device):
        result = await _sync(
            db_session, seeded_device, _item(seeded_device["card_uid"], 1, amount_minor=2_001)
        )
        assert result.rejected == 1
        assert "Per-transaction" in result.results[0].error

    async def test_per_card_limit_goes_to_manual_review(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        items = [_item(uid, n, amount_minor=2_000) for n in range(1, 4)]
        result = await _sync(db_session, seeded_device, *items)

        assert (result.accepted, result.manual_review) == (2, 1)
        assert "Per-card" in result.results[2].error
        assert await _balance(db_session, seeded_device) == 10_000 - 4_000

    async def test_stale_item_is_rejected(self, db_session, seeded_device):
        stale = _item(
            seeded_device["card_uid"], 1, occurred_at=datetime.now(UTC) - timedelta(hours=2)
        )
        result = await _sync(db_session, seeded_device, stale)
        assert result.rejected == 1
        assert "age limit" in result.results[0].error

    async def test_future_clock_goes_to_manual_review(self, db_session, seeded_device):
        ahead = _item(
            seeded_device["card_uid"], 1, occurred_at=datetime.now(UTC) + timedelta(hours=1)
        )
        result = await _sync(db_session, seeded_device, ahead)
        assert result.manual_review == 1
        assert "clock" in result.results[0].error

    async def test_sequence_gap_goes_to_manual_review(self, db_session, seeded_device):
        result = await _sync(db_session, seeded_device, _item(seeded_device["card_uid"], 5))
        assert result.manual_review == 1
        assert "Expected sequence 1" in result.results[0].error
        assert await _balance(db_session, seeded_device) == 10_000

    async def test_reused_sequence_with_new_key_goes_to_manual_review(
        self, db_session, seeded_device
    ):
        uid = seeded_device["card_uid"]
        await _sync(db_session, seeded_device, _item(uid, 1))
        result = await _sync(db_session, seeded_device, _item(uid, 1))
        assert result.manual_review == 1
        assert await _balance(db_session, seeded_device) == 10_000 - 500

        held = await DeviceOfflineService().list_review(
            db_session, UUID(seeded_device["tenant_id"])
        )
        assert len(held) == 1
        assert held[0].sequence_number is None
        assert held[0].payload["sequence_number"] == 1

    async def test_sequence_conflict_does_not_block_rest_of_queue(self, db_session, seeded_device):
        uid = seeded_device["card_uid"]
        await _sync(db_session, seeded_device, _item(uid, 1))
        result = await _sync(db_session, seeded_device, _item(uid, 1), _item(uid, 2))

        assert (result.accepted, result.manual_review) == (1, 1)
        assert await _balance(db_session, seeded_device) == 10_000 - 1_000


class TestOfflineManualReview:
    """Operators approve or reject items held for manual review."""

    async def _held_item(self, db_session, seeded_device):
        await _sync(db_session, seeded_device, _item(seeded_device["card_uid"], 3))
        held = await DeviceOfflineService().list_review(
            db_session, UUID(seeded_device["tenant_id"])
        )
        assert len(held) == 1
        return held[0]

    async def test_approve_applies_the_charge(self, db_session, seeded_device, seeded_admin):
        record = await self._held_item(db_session, seeded_device)
        reviewer = await db_session.get(User, UUID(seeded_admin["user_id"]))

        decided = await DeviceOfflineService().review(
            db_session,
            UUID(seeded_device["tenant_id"]),
            record.id,
            reviewer,
            OfflineReviewDecision(decision="accept", reason="Checked receipt"),
        )

        assert decided.status == "applied"
        assert decided.applied_transaction_id is not None
        assert await _balance(db_session, seeded_device) == 10_000 - 500

    async def test_reject_does_not_charge_and_is_final(
        self, db_session, seeded_device, seeded_admin
    ):
        record = await self._held_item(db_session, seeded_device)
        reviewer = await db_session.get(User, UUID(seeded_admin["user_id"]))
        service = DeviceOfflineService()
        tenant_id = UUID(seeded_device["tenant_id"])
        reject = OfflineReviewDecision(decision="reject", reason="Duplicate")

        record_id = record.id

        decided = await service.review(db_session, tenant_id, record_id, reviewer, reject)
        assert decided.status == "rejected"
        assert await _balance(db_session, seeded_device) == 10_000

        with pytest.raises(ValidationError, match="manual review"):
            await service.review(db_session, tenant_id, record_id, reviewer, reject)
