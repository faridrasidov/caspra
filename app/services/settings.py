# app/services/settings.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant.organization import BillingSettings, SecuritySettings
from app.schemas.settings import BillingSettingsUpdate, SecuritySettingsUpdate


class SettingsService:
    """Manage per-tenant billing and security settings (get-or-create)."""

    async def get_billing(self, db: AsyncSession, tenant_id: UUID) -> BillingSettings:
        stmt = select(BillingSettings).where(BillingSettings.tenant_id == tenant_id)
        row = (await db.execute(stmt)).scalars().first()
        if row is None:
            row = BillingSettings(tenant_id=tenant_id)
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return row

    async def update_billing(
        self, db: AsyncSession, tenant_id: UUID, payload: BillingSettingsUpdate
    ) -> BillingSettings:
        row = await self.get_billing(db, tenant_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await db.commit()
        await db.refresh(row)
        return row

    async def get_security(self, db: AsyncSession, tenant_id: UUID) -> SecuritySettings:
        stmt = select(SecuritySettings).where(SecuritySettings.tenant_id == tenant_id)
        row = (await db.execute(stmt)).scalars().first()
        if row is None:
            row = SecuritySettings(tenant_id=tenant_id)
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return row

    async def update_security(
        self, db: AsyncSession, tenant_id: UUID, payload: SecuritySettingsUpdate
    ) -> SecuritySettings:
        row = await self.get_security(db, tenant_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await db.commit()
        await db.refresh(row)
        return row
