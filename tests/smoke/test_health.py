"""
Health check smoke tests

Tests that validate the application is running and healthy
"""

import pytest
import httpx
import os
from typing import AsyncGenerator

# Configuration from environment
API_URL = os.getenv("API_URL", "http://localhost:8000")
HEALTH_ENDPOINT = f"{API_URL}/health"
STATS_ENDPOINT = f"{API_URL}/stats"
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide async HTTP client for tests"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        yield client


class TestHealthEndpoint:
    """Tests for the /health endpoint"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, http_client: httpx.AsyncClient):
        """Health endpoint should return HTTP 200"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_health_response_is_json(self, http_client: httpx.AsyncClient):
        """Health endpoint response should be valid JSON"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        # Should be parseable as JSON
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_health_contains_status(self, http_client: httpx.AsyncClient):
        """Health response should contain status field"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data or "healthy" in data, "Missing status field in health response"

    @pytest.mark.asyncio
    async def test_health_contains_database_status(self, http_client: httpx.AsyncClient):
        """Health response should include database connection status"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        assert "database" in data or "db" in data, "Missing database status in health response"

    @pytest.mark.asyncio
    async def test_health_response_time(self, http_client: httpx.AsyncClient):
        """Health check should respond quickly (< 1s)"""
        import time

        start = time.time()
        response = await http_client.get(HEALTH_ENDPOINT)
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0, f"Health check took {duration}s, expected < 1s"


class TestStatsEndpoint:
    """Tests for the /stats endpoint"""

    @pytest.mark.asyncio
    async def test_stats_endpoint_exists(self, http_client: httpx.AsyncClient):
        """Stats endpoint should return valid response"""
        response = await http_client.get(STATS_ENDPOINT)
        # Accept 200 or 404 (endpoint may not be implemented)
        assert response.status_code in [200, 404, 501]

    @pytest.mark.asyncio
    async def test_stats_response_is_json(self, http_client: httpx.AsyncClient):
        """Stats endpoint response should be valid JSON if implemented"""
        response = await http_client.get(STATS_ENDPOINT)

        if response.status_code == 200:
            # If endpoint returns 200, response should be JSON
            data = response.json()
            assert isinstance(data, dict)


class TestApplicationReadiness:
    """Tests for application readiness"""

    @pytest.mark.asyncio
    async def test_application_is_responding(self, http_client: httpx.AsyncClient):
        """Application should be responding to HTTP requests"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code in [200, 401, 403], "Application not responding"

    @pytest.mark.asyncio
    async def test_no_critical_errors(self, http_client: httpx.AsyncClient):
        """Health endpoint should not indicate critical errors"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200, "Application reported unhealthy status"

        data = response.json()

        # Check for error indicators
        status_str = str(data).lower()
        assert "critical" not in status_str, "Health response contains critical error"
        assert "500" not in status_str, "Health response contains 500 error"


class TestConnectivity:
    """Tests for service connectivity"""

    @pytest.mark.asyncio
    async def test_can_connect_to_api(self, http_client: httpx.AsyncClient):
        """Should be able to connect to API endpoint"""
        try:
            response = await http_client.get(HEALTH_ENDPOINT)
            assert response.status_code in [200, 401, 403, 404, 405], "Cannot connect to API"
        except Exception as e:
            pytest.fail(f"Cannot connect to API at {API_URL}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
