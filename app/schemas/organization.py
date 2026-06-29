# app/schemas/organization.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.tenant.organization import OrgStatus

# ========== Organization Schemas ==========


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    default_currency: str = Field("USD", min_length=3, max_length=3)


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    default_currency: str | None = Field(None, min_length=3, max_length=3)
    status: OrgStatus | None = None


class OrganizationOut(OrganizationBase):
    id: UUID
    slug: str
    status: OrgStatus

    model_config = ConfigDict(from_attributes=True)


# ========== Org Settings Schemas ==========


class OrgSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = Field(None, max_length=64)
    branding: dict | None = None
    config: dict | None = None


class OrgSettingsOut(BaseModel):
    id: UUID
    tenant_id: UUID
    timezone: str
    branding: dict | None = None
    config: dict | None = None

    model_config = ConfigDict(from_attributes=True)
