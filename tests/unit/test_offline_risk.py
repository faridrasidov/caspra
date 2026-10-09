# tests/unit/test_offline_risk.py

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.ledger.hold import OfflineTransactionStatus
from app.models.ledger.wallet import TransactionType
from app.models.tenant.organization import OfflinePolicy
from app.schemas.device_txn import OfflineQueueItem
from app.services.offline_risk import evaluate_offline_item

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
WINDOW_START = NOW - timedelta(hours=1)
POLICY = OfflinePolicy(
    max_transaction_minor=2_000,
    max_card_total_minor=5_000,
    max_device_total_minor=10_000,
    max_outage_total_minor=20_000,
)
REVIEW = OfflineTransactionStatus.MANUAL_REVIEW
REJECTED = OfflineTransactionStatus.REJECTED


def _evaluate(
    *,
    amount_minor: int = 500,
    occurred_at: datetime = NOW - timedelta(minutes=1),
    sequence_number: int = 1,
    expected_sequence: int = 1,
    tenant_total: int = 0,
    device_total: int = 0,
    card_total: int = 0,
    txn_type: TransactionType = TransactionType.DEBIT,
):
    item = OfflineQueueItem(
        idempotency_key=uuid4(),
        type=txn_type,
        card_uid="CARD-1",
        amount_minor=amount_minor,
        currency="USD",
        occurred_at=occurred_at,
        sequence_number=sequence_number,
    )
    return evaluate_offline_item(
        item,
        POLICY,
        NOW,
        WINDOW_START,
        expected_sequence,
        tenant_total,
        device_total,
        card_total,
    )


def test_item_within_all_limits_is_allowed():
    assert _evaluate() == (None, None)


def test_amount_exactly_at_each_limit_is_allowed():
    assert _evaluate(amount_minor=2_000, card_total=3_000, device_total=8_000) == (None, None)


@pytest.mark.parametrize(
    ("overrides", "disposition", "reason"),
    [
        ({"txn_type": TransactionType.CREDIT}, REJECTED, "Only debit"),
        ({"occurred_at": NOW + timedelta(minutes=6)}, REVIEW, "clock is ahead"),
        ({"occurred_at": WINDOW_START - timedelta(seconds=1)}, REJECTED, "age limit"),
        ({"sequence_number": 3}, REVIEW, "Expected sequence 1, received 3"),
        ({"amount_minor": 2_001}, REJECTED, "Per-transaction"),
        ({"card_total": 4_600}, REVIEW, "Per-card"),
        ({"device_total": 9_600}, REVIEW, "Per-device"),
        ({"tenant_total": 19_600}, REVIEW, "Tenant outage"),
    ],
)
def test_limit_breaches(overrides, disposition, reason):
    result, message = _evaluate(**overrides)
    assert result == disposition
    assert reason in message


def test_small_clock_skew_is_tolerated():
    assert _evaluate(occurred_at=NOW + timedelta(minutes=4)) == (None, None)


def test_rejections_take_priority_over_review():
    # Stale and over the per-transaction limit: the stale rejection wins.
    result, message = _evaluate(occurred_at=WINDOW_START - timedelta(minutes=1), amount_minor=5_000)
    assert result == REJECTED
    assert "age limit" in message
