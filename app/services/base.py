# app/services/base.py

from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.models.core.mixins import TenantMixin
from app.utils.pagination import Page, paginate_async_query


class TenantScopedService[ModelT: TenantMixin]:
    """Base for services whose model carries a ``tenant_id`` column.

    Provides reusable, tenant-isolated fetch and pagination helpers so every
    query filters by the caller's tenant.
    """

    model: type[ModelT]
    resource_name: str = "Resource"

    async def get_owned(self, db: AsyncSession, obj_id: UUID, tenant_id: UUID) -> ModelT:
        """Fetch a row by id scoped to the tenant or raise ``NotFoundError``."""
        stmt = select(self.model).where(
            # Every tenant-scoped model also uses UUIDPrimaryKeyMixin; the bound can't express both.
            self.model.id == obj_id,  # type: ignore[attr-defined]
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
    ) -> Page[ModelT]:
        """Return a paginated, tenant-scoped list of the service model."""
        stmt = select(self.model).where(self.model.tenant_id == tenant_id, *extra_filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return await paginate_async_query(
            session=db,
            base_query=stmt,
            page=page,
            limit=limit,
            use_scalars=True,
        )
