# app/api/admin/endpoints/notifications.py

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.notification import (
    NotificationReadAllResult,
    PaginatedNotificationOut,
)
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])


@router.get("", response_model=PaginatedNotificationOut)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedNotificationOut:
    """List notifications for the caller's tenant."""
    result = await NotificationService().list_notifications(
        db, current_admin.tenant_id, page, limit
    )
    return PaginatedNotificationOut(**result)


@router.post("/read-all", response_model=NotificationReadAllResult)
async def mark_all_read(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> NotificationReadAllResult:
    """Mark all notifications as read for the caller's tenant."""
    count = await NotificationService().mark_all_read(db, current_admin.tenant_id)
    return NotificationReadAllResult(marked_read=count)
