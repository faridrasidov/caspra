# app/schemas/kiosk.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import DeviceEventLevel, KioskStatus
from app.schemas import PaginationSchema


class KioskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    location_id: UUID | None = None


class KioskCreate(KioskBase):
    model_config = ConfigDict(extra="forbid")


class KioskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    location_id: UUID | None = None
    status: KioskStatus | None = None


class KioskOut(KioskBase):
    id: UUID
    tenant_id: UUID
    status: KioskStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedKioskOut(PaginationSchema):
    items: list[KioskOut]


class KioskLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    kiosk_id: UUID
    level: DeviceEventLevel
    message: str
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedKioskLogOut(PaginationSchema):
    items: list[KioskLogOut]
