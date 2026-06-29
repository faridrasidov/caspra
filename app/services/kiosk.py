# app/services/kiosk.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device.device import Kiosk, KioskLog
from app.schemas.kiosk import KioskCreate, KioskUpdate
from app.services.base import TenantScopedService
from app.utils.pagination import paginate_async_query


class KioskService(TenantScopedService):
    """Manage self-service kiosks and their logs."""

    model = Kiosk
    resource_name = "Kiosk"

    async def list_kiosks(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Kiosk.created_at.desc())

    async def create_kiosk(self, db: AsyncSession, tenant_id: UUID, payload: KioskCreate) -> Kiosk:
        kiosk = Kiosk(
            tenant_id=tenant_id,
            name=payload.name,
            location_id=payload.location_id,
        )
        db.add(kiosk)
        await db.commit()
        await db.refresh(kiosk)
        return kiosk

    async def get_kiosk(self, db: AsyncSession, tenant_id: UUID, kiosk_id: UUID) -> Kiosk:
        return await self.get_owned(db, kiosk_id, tenant_id)

    async def update_kiosk(
        self, db: AsyncSession, tenant_id: UUID, kiosk_id: UUID, payload: KioskUpdate
    ) -> Kiosk:
        kiosk = await self.get_owned(db, kiosk_id, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(kiosk, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(kiosk)
        return kiosk

    async def list_logs(
        self, db: AsyncSession, tenant_id: UUID, kiosk_id: UUID, page: int, limit: int
    ) -> dict:
        await self.get_owned(db, kiosk_id, tenant_id)
        stmt = (
            select(KioskLog)
            .where(KioskLog.tenant_id == tenant_id, KioskLog.kiosk_id == kiosk_id)
            .order_by(KioskLog.created_at.desc())
        )
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )
