"""Tests for reactive worker and job handlers."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.workers.reactive import ReactiveWorker
from app.workers.handlers import (
    handle_classify_job,
    handle_execute_job,
    handle_answer_job,
    wait_for_approval,
)
from app.db.models import (
    ReactiveJob,
    JobMode,
    JobStatus,
    ApprovalStatus,
    ChatThread,
    ChatMessage,
    MessageRole,
)


@pytest.fixture
def sample_thread():
    """Create sample chat thread."""
    return ChatThread(
        id=uuid4(),
        platform="telegram",
        chat_id="123456",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_message():
    """Create sample message."""
    return ChatMessage(
        id=uuid4(),
        thread_id=uuid4(),
        role=MessageRole.USER,
        text="What's the server status?",
        created_at=datetime.utcnow(),
        platform_message_id="1",
        author_user_id="user123",
        raw_payload={},
    )


@pytest.fixture
def classify_job(sample_thread, sample_message):
    """Create CLASSIFY job."""
    return ReactiveJob(
        id=uuid4(),
        thread_id=sample_thread.id,
        trigger_message_id=sample_message.id,
        status=JobStatus.QUEUED,
        mode=JobMode.CLASSIFY,
        payload_json=None,
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
    )


@pytest.fixture
def execute_job(sample_thread, sample_message):
    """Create EXECUTE job with classification payload."""
    return ReactiveJob(
        id=uuid4(),
        thread_id=sample_thread.id,
        trigger_message_id=sample_message.id,
        status=JobStatus.QUEUED,
        mode=JobMode.EXECUTE,
        payload_json={
            "classification": {
                "intent": "question",
                "summary": "User asks about server status",
                "plan": "Check server status with uptime command",
                "needs_confirmation": False,
                "confidence": 0.92,
            }
        },
        created_at=datetime.utcnow(),
        started_at=None,
        finished_at=None,
    )


class TestReactiveWorker:
    """Test reactive worker loop."""

    @pytest.mark.asyncio
    async def test_worker_start_stop(self):
        """Test starting and stopping worker."""
        worker = ReactiveWorker(poll_interval_ms=100)

        assert not worker.is_running

        await worker.start()
        assert worker.is_running

        # Give worker time to start
        await asyncio.sleep(0.2)

        await worker.stop()
        assert not worker.is_running

    @pytest.mark.asyncio
    @patch("app.workers.reactive.poll_pending_jobs")
    @patch("app.workers.reactive.update_job_status")
    @patch("app.workers.reactive.handle_classify_job")
    async def test_worker_processes_jobs(
        self, mock_handle, mock_update, mock_poll, classify_job
    ):
        """Test worker processes pending jobs."""
        # Mock poll to return one job then empty
        mock_poll.side_effect = [[classify_job], []]

        # Mock handler
        mock_handle.return_value = {
            "classification": {
                "intent": "question",
                "summary": "Test",
                "plan": "Test",
                "needs_confirmation": False,
                "confidence": 0.9,
            },
            "needs_execution": True,
        }

        # Mock update
        mock_update.return_value = classify_job

        # Start worker
        worker = ReactiveWorker(poll_interval_ms=50)
        await worker.start()

        # Wait for job to process
        await asyncio.sleep(0.3)

        # Stop worker
        await worker.stop()

        # Verify job was processed
        mock_handle.assert_called_once()
        assert mock_update.call_count >= 2  # RUNNING and DONE


class TestClassifyJobHandler:
    """Test CLASSIFY job handler."""

    @pytest.mark.asyncio
    @patch("app.workers.handlers.get_thread_by_id")
    @patch("app.workers.handlers.get_message_by_id")
    @patch("app.workers.handlers.build_conversation_context")
    @patch("app.workers.handlers.classify_intent")
    async def test_handle_classify_job(
        self,
        mock_classify,
        mock_context,
        mock_get_message,
        mock_get_thread,
        classify_job,
        sample_thread,
        sample_message,
    ):
        """Test handling CLASSIFY job."""
        # Mock dependencies
        mock_get_thread.return_value = sample_thread
        mock_get_message.return_value = sample_message
        mock_context.return_value = [sample_message]

        # Mock classification result
        from app.ai.haiku import ClassificationResult

        mock_classify.return_value = ClassificationResult(
            intent="question",
            summary="User asks about server status",
            plan="Check server status",
            needs_confirmation=False,
            confidence=0.92,
        )

        # Test handler
        result = await handle_classify_job(classify_job)

        assert result["classification"]["intent"] == "question"
        assert result["needs_execution"] is True
        assert result["classification"]["confidence"] == 0.92

        # Verify calls
        mock_get_thread.assert_called_once_with(classify_job.thread_id)
        mock_get_message.assert_called_once_with(classify_job.trigger_message_id)
        mock_classify.assert_called_once()


class TestExecuteJobHandler:
    """Test EXECUTE job handler."""

    @pytest.mark.asyncio
    @patch("app.workers.handlers.get_thread_by_id")
    @patch("app.workers.handlers.build_conversation_context")
    @patch("app.workers.handlers.execute_task")
    @patch("app.workers.handlers.send_response")
    async def test_handle_execute_job_no_confirmation(
        self,
        mock_send,
        mock_execute,
        mock_context,
        mock_get_thread,
        execute_job,
        sample_thread,
        sample_message,
    ):
        """Test handling EXECUTE job without confirmation."""
        # Mock dependencies
        mock_get_thread.return_value = sample_thread
        mock_context.return_value = [sample_message]

        # Mock execution result
        from app.ai.claude import ExecutionResult

        mock_execute.return_value = ExecutionResult(
            response_text="Server is running normally.",
            tool_calls=[],
            tokens_input=200,
            tokens_output=50,
        )

        # Test handler
        result = await handle_execute_job(execute_job)

        assert result["approved"] is None  # No confirmation needed
        assert "running normally" in result["response"]
        assert result["tool_calls"] == 0

        # Verify response was sent
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.workers.handlers.get_thread_by_id")
    @patch("app.workers.handlers.build_conversation_context")
    @patch("app.workers.handlers.create_approval")
    @patch("app.workers.handlers.send_acknowledgement")
    @patch("app.workers.handlers.wait_for_approval")
    @patch("app.workers.handlers.execute_task")
    @patch("app.workers.handlers.send_response")
    async def test_handle_execute_job_with_confirmation(
        self,
        mock_send,
        mock_execute,
        mock_wait,
        mock_send_ack,
        mock_create_approval,
        mock_context,
        mock_get_thread,
        sample_thread,
        sample_message,
    ):
        """Test handling EXECUTE job with confirmation."""
        # Create job that needs confirmation
        job = ReactiveJob(
            id=uuid4(),
            thread_id=sample_thread.id,
            trigger_message_id=sample_message.id,
            status=JobStatus.QUEUED,
            mode=JobMode.EXECUTE,
            payload_json={
                "classification": {
                    "intent": "command",
                    "summary": "User wants to restart service",
                    "plan": "Restart the web service",
                    "needs_confirmation": True,
                    "confidence": 0.88,
                }
            },
            created_at=datetime.utcnow(),
            started_at=None,
            finished_at=None,
        )

        # Mock dependencies
        mock_get_thread.return_value = sample_thread
        mock_context.return_value = [sample_message]

        # Mock approval
        from app.db.models import Approval

        mock_approval = Approval(
            id=uuid4(),
            thread_id=sample_thread.id,
            job_id=job.id,
            proposal_text="Restart service",
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            resolved_at=None,
        )
        mock_create_approval.return_value = mock_approval
        mock_wait.return_value = True  # Approved

        # Mock execution result
        from app.ai.claude import ExecutionResult

        mock_execute.return_value = ExecutionResult(
            response_text="Service restarted successfully.",
            tool_calls=[],
            tokens_input=200,
            tokens_output=50,
        )

        # Test handler
        result = await handle_execute_job(job)

        assert result["approved"] is True
        assert "restarted" in result["response"]

        # Verify approval flow
        mock_create_approval.assert_called_once()
        mock_send_ack.assert_called_once()
        mock_wait.assert_called_once()


class TestAnswerJobHandler:
    """Test ANSWER job handler."""

    @pytest.mark.asyncio
    @patch("app.workers.handlers.get_thread_by_id")
    @patch("app.workers.handlers.send_response")
    async def test_handle_answer_job(
        self, mock_send, mock_get_thread, sample_thread
    ):
        """Test handling ANSWER job."""
        # Create ANSWER job
        job = ReactiveJob(
            id=uuid4(),
            thread_id=sample_thread.id,
            trigger_message_id=uuid4(),
            status=JobStatus.QUEUED,
            mode=JobMode.ANSWER,
            payload_json={"answer": "Hello! How can I help you?"},
            created_at=datetime.utcnow(),
            started_at=None,
            finished_at=None,
        )

        # Mock thread
        mock_get_thread.return_value = sample_thread

        # Test handler
        result = await handle_answer_job(job)

        assert result["response"] == "Hello! How can I help you?"
        mock_send.assert_called_once()


class TestApprovalWaiting:
    """Test approval waiting mechanism."""

    @pytest.mark.asyncio
    @patch("app.workers.handlers.check_approval_status")
    async def test_wait_for_approval_approved(self, mock_check):
        """Test waiting for approval - approved."""
        from app.db.models import Approval

        approval_id = uuid4()

        # Mock approval status progression
        pending_approval = Approval(
            id=approval_id,
            thread_id=uuid4(),
            job_id=uuid4(),
            proposal_text="Test",
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            resolved_at=None,
        )

        approved_approval = Approval(
            id=approval_id,
            thread_id=uuid4(),
            job_id=uuid4(),
            proposal_text="Test",
            status=ApprovalStatus.APPROVED,
            created_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
        )

        # First call returns pending, second returns approved
        mock_check.side_effect = [pending_approval, approved_approval]

        # Test waiting (should return quickly)
        result = await wait_for_approval(approval_id, timeout=10)

        assert result is True
        assert mock_check.call_count == 2

    @pytest.mark.asyncio
    @patch("app.workers.handlers.check_approval_status")
    async def test_wait_for_approval_rejected(self, mock_check):
        """Test waiting for approval - rejected."""
        from app.db.models import Approval

        approval_id = uuid4()

        rejected_approval = Approval(
            id=approval_id,
            thread_id=uuid4(),
            job_id=uuid4(),
            proposal_text="Test",
            status=ApprovalStatus.REJECTED,
            created_at=datetime.utcnow(),
            resolved_at=datetime.utcnow(),
        )

        mock_check.return_value = rejected_approval

        # Test waiting
        result = await wait_for_approval(approval_id, timeout=10)

        assert result is False

    @pytest.mark.asyncio
    @patch("app.workers.handlers.check_approval_status")
    async def test_wait_for_approval_timeout(self, mock_check):
        """Test waiting for approval - timeout."""
        from app.db.models import Approval

        approval_id = uuid4()

        pending_approval = Approval(
            id=approval_id,
            thread_id=uuid4(),
            job_id=uuid4(),
            proposal_text="Test",
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            resolved_at=None,
        )

        # Always return pending
        mock_check.return_value = pending_approval

        # Test waiting with short timeout
        result = await wait_for_approval(approval_id, timeout=1)

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
