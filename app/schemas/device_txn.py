# app/schemas/device_txn.py

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.ledger.hold import OfflineTransactionStatus
from app.models.ledger.wallet import TransactionStatus, TransactionType
from app.schemas import PaginationSchema


class DeviceTransactionOut(BaseModel):
    """Minimal transaction view for a reader's local history."""

    id: UUID
    type: TransactionType
    amount_minor: int
    currency: str
    status: TransactionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedDeviceTransactionOut(PaginationSchema):
    items: list[DeviceTransactionOut]


class OfflineQueueItem(BaseModel):
    """A single queued offline operation uploaded on reconnect."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    type: TransactionType = TransactionType.DEBIT
    card_uid: str = Field(..., min_length=1, max_length=120)
    amount_minor: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    occurred_at: AwareDatetime
    sequence_number: int = Field(..., gt=0)
    description: str | None = Field(None, max_length=500)


class OfflineQueueUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OfflineQueueItem] = Field(..., max_length=500)


class OfflineItemResult(BaseModel):
    idempotency_key: UUID
    status: OfflineTransactionStatus
    transaction_id: UUID | None = None
    error: str | None = None


class OfflineSyncResultOut(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    manual_review: int
    results: list[OfflineItemResult]


class OfflineConfigOut(BaseModel):
    enabled: bool
    uid_risk_accepted: bool
    max_transaction_minor: int
    max_card_total_minor: int
    max_device_total_minor: int
    max_outage_total_minor: int
    max_queue_age_seconds: int
    max_queue_size: int
    sync_interval_s: int
    currency: str


class OfflinePolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    uid_risk_accepted: bool
    max_transaction_minor: int = Field(0, ge=0)
    max_card_total_minor: int = Field(0, ge=0)
    max_device_total_minor: int = Field(0, ge=0)
    max_outage_total_minor: int = Field(0, ge=0)
    max_queue_age_seconds: int = Field(3600, ge=60, le=604800)
    max_queue_size: int = Field(100, ge=1, le=500)
    sync_interval_seconds: int = Field(60, ge=5, le=3600)


class OfflinePolicyOut(OfflinePolicyUpdate):
    id: UUID
    tenant_id: UUID

    model_config = ConfigDict(from_attributes=True)


class OfflineReviewItemOut(BaseModel):
    id: UUID
    device_id: UUID
    idempotency_key: UUID
    card_uid: str
    amount_minor: int
    occurred_at: datetime
    sequence_number: int | None = None
    status: OfflineTransactionStatus
    error: str | None = None
    applied_transaction_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class OfflineReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., pattern="^(accept|reject)$")
    reason: str = Field(..., min_length=3, max_length=500)
