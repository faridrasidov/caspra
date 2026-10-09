# app/services/organization.py

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.device.device import Card, Device
from app.models.identity.user import User
from app.models.ledger.wallet import Customer, Transaction
from app.models.tenant.organization import Organization, OrgSettings
from app.schemas.organization import (
    OrganizationUpdate,
    OrgSettingsUpdate,
)
from app.schemas.public import OrgStatsOut
from app.schemas.user import UserCreate, UserUpdate
from app.utils.pagination import Page, paginate_async_query


class OrganizationService:
    """Manage the caller's organization, its settings, and member users."""

    async def get_organization(self, db: AsyncSession, tenant_id: UUID) -> Organization:
        org = await db.get(Organization, tenant_id)
        if org is None:
            raise NotFoundError("Organization", str(tenant_id))
        return org

    async def update_organization(
        self, db: AsyncSession, tenant_id: UUID, payload: OrganizationUpdate
    ) -> Organization:
        org = await self.get_organization(db, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(org, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(org)
        return org

    async def get_stats(self, db: AsyncSession, tenant_id: UUID) -> OrgStatsOut:
        """Return tenant-scoped resource counts for the public API."""

        async def _count(model: type) -> int:
            stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
            return int((await db.execute(stmt)).scalar_one())

        return OrgStatsOut(
            customers=await _count(Customer),
            cards=await _count(Card),
            devices=await _count(Device),
            transactions=await _count(Transaction),
        )

    async def get_settings(self, db: AsyncSession, tenant_id: UUID) -> OrgSettings:
        stmt = select(OrgSettings).where(OrgSettings.tenant_id == tenant_id)
        result = await db.execute(stmt)
        settings_row = result.scalars().first()
        if settings_row is None:
            settings_row = OrgSettings(tenant_id=tenant_id)
            db.add(settings_row)
            await db.commit()
            await db.refresh(settings_row)
        return settings_row

    async def update_settings(
        self, db: AsyncSession, tenant_id: UUID, payload: OrgSettingsUpdate
    ) -> OrgSettings:
        settings_row = await self.get_settings(db, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(settings_row, key, value)
        await db.commit()
        await db.refresh(settings_row)
        return settings_row

    async def list_users(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[User]:
        stmt = select(User).where(User.tenant_id == tenant_id).order_by(User.created_at.desc())
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )

    async def create_user(self, db: AsyncSession, tenant_id: UUID, payload: UserCreate) -> User:
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalars().first() is not None:
            raise ConflictError(f"User with email '{payload.email}' already exists")

        user = User(
            tenant_id=tenant_id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role_id=payload.role_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_user(self, db: AsyncSession, tenant_id: UUID, user_id: UUID) -> User:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if user is None:
            raise NotFoundError("User", str(user_id))
        return user

    async def update_user(
        self, db: AsyncSession, tenant_id: UUID, user_id: UUID, payload: UserUpdate
    ) -> User:
        user = await self.get_user(db, tenant_id, user_id)
        data = payload.model_dump(exclude_unset=True)
        if "password" in data:
            user.hashed_password = hash_password(data.pop("password"))
        for key, value in data.items():
            setattr(user, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(user)
        return user

    async def delete_user(self, db: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        user = await self.get_user(db, tenant_id, user_id)
        await db.delete(user)
        await db.commit()
