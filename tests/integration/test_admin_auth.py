# tests/integration/test_admin_auth.py

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/admin/api/v1"


class TestAdminAuthRBAC:
    """Authentication and authorization gating for the admin surface."""

    async def test_unauthenticated_returns_401(self, client):
        response = await client.get(f"{BASE}/org")
        assert response.status_code == 401

    async def test_non_admin_token_returns_403(self, client, auth_headers_user):
        response = await client.get(f"{BASE}/org", headers=auth_headers_user)
        assert response.status_code == 403

    async def test_admin_token_allowed(self, client, auth_headers_admin):
        response = await client.get(f"{BASE}/org", headers=auth_headers_admin)
        assert response.status_code == 200


class TestAdminLogin:
    """Tests for POST /auth/login and /auth/me."""

    async def test_login_success_and_me(self, client, seeded_admin):
        login = await client.post(
            f"{BASE}/auth/login",
            json={"email": "admin@primary.test", "password": "adminpassword"},
        )
        assert login.status_code == 200
        tokens = login.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me = await client.get(f"{BASE}/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == "admin@primary.test"

    async def test_login_wrong_password(self, client, seeded_admin):
        response = await client.post(
            f"{BASE}/auth/login",
            json={"email": "admin@primary.test", "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_refresh_rotates_token(self, client, seeded_admin):
        login = await client.post(
            f"{BASE}/auth/login",
            json={"email": "admin@primary.test", "password": "adminpassword"},
        )
        refresh_token = login.json()["refresh_token"]
        refreshed = await client.post(f"{BASE}/auth/refresh", json={"refresh_token": refresh_token})
        assert refreshed.status_code == 200
        assert refreshed.json()["access_token"]
