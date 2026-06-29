# app/services/location.py

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant.organization import Location
from app.schemas.location import LocationCreate, LocationUpdate
from app.services.base import TenantScopedService


class LocationService(TenantScopedService):
    """Manage tenant-scoped physical locations/venues."""

    model = Location
    resource_name = "Location"

    async def list_locations(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Location.created_at.desc())

    async def create_location(
        self, db: AsyncSession, tenant_id: UUID, payload: LocationCreate
    ) -> Location:
        location = Location(tenant_id=tenant_id, **payload.model_dump())
        db.add(location)
        await db.commit()
        await db.refresh(location)
        return location

    async def get_location(self, db: AsyncSession, tenant_id: UUID, location_id: UUID) -> Location:
        return await self.get_owned(db, location_id, tenant_id)

    async def update_location(
        self, db: AsyncSession, tenant_id: UUID, location_id: UUID, payload: LocationUpdate
    ) -> Location:
        location = await self.get_owned(db, location_id, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(location, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(location)
        return location

    async def delete_location(self, db: AsyncSession, tenant_id: UUID, location_id: UUID) -> None:
        location = await self.get_owned(db, location_id, tenant_id)
        await db.delete(location)
        await db.commit()
