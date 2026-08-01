from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models.tenant.organization import Webhook
from app.models.tenant.webhook_delivery import (
    WebhookDelivery,
    WebhookDeliveryStatus,
)
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService
from app.services.webhook import validate_webhook_destination

pytestmark = pytest.mark.asyncio


async def test_ledger_commit_creates_transactional_outbox_row(db_session, seeded_device):
    tenant_id = UUID(seeded_device["tenant_id"])
    webhook = Webhook(
        tenant_id=tenant_id,
        url="https://hooks.example.test/caspra",
        events=["transaction.posted"],
        secret="test-webhook-secret",
        active=True,
    )
    db_session.add(webhook)
    await db_session.commit()

    transaction = await LedgerService().topup(
        db_session,
        tenant_id,
        UUID(seeded_device["wallet_id"]),
        WalletTopupRequest(
            amount_minor=500,
            currency="USD",
            idempotency_key=uuid4(),
        ),
    )

    delivery = (
        (
            await db_session.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.webhook_id == webhook.id,
                    WebhookDelivery.event_type == "transaction.posted",
                )
            )
        )
        .scalars()
        .one()
    )
    assert delivery.status == WebhookDeliveryStatus.PENDING.value
    assert delivery.attempts == 0
    assert delivery.payload["transaction_id"] == str(transaction.id)
    assert delivery.payload["amount_minor"] == 500


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.test/caspra",
        "https://localhost/caspra",
        "https://127.0.0.1/caspra",
        "https://[::1]/caspra",
        "https://user:password@hooks.example.test/caspra",
    ],
)
async def test_webhook_destination_rejects_unsafe_targets(url):
    with pytest.raises(ValueError, match=r"public HTTPS|non-public"):
        await validate_webhook_destination(url)
