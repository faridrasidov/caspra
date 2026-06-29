# tests/integration/test_health.py

import pytest

pytestmark = pytest.mark.asyncio


class TestHealth:
    """Tests for GET /api/v1/health"""

    async def test_health_returns_ok(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
