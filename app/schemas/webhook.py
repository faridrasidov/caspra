# app/schemas/webhook.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import PaginationSchema


class WebhookBase(BaseModel):
    url: str = Field(..., min_length=1, max_length=1000)
    events: list[str] = Field(default_factory=list)


class WebhookCreate(WebhookBase):
    model_config = ConfigDict(extra="forbid")


class WebhookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(None, min_length=1, max_length=1000)
    events: list[str] | None = None
    active: bool | None = None


class WebhookOut(WebhookBase):
    id: UUID
    tenant_id: UUID
    active: bool

    model_config = ConfigDict(from_attributes=True)


class WebhookCreateResult(WebhookOut):
    secret: str


class PaginatedWebhookOut(PaginationSchema):
    items: list[WebhookOut]
