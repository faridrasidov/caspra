# app/schemas/organization.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tenant.organization import OrgStatus
from app.utils.validation import iso_currency, timezone_name

# ========== Organization Schemas ==========


class OrganizationBase(BaseModel):
    _currency = field_validator("default_currency")(iso_currency)
    name: str = Field(..., min_length=1, max_length=200)
    default_currency: str = Field("USD", min_length=3, max_length=3)


class OrganizationUpdate(BaseModel):
    _currency = field_validator("default_currency")(iso_currency)
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
    _timezone = field_validator("timezone")(timezone_name)
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
