# app/services/product_category.py

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog.product import ProductCategory
from app.services.base import TenantScopedService


class ProductCategoryService(TenantScopedService):
    """Read access to tenant-scoped product categories for the public API."""

    model = ProductCategory
    resource_name = "Product category"

    async def list_categories(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=ProductCategory.name.asc())

    async def get_category(
        self, db: AsyncSession, tenant_id: UUID, category_id: UUID
    ) -> ProductCategory:
        return await self.get_owned(db, category_id, tenant_id)
