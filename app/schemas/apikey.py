# app/schemas/apikey.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import PaginationSchema


class ApiKeyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)


class ApiKeyCreate(ApiKeyBase):
    model_config = ConfigDict(extra="forbid")


class ApiKeyOut(ApiKeyBase):
    id: UUID
    tenant_id: UUID
    prefix: str
    last_used_at: datetime | None = None
    revoked: bool

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreateResult(ApiKeyOut):
    api_key: str = Field(..., description="Plaintext key, shown only once")


class PaginatedApiKeyOut(PaginationSchema):
    items: list[ApiKeyOut]
