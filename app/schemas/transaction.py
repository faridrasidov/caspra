# app/schemas/transaction.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ledger.wallet import TransactionStatus, TransactionType
from app.schemas import PaginationSchema


class TransactionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    idempotency_key: UUID
    type: TransactionType
    amount_minor: int
    currency: str
    status: TransactionStatus
    wallet_id: UUID | None = None
    customer_id: UUID | None = None
    device_id: UUID | None = None
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTransactionOut(PaginationSchema):
    items: list[TransactionOut]


class RefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    amount_minor: int | None = Field(
        None, gt=0, description="Partial refund amount; defaults to full amount"
    )
    reason: str | None = Field(None, max_length=500)


class RefundOut(BaseModel):
    id: UUID
    tenant_id: UUID
    original_transaction_id: UUID
    refund_transaction_id: UUID | None = None
    amount_minor: int
    currency: str
    reason: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class TransactionStatsOut(BaseModel):
    total_count: int
    total_credit_minor: int
    total_debit_minor: int
    currency: str | None = None


class TransactionExportOut(BaseModel):
    format: str
    rows: list[TransactionOut]
