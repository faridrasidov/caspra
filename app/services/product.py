# app/services/product.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError
from app.models.catalog.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.base import TenantScopedService
from app.utils.pagination import Page


class ProductService(TenantScopedService[Product]):
    """Manage tenant-scoped point-of-sale products."""

    model = Product
    resource_name = "Product"

    async def list_products(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[Product]:
        return await self.paginate(db, tenant_id, page, limit, order_by=Product.created_at.desc())

    async def create_product(
        self, db: AsyncSession, tenant_id: UUID, payload: ProductCreate
    ) -> Product:
        await self._assert_sku_free(db, tenant_id, payload.sku)
        product = Product(tenant_id=tenant_id, **payload.model_dump())
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product

    async def get_product(self, db: AsyncSession, tenant_id: UUID, product_id: UUID) -> Product:
        return await self.get_owned(db, product_id, tenant_id)

    async def update_product(
        self, db: AsyncSession, tenant_id: UUID, product_id: UUID, payload: ProductUpdate
    ) -> Product:
        product = await self.get_owned(db, product_id, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        if "sku" in data and data["sku"] != product.sku:
            await self._assert_sku_free(db, tenant_id, data["sku"])
        for key, value in data.items():
            setattr(product, key, value)
        await db.commit()
        await db.refresh(product)
        return product

    async def delete_product(self, db: AsyncSession, tenant_id: UUID, product_id: UUID) -> None:
        product = await self.get_owned(db, product_id, tenant_id)
        await db.delete(product)
        await db.commit()

    async def _assert_sku_free(self, db: AsyncSession, tenant_id: UUID, sku: str) -> None:
        stmt = select(Product.id).where(Product.tenant_id == tenant_id, Product.sku == sku)
        if (await db.execute(stmt)).first() is not None:
            raise ConflictError(f"Product with sku '{sku}' already exists")
