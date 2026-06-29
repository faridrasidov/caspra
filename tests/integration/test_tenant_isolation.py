# tests/integration/test_tenant_isolation.py

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/admin/api/v1"


class TestTenantIsolation:
    """Cross-tenant access must be denied (rows are scoped by tenant_id)."""

    async def test_cross_tenant_customer_read_is_not_found(
        self, client, auth_headers_admin, auth_headers_admin_other
    ):
        created = await client.post(
            f"{BASE}/customers",
            headers=auth_headers_admin,
            json={"full_name": "Tenant A Customer"},
        )
        assert created.status_code == 201
        customer_id = created.json()["id"]

        # The second tenant's admin must not see tenant A's customer.
        cross = await client.get(
            f"{BASE}/customers/{customer_id}", headers=auth_headers_admin_other
        )
        assert cross.status_code == 404

        # But tenant A still sees it.
        own = await client.get(f"{BASE}/customers/{customer_id}", headers=auth_headers_admin)
        assert own.status_code == 200

    async def test_cross_tenant_wallet_topup_is_not_found(
        self, client, auth_headers_admin, auth_headers_admin_other
    ):
        customer = await client.post(
            f"{BASE}/customers", headers=auth_headers_admin, json={"full_name": "A"}
        )
        wallet = await client.post(
            f"{BASE}/wallets",
            headers=auth_headers_admin,
            json={"customer_id": customer.json()["id"], "currency": "USD"},
        )
        wallet_id = wallet.json()["id"]

        cross = await client.post(
            f"{BASE}/wallets/{wallet_id}/topup",
            headers=auth_headers_admin_other,
            json={
                "amount_minor": 1000,
                "currency": "USD",
                "idempotency_key": str(uuid4()),
            },
        )
        assert cross.status_code == 404
