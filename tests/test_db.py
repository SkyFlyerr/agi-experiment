"""Comprehensive database layer tests."""

import pytest
import asyncio
import os
from datetime import datetime, date, timedelta
from uuid import uuid4

# Import database modules
from app.db import Database, init_db, close_db, get_db
from app.db.models import (
    MessageRole,
    ArtifactKind,
    JobStatus,
    JobMode,
    ApprovalStatus,
    TokenScope,
    DeploymentStatus,
)
from app.db.threads import get_or_create_thread, update_thread, get_thread_by_chat_id
from app.db.messages import (
    insert_message,
    fetch_recent_messages,
    get_message_by_id,
    get_message_by_platform_id,
)
from app.db.artifacts import store_artifact, get_artifacts_for_message, update_artifact
from app.db.jobs import (
    enqueue_job,
    poll_pending_jobs,
    update_job_status,
    get_job_by_id,
    cancel_pending_jobs_for_thread,
)
from app.db.approvals import (
    create_approval,
    check_approval_status,
    resolve_approval,
    supersede_pending_approvals,
    get_pending_approval_for_job,
)
from app.db.tokens import log_tokens, get_daily_token_usage, get_token_stats
from app.db.deployments import (
    create_deployment,
    update_deployment_status,
    get_latest_deployment,
    get_deployment_by_id,
    get_recent_deployments,
)


# Test database URL (use environment variable or default)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://localhost/server_agent_test",
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db():
    """Initialize database connection for tests."""
    database = init_db(TEST_DATABASE_URL, min_size=1, max_size=5)
    await database.connect()
    yield database
    await close_db()


@pytest.fixture(autouse=True)
async def cleanup_tables(db):
    """Clean up test data after each test."""
    yield
    # Clean up tables in reverse order of dependencies
    await db.execute("TRUNCATE TABLE deployments CASCADE")
    await db.execute("TRUNCATE TABLE token_ledger CASCADE")
    await db.execute("TRUNCATE TABLE approvals CASCADE")
    await db.execute("TRUNCATE TABLE reactive_jobs CASCADE")
    await db.execute("TRUNCATE TABLE message_artifacts CASCADE")
    await db.execute("TRUNCATE TABLE chat_messages CASCADE")
    await db.execute("TRUNCATE TABLE chat_threads CASCADE")


# === Database Connection Tests ===


@pytest.mark.asyncio
async def test_database_connection(db):
    """Test database connection pool."""
    assert db.pool is not None
    result = await db.fetch_val("SELECT 1")
    assert result == 1


@pytest.mark.asyncio
async def test_database_transaction(db):
    """Test transaction context manager."""
    async with db.transaction() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1


@pytest.mark.asyncio
async def test_database_execute(db):
    """Test execute method."""
    thread = await get_or_create_thread("telegram", "test_chat_1")
    result = await db.execute(
        "UPDATE chat_threads SET updated_at = NOW() WHERE id = $1",
        thread.id,
    )
    assert "UPDATE" in result


# === Thread Operations Tests ===


@pytest.mark.asyncio
async def test_get_or_create_thread_new(db):
    """Test creating a new thread."""
    thread = await get_or_create_thread("telegram", "new_chat_123")
    assert thread.id is not None
    assert thread.platform == "telegram"
    assert thread.chat_id == "new_chat_123"
    assert thread.created_at is not None
    assert thread.updated_at is not None


@pytest.mark.asyncio
async def test_get_or_create_thread_existing(db):
    """Test getting an existing thread."""
    # Create thread
    thread1 = await get_or_create_thread("telegram", "existing_chat")

    # Get the same thread
    thread2 = await get_or_create_thread("telegram", "existing_chat")

    # Should be the same thread
    assert thread1.id == thread2.id
    assert thread1.chat_id == thread2.chat_id


@pytest.mark.asyncio
async def test_update_thread(db):
    """Test updating thread timestamp."""
    thread = await get_or_create_thread("telegram", "update_test")
    original_updated_at = thread.updated_at

    # Wait a bit and update
    await asyncio.sleep(0.1)
    updated_thread = await update_thread(thread.id)

    # Timestamp should be newer
    assert updated_thread.updated_at >= original_updated_at


@pytest.mark.asyncio
async def test_get_thread_by_chat_id(db):
    """Test fetching thread by platform and chat_id."""
    await get_or_create_thread("telegram", "fetch_test")
    thread = await get_thread_by_chat_id("telegram", "fetch_test")
    assert thread is not None
    assert thread.chat_id == "fetch_test"

    # Non-existent thread
    thread = await get_thread_by_chat_id("telegram", "nonexistent")
    assert thread is None


# === Message Operations Tests ===


@pytest.mark.asyncio
async def test_insert_message(db):
    """Test inserting a message."""
    thread = await get_or_create_thread("telegram", "msg_test")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Hello, world!",
        author_user_id="user_123",
        platform_message_id="msg_456",
        raw_payload={"foo": "bar"},
    )

    assert message.id is not None
    assert message.thread_id == thread.id
    assert message.role == MessageRole.USER
    assert message.text == "Hello, world!"
    assert message.author_user_id == "user_123"
    assert message.platform_message_id == "msg_456"
    assert message.raw_payload == {"foo": "bar"}


@pytest.mark.asyncio
async def test_fetch_recent_messages(db):
    """Test fetching recent messages."""
    thread = await get_or_create_thread("telegram", "recent_msgs")

    # Insert multiple messages
    for i in range(5):
        await insert_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            text=f"Message {i}",
        )

    messages = await fetch_recent_messages(thread.id, limit=3)
    assert len(messages) == 3
    # Should be in reverse chronological order
    assert "Message 4" in messages[0].text


@pytest.mark.asyncio
async def test_get_message_by_id(db):
    """Test fetching message by ID."""
    thread = await get_or_create_thread("telegram", "get_msg")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.ASSISTANT,
        text="Test message",
    )

    fetched = await get_message_by_id(message.id)
    assert fetched is not None
    assert fetched.id == message.id
    assert fetched.text == "Test message"


@pytest.mark.asyncio
async def test_get_message_by_platform_id(db):
    """Test fetching message by platform message ID."""
    thread = await get_or_create_thread("telegram", "platform_msg")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Platform test",
        platform_message_id="platform_123",
    )

    fetched = await get_message_by_platform_id(thread.id, "platform_123")
    assert fetched is not None
    assert fetched.id == message.id


# === Artifact Operations Tests ===


@pytest.mark.asyncio
async def test_store_artifact(db):
    """Test storing an artifact."""
    thread = await get_or_create_thread("telegram", "artifact_test")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Message with artifact",
    )

    artifact = await store_artifact(
        message_id=message.id,
        kind=ArtifactKind.VOICE_TRANSCRIPT,
        content_json={"text": "Transcribed text", "confidence": 0.95},
        uri="s3://bucket/audio.mp3",
    )

    assert artifact.id is not None
    assert artifact.message_id == message.id
    assert artifact.kind == ArtifactKind.VOICE_TRANSCRIPT
    assert artifact.content_json["text"] == "Transcribed text"
    assert artifact.uri == "s3://bucket/audio.mp3"


@pytest.mark.asyncio
async def test_get_artifacts_for_message(db):
    """Test fetching artifacts for a message."""
    thread = await get_or_create_thread("telegram", "multi_artifacts")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Message with multiple artifacts",
    )

    # Store multiple artifacts
    await store_artifact(
        message_id=message.id,
        kind=ArtifactKind.VOICE_TRANSCRIPT,
        content_json={"text": "Audio"},
    )
    await store_artifact(
        message_id=message.id,
        kind=ArtifactKind.IMAGE_JSON,
        content_json={"objects": ["cat", "dog"]},
    )

    artifacts = await get_artifacts_for_message(message.id)
    assert len(artifacts) == 2


@pytest.mark.asyncio
async def test_update_artifact(db):
    """Test updating artifact content."""
    thread = await get_or_create_thread("telegram", "update_artifact")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Message",
    )
    artifact = await store_artifact(
        message_id=message.id,
        kind=ArtifactKind.OCR_TEXT,
        content_json={"text": "Original"},
    )

    updated = await update_artifact(
        artifact.id,
        content_json={"text": "Updated", "confidence": 0.99},
    )

    assert updated.content_json["text"] == "Updated"
    assert updated.content_json["confidence"] == 0.99


# === Job Operations Tests ===


@pytest.mark.asyncio
async def test_enqueue_job(db):
    """Test enqueuing a job."""
    thread = await get_or_create_thread("telegram", "job_test")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger message",
    )

    job = await enqueue_job(
        thread_id=thread.id,
        trigger_message_id=message.id,
        mode=JobMode.CLASSIFY,
        payload_json={"intent": "question"},
    )

    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.mode == JobMode.CLASSIFY
    assert job.payload_json["intent"] == "question"


@pytest.mark.asyncio
async def test_poll_pending_jobs(db):
    """Test polling for pending jobs."""
    thread = await get_or_create_thread("telegram", "poll_jobs")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )

    # Enqueue multiple jobs
    await enqueue_job(thread.id, message.id, JobMode.CLASSIFY)
    await enqueue_job(thread.id, message.id, JobMode.PLAN)

    jobs = await poll_pending_jobs(limit=10)
    assert len(jobs) >= 2


@pytest.mark.asyncio
async def test_update_job_status(db):
    """Test updating job status."""
    thread = await get_or_create_thread("telegram", "job_status")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)

    started = datetime.utcnow()
    updated = await update_job_status(
        job.id,
        JobStatus.RUNNING,
        started_at=started,
    )

    assert updated.status == JobStatus.RUNNING
    assert updated.started_at is not None


@pytest.mark.asyncio
async def test_cancel_pending_jobs_for_thread(db):
    """Test canceling pending jobs for a thread."""
    thread = await get_or_create_thread("telegram", "cancel_jobs")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )

    # Enqueue jobs
    job1 = await enqueue_job(thread.id, message.id, JobMode.CLASSIFY)
    job2 = await enqueue_job(thread.id, message.id, JobMode.PLAN)

    # Cancel all pending jobs
    await cancel_pending_jobs_for_thread(thread.id)

    # Check jobs are canceled
    updated1 = await get_job_by_id(job1.id)
    updated2 = await get_job_by_id(job2.id)

    assert updated1.status == JobStatus.CANCELED
    assert updated2.status == JobStatus.CANCELED


# === Approval Operations Tests ===


@pytest.mark.asyncio
async def test_create_approval(db):
    """Test creating an approval."""
    thread = await get_or_create_thread("telegram", "approval_test")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)

    approval = await create_approval(
        thread_id=thread.id,
        job_id=job.id,
        proposal_text="Deploy to production?",
    )

    assert approval.id is not None
    assert approval.status == ApprovalStatus.PENDING
    assert approval.proposal_text == "Deploy to production?"


@pytest.mark.asyncio
async def test_resolve_approval(db):
    """Test resolving an approval."""
    thread = await get_or_create_thread("telegram", "resolve_approval")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)
    approval = await create_approval(thread.id, job.id, "Approve this?")

    resolved = await resolve_approval(approval.id, ApprovalStatus.APPROVED)

    assert resolved.status == ApprovalStatus.APPROVED
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_supersede_pending_approvals(db):
    """Test superseding pending approvals."""
    thread = await get_or_create_thread("telegram", "supersede_approvals")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)
    approval = await create_approval(thread.id, job.id, "Old approval")

    # Supersede all pending approvals
    await supersede_pending_approvals(thread.id)

    # Check approval is superseded
    updated = await check_approval_status(approval.id)
    assert updated.status == ApprovalStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_get_pending_approval_for_job(db):
    """Test fetching pending approval for a job."""
    thread = await get_or_create_thread("telegram", "pending_approval")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)
    approval = await create_approval(thread.id, job.id, "Pending")

    fetched = await get_pending_approval_for_job(job.id)
    assert fetched is not None
    assert fetched.id == approval.id


# === Token Ledger Tests ===


@pytest.mark.asyncio
async def test_log_tokens(db):
    """Test logging token usage."""
    entry = await log_tokens(
        scope=TokenScope.REACTIVE,
        provider="anthropic",
        tokens_input=100,
        tokens_output=50,
        meta_json={"model": "claude-3-sonnet", "job_id": "abc123"},
    )

    assert entry.id is not None
    assert entry.scope == TokenScope.REACTIVE
    assert entry.provider == "anthropic"
    assert entry.tokens_input == 100
    assert entry.tokens_output == 50
    assert entry.tokens_total == 150


@pytest.mark.asyncio
async def test_get_daily_token_usage(db):
    """Test getting daily token usage."""
    today = date.today()

    # Log some tokens
    await log_tokens(TokenScope.PROACTIVE, "anthropic", 100, 50)
    await log_tokens(TokenScope.REACTIVE, "anthropic", 200, 100)

    usage = await get_daily_token_usage(today)
    assert len(usage) >= 2


@pytest.mark.asyncio
async def test_get_token_stats(db):
    """Test getting token statistics."""
    # Log tokens
    await log_tokens(TokenScope.PROACTIVE, "anthropic", 100, 50)
    await log_tokens(TokenScope.REACTIVE, "openai", 200, 100)

    stats = await get_token_stats(days_back=1)
    assert "by_scope" in stats
    assert "by_provider" in stats
    assert "period_start" in stats
    assert "period_end" in stats


# === Deployment Operations Tests ===


@pytest.mark.asyncio
async def test_create_deployment(db):
    """Test creating a deployment."""
    deployment = await create_deployment(
        git_sha="abc123def456",
        branch="main",
    )

    assert deployment.id is not None
    assert deployment.git_sha == "abc123def456"
    assert deployment.branch == "main"
    assert deployment.status == DeploymentStatus.BUILDING


@pytest.mark.asyncio
async def test_update_deployment_status(db):
    """Test updating deployment status."""
    deployment = await create_deployment("sha123", "develop")

    updated = await update_deployment_status(
        deployment.id,
        DeploymentStatus.HEALTHY,
        report_text="Deployment successful",
    )

    assert updated.status == DeploymentStatus.HEALTHY
    assert updated.finished_at is not None
    assert updated.report_text == "Deployment successful"


@pytest.mark.asyncio
async def test_get_latest_deployment(db):
    """Test getting the latest deployment."""
    await create_deployment("sha1", "main")
    await create_deployment("sha2", "develop")

    latest = await get_latest_deployment()
    assert latest is not None
    assert latest.git_sha == "sha2"  # Most recent


@pytest.mark.asyncio
async def test_get_recent_deployments(db):
    """Test getting recent deployments."""
    await create_deployment("sha1", "main")
    await create_deployment("sha2", "develop")
    await create_deployment("sha3", "feature")

    deployments = await get_recent_deployments(limit=2)
    assert len(deployments) == 2


# === Error Handling Tests ===


@pytest.mark.asyncio
async def test_update_nonexistent_thread(db):
    """Test updating a non-existent thread."""
    with pytest.raises(ValueError, match="Thread not found"):
        await update_thread(uuid4())


@pytest.mark.asyncio
async def test_update_nonexistent_job(db):
    """Test updating a non-existent job."""
    with pytest.raises(ValueError, match="Job not found"):
        await update_job_status(uuid4(), JobStatus.DONE)


@pytest.mark.asyncio
async def test_invalid_approval_status(db):
    """Test resolving approval with invalid status."""
    thread = await get_or_create_thread("telegram", "invalid_approval")
    message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Trigger",
    )
    job = await enqueue_job(thread.id, message.id, JobMode.EXECUTE)
    approval = await create_approval(thread.id, job.id, "Test")

    with pytest.raises(ValueError, match="Invalid approval status"):
        await resolve_approval(approval.id, ApprovalStatus.PENDING)
