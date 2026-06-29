# app/api/public/endpoints/products.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    PaginatedProductCategoryOut,
    PaginatedPublicProductOut,
    PublicProductOut,
)
from app.services.product import ProductService
from app.services.product_category import ProductCategoryService

router = APIRouter(
    prefix="/products",
    tags=["public-products"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("", response_model=PaginatedPublicProductOut)
async def list_products(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.PRODUCTS_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicProductOut:
    """List products for the API key's tenant."""
    try:
        result = await ProductService().list_products(db, ctx.tenant_id, page, limit)
        return PaginatedPublicProductOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list products: {e}",
        ) from e


@router.get("/categories", response_model=PaginatedProductCategoryOut)
async def list_categories(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.PRODUCTS_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedProductCategoryOut:
    """List product categories for the API key's tenant."""
    try:
        result = await ProductCategoryService().list_categories(db, ctx.tenant_id, page, limit)
        return PaginatedProductCategoryOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list categories: {e}",
        ) from e


@router.get("/{product_id}", response_model=PublicProductOut)
async def get_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.PRODUCTS_READ))],
) -> PublicProductOut:
    """Get a single product."""
    try:
        return await ProductService().get_product(db, ctx.tenant_id, product_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch product: {e}",
        ) from e
