# app/services/notification.py

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant.organization import Notification
from app.services.base import TenantScopedService
from app.utils.pagination import Page


class NotificationService(TenantScopedService[Notification]):
    """Manage admin-facing notifications for a tenant."""

    model = Notification
    resource_name = "Notification"

    async def list_notifications(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[Notification]:
        return await self.paginate(
            db, tenant_id, page, limit, order_by=Notification.created_at.desc()
        )

    async def mark_all_read(self, db: AsyncSession, tenant_id: UUID) -> int:
        stmt = (
            update(Notification)
            .where(Notification.tenant_id == tenant_id, Notification.read.is_(False))
            .values(read=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0
