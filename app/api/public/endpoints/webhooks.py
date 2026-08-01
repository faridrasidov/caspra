# app/api/public/endpoints/webhooks.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PublicScope
from app.schemas.public import (
    PaginatedPublicWebhookOut,
    PublicWebhookCreate,
    PublicWebhookCreateResult,
    PublicWebhookOut,
    PublicWebhookUpdate,
    WebhookEventTypesOut,
)
from app.schemas.webhook import WebhookCreate, WebhookUpdate
from app.services.webhook import WebhookService

router = APIRouter(
    prefix="/webhooks",
    tags=["public-webhooks"],
    dependencies=[Depends(rate_limit_public)],
)


@router.get("/events", response_model=WebhookEventTypesOut)
async def list_event_types(
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
) -> WebhookEventTypesOut:
    """List the event types a webhook can subscribe to."""
    try:
        _ = ctx
        return WebhookEventTypesOut(event_types=WebhookService.list_event_types())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("", response_model=PaginatedPublicWebhookOut)
async def list_webhooks(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicWebhookOut:
    """List webhook subscriptions for the API key's tenant."""
    try:
        result = await WebhookService().list_webhooks(db, ctx.tenant_id, page, limit)
        return PaginatedPublicWebhookOut(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post("", response_model=PublicWebhookCreateResult, status_code=status.HTTP_201_CREATED)
async def register_webhook(
    payload: PublicWebhookCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
) -> PublicWebhookCreateResult:
    """Register a webhook subscription. The signing secret is returned once."""
    try:
        webhook = await WebhookService().register_webhook(
            db, ctx.tenant_id, WebhookCreate(url=payload.url, events=payload.events)
        )
        return PublicWebhookCreateResult.model_validate(webhook)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get("/{webhook_id}", response_model=PublicWebhookOut)
async def get_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
) -> PublicWebhookOut:
    """Get a single webhook subscription."""
    try:
        return await WebhookService().get_webhook(db, ctx.tenant_id, webhook_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.patch("/{webhook_id}", response_model=PublicWebhookOut)
async def update_webhook(
    webhook_id: UUID,
    payload: PublicWebhookUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
) -> PublicWebhookOut:
    """Update a webhook subscription."""
    try:
        return await WebhookService().update_webhook(
            db, ctx.tenant_id, webhook_id, WebhookUpdate(**payload.model_dump(exclude_unset=True))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.WEBHOOKS_MANAGE))],
) -> None:
    """Delete a webhook subscription."""
    try:
        await WebhookService().delete_webhook(db, ctx.tenant_id, webhook_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
