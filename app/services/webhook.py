# app/services/webhook.py

import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError, ValidationError
from app.core.metrics import increment_metric, set_metric_gauge
from app.models.tenant.organization import Webhook
from app.models.tenant.webhook_delivery import WebhookDelivery, WebhookDeliveryStatus
from app.schemas.webhook import WebhookCreate, WebhookUpdate
from app.services.base import TenantScopedService
from app.utils.pagination import Page, paginate_async_query

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
MAX_DELIVERY_ATTEMPTS = 8
PROCESSING_LEASE = timedelta(minutes=5)
MAX_RESPONSE_BODY = 2000


class WebhookService(TenantScopedService[Webhook]):
    """Transactional webhook outbox management and signed delivery."""

    model = Webhook
    resource_name = "Webhook"

    @staticmethod
    def list_event_types() -> list[str]:
        return list(SUBSCRIBABLE_EVENT_TYPES)

    async def enqueue(
        self, db: AsyncSession, tenant_id: UUID, event_type: str, payload: dict[str, Any]
    ) -> list[WebhookDelivery]:
        """Add outbox rows without committing, so callers can commit atomically."""
        if event_type not in SUBSCRIBABLE_EVENT_TYPES:
            raise ValidationError(f"Unsupported webhook event: {event_type}")
        stmt = select(Webhook).where(
            Webhook.tenant_id == tenant_id,
            Webhook.active.is_(True),
        )
        deliveries: list[WebhookDelivery] = []
        for webhook in (await db.execute(stmt)).scalars().all():
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
            await db.flush()
        return deliveries

    async def dispatch(
        self, db: AsyncSession, tenant_id: UUID, event_type: str, payload: dict[str, Any]
    ) -> list[WebhookDelivery]:
        """Compatibility helper for non-transactional callers."""
        deliveries = await self.enqueue(db, tenant_id, event_type, payload)
        if deliveries:
            await db.commit()
            for delivery in deliveries:
                await db.refresh(delivery)
        return deliveries

    async def process_due(self, db: AsyncSession, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        stale_before = now - PROCESSING_LEASE
        stmt = (
            select(WebhookDelivery.id)
            .where(
                or_(
                    WebhookDelivery.status == WebhookDeliveryStatus.PENDING.value,
                    (
                        (WebhookDelivery.status == WebhookDeliveryStatus.RETRYING.value)
                        & (WebhookDelivery.next_retry_at <= now)
                    ),
                    (
                        (WebhookDelivery.status == WebhookDeliveryStatus.PROCESSING.value)
                        & (WebhookDelivery.locked_at <= stale_before)
                    ),
                )
            )
            .order_by(WebhookDelivery.created_at.asc())
            .limit(limit)
        )
        delivery_ids = list((await db.execute(stmt)).scalars().all())
        set_metric_gauge("webhook_backlog", len(delivery_ids))
        processed = 0
        for delivery_id in delivery_ids:
            if await self.deliver(db, delivery_id):
                processed += 1
        return processed

    async def deliver(self, db: AsyncSession, delivery_id: UUID) -> bool:
        stmt = (
            select(WebhookDelivery, Webhook)
            .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
            .where(WebhookDelivery.id == delivery_id)
            .with_for_update()
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            return False
        delivery, webhook = row
        if delivery.status in {
            WebhookDeliveryStatus.SUCCESS.value,
            WebhookDeliveryStatus.DEAD.value,
        }:
            return False
        if not webhook.active:
            delivery.status = WebhookDeliveryStatus.DEAD.value
            delivery.error = "Webhook subscription is inactive"
            await db.commit()
            return True

        delivery.status = WebhookDeliveryStatus.PROCESSING.value
        delivery.locked_at = datetime.now(UTC)
        delivery.attempts += 1
        await db.commit()

        try:
            await validate_webhook_destination(webhook.url)
            body = json.dumps(delivery.payload, sort_keys=True, separators=(",", ":")).encode()
            timestamp = str(int(datetime.now(UTC).timestamp()))
            signature = hmac.new(
                webhook.secret.encode(),
                timestamp.encode() + b"." + body,
                hashlib.sha256,
            ).hexdigest()
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    webhook.url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Caspra-Webhooks/1.0",
                        "X-Caspra-Event": delivery.event_type,
                        "X-Caspra-Event-Id": str(delivery.id),
                        "X-Caspra-Timestamp": timestamp,
                        "X-Caspra-Signature": f"v1={signature}",
                    },
                )
            delivery.response_code = response.status_code
            delivery.response_body = response.text[:MAX_RESPONSE_BODY]
            if 200 <= response.status_code < 300:
                delivery.status = WebhookDeliveryStatus.SUCCESS.value
                delivery.delivered_at = datetime.now(UTC)
                delivery.error = None
                delivery.next_retry_at = None
                increment_metric("webhook_delivery_success_total")
            else:
                self._schedule_retry(delivery, f"HTTP {response.status_code}")
        except (httpx.HTTPError, OSError, ValueError) as exc:
            self._schedule_retry(delivery, str(exc))
        delivery.locked_at = None
        await db.commit()
        return True

    def _schedule_retry(self, delivery: WebhookDelivery, error: str) -> None:
        delivery.error = error[:1000]
        increment_metric("webhook_delivery_failure_total")
        if delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
            delivery.status = WebhookDeliveryStatus.DEAD.value
            delivery.next_retry_at = None
            increment_metric("webhook_dead_letter_total")
            return
        delay_seconds = min(3600, 2 ** min(delivery.attempts, 12))
        delivery.status = WebhookDeliveryStatus.RETRYING.value
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)

    async def list_webhooks(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[Webhook]:
        return await self.paginate(db, tenant_id, page, limit, order_by=Webhook.created_at.desc())

    async def list_deliveries(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> Page[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .where(WebhookDelivery.tenant_id == tenant_id)
            .order_by(WebhookDelivery.created_at.desc())
        )
        return await paginate_async_query(
            session=db,
            base_query=stmt,
            page=page,
            limit=limit,
            use_scalars=True,
        )

    async def replay_delivery(
        self, db: AsyncSession, tenant_id: UUID, delivery_id: UUID
    ) -> WebhookDelivery:
        stmt = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.id == delivery_id,
                WebhookDelivery.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        delivery = (await db.execute(stmt)).scalars().first()
        if delivery is None:
            raise NotFoundError("Webhook delivery", str(delivery_id))
        delivery.status = WebhookDeliveryStatus.PENDING.value
        delivery.attempts = 0
        delivery.response_code = None
        delivery.response_body = None
        delivery.error = None
        delivery.next_retry_at = None
        delivery.delivered_at = None
        delivery.locked_at = None
        await db.commit()
        await db.refresh(delivery)
        return delivery

    async def register_webhook(
        self, db: AsyncSession, tenant_id: UUID, payload: WebhookCreate
    ) -> Webhook:
        self._validate_events(payload.events)
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
        values = payload.model_dump(exclude_unset=True)
        if "events" in values and values["events"] is not None:
            self._validate_events(values["events"])
        for key, value in values.items():
            setattr(webhook, key, value)
        await db.commit()
        await db.refresh(webhook)
        return webhook

    async def rotate_secret(self, db: AsyncSession, tenant_id: UUID, webhook_id: UUID) -> Webhook:
        webhook = await self.get_owned(db, webhook_id, tenant_id)
        webhook.previous_secret = webhook.secret
        webhook.secret = secrets.token_urlsafe(32)
        webhook.secret_rotated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(webhook)
        return webhook

    async def delete_webhook(self, db: AsyncSession, tenant_id: UUID, webhook_id: UUID) -> None:
        webhook = await self.get_owned(db, webhook_id, tenant_id)
        await db.delete(webhook)
        await db.commit()

    @staticmethod
    def _validate_events(events: list[str]) -> None:
        unsupported = sorted(set(events) - set(SUBSCRIBABLE_EVENT_TYPES))
        if unsupported:
            raise ValidationError(f"Unsupported webhook events: {', '.join(unsupported)}")


async def validate_webhook_destination(url: str) -> None:
    """Reject non-HTTPS and non-public destinations immediately before delivery."""
    parts = urlsplit(url)
    hostname = (parts.hostname or "").rstrip(".").lower()
    if (
        parts.scheme != "https"
        or not hostname
        or parts.username is not None
        or parts.password is not None
        or hostname == "localhost"
        or hostname.endswith(".local")
    ):
        raise ValueError("Webhook destination must be a public HTTPS URL")

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parts.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("Webhook destination could not be resolved") from exc

    for address in {item[4][0] for item in addresses}:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Webhook destination resolves to a non-public address")
