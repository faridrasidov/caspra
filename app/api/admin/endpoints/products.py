# app/api/admin/endpoints/products.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.product import (
    PaginatedProductOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.services.product import ProductService

router = APIRouter(prefix="/products", tags=["admin-products"])


@router.get("", response_model=PaginatedProductOut)
async def list_products(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedProductOut:
    """List products for the caller's tenant."""
    result = await ProductService().list_products(db, current_admin.tenant_id, page, limit)
    return PaginatedProductOut(**result)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Create a product."""
    return await ProductService().create_product(db, current_admin.tenant_id, payload)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Get a single product."""
    return await ProductService().get_product(db, current_admin.tenant_id, product_id)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Update a product."""
    return await ProductService().update_product(db, current_admin.tenant_id, product_id, payload)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a product."""
    await ProductService().delete_product(db, current_admin.tenant_id, product_id)
