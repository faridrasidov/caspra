from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.webhook import (
    PaginatedWebhookDeliveryOut,
    PaginatedWebhookOut,
    WebhookCreate,
    WebhookCreateResult,
    WebhookDeliveryOut,
    WebhookOut,
    WebhookSecretRotationOut,
    WebhookUpdate,
)
from app.services.webhook import WebhookService

router = APIRouter(prefix="/webhooks", tags=["admin-webhooks"])


@router.get("", response_model=PaginatedWebhookOut)
async def list_webhooks(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedWebhookOut:
    result = await WebhookService().list_webhooks(db, current_admin.tenant_id, page, limit)
    return PaginatedWebhookOut(**result)


@router.post("", response_model=WebhookCreateResult, status_code=status.HTTP_201_CREATED)
async def register_webhook(
    payload: WebhookCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> WebhookCreateResult:
    webhook = await WebhookService().register_webhook(db, current_admin.tenant_id, payload)
    return WebhookCreateResult.model_validate(webhook)


@router.get("/deliveries", response_model=PaginatedWebhookDeliveryOut)
async def list_webhook_deliveries(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedWebhookDeliveryOut:
    result = await WebhookService().list_deliveries(db, current_admin.tenant_id, page, limit)
    return PaginatedWebhookDeliveryOut(**result)


@router.post("/deliveries/{delivery_id}/replay", response_model=WebhookDeliveryOut)
async def replay_webhook_delivery(
    delivery_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> WebhookDeliveryOut:
    delivery = await WebhookService().replay_delivery(db, current_admin.tenant_id, delivery_id)
    return WebhookDeliveryOut.model_validate(delivery)


@router.get("/{webhook_id}", response_model=WebhookOut)
async def get_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> WebhookOut:
    return await WebhookService().get_webhook(db, current_admin.tenant_id, webhook_id)


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> WebhookOut:
    return await WebhookService().update_webhook(db, current_admin.tenant_id, webhook_id, payload)


@router.post("/{webhook_id}/rotate-secret", response_model=WebhookSecretRotationOut)
async def rotate_webhook_secret(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> WebhookSecretRotationOut:
    webhook = await WebhookService().rotate_secret(db, current_admin.tenant_id, webhook_id)
    return WebhookSecretRotationOut(
        webhook_id=webhook.id,
        secret=webhook.secret,
        rotated_at=webhook.secret_rotated_at,
    )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.INTEGRATIONS_MANAGE))
    ],
) -> None:
    await WebhookService().delete_webhook(db, current_admin.tenant_id, webhook_id)
