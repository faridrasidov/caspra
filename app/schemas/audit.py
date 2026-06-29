# app/schemas/audit.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas import PaginationSchema


class AuditLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAuditLogOut(PaginationSchema):
    items: list[AuditLogOut]
