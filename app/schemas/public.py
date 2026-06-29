# app/schemas/public.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import CardStatus, CardType, DeviceStatus, DeviceType
from app.models.ledger.external_topup import ExternalTopupStatus
from app.models.ledger.wallet import CustomerStatus, TransactionStatus, TransactionType
from app.schemas import PaginationSchema

# ========== Auth Schemas ==========


class ApiKeyTestOut(BaseModel):
    """Result of validating the presented API key."""

    valid: bool
    tenant_id: UUID
    api_key_id: UUID


class ApiKeyScopesOut(BaseModel):
    """The scopes granted to the presented API key."""

    scopes: list[str]


# ========== Customer Schemas (PII redacted unless elevated scope) ==========


class PublicCustomerOut(BaseModel):
    id: UUID
    external_id: str | None = None
    full_name: str | None = None
    email: str | None = Field(None, description="Redacted unless key holds customers:write")
    phone: str | None = Field(None, description="Redacted unless key holds customers:write")
    status: CustomerStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedPublicCustomerOut(PaginationSchema):
    items: list[PublicCustomerOut]


class PublicCustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(None, max_length=120)
    full_name: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=40)


class PublicWalletBalanceOut(BaseModel):
    wallet_id: UUID
    currency: str
    balance_minor: int
    type: str

    model_config = ConfigDict(from_attributes=True)


class PublicBalancesOut(BaseModel):
    balances: list[PublicWalletBalanceOut]


# ========== Card Schemas ==========


class PublicCardOut(BaseModel):
    id: UUID
    uid: str
    type: CardType
    status: CardStatus
    customer_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPublicCardOut(PaginationSchema):
    items: list[PublicCardOut]


class PublicCardLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID


# ========== Device Schemas (read-only) ==========


class PublicDeviceOut(BaseModel):
    id: UUID
    name: str
    type: DeviceType
    status: DeviceStatus
    location_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPublicDeviceOut(PaginationSchema):
    items: list[PublicDeviceOut]


class PublicDeviceStatusOut(BaseModel):
    id: UUID
    status: DeviceStatus

    model_config = ConfigDict(from_attributes=True)


# ========== Product Schemas ==========


class PublicProductOut(BaseModel):
    id: UUID
    name: str
    sku: str
    price_minor: int
    currency: str
    active: bool
    category_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPublicProductOut(PaginationSchema):
    items: list[PublicProductOut]


class ProductCategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedProductCategoryOut(PaginationSchema):
    items: list[ProductCategoryOut]


# ========== Transaction Schemas ==========


class PublicTransactionOut(BaseModel):
    id: UUID
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


class PaginatedPublicTransactionOut(PaginationSchema):
    items: list[PublicTransactionOut]


class PublicTopupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_id: UUID
    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    description: str | None = Field(None, max_length=500)


class PublicRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    amount_minor: int | None = Field(
        None, gt=0, description="Partial refund amount; defaults to full amount"
    )
    reason: str | None = Field(None, max_length=500)


class PublicRefundOut(BaseModel):
    id: UUID
    original_transaction_id: UUID
    refund_transaction_id: UUID | None = None
    amount_minor: int
    currency: str
    reason: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


# ========== External Top-up Session Schemas ==========


class ExternalTopupStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_id: UUID
    amount_minor: int = Field(..., gt=0, description="Amount in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    idempotency_key: UUID
    customer_id: UUID | None = None
    card_id: UUID | None = None
    external_payment_ref: str | None = Field(None, max_length=200)


class ExternalTopupConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_payment_ref: str | None = Field(
        None, max_length=200, description="Reference returned by the payment gateway"
    )


class ExternalTopupSessionOut(BaseModel):
    id: UUID
    wallet_id: UUID | None = None
    customer_id: UUID | None = None
    card_id: UUID | None = None
    amount_minor: int
    currency: str
    status: ExternalTopupStatus
    external_payment_ref: str | None = None
    transaction_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


# ========== Webhook Schemas ==========


class PublicWebhookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, max_length=1000)
    events: list[str] = Field(default_factory=list)


class PublicWebhookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(None, min_length=1, max_length=1000)
    events: list[str] | None = None
    active: bool | None = None


class PublicWebhookOut(BaseModel):
    id: UUID
    url: str
    events: list[str]
    active: bool

    model_config = ConfigDict(from_attributes=True)


class PublicWebhookCreateResult(PublicWebhookOut):
    secret: str


class PaginatedPublicWebhookOut(PaginationSchema):
    items: list[PublicWebhookOut]


class WebhookEventTypesOut(BaseModel):
    event_types: list[str]


# ========== Org Schemas ==========


class PublicOrgOut(BaseModel):
    id: UUID
    name: str
    slug: str
    default_currency: str

    model_config = ConfigDict(from_attributes=True)


class OrgStatsOut(BaseModel):
    customers: int
    cards: int
    devices: int
    transactions: int


# ========== Report Schemas ==========


class SalesReportRow(BaseModel):
    day: str
    transaction_count: int
    total_credit_minor: int
    total_debit_minor: int


class SalesReportOut(BaseModel):
    currency: str | None = None
    rows: list[SalesReportRow]


class TopCustomerRow(BaseModel):
    customer_ref: str = Field(..., description="Anonymized customer reference")
    transaction_count: int
    total_spent_minor: int


class TopCustomersOut(BaseModel):
    rows: list[TopCustomerRow]


class TopProductRow(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    revenue_minor: int


class TopProductsReportOut(BaseModel):
    rows: list[TopProductRow]


class DeviceUsageRow(BaseModel):
    device_id: str
    device_name: str
    transaction_count: int
    total_amount_minor: int


class DeviceUsageOut(BaseModel):
    rows: list[DeviceUsageRow]


class BalancesReportRow(BaseModel):
    currency: str
    total_balance_minor: int
    wallet_count: int


class BalancesReportOut(BaseModel):
    rows: list[BalancesReportRow]


# ========== Metadata Schemas ==========


class VersionOut(BaseModel):
    name: str
    version: str
    surface: str = "public"
