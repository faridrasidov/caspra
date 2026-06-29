# app/services/webhook.py

import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant.organization import Webhook
from app.models.tenant.webhook_delivery import WebhookDelivery, WebhookDeliveryStatus
from app.schemas.webhook import WebhookCreate, WebhookUpdate
from app.services.base import TenantScopedService

# Catalog of event types third-party developers can subscribe to. Keep in sync
# with the events actually dispatched by the platform.
SUBSCRIBABLE_EVENT_TYPES: list[str] = [
    "customer.created",
    "customer.updated",
    "card.linked",
    "card.unlinked",
    "transaction.posted",
    "transaction.refunded",
    "topup.confirmed",
    "device.status_changed",
]


class WebhookService(TenantScopedService):
    """Manage tenant outbound webhook subscriptions."""

    model = Webhook
    resource_name = "Webhook"

    @staticmethod
    def list_event_types() -> list[str]:
        """Return the event types a webhook can subscribe to."""
        return list(SUBSCRIBABLE_EVENT_TYPES)

    async def dispatch(
        self, db: AsyncSession, tenant_id: UUID, event_type: str, payload: dict
    ) -> list[WebhookDelivery]:
        """Record a delivery row for every active webhook subscribed to ``event_type``.

        Records the intent to deliver synchronously; the real outbound HTTP call
        is performed out of band. TODO: enqueue an async worker (e.g. Celery /
        Redis queue) to perform signed POSTs with retry/backoff using
        ``next_retry_at`` and update ``status``/``response_code``.
        """
        stmt = select(Webhook).where(Webhook.tenant_id == tenant_id, Webhook.active.is_(True))
        webhooks = (await db.execute(stmt)).scalars().all()
        deliveries: list[WebhookDelivery] = []
        for webhook in webhooks:
            if event_type not in (webhook.events or []):
                continue
            delivery = WebhookDelivery(
                tenant_id=tenant_id,
                webhook_id=webhook.id,
                event_type=event_type,
                payload=payload,
                status=WebhookDeliveryStatus.PENDING.value,
                attempts=0,
            )
            db.add(delivery)
            deliveries.append(delivery)
        if deliveries:
            await db.commit()
            for delivery in deliveries:
                await db.refresh(delivery)
        return deliveries

    async def list_webhooks(self, db: AsyncSession, tenant_id: UUID, page: int, limit: int) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Webhook.created_at.desc())

    async def register_webhook(
        self, db: AsyncSession, tenant_id: UUID, payload: WebhookCreate
    ) -> Webhook:
        webhook = Webhook(
            tenant_id=tenant_id,
            url=payload.url,
            events=payload.events,
            secret=secrets.token_urlsafe(32),
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        return webhook

    async def get_webhook(self, db: AsyncSession, tenant_id: UUID, webhook_id: UUID) -> Webhook:
        return await self.get_owned(db, webhook_id, tenant_id)

    async def update_webhook(
        self, db: AsyncSession, tenant_id: UUID, webhook_id: UUID, payload: WebhookUpdate
    ) -> Webhook:
        webhook = await self.get_owned(db, webhook_id, tenant_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(webhook, key, value)
        await db.commit()
        await db.refresh(webhook)
        return webhook

    async def delete_webhook(self, db: AsyncSession, tenant_id: UUID, webhook_id: UUID) -> None:
        webhook = await self.get_owned(db, webhook_id, tenant_id)
        await db.delete(webhook)
        await db.commit()
