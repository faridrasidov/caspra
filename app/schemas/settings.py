# app/schemas/settings.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ========== Billing Settings Schemas ==========


class BillingSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str | None = Field(None, max_length=50)
    billing_email: str | None = Field(None, max_length=320)
    currency: str | None = Field(None, min_length=3, max_length=3)
    payment_method: dict | None = None


class BillingSettingsOut(BaseModel):
    id: UUID
    tenant_id: UUID
    plan: str
    billing_email: str | None = None
    currency: str
    payment_method: dict | None = None

    model_config = ConfigDict(from_attributes=True)


# ========== Security Settings Schemas ==========


class SecuritySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfa_required: bool | None = None
    session_timeout_minutes: int | None = Field(None, ge=1, le=10080)
    password_policy: dict | None = None
    ip_allowlist: list[str] | None = None


class SecuritySettingsOut(BaseModel):
    id: UUID
    tenant_id: UUID
    mfa_required: bool
    session_timeout_minutes: int
    password_policy: dict | None = None
    ip_allowlist: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)
