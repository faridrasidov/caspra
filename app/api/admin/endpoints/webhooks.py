# app/api/admin/endpoints/webhooks.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.webhook import (
    PaginatedWebhookOut,
    WebhookCreate,
    WebhookCreateResult,
    WebhookOut,
    WebhookUpdate,
)
from app.services.webhook import WebhookService

router = APIRouter(prefix="/webhooks", tags=["admin-webhooks"])


@router.get("", response_model=PaginatedWebhookOut)
async def list_webhooks(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedWebhookOut:
    """List webhooks for the caller's tenant."""
    try:
        result = await WebhookService().list_webhooks(db, current_admin.tenant_id, page, limit)
        return PaginatedWebhookOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {e}",
        ) from e


@router.post("", response_model=WebhookCreateResult, status_code=status.HTTP_201_CREATED)
async def register_webhook(
    payload: WebhookCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WebhookCreateResult:
    """Register a webhook. The signing secret is returned only on creation."""
    try:
        webhook = await WebhookService().register_webhook(db, current_admin.tenant_id, payload)
        return WebhookCreateResult.model_validate(webhook)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register webhook: {e}",
        ) from e


@router.get("/{webhook_id}", response_model=WebhookOut)
async def get_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WebhookOut:
    """Get a single webhook."""
    try:
        return await WebhookService().get_webhook(db, current_admin.tenant_id, webhook_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch webhook: {e}",
        ) from e


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> WebhookOut:
    """Update a webhook."""
    try:
        return await WebhookService().update_webhook(
            db, current_admin.tenant_id, webhook_id, payload
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update webhook: {e}",
        ) from e


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a webhook."""
    try:
        await WebhookService().delete_webhook(db, current_admin.tenant_id, webhook_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook: {e}",
        ) from e
