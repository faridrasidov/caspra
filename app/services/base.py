from __future__ import annotations

# app/services/base.py
from contextlib import suppress
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ColumnElement, String, or_, select

from app.core.domain_errors import NotFoundError
from app.utils.pagination import paginate_async_query

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TenantScopedService:
    """Base for services whose model carries a ``tenant_id`` column.

    Provides reusable, tenant-isolated fetch and pagination helpers so every
    query filters by the caller's tenant.
    """

    model: type[Any]
    resource_name: str = "Resource"

    async def get_owned(self, db: AsyncSession, obj_id: UUID, tenant_id: UUID) -> Any:
        """Fetch a row by id scoped to the tenant or raise ``NotFoundError``."""
        stmt = select(self.model).where(
            self.model.id == obj_id,
            self.model.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        obj = result.scalars().first()
        if obj is None:
            raise NotFoundError(self.resource_name, str(obj_id))
        return obj

    async def paginate(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        page: int,
        limit: int,
        *extra_filters: ColumnElement[bool],
        order_by: Any | None = None,
        q: str | None = None,
    ) -> dict:
        """Return a paginated, tenant-scoped list of the service model."""
        stmt = select(self.model).where(self.model.tenant_id == tenant_id, *extra_filters)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            names = {
                "name",
                "full_name",
                "email",
                "phone",
                "uid",
                "serial",
                "sku",
                "description",
                "action",
                "status",
                "external_id",
            }
            conditions = [
                column.ilike(f"%{escaped}%", escape="\\")
                for column in self.model.__table__.columns
                if column.name in names and isinstance(column.type, String)
            ]
            with suppress(ValueError):
                conditions.append(self.model.id == UUID(q))
            if conditions:
                stmt = stmt.where(or_(*conditions))
        if order_by is not None:
            stmt = stmt.order_by(order_by, self.model.id.desc())
        return await paginate_async_query(
            session=db,
            base_query=stmt,
            page=page,
            limit=limit,
            use_scalars=True,
        )
