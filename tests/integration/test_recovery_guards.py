from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ledger.hold import OfflineTransaction
from app.models.ledger.wallet import Wallet
from app.models.tenant.organization import Webhook
from app.models.tenant.webhook_delivery import WebhookDelivery
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService
from app.services.webhook import WebhookService

pytestmark = pytest.mark.asyncio


class TestOfflineRecovery:
    async def test_currency_must_match_the_venue_risk_policy(
        self, client, db_session, seeded_device, device_v2_signer
    ):
        wallet = Wallet(
            tenant_id=UUID(seeded_device["tenant_id"]),
            customer_id=UUID(seeded_device["customer_id"]),
            currency="JPY",
            type="credit",
        )
        db_session.add(wallet)
        await db_session.commit()
        await LedgerService().topup(
            db_session,
            wallet.tenant_id,
            wallet.id,
            WalletTopupRequest(amount_minor=1000, currency="JPY", idempotency_key=uuid4()),
        )
        item = {
            "idempotency_key": str(uuid4()),
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 100,
            "currency": "JPY",
            "occurred_at": datetime.now(UTC).isoformat(),
            "sequence_number": 1,
        }
        path = "/device/api/v1/offline/queue"
        headers, body = device_v2_signer(
            seeded_device["device_id"],
            seeded_device["device_secret"],
            "POST",
            path,
            {"items": [item]},
        )
        response = await client.post(path, headers=headers, content=body)
        assert response.status_code == 201, response.text
        assert response.json()["rejected"] == 1
        await db_session.refresh(wallet)
        assert wallet.balance_minor == 1000

    async def test_old_pending_record_with_posted_ledger_is_completed_without_recharge(
        self, client, db_session, seeded_device, device_v2_signer
    ):
        key = uuid4()
        tenant, device = UUID(seeded_device["tenant_id"]), UUID(seeded_device["device_id"])
        item = {
            "idempotency_key": str(key),
            "type": "debit",
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 500,
            "currency": "USD",
            "occurred_at": datetime.now(UTC).isoformat(),
            "sequence_number": 1,
            "description": None,
        }
        row = OfflineTransaction(
            tenant_id=tenant,
            device_id=device,
            idempotency_key=key,
            occurred_at=datetime.fromisoformat(item["occurred_at"]),
            sequence_number=1,
            card_uid=item["card_uid"],
            amount_minor=500,
            payload=item,
            status="pending",
        )
        db_session.add(row)
        await db_session.commit()
        txn = await LedgerService().charge(
            db_session,
            tenant,
            UUID(seeded_device["wallet_id"]),
            amount_minor=500,
            currency="USD",
            idempotency_key=key,
            device_id=device,
        )
        path = "/device/api/v1/offline/queue"
        headers, body = device_v2_signer(
            str(device), seeded_device["device_secret"], "POST", path, {"items": [item]}
        )
        result = await client.post(path, headers=headers, content=body)
        assert result.status_code == 201, result.text
        assert result.json()["accepted"] == 1
        assert result.json()["results"][0]["transaction_id"] == str(txn.id)
        wallet = await db_session.get(
            Wallet, UUID(seeded_device["wallet_id"]), populate_existing=True
        )
        assert wallet.balance_minor == int(seeded_device["balance_minor"]) - 500
        conflicting = {**item, "idempotency_key": str(uuid4())}
        headers, body = device_v2_signer(
            str(device), seeded_device["device_secret"], "POST", path, {"items": [conflicting]}
        )
        conflict = await client.post(path, headers=headers, content=body)
        assert conflict.status_code == 201, conflict.text
        assert conflict.json()["rejected"] == 1
        await db_session.refresh(row)
        assert row.status == "applied"
        assert row.applied_transaction_id == txn.id


class TestWebhookLease:
    async def test_stale_worker_cannot_overwrite_replacement_lease(
        self, db_session, db_engine, seeded_device, monkeypatch
    ):
        tenant = UUID(seeded_device["tenant_id"])
        hook = Webhook(
            tenant_id=tenant,
            url="https://example.test/hook",
            secret="test-secret",
            events=["transaction.posted"],
            active=True,
        )
        db_session.add(hook)
        await db_session.flush()
        delivery = WebhookDelivery(
            tenant_id=tenant,
            webhook_id=hook.id,
            event_type="transaction.posted",
            payload={"test": True},
            status="pending",
        )
        db_session.add(delivery)
        await db_session.commit()
        delivery_id = delivery.id
        factory = async_sessionmaker(db_engine, expire_on_commit=False)

        class ReplacementDuringRequest:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, *args, **kwargs):
                async with factory() as replacement:
                    row = await replacement.get(WebhookDelivery, delivery_id)
                    row.lease_token = "replacement-lease"
                    row.response_code = 202
                    await replacement.commit()
                return httpx.Response(200, text="old worker response")

        monkeypatch.setattr("app.services.webhook.validate_webhook_destination", AsyncMock())
        monkeypatch.setattr("app.services.webhook.httpx.AsyncClient", ReplacementDuringRequest)
        assert await WebhookService().deliver(db_session, delivery_id) is False
        current = (
            await db_session.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
        ).scalar_one()
        assert current.lease_token == "replacement-lease"
        assert current.status == "processing"
        assert current.response_code == 202
