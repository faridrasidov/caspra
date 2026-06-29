# app/schemas/auth.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)


class MeOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str | None = None
    status: str
    role_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PermissionsOut(BaseModel):
    permissions: list[str]
