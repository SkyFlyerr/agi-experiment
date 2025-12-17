"""
Webhook smoke tests

Tests that validate webhook endpoints are operational
"""

import pytest
import httpx
import os
import json
from typing import AsyncGenerator

# Configuration from environment
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_ENDPOINT = f"{API_URL}/webhook/telegram"
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide async HTTP client for tests"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        yield client


class TestTelegramWebhook:
    """Tests for the Telegram webhook endpoint"""

    @pytest.mark.asyncio
    async def test_webhook_endpoint_exists(self, http_client: httpx.AsyncClient):
        """Webhook endpoint should exist"""
        # Send OPTIONS request to check if endpoint exists
        response = await http_client.options(WEBHOOK_ENDPOINT)
        assert response.status_code in [200, 204, 405], "Webhook endpoint not found"

    @pytest.mark.asyncio
    async def test_webhook_accepts_post(self, http_client: httpx.AsyncClient):
        """Webhook should accept POST requests"""
        # Send empty POST (should fail validation but not 404)
        response = await http_client.post(WEBHOOK_ENDPOINT)
        assert response.status_code != 404, "Webhook endpoint not found"

    @pytest.mark.asyncio
    async def test_webhook_requires_json(self, http_client: httpx.AsyncClient):
        """Webhook should handle JSON requests"""
        # Send valid JSON structure
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456,
                    "first_name": "Test",
                    "is_bot": False
                },
                "chat": {
                    "id": 123456,
                    "type": "private"
                },
                "date": 1234567890,
                "text": "/start"
            }
        }

        response = await http_client.post(
            WEBHOOK_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        # Should return 200 (processed), 400 (invalid), or 401 (unauthorized)
        assert response.status_code in [200, 400, 401, 422], f"Unexpected status: {response.status_code}"

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_json(self, http_client: httpx.AsyncClient):
        """Webhook should reject malformed JSON"""
        response = await http_client.post(
            WEBHOOK_ENDPOINT,
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422], "Should reject invalid JSON"

    @pytest.mark.asyncio
    async def test_webhook_response_is_valid(self, http_client: httpx.AsyncClient):
        """Webhook response should be valid JSON or empty"""
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456,
                    "first_name": "Test",
                    "is_bot": False
                },
                "chat": {
                    "id": 123456,
                    "type": "private"
                },
                "date": 1234567890,
                "text": "/status"
            }
        }

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Response should be either empty or valid JSON
        if response.status_code == 200 and response.content:
            try:
                response.json()
            except ValueError:
                # Empty response is okay
                assert len(response.content) == 0

    @pytest.mark.asyncio
    async def test_webhook_handles_missing_fields(self, http_client: httpx.AsyncClient):
        """Webhook should handle malformed Telegram updates"""
        # Minimal invalid update
        payload = {}

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Should return 400 or 422, not 500
        assert response.status_code in [200, 400, 422], "Should handle gracefully"


class TestWebhookSecurity:
    """Tests for webhook security"""

    @pytest.mark.asyncio
    async def test_webhook_is_accessible(self, http_client: httpx.AsyncClient):
        """Webhook endpoint should be accessible"""
        # Just verify the endpoint is reachable
        response = await http_client.options(WEBHOOK_ENDPOINT)
        assert response.status_code != 500, "Webhook endpoint error"

    @pytest.mark.asyncio
    async def test_webhook_handles_content_type(self, http_client: httpx.AsyncClient):
        """Webhook should handle different content types appropriately"""
        payload = {"test": "data"}

        # Test JSON content type
        response = await http_client.post(
            WEBHOOK_ENDPOINT,
            json=payload
        )

        assert response.status_code in [200, 400, 401, 422], "Unexpected response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
