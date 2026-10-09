# tests/integration/test_external_topup.py

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models.ledger.wallet import Wallet

pytestmark = pytest.mark.asyncio

BASE = "/public/api/v1/topup"


async def _balance(db_session, wallet_id: str) -> int:
    db_session.expire_all()
    stmt = select(Wallet.balance_minor).where(Wallet.id == UUID(wallet_id))
    return (await db_session.execute(stmt)).scalar_one()


def _start_payload(seeded: dict[str, str], **overrides) -> dict:
    payload = {
        "wallet_id": seeded["wallet_id"],
        "amount_minor": 1_500,
        "currency": seeded["currency"],
        "idempotency_key": str(uuid4()),
    }
    payload.update(overrides)
    return payload


class TestExternalTopupLifecycle:
    """Start → confirm/cancel flow for external top-up sessions."""

    async def test_confirm_credits_wallet_once(
        self, client, db_session, seeded_public, api_key_headers
    ):
        before = await _balance(db_session, seeded_public["wallet_id"])

        started = await client.post(
            f"{BASE}/start", headers=api_key_headers, json=_start_payload(seeded_public)
        )
        assert started.status_code == 201
        session = started.json()
        assert session["status"] == "started"
        assert session["transaction_id"] is None
        assert await _balance(db_session, seeded_public["wallet_id"]) == before

        confirmed = await client.post(
            f"{BASE}/{session['id']}/confirm",
            headers=api_key_headers,
            json={"external_payment_ref": "gw-123"},
        )
        assert confirmed.status_code == 200
        body = confirmed.json()
        assert body["status"] == "confirmed"
        assert body["transaction_id"] is not None
        assert body["external_payment_ref"] == "gw-123"
        assert await _balance(db_session, seeded_public["wallet_id"]) == before + 1_500

        replay = await client.post(
            f"{BASE}/{session['id']}/confirm", headers=api_key_headers, json={}
        )
        assert replay.status_code == 200
        assert replay.json()["transaction_id"] == body["transaction_id"]
        assert await _balance(db_session, seeded_public["wallet_id"]) == before + 1_500

    async def test_start_is_idempotent_and_rejects_changed_request(
        self, client, seeded_public, api_key_headers
    ):
        payload = _start_payload(seeded_public)
        first = await client.post(f"{BASE}/start", headers=api_key_headers, json=payload)
        replay = await client.post(f"{BASE}/start", headers=api_key_headers, json=payload)
        assert first.status_code == 201
        assert replay.json()["id"] == first.json()["id"]

        changed = await client.post(
            f"{BASE}/start", headers=api_key_headers, json={**payload, "amount_minor": 9_999}
        )
        assert changed.status_code == 409

    async def test_currency_mismatch_is_rejected(self, client, seeded_public, api_key_headers):
        response = await client.post(
            f"{BASE}/start",
            headers=api_key_headers,
            json=_start_payload(seeded_public, currency="EUR"),
        )
        assert response.status_code == 409

    async def test_cancelled_session_cannot_be_confirmed(
        self, client, db_session, seeded_public, api_key_headers
    ):
        before = await _balance(db_session, seeded_public["wallet_id"])
        started = await client.post(
            f"{BASE}/start", headers=api_key_headers, json=_start_payload(seeded_public)
        )
        session_id = started.json()["id"]

        cancelled = await client.post(f"{BASE}/{session_id}/cancel", headers=api_key_headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        confirmed = await client.post(
            f"{BASE}/{session_id}/confirm", headers=api_key_headers, json={}
        )
        assert confirmed.status_code == 409
        assert await _balance(db_session, seeded_public["wallet_id"]) == before

    async def test_confirmed_session_cannot_be_cancelled(
        self, client, seeded_public, api_key_headers
    ):
        started = await client.post(
            f"{BASE}/start", headers=api_key_headers, json=_start_payload(seeded_public)
        )
        session_id = started.json()["id"]
        await client.post(f"{BASE}/{session_id}/confirm", headers=api_key_headers, json={})

        cancelled = await client.post(f"{BASE}/{session_id}/cancel", headers=api_key_headers)
        assert cancelled.status_code == 409


class TestExternalTopupAccess:
    """Scope and tenant isolation for top-up sessions."""

    async def test_unknown_wallet_returns_404(self, client, seeded_public, api_key_headers):
        response = await client.post(
            f"{BASE}/start",
            headers=api_key_headers,
            json=_start_payload(seeded_public, wallet_id=str(uuid4())),
        )
        assert response.status_code == 404

    async def test_readonly_key_cannot_start(self, client, seeded_public, api_key_headers_readonly):
        response = await client.post(
            f"{BASE}/start",
            headers=api_key_headers_readonly,
            json=_start_payload(seeded_public),
        )
        assert response.status_code == 403

    async def test_other_tenant_cannot_touch_session(
        self, client, seeded_public, api_key_headers, api_key_headers_other
    ):
        started = await client.post(
            f"{BASE}/start", headers=api_key_headers, json=_start_payload(seeded_public)
        )
        session_id = started.json()["id"]

        fetched = await client.get(f"{BASE}/{session_id}", headers=api_key_headers_other)
        confirmed = await client.post(
            f"{BASE}/{session_id}/confirm", headers=api_key_headers_other, json={}
        )
        assert fetched.status_code == 404
        assert confirmed.status_code == 404

    async def test_other_tenant_wallet_is_not_found(
        self, client, seeded_public_other, api_key_headers
    ):
        response = await client.post(
            f"{BASE}/start",
            headers=api_key_headers,
            json=_start_payload(seeded_public_other),
        )
        assert response.status_code == 404
