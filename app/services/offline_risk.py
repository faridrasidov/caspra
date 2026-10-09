# app/services/offline_risk.py

from datetime import datetime, timedelta

from app.models.ledger.hold import OfflineTransactionStatus
from app.models.ledger.wallet import TransactionType
from app.models.tenant.organization import OfflinePolicy
from app.schemas.device_txn import OfflineQueueItem


def evaluate_offline_item(  # noqa: PLR0911
    item: OfflineQueueItem,
    policy: OfflinePolicy,
    now: datetime,
    window_start: datetime,
    expected_sequence: int,
    tenant_total: int,
    device_total: int,
    card_total: int,
) -> tuple[OfflineTransactionStatus | None, str | None]:
    """Apply the tenant's offline risk policy to one queued item.

    Returns ``(None, None)`` when the item may be charged, otherwise the
    disposition (rejected or held for manual review) and the reason.
    """
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
