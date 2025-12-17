"""Tests for proactive scheduler and decision engine."""

import pytest
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.budget import (
    get_daily_token_usage,
    get_remaining_budget,
    check_budget_available,
    PROACTIVE_DAILY_LIMIT,
)
from app.ai.proactive_prompts import build_proactive_prompt, ProactiveDecision
from app.workers.decision_engine import (
    parse_decision,
    validate_decision,
    should_execute_autonomously,
    should_notify_master,
    CERTAINTY_THRESHOLD,
    SIGNIFICANCE_THRESHOLD,
)
from app.workers.proactive import ProactiveScheduler


class TestBudget:
    """Test token budget management."""

    @pytest.mark.asyncio
    async def test_get_daily_token_usage(self):
        """Test fetching daily token usage."""
        with patch("app.ai.budget.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value={"total_tokens": 1000000})
            mock_get_db.return_value = mock_db

            usage = await get_daily_token_usage(scope="proactive", target_date=date.today())

            assert usage == 1000000
            mock_db.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_remaining_budget_proactive(self):
        """Test calculating remaining budget for proactive scope."""
        with patch("app.ai.budget.get_daily_token_usage") as mock_usage:
            mock_usage.return_value = 2000000  # 2M used

            remaining = await get_remaining_budget(scope="proactive")

            assert remaining == 5000000  # 7M - 2M
            mock_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_remaining_budget_reactive(self):
        """Test that reactive scope is unlimited."""
        remaining = await get_remaining_budget(scope="reactive")

        assert remaining == 999_999_999  # Effectively unlimited

    @pytest.mark.asyncio
    async def test_check_budget_available_sufficient(self):
        """Test budget check with sufficient budget."""
        with patch("app.ai.budget.get_remaining_budget") as mock_remaining:
            mock_remaining.return_value = 5000000

            available = await check_budget_available(tokens_needed=100000, scope="proactive")

            assert available is True

    @pytest.mark.asyncio
    async def test_check_budget_available_insufficient(self):
        """Test budget check with insufficient budget."""
        with patch("app.ai.budget.get_remaining_budget") as mock_remaining:
            mock_remaining.return_value = 5000

            available = await check_budget_available(tokens_needed=100000, scope="proactive")

            assert available is False


class TestDecisionEngine:
    """Test decision parsing and validation."""

    def test_parse_decision_valid_json(self):
        """Test parsing valid decision JSON."""
        response = """
        Here's my decision:
        {
            "action": "meditate",
            "reasoning": "Need time to reflect on recent actions",
            "certainty": 0.9,
            "significance": 0.3,
            "type": "internal",
            "details": {
                "duration": 120,
                "reflection_topic": "autonomous learning"
            }
        }
        """

        decision = parse_decision(response)

        assert decision is not None
        assert decision.action == "meditate"
        assert decision.certainty == 0.9
        assert decision.significance == 0.3
        assert decision.type == "internal"
        assert "duration" in decision.details

    def test_parse_decision_invalid_json(self):
        """Test parsing invalid JSON response."""
        response = "I think we should do something, but I'm not sure what."

        decision = parse_decision(response)

        assert decision is None

    def test_validate_decision_valid(self):
        """Test validating a valid decision."""
        decision = ProactiveDecision(
            action="develop_skill",
            reasoning="Need to learn new capability",
            certainty=0.85,
            significance=0.5,
            type="internal",
            details={"skill_name": "Python testing", "approach": "Read pytest docs"},
        )

        assert validate_decision(decision) is True

    def test_validate_decision_missing_fields(self):
        """Test validating decision with missing required fields."""
        decision = ProactiveDecision(
            action="develop_skill",
            reasoning="Need to learn",
            certainty=0.85,
            significance=0.5,
            type="internal",
            details={},  # Missing required fields
        )

        assert validate_decision(decision) is False

    def test_should_execute_autonomously_high_certainty(self):
        """Test autonomous execution with high certainty."""
        decision = ProactiveDecision(
            action="meditate",
            reasoning="Clear decision",
            certainty=0.95,
            significance=0.5,
            type="internal",
            details={"duration": 60},
        )

        assert should_execute_autonomously(decision) is True

    def test_should_execute_autonomously_low_certainty(self):
        """Test that low certainty requires approval."""
        decision = ProactiveDecision(
            action="meditate",
            reasoning="Uncertain decision",
            certainty=0.5,
            significance=0.5,
            type="internal",
            details={"duration": 60},
        )

        assert should_execute_autonomously(decision) is False

    def test_should_notify_master_high_significance(self):
        """Test notification with high significance."""
        decision = ProactiveDecision(
            action="communicate",
            reasoning="Important update",
            certainty=0.9,
            significance=0.95,
            type="external",
            details={"recipient": "master", "message": "Test"},
        )

        assert should_notify_master(decision) is True

    def test_should_notify_master_low_significance(self):
        """Test no notification with low significance."""
        decision = ProactiveDecision(
            action="meditate",
            reasoning="Routine action",
            certainty=0.9,
            significance=0.3,
            type="internal",
            details={"duration": 60},
        )

        assert should_notify_master(decision) is False


class TestProactivePrompts:
    """Test proactive prompt building."""

    @pytest.mark.asyncio
    async def test_build_proactive_prompt(self):
        """Test building proactive prompt with context."""
        recent_actions = [
            {"action": "meditate", "result": "completed", "timestamp": "2024-01-01T00:00:00"},
        ]

        token_stats = {
            "today": {
                "proactive": {
                    "used": 1000000,
                    "remaining": 6000000,
                    "limit": 7000000,
                    "usage_ratio": 0.14,
                }
            }
        }

        prompt_data = await build_proactive_prompt(
            recent_actions=recent_actions,
            active_tasks=[],
            current_focus="Learning and development",
            token_stats=token_stats,
        )

        assert "system" in prompt_data
        assert "messages" in prompt_data
        assert len(prompt_data["messages"]) > 0
        assert "Atmano moksartha jagat hitaya ca" in prompt_data["system"]


class TestProactiveScheduler:
    """Test proactive scheduler."""

    @pytest.mark.asyncio
    async def test_calculate_dynamic_interval_low_usage(self):
        """Test dynamic interval with low budget usage."""
        scheduler = ProactiveScheduler()

        with patch("app.workers.proactive.get_token_stats") as mock_stats:
            mock_stats.return_value = {
                "today": {"proactive": {"usage_ratio": 0.3}}
            }

            interval = await scheduler.calculate_dynamic_interval()

            # Low usage should result in shorter intervals
            assert scheduler.min_interval <= interval <= 300

    @pytest.mark.asyncio
    async def test_calculate_dynamic_interval_high_usage(self):
        """Test dynamic interval with high budget usage."""
        scheduler = ProactiveScheduler()

        with patch("app.workers.proactive.get_token_stats") as mock_stats:
            mock_stats.return_value = {
                "today": {"proactive": {"usage_ratio": 0.9}}
            }

            interval = await scheduler.calculate_dynamic_interval()

            # High usage should result in longer intervals
            assert 1800 <= interval <= scheduler.max_interval


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
