"""Tests for AI module (Haiku classification, Claude execution, context building)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.ai.haiku import classify_intent, ClassificationResult
from app.ai.claude import execute_task, ExecutionResult
from app.ai.context import build_conversation_context, _summarize_artifact
from app.ai.prompts import build_classification_prompt, build_execution_prompt
from app.db.models import ChatMessage, MessageRole, ArtifactKind


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    thread_id = uuid4()
    return [
        ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            role=MessageRole.USER,
            text="Hello, how are you?",
            created_at=datetime.utcnow(),
            platform_message_id="1",
            author_user_id="user123",
            raw_payload={},
        ),
        ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            role=MessageRole.ASSISTANT,
            text="I'm doing well, thanks!",
            created_at=datetime.utcnow(),
            platform_message_id="2",
            author_user_id=None,
            raw_payload={},
        ),
        ChatMessage(
            id=uuid4(),
            thread_id=thread_id,
            role=MessageRole.USER,
            text="What's the server uptime?",
            created_at=datetime.utcnow(),
            platform_message_id="3",
            author_user_id="user123",
            raw_payload={},
        ),
    ]


class TestPrompts:
    """Test prompt formatting."""

    def test_build_classification_prompt(self, sample_messages):
        """Test classification prompt building."""
        trigger_message = sample_messages[-1]
        prompt = build_classification_prompt(sample_messages, trigger_message)

        assert "What's the server uptime?" in prompt
        assert "Classify the intent" in prompt
        assert "user:" in prompt.lower()

    def test_build_execution_prompt(self, sample_messages):
        """Test execution prompt building."""
        prompt = build_execution_prompt(
            messages=sample_messages,
            intent="question",
            summary="User wants to know server uptime",
            plan="Check uptime with 'uptime' command",
        )

        assert "question" in prompt
        assert "server uptime" in prompt.lower()
        assert "What's the server uptime?" in prompt


class TestHaikuClassification:
    """Test Haiku classification."""

    @pytest.mark.asyncio
    @patch("app.ai.haiku.AsyncAnthropic")
    @patch("app.ai.haiku.log_tokens")
    async def test_classify_intent_question(
        self, mock_log_tokens, mock_anthropic, sample_messages
    ):
        """Test classifying a question."""
        # Mock Anthropic API response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"intent": "question", "summary": "User asks about uptime", "plan": "Check server uptime", "needs_confirmation": false, "confidence": 0.95}'
            )
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        # Test classification
        trigger_message = sample_messages[-1]
        result = await classify_intent(sample_messages, trigger_message)

        assert isinstance(result, ClassificationResult)
        assert result.intent == "question"
        assert result.confidence == 0.95
        assert result.needs_confirmation is False
        assert "uptime" in result.summary.lower()

        # Verify token logging was called
        mock_log_tokens.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.ai.haiku.AsyncAnthropic")
    @patch("app.ai.haiku.log_tokens")
    async def test_classify_intent_command(
        self, mock_log_tokens, mock_anthropic, sample_messages
    ):
        """Test classifying a command."""
        # Mock Anthropic API response for command
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='{"intent": "command", "summary": "User wants to restart service", "plan": "Restart the service", "needs_confirmation": true, "confidence": 0.88}'
            )
        ]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        # Create command message
        command_message = ChatMessage(
            id=uuid4(),
            thread_id=sample_messages[0].thread_id,
            role=MessageRole.USER,
            text="Restart the web service",
            created_at=datetime.utcnow(),
            platform_message_id="4",
            author_user_id="user123",
            raw_payload={},
        )

        result = await classify_intent(sample_messages, command_message)

        assert result.intent == "command"
        assert result.needs_confirmation is True
        assert result.confidence == 0.88


class TestClaudeExecution:
    """Test Claude execution."""

    @pytest.mark.asyncio
    @patch("app.ai.claude.AsyncAnthropic")
    @patch("app.ai.claude.log_tokens")
    async def test_execute_task_simple_response(
        self, mock_log_tokens, mock_anthropic, sample_messages
    ):
        """Test executing a simple task."""
        # Mock Anthropic API response
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="The server has been running for 5 days.")
        ]
        mock_response.usage = MagicMock(input_tokens=200, output_tokens=100)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        # Test execution
        result = await execute_task(
            messages=sample_messages,
            intent="question",
            summary="User asks about uptime",
            plan="Check server uptime",
        )

        assert isinstance(result, ExecutionResult)
        assert "5 days" in result.response_text
        assert result.has_tool_calls is False
        assert result.tokens_input == 200
        assert result.tokens_output == 100

    @pytest.mark.asyncio
    @patch("app.ai.claude.AsyncAnthropic")
    @patch("app.ai.claude.log_tokens")
    async def test_execute_task_with_tool_calls(
        self, mock_log_tokens, mock_anthropic, sample_messages
    ):
        """Test executing a task with tool calls."""
        # Mock Anthropic API response with tool use
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="Let me check the uptime for you."),
            MagicMock(
                type="tool_use",
                id="tool_123",
                name="bash",
                input={"command": "uptime"},
            ),
        ]
        mock_response.usage = MagicMock(input_tokens=200, output_tokens=100)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        # Test execution
        result = await execute_task(
            messages=sample_messages,
            intent="command",
            summary="User asks about uptime",
            plan="Check server uptime with bash command",
        )

        assert result.has_tool_calls is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "bash"
        assert result.tool_calls[0]["input"]["command"] == "uptime"


class TestContextBuilding:
    """Test conversation context building."""

    def test_summarize_voice_artifact(self):
        """Test voice transcript artifact summarization."""
        content = {
            "text": "This is a long voice message transcript that should be previewed.",
            "duration_seconds": 45,
        }

        summary = _summarize_artifact(ArtifactKind.VOICE_TRANSCRIPT, content, None)

        assert summary is not None
        assert "45s" in summary
        assert "Voice message" in summary
        assert "This is a long voice message" in summary

    def test_summarize_image_artifact(self):
        """Test image artifact summarization."""
        content = {
            "description": "A screenshot of the dashboard",
            "width": 1920,
            "height": 1080,
        }

        summary = _summarize_artifact(ArtifactKind.IMAGE_JSON, content, None)

        assert summary is not None
        assert "Image" in summary
        assert "1920x1080" in summary
        assert "dashboard" in summary

    def test_summarize_ocr_artifact(self):
        """Test OCR text artifact summarization."""
        content = {"text": "This is extracted text from an image document."}

        summary = _summarize_artifact(ArtifactKind.OCR_TEXT, content, None)

        assert summary is not None
        assert "OCR text" in summary
        assert "extracted text" in summary

    @pytest.mark.asyncio
    @patch("app.ai.context.fetch_recent_messages")
    @patch("app.ai.context.get_artifacts_for_message")
    async def test_build_conversation_context(
        self, mock_get_artifacts, mock_fetch_messages, sample_messages
    ):
        """Test building conversation context with artifacts."""
        thread_id = uuid4()

        # Mock database calls
        mock_fetch_messages.return_value = sample_messages
        mock_get_artifacts.return_value = []

        # Test context building
        context = await build_conversation_context(thread_id, limit=30)

        assert len(context) == len(sample_messages)
        assert context[0].text == sample_messages[0].text
        mock_fetch_messages.assert_called_once_with(thread_id, limit=30)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
