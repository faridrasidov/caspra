# app/schemas/webhook.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tenant.webhook_delivery import WebhookDeliveryStatus
from app.schemas import PaginationSchema


class WebhookBase(BaseModel):
    url: str = Field(..., min_length=1, max_length=1000)
    events: list[str] = Field(default_factory=list)

    @field_validator("url")
    @classmethod
    def require_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("Webhook destinations must use HTTPS")
        return value


class WebhookCreate(WebhookBase):
    model_config = ConfigDict(extra="forbid")


class WebhookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(None, min_length=1, max_length=1000)
    events: list[str] | None = None
    active: bool | None = None

    @field_validator("url")
    @classmethod
    def require_https(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("Webhook destinations must use HTTPS")
        return value


class WebhookOut(WebhookBase):
    id: UUID
    tenant_id: UUID
    active: bool

    model_config = ConfigDict(from_attributes=True)


class WebhookCreateResult(WebhookOut):
    secret: str


class PaginatedWebhookOut(PaginationSchema):
    items: list[WebhookOut]


class WebhookSecretRotationOut(BaseModel):
    webhook_id: UUID
    secret: str
    rotated_at: datetime


class WebhookDeliveryOut(BaseModel):
    id: UUID
    webhook_id: UUID
    event_type: str
    payload: dict
    status: WebhookDeliveryStatus
    attempts: int
    response_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    next_retry_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedWebhookDeliveryOut(PaginationSchema):
    items: list[WebhookDeliveryOut]
