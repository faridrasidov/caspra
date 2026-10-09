# tests/integration/test_webhook_delivery.py

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.domain_errors import NotFoundError, ValidationError
from app.models.tenant.organization import Webhook
from app.models.tenant.webhook_delivery import WebhookDelivery, WebhookDeliveryStatus
from app.schemas.webhook import WebhookCreate
from app.services import webhook as webhook_module
from app.services.webhook import MAX_DELIVERY_ATTEMPTS, WebhookService

pytestmark = pytest.mark.asyncio

SECRET = "test-webhook-secret"


@pytest.fixture
def receiver(monkeypatch):
    """Route outgoing webhook HTTP calls to an in-memory handler.

    Set ``receiver.status`` to choose the response code; sent requests are
    collected in ``receiver.requests``.
    """

    class Receiver:
        status = 200
        requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        Receiver.requests.append(request)
        return httpx.Response(Receiver.status, text="ok")

    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    async def allow_destination(url: str) -> None:
        return None

    Receiver.requests = []
    monkeypatch.setattr(webhook_module.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(webhook_module, "validate_webhook_destination", allow_destination)
    return Receiver


async def _webhook(db_session, tenant_id: UUID, **overrides) -> Webhook:
    data = {
        "tenant_id": tenant_id,
        "url": "https://hooks.example.test/caspra",
        "events": ["transaction.posted"],
        "secret": SECRET,
        "active": True,
    }
    data.update(overrides)
    webhook = Webhook(**data)
    db_session.add(webhook)
    await db_session.commit()
    return webhook


async def _enqueue(db_session, tenant_id: UUID, payload: dict | None = None) -> WebhookDelivery:
    deliveries = await WebhookService().dispatch(
        db_session, tenant_id, "transaction.posted", payload or {"amount_minor": 500}
    )
    assert len(deliveries) == 1
    return deliveries[0]


async def _reload(db_session, delivery_id: UUID) -> WebhookDelivery:
    db_session.expire_all()
    return await db_session.get(WebhookDelivery, delivery_id)


@pytest.fixture
def tenant_id(seeded_device) -> UUID:
    return UUID(seeded_device["tenant_id"])


class TestDelivery:
    """Signed delivery, retry backoff and dead-lettering."""

    async def test_success_is_signed_over_timestamp_and_body(self, db_session, tenant_id, receiver):
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id, {"b": 2, "a": 1})
        delivery_id = delivery.id

        assert await WebhookService().deliver(db_session, delivery_id) is True

        sent = receiver.requests[0]
        body = sent.content
        assert json.loads(body) == {"a": 1, "b": 2}
        timestamp = sent.headers["X-Caspra-Timestamp"]
        expected = hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
        assert sent.headers["X-Caspra-Signature"] == f"v1={expected.hexdigest()}"
        assert sent.headers["X-Caspra-Event"] == "transaction.posted"
        assert sent.headers["X-Caspra-Event-Id"] == str(delivery_id)

        stored = await _reload(db_session, delivery_id)
        assert stored.status == WebhookDeliveryStatus.SUCCESS.value
        assert stored.attempts == 1
        assert stored.delivered_at is not None

    async def test_delivered_event_is_not_sent_again(self, db_session, tenant_id, receiver):
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        delivery_id = delivery.id
        service = WebhookService()

        await service.deliver(db_session, delivery_id)
        assert await service.deliver(db_session, delivery_id) is False
        assert len(receiver.requests) == 1

    async def test_error_response_schedules_retry(self, db_session, tenant_id, receiver):
        receiver.status = 503
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        delivery_id = delivery.id

        await WebhookService().deliver(db_session, delivery_id)

        stored = await _reload(db_session, delivery_id)
        assert stored.status == WebhookDeliveryStatus.RETRYING.value
        assert stored.error == "HTTP 503"
        assert stored.response_code == 503
        assert stored.next_retry_at > datetime.now(UTC)

    async def test_last_attempt_is_dead_lettered(self, db_session, tenant_id, receiver):
        receiver.status = 500
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        delivery_id = delivery.id
        delivery.attempts = MAX_DELIVERY_ATTEMPTS - 1
        await db_session.commit()

        await WebhookService().deliver(db_session, delivery_id)

        stored = await _reload(db_session, delivery_id)
        assert stored.status == WebhookDeliveryStatus.DEAD.value
        assert stored.next_retry_at is None

    async def test_inactive_webhook_is_dead_lettered_without_sending(
        self, db_session, tenant_id, receiver
    ):
        webhook = await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        delivery_id = delivery.id
        webhook.active = False
        await db_session.commit()

        await WebhookService().deliver(db_session, delivery_id)

        stored = await _reload(db_session, delivery_id)
        assert stored.status == WebhookDeliveryStatus.DEAD.value
        assert receiver.requests == []

    async def test_process_due_skips_retries_not_yet_due(self, db_session, tenant_id, receiver):
        await _webhook(db_session, tenant_id)
        due = await _enqueue(db_session, tenant_id)
        later = await _enqueue(db_session, tenant_id)
        due_id, later_id = due.id, later.id
        later.status = WebhookDeliveryStatus.RETRYING.value
        later.next_retry_at = datetime.now(UTC) + timedelta(hours=1)
        await db_session.commit()

        assert await WebhookService().process_due(db_session) == 1

        assert (await _reload(db_session, due_id)).status == "success"
        assert (await _reload(db_session, later_id)).status == "retrying"

    async def test_replay_resets_dead_delivery(self, db_session, tenant_id, receiver):
        receiver.status = 500
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        delivery_id = delivery.id
        delivery.attempts = MAX_DELIVERY_ATTEMPTS - 1
        await db_session.commit()
        await WebhookService().deliver(db_session, delivery_id)

        replayed = await WebhookService().replay_delivery(db_session, tenant_id, delivery_id)
        assert replayed.status == WebhookDeliveryStatus.PENDING.value
        assert replayed.attempts == 0
        assert replayed.error is None

    async def test_other_tenant_cannot_replay(self, db_session, tenant_id, seeded_device_other):
        await _webhook(db_session, tenant_id)
        delivery = await _enqueue(db_session, tenant_id)
        with pytest.raises(NotFoundError, match="Webhook delivery"):
            await WebhookService().replay_delivery(
                db_session, UUID(seeded_device_other["tenant_id"]), delivery.id
            )


class TestSubscriptions:
    """Event filtering and subscription management."""

    async def test_only_matching_active_subscriptions_receive_events(
        self, db_session, tenant_id, seeded_device_other
    ):
        await _webhook(db_session, tenant_id)
        await _webhook(db_session, tenant_id, events=["customer.created"])
        await _webhook(db_session, tenant_id, active=False)
        await _webhook(db_session, UUID(seeded_device_other["tenant_id"]))

        await _enqueue(db_session, tenant_id)

        rows = (
            (
                await db_session.execute(
                    select(WebhookDelivery).where(WebhookDelivery.tenant_id == tenant_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    async def test_unknown_event_type_is_rejected(self, db_session, tenant_id):
        with pytest.raises(ValidationError, match="Unsupported webhook event"):
            await WebhookService().enqueue(db_session, tenant_id, "made.up", {})
        with pytest.raises(ValidationError, match="Unsupported webhook events"):
            await WebhookService().register_webhook(
                db_session,
                tenant_id,
                WebhookCreate(url="https://hooks.example.test/x", events=["made.up"]),
            )

    async def test_rotate_secret_keeps_previous(self, db_session, tenant_id):
        service = WebhookService()
        webhook = await service.register_webhook(
            db_session,
            tenant_id,
            WebhookCreate(url="https://hooks.example.test/x", events=["transaction.posted"]),
        )
        original = webhook.secret

        rotated = await service.rotate_secret(db_session, tenant_id, webhook.id)
        assert rotated.secret != original
        assert rotated.previous_secret == original
        assert rotated.secret_rotated_at is not None

    async def test_other_tenant_cannot_read_webhook(
        self, db_session, tenant_id, seeded_device_other
    ):
        webhook = await _webhook(db_session, tenant_id)
        with pytest.raises(NotFoundError, match="Webhook"):
            await WebhookService().get_webhook(
                db_session, UUID(seeded_device_other["tenant_id"]), webhook.id
            )

    async def test_unknown_webhook_is_not_found(self, db_session, tenant_id):
        with pytest.raises(NotFoundError, match="Webhook"):
            await WebhookService().delete_webhook(db_session, tenant_id, uuid4())
