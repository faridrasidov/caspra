# app/models/catalog/product.py

import enum
from uuid import UUID as PyUUID

from sqlalchemy import VARCHAR, BigInteger, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.core.mixins import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ProductStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductCategory(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A tenant-scoped grouping for products (e.g. food, drinks, merch)."""

    __tablename__ = "product_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_product_categories_tenant_slug"),
    )

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    slug: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)


class Product(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A point-of-sale product/SKU. Price stored as integer minor units."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),)

    name: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    sku: Mapped[str] = mapped_column(VARCHAR(120), nullable=False, index=True)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(VARCHAR(3), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    location_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", name="fk_products_location_id_locations", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "product_categories.id",
            name="fk_products_category_id_product_categories",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
