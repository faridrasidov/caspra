# app/services/device.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device.device import (
    Device,
    DeviceConfig,
    DeviceEvent,
    DeviceStatus,
)
from app.schemas.device import (
    DeviceConfigUpdate,
    DeviceCreate,
    DeviceStatusUpdate,
    DeviceUpdate,
)
from app.services.base import TenantScopedService
from app.utils.pagination import paginate_async_query


class DeviceService(TenantScopedService):
    """Manage reader/POS devices, their config, and event stream."""

    model = Device
    resource_name = "Device"

    async def list_devices(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Device.created_at.desc())

    async def register_device(
        self, db: AsyncSession, tenant_id: UUID, payload: DeviceCreate
    ) -> Device:
        device = Device(
            tenant_id=tenant_id,
            name=payload.name,
            serial=payload.serial,
            type=payload.type.value,
            location_id=payload.location_id,
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device

    async def get_device(self, db: AsyncSession, tenant_id: UUID, device_id: UUID) -> Device:
        return await self.get_owned(db, device_id, tenant_id)

    async def update_device(
        self, db: AsyncSession, tenant_id: UUID, device_id: UUID, payload: DeviceUpdate
    ) -> Device:
        device = await self.get_owned(db, device_id, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(device, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(device)
        return device

    async def delete_device(self, db: AsyncSession, tenant_id: UUID, device_id: UUID) -> None:
        device = await self.get_owned(db, device_id, tenant_id)
        await db.delete(device)
        await db.commit()

    async def set_status(
        self, db: AsyncSession, tenant_id: UUID, device_id: UUID, payload: DeviceStatusUpdate
    ) -> Device:
        device = await self.get_owned(db, device_id, tenant_id)
        device.status = payload.status.value
        await db.commit()
        await db.refresh(device)
        return device

    async def reset(self, db: AsyncSession, tenant_id: UUID, device_id: UUID) -> Device:
        """Reset a device back to active state."""
        device = await self.get_owned(db, device_id, tenant_id)
        device.status = DeviceStatus.ACTIVE.value
        await db.commit()
        await db.refresh(device)
        return device

    async def get_config(self, db: AsyncSession, tenant_id: UUID, device_id: UUID) -> DeviceConfig:
        await self.get_owned(db, device_id, tenant_id)
        stmt = select(DeviceConfig).where(
            DeviceConfig.device_id == device_id, DeviceConfig.tenant_id == tenant_id
        )
        config = (await db.execute(stmt)).scalars().first()
        if config is None:
            config = DeviceConfig(tenant_id=tenant_id, device_id=device_id, config={})
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return config

    async def update_config(
        self, db: AsyncSession, tenant_id: UUID, device_id: UUID, payload: DeviceConfigUpdate
    ) -> DeviceConfig:
        config = await self.get_config(db, tenant_id, device_id)
        config.config = payload.config
        await db.commit()
        await db.refresh(config)
        return config

    async def list_events(
        self, db: AsyncSession, tenant_id: UUID, device_id: UUID, page: int, limit: int
    ) -> dict:
        await self.get_owned(db, device_id, tenant_id)
        stmt = (
            select(DeviceEvent)
            .where(DeviceEvent.tenant_id == tenant_id, DeviceEvent.device_id == device_id)
            .order_by(DeviceEvent.created_at.desc())
        )
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )
