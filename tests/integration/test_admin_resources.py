# tests/integration/test_admin_resources.py

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/admin/api/v1"


class TestOrganization:
    """Tests for the org resource group."""

    async def test_get_and_update_org(self, client, auth_headers_admin):
        resp = await client.get(f"{BASE}/org", headers=auth_headers_admin)
        assert resp.status_code == 200

        updated = await client.patch(
            f"{BASE}/org", headers=auth_headers_admin, json={"name": "Renamed Org"}
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Renamed Org"

    async def test_create_and_list_users(self, client, auth_headers_admin):
        created = await client.post(
            f"{BASE}/org/users",
            headers=auth_headers_admin,
            json={
                "email": "staff@primary.test",
                "full_name": "Staff",
                "password": "staffpassword",
            },
        )
        assert created.status_code == 201

        listed = await client.get(f"{BASE}/org/users", headers=auth_headers_admin)
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1


class TestCustomersAndCards:
    """Tests for customers and cards resource groups."""

    async def test_customer_crud(self, client, auth_headers_admin):
        created = await client.post(
            f"{BASE}/customers",
            headers=auth_headers_admin,
            json={"full_name": "Jane Doe", "external_id": "ext-1"},
        )
        assert created.status_code == 201
        customer_id = created.json()["id"]

        fetched = await client.get(f"{BASE}/customers/{customer_id}", headers=auth_headers_admin)
        assert fetched.status_code == 200

        balances = await client.get(
            f"{BASE}/customers/{customer_id}/balances", headers=auth_headers_admin
        )
        assert balances.status_code == 200
        assert balances.json()["balances"] == []

    async def test_card_register_and_block(self, client, auth_headers_admin):
        card = await client.post(
            f"{BASE}/cards", headers=auth_headers_admin, json={"uid": "CARD-001"}
        )
        assert card.status_code == 201
        card_id = card.json()["id"]

        blocked = await client.post(f"{BASE}/cards/{card_id}/block", headers=auth_headers_admin)
        assert blocked.status_code == 200
        assert blocked.json()["status"] == "blocked"


class TestWalletMoneyFlow:
    """End-to-end money flow with idempotency and balance checks."""

    async def _create_wallet(self, client, headers) -> str:
        customer = await client.post(
            f"{BASE}/customers", headers=headers, json={"full_name": "Wallet Owner"}
        )
        customer_id = customer.json()["id"]
        wallet = await client.post(
            f"{BASE}/wallets",
            headers=headers,
            json={"customer_id": customer_id, "currency": "USD", "type": "credit"},
        )
        assert wallet.status_code == 201
        return wallet.json()["id"]

    async def test_topup_deduct_and_balance(self, client, auth_headers_admin):
        wallet_id = await self._create_wallet(client, auth_headers_admin)

        topup = await client.post(
            f"{BASE}/wallets/{wallet_id}/topup",
            headers=auth_headers_admin,
            json={
                "amount_minor": 5000,
                "currency": "USD",
                "idempotency_key": str(uuid4()),
            },
        )
        assert topup.status_code == 200

        deduct = await client.post(
            f"{BASE}/wallets/{wallet_id}/deduct",
            headers=auth_headers_admin,
            json={
                "amount_minor": 2000,
                "currency": "USD",
                "idempotency_key": str(uuid4()),
            },
        )
        assert deduct.status_code == 200

        balance = await client.get(
            f"{BASE}/wallets/{wallet_id}/balance", headers=auth_headers_admin
        )
        assert balance.status_code == 200
        assert balance.json()["balance_minor"] == 3000

    async def test_topup_idempotency_replay(self, client, auth_headers_admin):
        wallet_id = await self._create_wallet(client, auth_headers_admin)
        key = str(uuid4())
        body = {"amount_minor": 1000, "currency": "USD", "idempotency_key": key}

        first = await client.post(
            f"{BASE}/wallets/{wallet_id}/topup", headers=auth_headers_admin, json=body
        )
        second = await client.post(
            f"{BASE}/wallets/{wallet_id}/topup", headers=auth_headers_admin, json=body
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

        balance = await client.get(
            f"{BASE}/wallets/{wallet_id}/balance", headers=auth_headers_admin
        )
        assert balance.json()["balance_minor"] == 1000

    async def test_deduct_insufficient_funds(self, client, auth_headers_admin):
        wallet_id = await self._create_wallet(client, auth_headers_admin)
        resp = await client.post(
            f"{BASE}/wallets/{wallet_id}/deduct",
            headers=auth_headers_admin,
            json={
                "amount_minor": 999,
                "currency": "USD",
                "idempotency_key": str(uuid4()),
            },
        )
        assert resp.status_code == 402


class TestCatalogAndDevices:
    """Tests for products, locations, and devices resource groups."""

    async def test_product_create(self, client, auth_headers_admin):
        resp = await client.post(
            f"{BASE}/products",
            headers=auth_headers_admin,
            json={
                "name": "Soda",
                "sku": "SKU-1",
                "price_minor": 250,
                "currency": "USD",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["price_minor"] == 250

    async def test_location_and_device(self, client, auth_headers_admin):
        location = await client.post(
            f"{BASE}/locations", headers=auth_headers_admin, json={"name": "Gate A"}
        )
        assert location.status_code == 201
        location_id = location.json()["id"]

        device = await client.post(
            f"{BASE}/devices",
            headers=auth_headers_admin,
            json={"name": "Reader 1", "type": "reader", "location_id": location_id},
        )
        assert device.status_code == 201
        device_id = device.json()["id"]

        config = await client.get(f"{BASE}/devices/{device_id}/config", headers=auth_headers_admin)
        assert config.status_code == 200


class TestReportsAndNotifications:
    """Smoke tests for read-only aggregation and notification endpoints."""

    async def test_daily_report(self, client, auth_headers_admin):
        resp = await client.get(f"{BASE}/reports/daily", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert "rows" in resp.json()

    async def test_notifications_read_all(self, client, auth_headers_admin):
        resp = await client.post(f"{BASE}/notifications/read-all", headers=auth_headers_admin)
        assert resp.status_code == 200
        assert "marked_read" in resp.json()
