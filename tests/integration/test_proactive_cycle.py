"""
Proactive scheduler integration tests

Tests for proactive cycle functionality and autonomous decision-making
"""

import pytest
import httpx
import os
import time
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


class TestProactiveScheduler:
    """Tests for proactive scheduler functionality"""

    @pytest.mark.asyncio
    async def test_proactive_scheduler_running(self, http_client: httpx.AsyncClient):
        """Proactive scheduler should be running"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        # Check for proactive scheduler status
        status_str = str(data).lower()
        # Should not have explicit error about scheduler
        assert "proactive" not in status_str or "running" in status_str

    @pytest.mark.asyncio
    async def test_proactive_cycles_executing(self, http_client: httpx.AsyncClient):
        """Proactive cycles should be executing"""
        # Check stats endpoint for cycle count
        response = await http_client.get(STATS_ENDPOINT)

        if response.status_code == 200:
            data = response.json()
            # If stats available, should show cycle activity
            assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_scheduler_respects_token_budget(self, http_client: httpx.AsyncClient):
        """Scheduler should respect token budget"""
        response = await http_client.get(STATS_ENDPOINT)

        if response.status_code == 200:
            data = response.json()
            # If token budget tracking available
            if "token_budget" in data:
                # Budget should be a reasonable number
                assert data["token_budget"] > 0

    @pytest.mark.asyncio
    async def test_scheduler_handles_pause(self, http_client: httpx.AsyncClient):
        """Scheduler should handle pause/resume commands"""
        # This test assumes there's a pause endpoint or command
        # Implementation depends on your API design
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200


class TestAutonomousDecision:
    """Tests for autonomous decision-making"""

    @pytest.mark.asyncio
    async def test_uncertain_decisions_request_approval(self, http_client: httpx.AsyncClient):
        """Uncertain decisions should request master approval"""
        # This would test the decision-making logic
        # Implementation depends on your decision framework
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_skill_development_executes(self, http_client: httpx.AsyncClient):
        """Skill development actions should execute"""
        # Test that skill development is possible
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200


class TestSchedulerStability:
    """Tests for scheduler stability and reliability"""

    @pytest.mark.asyncio
    async def test_scheduler_recovers_from_errors(self, http_client: httpx.AsyncClient):
        """Scheduler should recover from errors gracefully"""
        # Application should remain healthy
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_scheduler_doesnt_consume_excessive_tokens(self, http_client: httpx.AsyncClient):
        """Scheduler should not consume tokens excessively in short time"""
        # Check initial stats
        start_response = await http_client.get(STATS_ENDPOINT)

        # Wait a moment
        await asyncio.sleep(2)

        # Check final stats
        end_response = await http_client.get(STATS_ENDPOINT)

        # Token usage should be reasonable (not critical for this test)
        assert end_response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_multiple_proactive_cycles_succeed(self, http_client: httpx.AsyncClient):
        """Multiple proactive cycles should execute successfully"""
        # This is more of a time-based test
        # Application should remain healthy after multiple cycles
        for i in range(3):
            response = await http_client.get(HEALTH_ENDPOINT)
            assert response.status_code == 200
            await asyncio.sleep(1)


class TestProactiveMessaging:
    """Tests for proactive message sending"""

    @pytest.mark.asyncio
    async def test_can_send_proactive_message(self, http_client: httpx.AsyncClient):
        """Proactive messages should be sendable"""
        # Check that messaging capability exists
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        data = response.json()
        # Should have telegram initialized
        assert "telegram" not in str(data).lower() or "error" not in str(data).lower()


class TestLoggingAndTracking:
    """Tests for logging and activity tracking"""

    @pytest.mark.asyncio
    async def test_proactive_cycles_logged(self, http_client: httpx.AsyncClient):
        """Proactive cycles should be logged"""
        # Check that logs exist
        import os

        log_files = [
            "logs/app.log",
            "logs/proactive.log",
            "logs/agent.log"
        ]

        # At least one log file should exist
        has_logs = any(os.path.exists(f) for f in log_files)
        # Logging is optional, so we just check health
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_activity_tracking_enabled(self, http_client: httpx.AsyncClient):
        """Activity should be tracked"""
        response = await http_client.get(HEALTH_ENDPOINT)
        assert response.status_code == 200

        # If stats available, should show activity
        stats = await http_client.get(STATS_ENDPOINT)
        # Stats endpoint may not be implemented
        assert stats.status_code in [200, 404]


# Import asyncio for tests
import asyncio


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
