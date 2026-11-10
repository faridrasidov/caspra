from __future__ import annotations

# app/services/organization.py
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from app.core.domain_errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.device.device import Card, Device
from app.models.identity.user import RefreshToken, Role, User, UserStatus
from app.models.ledger.wallet import Customer, Transaction
from app.models.tenant.organization import Membership, Organization, OrgSettings
from app.schemas.public import OrgStatsOut
from app.utils.pagination import paginate_async_query

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.organization import (
        OrganizationUpdate,
        OrgSettingsUpdate,
    )
    from app.schemas.user import UserCreate, UserUpdate


class OrganizationService:
    """Manage the caller's organization, its settings, and member users."""

    async def protect_last_owner(self, db, user, data):
        await db.execute(
            select(Organization).where(Organization.id == user.tenant_id).with_for_update()
        )
        await db.refresh(user)
        names = {"admin", "owner", "superadmin"}
        current = await db.get(Role, user.role_id) if user.role_id else None
        if current is None or current.name not in names or user.status != "active":
            return
        replacement = (
            await db.get(Role, data["role_id"])
            if data.get("role_id")
            else current
            if "role_id" not in data
            else None
        )
        loses_access = (
            data.get("status", "active") != "active"
            or replacement is None
            or replacement.name not in names
        )
        if loses_access:
            another = (
                await db.execute(
                    select(User.id)
                    .join(Role, Role.id == User.role_id)
                    .where(
                        User.tenant_id == user.tenant_id,
                        User.id != user.id,
                        User.status == "active",
                        Role.name.in_(names),
                    )
                )
            ).first()
            if another is None:
                raise ConflictError("Keep at least one active venue owner")

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

    async def list_users(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        stmt = select(User).where(User.tenant_id == tenant_id).order_by(User.created_at.desc())
        return await paginate_async_query(
            session=db, base_query=stmt, page=page, limit=limit, use_scalars=True
        )

    async def create_user(self, db: AsyncSession, tenant_id: UUID, payload: UserCreate) -> User:
        if payload.role_id is not None:
            role = await db.get(Role, payload.role_id)
            if role is None or not role.is_system:
                raise ConflictError("Assign a built-in staff role")
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
        if "role_id" in data and data["role_id"] is not None:
            role = await db.get(Role, data["role_id"])
            if role is None or not role.is_system:
                raise ConflictError("Assign a built-in staff role")
        await self.protect_last_owner(db, user, data)
        if any(key in data for key in ("role_id", "status", "password")):
            await db.execute(
                update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
            )
        if "role_id" in data:
            await db.execute(
                update(Membership)
                .where(Membership.tenant_id == tenant_id, Membership.user_id == user.id)
                .values(role_id=data["role_id"])
            )
        if "password" in data:
            user.hashed_password = hash_password(data.pop("password"))
        for key, value in data.items():
            setattr(user, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(user)
        return user

    async def delete_user(self, db: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        user = await self.get_user(db, tenant_id, user_id)
        await self.protect_last_owner(db, user, {"status": "inactive"})
        user.status = UserStatus.INACTIVE.value
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
        )
        await db.commit()
