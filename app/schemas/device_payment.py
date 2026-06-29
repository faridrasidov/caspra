# app/schemas/device_payment.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ledger.hold import HoldStatus
from app.models.ledger.wallet import TransactionStatus, WalletType


class DeviceChargeRequest(BaseModel):
    """Debit a card's wallet (money out). Idempotent and replay-safe."""

    model_config = ConfigDict(extra="forbid")

    card_uid: str = Field(..., min_length=1, max_length=120)
    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    wallet_type: WalletType = WalletType.CREDIT
    description: str | None = Field(None, max_length=500)


class DeviceRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    idempotency_key: UUID
    amount_minor: int | None = Field(None, gt=0)
    reason: str | None = Field(None, max_length=500)


class DevicePreauthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_uid: str = Field(..., min_length=1, max_length=120)
    amount_minor: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    wallet_type: WalletType = WalletType.CREDIT
    expires_in_s: int | None = Field(None, ge=0)


class DeviceCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: UUID
    idempotency_key: UUID
    amount_minor: int | None = Field(None, gt=0, description="Capture up to the held amount")


class DeviceVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: UUID


class DevicePaymentOut(BaseModel):
    """Lightweight payment result a reader needs to print a receipt."""

    transaction_id: UUID
    status: TransactionStatus
    amount_minor: int
    currency: str
    wallet_id: UUID | None = None
    balance_minor: int | None = None


class HoldOut(BaseModel):
    hold_id: UUID
    status: HoldStatus
    amount_minor: int
    currency: str
    wallet_id: UUID
    expires_at: datetime | None = None
