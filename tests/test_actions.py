"""Tests for action handlers."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.actions import develop_skill, work_on_task, communicate, meditate, ask_master


class TestDevelopSkill:
    """Test skill development action."""

    @pytest.mark.asyncio
    async def test_execute_skill_development(self):
        """Test executing skill development action."""
        details = {
            "skill_name": "Python async",
            "approach": "Read asyncio documentation",
            "duration_estimate": "30 minutes",
        }

        with patch("app.actions.develop_skill.get_db"):
            result = await develop_skill.execute(details)

            assert result["skill_name"] == "Python async"
            assert result["approach"] == "Read asyncio documentation"
            assert result["status"] == "initiated"
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_execute_skill_development_minimal(self):
        """Test skill development with minimal details."""
        details = {"skill_name": "Testing"}

        with patch("app.actions.develop_skill.get_db"):
            result = await develop_skill.execute(details)

            assert result["skill_name"] == "Testing"
            assert "status" in result


class TestWorkOnTask:
    """Test task execution action."""

    @pytest.mark.asyncio
    async def test_execute_task_found(self):
        """Test executing existing task."""
        task_id = "550e8400-e29b-41d4-a716-446655440000"
        details = {"task_id": task_id, "approach": "Step by step"}

        mock_task = {
            "id": task_id,
            "mode": "execute",
            "payload_json": {},
            "status": "queued",
        }

        with patch("app.actions.work_on_task.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=mock_task)
            mock_db.execute = AsyncMock()
            mock_get_db.return_value = mock_db

            result = await work_on_task.execute(details)

            assert result["task_id"] == task_id
            assert result["status"] == "completed"
            assert result["mode"] == "execute"

    @pytest.mark.asyncio
    async def test_execute_task_not_found(self):
        """Test executing non-existent task."""
        task_id = "550e8400-e29b-41d4-a716-446655440000"
        details = {"task_id": task_id, "approach": "Step by step"}

        with patch("app.actions.work_on_task.get_db") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.fetch_one = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            result = await work_on_task.execute(details)

            assert result["task_id"] == task_id
            assert result["status"] == "not_found"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_task_missing_id(self):
        """Test executing task without ID."""
        details = {"approach": "Step by step"}

        with pytest.raises(ValueError, match="task_id is required"):
            await work_on_task.execute(details)


class TestCommunicate:
    """Test communication actions."""

    @pytest.mark.asyncio
    async def test_send_to_master(self):
        """Test sending message to Master."""
        details = {
            "recipient": "master",
            "message": "Test message",
            "priority": "medium",
        }

        with patch("app.actions.communicate.send_message") as mock_send:
            mock_send.return_value = "12345"

            with patch("app.actions.communicate.settings") as mock_settings:
                mock_settings.master_chat_ids_list = [46808774]

                result = await communicate.send_to_master(details)

                assert result["status"] == "sent"
                assert result["message_id"] == "12345"
                assert result["recipient"] == "master"
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_master_high_priority(self):
        """Test sending high priority message."""
        details = {
            "recipient": "master",
            "message": "Urgent message",
            "priority": "high",
        }

        with patch("app.actions.communicate.send_message") as mock_send:
            mock_send.return_value = "12345"

            with patch("app.actions.communicate.settings") as mock_settings:
                mock_settings.master_chat_ids_list = [46808774]

                result = await communicate.send_to_master(details)

                # Check that high priority indicator was added
                call_args = mock_send.call_args
                assert "HIGH PRIORITY" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_proactive_outreach(self):
        """Test proactive outreach to chat."""
        details = {
            "chat_id": "123456789",
            "message": "Hello there",
            "purpose": "Greeting",
        }

        with patch("app.actions.communicate.send_message") as mock_send:
            mock_send.return_value = "12345"

            result = await communicate.proactive_outreach(details)

            assert result["status"] == "sent"
            assert result["chat_id"] == "123456789"
            assert result["purpose"] == "Greeting"
            mock_send.assert_called_once()


class TestMeditate:
    """Test meditation/reflection action."""

    @pytest.mark.asyncio
    async def test_execute_meditation(self):
        """Test executing meditation action."""
        details = {
            "duration": 2,  # 2 seconds for testing
            "reflection_topic": "consciousness",
        }

        start = datetime.utcnow()
        result = await meditate.execute(details)
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert result["status"] == "completed"
        assert result["reflection_topic"] == "consciousness"
        assert result["duration_requested"] == 2
        assert 1.9 <= result["duration_actual"] <= 2.5  # Allow some timing variance
        assert 1.9 <= elapsed <= 2.5

    @pytest.mark.asyncio
    async def test_execute_meditation_default_duration(self):
        """Test meditation with default duration."""
        details = {"reflection_topic": "being"}

        result = await meditate.execute(details)

        assert result["status"] == "completed"
        assert result["reflection_topic"] == "being"
        assert "duration_actual" in result

    @pytest.mark.asyncio
    async def test_execute_meditation_cap_duration(self):
        """Test that meditation duration is capped at 10 minutes."""
        details = {
            "duration": 10000,  # Request 10000 seconds
            "reflection_topic": "patience",
        }

        # Should cap at 600 seconds (10 minutes), but we'll mock sleep to speed up test
        with patch("app.actions.meditate.asyncio.sleep") as mock_sleep:
            result = await meditate.execute(details)

            # Duration should be capped
            assert result["duration_requested"] == 600  # Capped at 10 minutes


class TestAskMaster:
    """Test ask Master action."""

    @pytest.mark.asyncio
    async def test_execute_ask_master(self):
        """Test asking Master for guidance."""
        details = {
            "question": "Should I proceed with this approach?",
            "context": "Working on feature X",
        }

        with patch("app.actions.ask_master.send_message") as mock_send:
            mock_send.return_value = "12345"

            with patch("app.actions.ask_master.settings") as mock_settings:
                mock_settings.master_chat_ids_list = [46808774]
                mock_settings.APPROVAL_TIMEOUT_SECONDS = 1  # 1 second timeout for testing

                with patch("app.actions.ask_master.create_approval") as mock_create:
                    mock_approval = AsyncMock()
                    mock_approval.id = "approval-id"
                    mock_create.return_value = mock_approval

                    with patch("app.actions.ask_master.get_approval") as mock_get:
                        mock_get.return_value = None  # Simulate no response (timeout)

                        result = await ask_master.execute(details)

                        assert result["question"] == details["question"]
                        assert result["response_status"] == "timeout"
                        assert "wait_time" in result
                        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_ask_master_missing_question(self):
        """Test asking Master without question."""
        details = {"context": "Some context"}

        with pytest.raises(ValueError, match="question is required"):
            await ask_master.execute(details)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
