# app/api/admin/endpoints/products.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    try:
        result = await ProductService().list_products(db, current_admin.tenant_id, page, limit)
        return PaginatedProductOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list products: {e}",
        ) from e


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Create a product."""
    try:
        return await ProductService().create_product(db, current_admin.tenant_id, payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {e}",
        ) from e


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Get a single product."""
    try:
        return await ProductService().get_product(db, current_admin.tenant_id, product_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch product: {e}",
        ) from e


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ProductOut:
    """Update a product."""
    try:
        return await ProductService().update_product(
            db, current_admin.tenant_id, product_id, payload
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update product: {e}",
        ) from e


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a product."""
    try:
        await ProductService().delete_product(db, current_admin.tenant_id, product_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {e}",
        ) from e
