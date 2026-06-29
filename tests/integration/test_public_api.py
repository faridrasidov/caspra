# tests/integration/test_public_api.py

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/public/api/v1"


class TestPublicAuth:
    """API-key authentication for the public surface."""

    async def test_missing_key_returns_401(self, client):
        response = await client.get(f"{BASE}/auth/test")
        assert response.status_code == 401

    async def test_invalid_key_returns_401(self, client):
        response = await client.get(
            f"{BASE}/auth/test", headers={"Authorization": "Bearer not-a-real-key"}
        )
        assert response.status_code == 401

    async def test_auth_test_happy_path(self, client, api_key_headers, seeded_public):
        response = await client.get(f"{BASE}/auth/test", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["tenant_id"] == seeded_public["tenant_id"]

    async def test_auth_scopes_happy_path(self, client, api_key_headers_readonly):
        response = await client.get(f"{BASE}/auth/scopes", headers=api_key_headers_readonly)
        assert response.status_code == 200
        scopes = response.json()["scopes"]
        assert "customers:read" in scopes
        assert "customers:write" not in scopes

    async def test_x_api_key_header_accepted(self, client, api_key_headers_readonly):
        response = await client.get(f"{BASE}/auth/test", headers=api_key_headers_readonly)
        assert response.status_code == 200

    async def test_admin_jwt_not_accepted(self, client, auth_headers_admin):
        """An admin JWT must not authenticate on the public surface."""
        response = await client.get(f"{BASE}/auth/test", headers=auth_headers_admin)
        assert response.status_code == 401


class TestPublicScopeGuard:
    """Scope-based authorization (403 when the key lacks the scope)."""

    async def test_missing_scope_returns_403(self, client, api_key_headers_noscope):
        response = await client.get(f"{BASE}/customers", headers=api_key_headers_noscope)
        assert response.status_code == 403

    async def test_write_scope_required_for_create(self, client, api_key_headers_readonly):
        response = await client.post(
            f"{BASE}/customers",
            headers=api_key_headers_readonly,
            json={"full_name": "No Write"},
        )
        assert response.status_code == 403


class TestPublicCustomers:
    """Customer listing, creation, and PII redaction."""

    async def test_list_redacts_pii_for_readonly_key(self, client, api_key_headers_readonly):
        response = await client.get(f"{BASE}/customers", headers=api_key_headers_readonly)
        assert response.status_code == 200
        items = response.json()["items"]
        assert items
        assert all(item["email"] is None for item in items)
        assert all(item["phone"] is None for item in items)

    async def test_list_shows_pii_for_elevated_key(self, client, api_key_headers, seeded_public):
        response = await client.get(f"{BASE}/customers", headers=api_key_headers)
        assert response.status_code == 200
        items = response.json()["items"]
        emails = [item["email"] for item in items]
        assert seeded_public["customer_email"] in emails

    async def test_create_customer(self, client, api_key_headers):
        response = await client.post(
            f"{BASE}/customers",
            headers=api_key_headers,
            json={"full_name": "New Dev Customer", "email": "new@example.test"},
        )
        assert response.status_code == 201
        assert response.json()["full_name"] == "New Dev Customer"


class TestPublicTenantIsolation:
    """Cross-tenant reads must 404 (rows scoped by the key's tenant)."""

    async def test_cross_tenant_customer_read_is_404(
        self, client, api_key_headers, seeded_public_other
    ):
        other_customer = seeded_public_other["customer_id"]
        response = await client.get(f"{BASE}/customers/{other_customer}", headers=api_key_headers)
        assert response.status_code == 404

    async def test_cross_tenant_card_read_is_404(
        self, client, api_key_headers, seeded_public_other
    ):
        other_card = seeded_public_other["card_id"]
        response = await client.get(f"{BASE}/cards/{other_card}", headers=api_key_headers)
        assert response.status_code == 404


class TestPublicTopupIdempotency:
    """Top-up goes through the ledger and is replay-safe."""

    async def test_topup_is_idempotent(self, client, api_key_headers, seeded_public):
        wallet_id = seeded_public["wallet_id"]
        customer_id = seeded_public["customer_id"]
        idem = str(uuid4())
        body = {
            "wallet_id": wallet_id,
            "amount_minor": 2500,
            "currency": "USD",
            "idempotency_key": idem,
        }

        first = await client.post(f"{BASE}/transactions/topup", headers=api_key_headers, json=body)
        assert first.status_code == 201
        txn_id = first.json()["id"]

        second = await client.post(f"{BASE}/transactions/topup", headers=api_key_headers, json=body)
        assert second.status_code == 201
        assert second.json()["id"] == txn_id  # replay returns the same transaction

        balances = await client.get(
            f"{BASE}/customers/{customer_id}/balances", headers=api_key_headers
        )
        wallet = next(b for b in balances.json()["balances"] if b["wallet_id"] == wallet_id)
        # Seed balance 50_000 + a single 2_500 credit (no double-post on replay).
        assert wallet["balance_minor"] == 52_500


class TestPublicExternalTopupSessions:
    """Mobile/partner top-up session lifecycle."""

    async def test_start_confirm_credits_wallet(self, client, api_key_headers, seeded_public):
        wallet_id = seeded_public["wallet_id"]
        start = await client.post(
            f"{BASE}/topup/start",
            headers=api_key_headers,
            json={
                "wallet_id": wallet_id,
                "amount_minor": 1000,
                "currency": "USD",
                "idempotency_key": str(uuid4()),
            },
        )
        assert start.status_code == 201
        session_id = start.json()["id"]
        assert start.json()["status"] == "started"

        confirm = await client.post(
            f"{BASE}/topup/{session_id}/confirm",
            headers=api_key_headers,
            json={"external_payment_ref": "pay_123"},
        )
        assert confirm.status_code == 200
        assert confirm.json()["status"] == "confirmed"
        assert confirm.json()["transaction_id"] is not None


class TestPublicWebhooks:
    """Webhook subscription lifecycle and event catalog."""

    async def test_event_types_listed(self, client, api_key_headers):
        response = await client.get(f"{BASE}/webhooks/events", headers=api_key_headers)
        assert response.status_code == 200
        assert "transaction.posted" in response.json()["event_types"]

    async def test_register_list_delete(self, client, api_key_headers):
        created = await client.post(
            f"{BASE}/webhooks",
            headers=api_key_headers,
            json={"url": "https://example.test/hook", "events": ["transaction.posted"]},
        )
        assert created.status_code == 201
        assert created.json()["secret"]
        webhook_id = created.json()["id"]

        listed = await client.get(f"{BASE}/webhooks", headers=api_key_headers)
        assert listed.status_code == 200
        assert any(w["id"] == webhook_id for w in listed.json()["items"])

        deleted = await client.delete(f"{BASE}/webhooks/{webhook_id}", headers=api_key_headers)
        assert deleted.status_code == 204


class TestPublicOrg:
    """Org info and stats."""

    async def test_org_stats_counts(self, client, api_key_headers):
        response = await client.get(f"{BASE}/org/stats", headers=api_key_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["customers"] >= 1
        assert data["cards"] >= 1
        assert data["devices"] >= 1


class TestPublicEventsStream:
    """SSE event stream."""

    async def test_stream_returns_event_stream(self, client, api_key_headers):
        response = await client.get(f"{BASE}/events/stream", headers=api_key_headers)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


class TestPublicMetadata:
    """Open metadata routes (no API key required)."""

    async def test_version_is_open(self, client):
        response = await client.get(f"{BASE}/metadata/version")
        assert response.status_code == 200
        assert response.json()["surface"] == "public"

    async def test_schema_is_open_and_public_only(self, client):
        response = await client.get(f"{BASE}/metadata/schema")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert paths
        assert all(p.startswith(BASE) for p in paths)
