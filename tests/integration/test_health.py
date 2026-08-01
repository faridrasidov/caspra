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

    async def test_readiness_records_dependency_metrics(self, client):
        readiness = await client.get("/api/v1/health/ready")
        assert readiness.status_code == 200
        assert readiness.json()["components"]["database"] == "ok"

        metrics = await client.get("/api/v1/metrics")
        assert metrics.status_code == 200
        assert "# TYPE caspra_database_latency_seconds summary" in metrics.text
        assert "caspra_database_latency_seconds_count " in metrics.text
