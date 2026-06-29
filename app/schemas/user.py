# app/schemas/user.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.identity.user import UserStatus
from app.schemas import PaginationSchema


class UserBase(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    full_name: str | None = Field(None, max_length=200)


class UserCreate(UserBase):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(..., min_length=8, max_length=128)
    role_id: UUID | None = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=8, max_length=128)
    status: UserStatus | None = None
    role_id: UUID | None = None


class UserOut(UserBase):
    id: UUID
    tenant_id: UUID
    status: UserStatus
    role_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedUserOut(PaginationSchema):
    items: list[UserOut]
