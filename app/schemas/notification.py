# app/schemas/notification.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tenant.organization import NotificationLevel
from app.schemas import PaginationSchema


class NotificationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    message: str
    level: NotificationLevel
    read: bool
    user_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotificationOut(PaginationSchema):
    items: list[NotificationOut]


class NotificationReadAllResult(BaseModel):
    marked_read: int
