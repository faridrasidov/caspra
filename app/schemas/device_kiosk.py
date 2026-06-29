# app/schemas/device_kiosk.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.kiosk_topup import KioskTopupStatus, PaymentMethodCode


class KioskTopupRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kiosk_id: UUID
    customer_id: UUID | None = None
    card_uid: str | None = Field(None, max_length=120)
    amount_minor: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    payment_method: PaymentMethodCode
    idempotency_key: UUID


class KioskTopupConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    idempotency_key: UUID


class KioskTopupCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID


class KioskTopupSessionOut(BaseModel):
    id: UUID
    kiosk_id: UUID
    customer_id: UUID | None = None
    amount_minor: int
    currency: str
    payment_method: PaymentMethodCode
    status: KioskTopupStatus
    transaction_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaymentMethodOut(BaseModel):
    code: PaymentMethodCode
    label: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class PaymentMethodsOut(BaseModel):
    items: list[PaymentMethodOut]
