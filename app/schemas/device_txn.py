# app/schemas/device_txn.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    results: list[OfflineItemResult]


class OfflineConfigOut(BaseModel):
    max_offline_amount_minor: int
    max_queue_size: int
    sync_interval_s: int
    currency: str
