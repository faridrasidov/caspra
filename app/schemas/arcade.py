from datetime import date, datetime
from typing import Literal
from uuid import UUID

import pycountry
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.card import CardOut
from app.schemas.customer import CustomerOut
from app.schemas.transaction import TransactionOut
from app.schemas.wallet import WalletOut


class Page[T](BaseModel):
    page: int
    total: int
    pages: int
    items: list[T]
    next_cursor: str | None = None


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MoneyInput(Input):
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value: str) -> str:
        value = value.upper()
        if pycountry.currencies.get(alpha_3=value) is None:
            raise ValueError("Unsupported ISO currency")
        return value


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class MachineCreate(MoneyInput):
    name: str = Field(min_length=1, max_length=200)
    device_id: UUID
    location_id: UUID | None = None
    price_minor: int = Field(gt=0, strict=True)


class MachineUpdate(Input):
    name: str | None = Field(None, min_length=1, max_length=200)
    price_minor: int | None = Field(None, gt=0, strict=True)
    state: Literal["available", "maintenance", "offline", "archived"] | None = None


class MachineOut(RecordOut):
    name: str
    device_id: UUID
    location_id: UUID | None
    price_minor: int
    currency: str
    price_revision: int
    state: str


class PricingScheduleCreate(Input):
    machine_id: UUID
    name: str = Field(min_length=1, max_length=200)
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(gt=0, le=1440)
    price_minor: int = Field(gt=0, strict=True)


class PricingScheduleOut(RecordOut):
    machine_id: UUID
    name: str
    weekday: int
    start_minute: int
    end_minute: int
    price_minor: int
    active: bool
    currency: str

    @computed_field
    @property
    def start_time(self) -> str:
        return f"{self.start_minute // 60:02}:{self.start_minute % 60:02}"

    @computed_field
    @property
    def end_time(self) -> str:
        return f"{self.end_minute // 60:02}:{self.end_minute % 60:02}"

    @computed_field
    @property
    def weekday_name(self) -> str:
        return ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[
            self.weekday
        ]


class PlayRequest(Input):
    card_uid: str = Field(min_length=1, max_length=120)
    idempotency_key: UUID


class PlayOutcome(Input):
    outcome: Literal["activated", "failed", "unknown"]
    reason: str | None = Field(None, max_length=500)


class PlayResolution(Input):
    outcome: Literal["activated", "refunded"]
    reason: str = Field(min_length=3, max_length=500)


class PlayOut(RecordOut):
    machine_id: UUID
    device_id: UUID
    customer_id: UUID
    transaction_id: UUID
    refund_transaction_id: UUID | None
    amount_minor: int
    currency: str
    status: str
    activation_outcome: str | None = None
    price_snapshot: dict
    execute_before: datetime
    outcome_at: datetime | None
    resolution_reason: str | None


class ShiftOpen(MoneyInput):
    terminal: str = Field(min_length=1, max_length=120)
    location_id: UUID | None = None
    opening_minor: int = Field(ge=0, strict=True)


class ShiftClose(Input):
    counted_minor: int = Field(ge=0, strict=True)


class Reason(Input):
    reason: str = Field(min_length=3, max_length=500)


class CacheRepair(Reason):
    wallet_id: UUID


class ShiftOut(RecordOut):
    cashier_id: UUID
    terminal: str
    location_id: UUID | None
    currency: str
    opening_minor: int
    counted_minor: int | None
    expected_minor: int | None
    variance_minor: int | None
    closed_at: datetime | None
    reviewed_by: UUID | None
    review_reason: str | None


class CashMovementCreate(Reason):
    amount_minor: int = Field(strict=True)
    idempotency_key: UUID


class CashMovementOut(RecordOut):
    shift_id: UUID
    actor_id: UUID
    amount_minor: int
    reason: str


class PackageCreate(MoneyInput):
    name: str = Field(min_length=1, max_length=200)
    paid_minor: int = Field(gt=0, strict=True)
    bonus_minor: int = Field(0, ge=0, strict=True)


class PackageOut(RecordOut):
    name: str
    paid_minor: int
    bonus_minor: int
    currency: str
    active: bool


class CashTopup(MoneyInput):
    shift_id: UUID
    customer_id: UUID
    amount_minor: int = Field(gt=0, strict=True)
    package_id: UUID | None = None
    idempotency_key: UUID


class ReceiptOut(RecordOut):
    number: str
    shift_id: UUID | None
    customer_id: UUID
    paid_minor: int
    bonus_minor: int
    currency: str
    tender: str
    package_snapshot: dict | None
    transaction_ids: list[str]


class FamilyCreate(Input):
    guardian_id: UUID
    child_id: UUID


class FamilyOut(RecordOut):
    guardian_id: UUID
    child_id: UUID


class LimitUpdate(MoneyInput):
    daily_minor: int = Field(ge=0, strict=True)


class LimitOut(RecordOut):
    customer_id: UUID
    currency: str
    daily_minor: int


class FamilyFunding(MoneyInput):
    amount_minor: int = Field(gt=0, strict=True)
    idempotency_key: UUID


class AlertOut(RecordOut):
    kind: str
    detail: str
    active: bool
    resolved_at: datetime | None


class CustomerWorkspace(BaseModel):
    customer: CustomerOut
    cards: list[CardOut]
    wallets: list[WalletOut]
    transactions: list[TransactionOut]
    plays: list[PlayOut]
    receipts: list[ReceiptOut]
    reserved_minor: dict[str, int]
    spending_limits: list[LimitOut] = []


class CurrencyOverview(BaseModel):
    currency: str
    exponent: int
    paid_balance_minor: int = 0
    bonus_balance_minor: int = 0
    topup_minor: int = 0
    spend_minor: int = 0
    refund_minor: int = 0
    net_spend_minor: int = 0
    adjustment_minor: int = 0
    bonus_grant_minor: int = 0
    paid_spend_minor: int = 0
    bonus_spend_minor: int = 0
    paid_refund_minor: int = 0
    bonus_refund_minor: int = 0


class DailyMetric(BaseModel):
    day: date
    currency: str
    topup_minor: int = 0
    spend_minor: int = 0
    refund_minor: int = 0


class MachineReportOut(BaseModel):
    machine_id: UUID
    machine_name: str
    currency: str
    attempts: int = 0
    activations: int = 0
    failures: int = 0
    unresolved: int = 0
    gross_spend_minor: int = 0
    refund_minor: int = 0
    paid_spend_minor: int = 0
    bonus_spend_minor: int = 0
    net_paid_spend_minor: int = 0
    reader_offline_seconds: int = 0


class OverviewOut(BaseModel):
    generated_at: datetime
    timezone: str
    currencies: list[CurrencyOverview]
    today: list[CurrencyOverview]
    daily: list[DailyMetric]
    reconciliation: dict | None
    reconciliation_state: Literal["healthy", "unhealthy", "stale", "not_checked"]
    financial_writes_paused: bool = False
    device_counts: dict[str, int]
    exceptions: dict[str, int]


class PortalInvite(Input):
    email: str = Field(min_length=3, max_length=320)


class PortalInvitationOut(BaseModel):
    invitation_token: str
    expires_at: datetime


class PortalEnroll(Input):
    invitation_token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class PortalLogin(Input):
    tenant_slug: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class PortalToken(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")


class CheckoutRequest(MoneyInput):
    amount_minor: int = Field(gt=0, strict=True)
    package_id: UUID | None = None
    idempotency_key: UUID


class CheckoutOut(BaseModel):
    session_id: UUID
    status: str
    provider: str
    checkout_url: str | None = None


class RoleOut(BaseModel):
    id: UUID
    name: str
    permissions: list[str]
