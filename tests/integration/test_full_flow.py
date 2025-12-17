"""
Full flow integration tests

Tests complete workflows: webhook → reactive processing → response
"""

import pytest
import httpx
import os
import json
from typing import AsyncGenerator

# Configuration from environment
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_ENDPOINT = f"{API_URL}/webhook/telegram"
HEALTH_ENDPOINT = f"{API_URL}/health"
TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide async HTTP client for tests"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        yield client


class TestFullFlowWorkflow:
    """Tests complete end-to-end workflow"""

    @pytest.mark.asyncio
    async def test_application_is_ready(self, http_client: httpx.AsyncClient):
        """Application should be ready before testing full flow"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200, "Application not healthy"

    @pytest.mark.asyncio
    async def test_webhook_processes_message(self, http_client: httpx.AsyncClient):
        """Webhook should process incoming Telegram message"""
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
                "text": "test message"
            }
        }

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Should process message successfully
        assert response.status_code in [200, 202], f"Webhook returned {response.status_code}"

    @pytest.mark.asyncio
    async def test_webhook_with_command(self, http_client: httpx.AsyncClient):
        """Webhook should process command messages"""
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

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Should accept command
        assert response.status_code in [200, 202], f"Webhook returned {response.status_code}"

    @pytest.mark.asyncio
    async def test_multiple_messages_processed(self, http_client: httpx.AsyncClient):
        """Webhook should process multiple messages sequentially"""
        messages = [
            "/start",
            "Hello agent",
            "/status"
        ]

        for i, text in enumerate(messages):
            payload = {
                "update_id": 123456789 + i,
                "message": {
                    "message_id": i + 1,
                    "from": {
                        "id": 123456,
                        "first_name": "Test",
                        "is_bot": False
                    },
                    "chat": {
                        "id": 123456,
                        "type": "private"
                    },
                    "date": 1234567890 + i,
                    "text": text
                }
            }

            response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)
            assert response.status_code in [200, 202], f"Failed to process: {text}"

    @pytest.mark.asyncio
    async def test_reactive_processing_completes(self, http_client: httpx.AsyncClient):
        """Reactive message processing should complete within timeout"""
        import time

        payload = {
            "update_id": 999999999,
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
                "date": int(time.time()),
                "text": "test"
            }
        }

        start = time.time()
        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload, timeout=30)
        duration = time.time() - start

        assert response.status_code in [200, 202], "Reactive processing failed"
        assert duration < 30, f"Processing took too long: {duration}s"

    @pytest.mark.asyncio
    async def test_application_remains_healthy(self, http_client: httpx.AsyncClient):
        """Application should remain healthy after processing messages"""
        # Process a message
        payload = {
            "update_id": 888888888,
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
                "text": "health check"
            }
        }

        await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Check health after processing
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200, "Application became unhealthy"


class TestReactiveWorker:
    """Tests for reactive worker functionality"""

    @pytest.mark.asyncio
    async def test_reactive_worker_processes_messages(self, http_client: httpx.AsyncClient):
        """Reactive worker should process incoming messages"""
        payload = {
            "update_id": 555555555,
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
                "text": "worker test"
            }
        }

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)
        assert response.status_code in [200, 202], "Reactive worker not responding"

    @pytest.mark.asyncio
    async def test_reactive_worker_handles_errors(self, http_client: httpx.AsyncClient):
        """Reactive worker should handle errors gracefully"""
        # Send empty/invalid message
        payload = {}

        response = await http_client.post(WEBHOOK_ENDPOINT, json=payload)

        # Should not crash the application
        # Check that health is still good
        health = await http_client.get(HEALTH_ENDPOINT)
        assert health.status_code == 200, "Application crashed after error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
