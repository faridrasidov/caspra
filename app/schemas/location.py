# app/schemas/location.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.tenant.organization import LocationStatus
from app.schemas import PaginationSchema


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address: str | None = Field(None, max_length=500)
    timezone: str = Field("UTC", max_length=64)


class LocationCreate(LocationBase):
    model_config = ConfigDict(extra="forbid")


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, max_length=500)
    timezone: str | None = Field(None, max_length=64)
    status: LocationStatus | None = None


class LocationOut(LocationBase):
    id: UUID
    tenant_id: UUID
    status: LocationStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedLocationOut(PaginationSchema):
    items: list[LocationOut]
