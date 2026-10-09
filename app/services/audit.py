# app/services/audit.py

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit.audit_log import AuditLog
from app.services.base import TenantScopedService
from app.utils.pagination import Page


class AuditService(TenantScopedService[AuditLog]):
    """Read access to the tenant's append-only audit trail."""

    model = AuditLog
    resource_name = "Audit log"

    async def list_logs(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[AuditLog]:
        return await self.paginate(db, tenant_id, page, limit, order_by=AuditLog.created_at.desc())

    async def get_log(self, db: AsyncSession, tenant_id: UUID, log_id: UUID) -> AuditLog:
        return await self.get_owned(db, log_id, tenant_id)

    async def record(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        payload: dict | None = None,
    ) -> AuditLog:
        """Append an audit entry. Caller is responsible for committing."""
        entry = AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry
