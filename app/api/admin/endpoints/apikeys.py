# app/api/admin/endpoints/apikeys.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.apikey import (
    ApiKeyCreate,
    ApiKeyCreateResult,
    ApiKeyOut,
    PaginatedApiKeyOut,
)
from app.services.apikey import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["admin-api-keys"])


@router.get("", response_model=PaginatedApiKeyOut)
async def list_api_keys(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedApiKeyOut:
    """List API keys for the caller's tenant."""
    result = await ApiKeyService().list_keys(db, current_admin.tenant_id, page, limit)
    return PaginatedApiKeyOut(**result)


@router.post("", response_model=ApiKeyCreateResult, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ApiKeyCreateResult:
    """Create an API key. The plaintext key is returned only once."""
    api_key, plaintext = await ApiKeyService().create_key(
        db, current_admin.tenant_id, current_admin.id, payload
    )
    return ApiKeyCreateResult(**ApiKeyOut.model_validate(api_key).model_dump(), api_key=plaintext)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ApiKeyOut:
    """Revoke an API key."""
    return await ApiKeyService().revoke_key(db, current_admin.tenant_id, key_id)


@router.post("/{key_id}/regenerate", response_model=ApiKeyCreateResult)
async def regenerate_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> ApiKeyCreateResult:
    """Regenerate an API key, returning a fresh plaintext key once."""
    api_key, plaintext = await ApiKeyService().regenerate_key(db, current_admin.tenant_id, key_id)
    return ApiKeyCreateResult(**ApiKeyOut.model_validate(api_key).model_dump(), api_key=plaintext)
