# tests/device/test_device_api.py

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.ledger.wallet import LedgerEntry, Transaction

pytestmark = pytest.mark.asyncio

BASE = "/device/api/v1"


class TestDeviceAuthRBAC:
    """HMAC gating for the device surface."""

    async def test_missing_signature_returns_401(self, client, seeded_device):
        resp = await client.post(
            f"{BASE}/card/verify", json={"card_uid": seeded_device["card_uid"]}
        )
        assert resp.status_code == 401

    async def test_bad_signature_returns_401(self, client, seeded_device):
        headers = {
            "X-Device-Id": seeded_device["device_id"],
            "X-Device-Timestamp": "0",
            "X-Device-Signature": "deadbeef",
            "Content-Type": "application/json",
        }
        resp = await client.post(
            f"{BASE}/card/verify", headers=headers, content=b'{"card_uid":"x"}'
        )
        assert resp.status_code == 401

    async def test_unknown_device_returns_401(self, client, seeded_device, device_signer):
        headers, body = device_signer(str(uuid4()), {"card_uid": "x"})
        resp = await client.post(f"{BASE}/card/verify", headers=headers, content=body)
        assert resp.status_code == 401

    async def test_handshake_is_open(self, client, seeded_device):
        resp = await client.post(
            f"{BASE}/auth/handshake", json={"device_id": seeded_device["device_id"]}
        )
        assert resp.status_code == 200
        assert resp.json()["registered"] is True

    async def test_ping_is_open(self, client):
        resp = await client.get(f"{BASE}/ping")
        assert resp.status_code == 200
        assert resp.json()["pong"] is True


class TestDeviceCard:
    """Card verification and lookups."""

    async def test_verify_happy_path(self, client, seeded_device, device_signer):
        headers, body = device_signer(
            seeded_device["device_id"], {"card_uid": seeded_device["card_uid"]}
        )
        resp = await client.post(f"{BASE}/card/verify", headers=headers, content=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["blocked"] is False

    async def test_balance_lists_wallets(self, client, seeded_device, device_signer):
        headers, body = device_signer(
            seeded_device["device_id"], {"card_uid": seeded_device["card_uid"]}
        )
        resp = await client.post(f"{BASE}/card/balance", headers=headers, content=body)
        assert resp.status_code == 200
        balances = resp.json()["balances"]
        assert len(balances) == 1
        assert balances[0]["balance_minor"] == int(seeded_device["balance_minor"])


class TestDevicePaymentCharge:
    """Core money movement via the ledger."""

    async def test_charge_debits_and_writes_ledger_entry(
        self, client, db_session, seeded_device, device_signer
    ):
        payload = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 2000,
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], payload)
        resp = await client.post(f"{BASE}/payment/charge", headers=headers, content=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["balance_minor"] == int(seeded_device["balance_minor"]) - 2000

        wallet_id = UUID(seeded_device["wallet_id"])
        entry_count = (
            await db_session.execute(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.wallet_id == wallet_id)
            )
        ).scalar_one()
        assert entry_count == 1

    async def test_charge_idempotency_replay_does_not_double_post(
        self, client, db_session, seeded_device, device_signer
    ):
        payload = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 1500,
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], payload)
        first = await client.post(f"{BASE}/payment/charge", headers=headers, content=body)
        second = await client.post(f"{BASE}/payment/charge", headers=headers, content=body)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["transaction_id"] == second.json()["transaction_id"]

        txn_count = (
            await db_session.execute(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.wallet_id == UUID(seeded_device["wallet_id"]))
            )
        ).scalar_one()
        assert txn_count == 1

    async def test_charge_insufficient_funds(self, client, seeded_device, device_signer):
        payload = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 999_999,
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], payload)
        resp = await client.post(f"{BASE}/payment/charge", headers=headers, content=body)
        assert resp.status_code == 402


class TestDevicePreauth:
    """Pre-authorization, capture, and void flows."""

    async def test_preauth_then_capture(self, client, seeded_device, device_signer):
        pre = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 3000,
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], pre)
        pre_resp = await client.post(f"{BASE}/payment/preauth", headers=headers, content=body)
        assert pre_resp.status_code == 201
        hold_id = pre_resp.json()["hold_id"]
        assert pre_resp.json()["status"] == "preauth"

        cap = {"hold_id": hold_id, "idempotency_key": str(uuid4())}
        headers, body = device_signer(seeded_device["device_id"], cap)
        cap_resp = await client.post(f"{BASE}/payment/capture", headers=headers, content=body)
        assert cap_resp.status_code == 201
        assert cap_resp.json()["balance_minor"] == int(seeded_device["balance_minor"]) - 3000

    async def test_preauth_then_void_releases_funds(self, client, seeded_device, device_signer):
        pre = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": 1000,
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], pre)
        pre_resp = await client.post(f"{BASE}/payment/preauth", headers=headers, content=body)
        hold_id = pre_resp.json()["hold_id"]

        void = {"hold_id": hold_id}
        headers, body = device_signer(seeded_device["device_id"], void)
        void_resp = await client.post(f"{BASE}/payment/void", headers=headers, content=body)
        assert void_resp.status_code == 200
        assert void_resp.json()["status"] == "voided"

        # Funds released: a full-balance charge still succeeds.
        charge = {
            "card_uid": seeded_device["card_uid"],
            "amount_minor": int(seeded_device["balance_minor"]),
            "currency": "USD",
            "idempotency_key": str(uuid4()),
        }
        headers, body = device_signer(seeded_device["device_id"], charge)
        charge_resp = await client.post(f"{BASE}/payment/charge", headers=headers, content=body)
        assert charge_resp.status_code == 201


class TestDeviceOffline:
    """Offline queue upload must be replay-safe."""

    async def test_queue_upload_is_replay_safe(self, client, seeded_device, device_signer):
        key = str(uuid4())
        request = {
            "items": [
                {
                    "idempotency_key": key,
                    "type": "debit",
                    "card_uid": seeded_device["card_uid"],
                    "amount_minor": 500,
                    "currency": "USD",
                }
            ]
        }
        headers, body = device_signer(seeded_device["device_id"], request)
        first = await client.post(f"{BASE}/offline/queue", headers=headers, content=body)
        assert first.status_code == 201
        assert first.json()["accepted"] == 1

        headers, body = device_signer(seeded_device["device_id"], request)
        second = await client.post(f"{BASE}/offline/queue", headers=headers, content=body)
        assert second.status_code == 201
        assert second.json()["duplicates"] == 1
        assert second.json()["accepted"] == 0

        # Balance reduced by exactly one application of the queued op.
        headers, body = device_signer(
            seeded_device["device_id"], {"card_uid": seeded_device["card_uid"]}
        )
        balance = await client.post(f"{BASE}/card/balance", headers=headers, content=body)
        assert balance.json()["balances"][0]["balance_minor"] == (
            int(seeded_device["balance_minor"]) - 500
        )


class TestDeviceTenantIsolation:
    """A device must never read another tenant's card."""

    async def test_cross_tenant_card_verify_is_not_found(
        self, client, seeded_device, seeded_device_other, device_signer
    ):
        # Device A authenticates, but asks about tenant B's card UID.
        headers, body = device_signer(
            seeded_device["device_id"], {"card_uid": seeded_device_other["card_uid"]}
        )
        resp = await client.post(f"{BASE}/card/verify", headers=headers, content=body)
        assert resp.status_code == 404
