# app/schemas/product.py

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import PaginationSchema


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: str = Field(..., min_length=1, max_length=120)
    price_minor: int = Field(..., ge=0, description="Price in integer minor units")
    currency: str = Field(..., min_length=3, max_length=3)
    location_id: UUID | None = None


class ProductCreate(ProductBase):
    model_config = ConfigDict(extra="forbid")


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    sku: str | None = Field(None, min_length=1, max_length=120)
    price_minor: int | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    location_id: UUID | None = None
    active: bool | None = None


class ProductOut(ProductBase):
    id: UUID
    tenant_id: UUID
    active: bool

    model_config = ConfigDict(from_attributes=True)


class PaginatedProductOut(PaginationSchema):
    items: list[ProductOut]
