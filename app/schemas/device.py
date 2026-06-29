# app/schemas/device.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device.device import (
    DeviceEventLevel,
    DeviceStatus,
    DeviceType,
)
from app.schemas import PaginationSchema


class DeviceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    serial: str | None = Field(None, max_length=120)
    type: DeviceType = DeviceType.READER
    location_id: UUID | None = None


class DeviceCreate(DeviceBase):
    model_config = ConfigDict(extra="forbid")


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    serial: str | None = Field(None, max_length=120)
    type: DeviceType | None = None
    location_id: UUID | None = None


class DeviceStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DeviceStatus


class DeviceOut(DeviceBase):
    id: UUID
    tenant_id: UUID
    status: DeviceStatus

    model_config = ConfigDict(from_attributes=True)


class PaginatedDeviceOut(PaginationSchema):
    items: list[DeviceOut]


class DeviceConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict


class DeviceConfigOut(BaseModel):
    id: UUID
    tenant_id: UUID
    device_id: UUID
    config: dict

    model_config = ConfigDict(from_attributes=True)


class DeviceEventOut(BaseModel):
    id: UUID
    tenant_id: UUID
    device_id: UUID
    type: str
    level: DeviceEventLevel
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedDeviceEventOut(PaginationSchema):
    items: list[DeviceEventOut]
