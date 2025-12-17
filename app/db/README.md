# Database Layer - Server Agent vNext

This directory contains the complete async database layer for the Server Agent vNext project, built with asyncpg for high-performance PostgreSQL operations.

## Architecture

```
app/db/
├── __init__.py       # Database connection manager with pooling
├── models.py         # Pydantic models for all tables
├── queries.py        # SQL query constants
├── threads.py        # Thread operations
├── messages.py       # Message operations
├── artifacts.py      # Artifact operations
├── jobs.py           # Job operations
├── approvals.py      # Approval operations
├── tokens.py         # Token ledger operations
└── deployments.py    # Deployment operations
```

## Quick Start

### 1. Initialize Database Connection

```python
from app.db import init_db

# Initialize with connection string
db = init_db("postgresql://user:pass@localhost/dbname")
await db.connect()

# Close when done
await db.disconnect()
```

### 2. Use Operations

```python
from app.db.threads import get_or_create_thread
from app.db.messages import insert_message
from app.db.models import MessageRole

# Get or create thread
thread = await get_or_create_thread("telegram", "chat_123")

# Insert message
message = await insert_message(
    thread_id=thread.id,
    role=MessageRole.USER,
    text="Hello!",
    author_user_id="user_456",
)
```

## Core Components

### Database Manager (`__init__.py`)

Provides connection pooling and transaction management:

```python
from app.db import get_db

db = get_db()

# Execute queries
await db.execute("UPDATE ...")
row = await db.fetch_one("SELECT ...")
rows = await db.fetch_all("SELECT ...")
value = await db.fetch_val("SELECT COUNT(*)")

# Use transactions
async with db.transaction() as conn:
    await conn.execute("INSERT ...")
    await conn.execute("UPDATE ...")
```

**Connection Pool Settings:**
- Min size: 2 connections
- Max size: 10 connections
- Command timeout: 60 seconds

### Models (`models.py`)

Pydantic models for type safety:

**Enums:**
- `MessageRole`: USER, ASSISTANT, SYSTEM
- `ArtifactKind`: VOICE_TRANSCRIPT, IMAGE_JSON, OCR_TEXT, FILE_META, TOOL_RESULT
- `JobStatus`: QUEUED, RUNNING, DONE, FAILED, CANCELED
- `JobMode`: CLASSIFY, PLAN, EXECUTE, ANSWER
- `ApprovalStatus`: PENDING, APPROVED, REJECTED, SUPERSEDED
- `TokenScope`: PROACTIVE, REACTIVE
- `DeploymentStatus`: BUILDING, TESTING, DEPLOYING, HEALTHY, ROLLED_BACK, FAILED

**Models:**
- `ChatThread`: Thread tracking
- `ChatMessage`: Messages in threads
- `MessageArtifact`: Attachments and metadata
- `ReactiveJob`: Background jobs
- `Approval`: Approval requests
- `TokenLedger`: Token usage tracking
- `Deployment`: Deployment tracking

### Operations Modules

#### Threads (`threads.py`)

```python
from app.db.threads import get_or_create_thread, update_thread

# Get or create thread (idempotent)
thread = await get_or_create_thread("telegram", "chat_id")

# Update thread timestamp
thread = await update_thread(thread_id)
```

#### Messages (`messages.py`)

```python
from app.db.messages import insert_message, fetch_recent_messages

# Insert message
message = await insert_message(
    thread_id=thread.id,
    role=MessageRole.USER,
    text="Hello",
)

# Fetch recent messages
messages = await fetch_recent_messages(thread.id, limit=30)
```

#### Artifacts (`artifacts.py`)

```python
from app.db.artifacts import store_artifact, get_artifacts_for_message
from app.db.models import ArtifactKind

# Store artifact
artifact = await store_artifact(
    message_id=message.id,
    kind=ArtifactKind.VOICE_TRANSCRIPT,
    content_json={"text": "Transcribed text"},
    uri="s3://bucket/audio.mp3",
)

# Get all artifacts for message
artifacts = await get_artifacts_for_message(message.id)
```

#### Jobs (`jobs.py`)

```python
from app.db.jobs import enqueue_job, poll_pending_jobs, update_job_status
from app.db.models import JobMode, JobStatus

# Enqueue job
job = await enqueue_job(
    thread_id=thread.id,
    trigger_message_id=message.id,
    mode=JobMode.CLASSIFY,
)

# Poll for pending jobs
jobs = await poll_pending_jobs(limit=10)

# Update job status
job = await update_job_status(
    job.id,
    JobStatus.RUNNING,
    started_at=datetime.utcnow(),
)
```

#### Approvals (`approvals.py`)

```python
from app.db.approvals import create_approval, resolve_approval
from app.db.models import ApprovalStatus

# Create approval
approval = await create_approval(
    thread_id=thread.id,
    job_id=job.id,
    proposal_text="Deploy to production?",
)

# Resolve approval
approval = await resolve_approval(
    approval.id,
    ApprovalStatus.APPROVED,
)
```

#### Tokens (`tokens.py`)

```python
from app.db.tokens import log_tokens, get_token_stats
from app.db.models import TokenScope

# Log token usage
entry = await log_tokens(
    scope=TokenScope.REACTIVE,
    provider="anthropic",
    tokens_input=100,
    tokens_output=50,
    meta_json={"model": "claude-3-sonnet"},
)

# Get token statistics
stats = await get_token_stats(days_back=7)
```

#### Deployments (`deployments.py`)

```python
from app.db.deployments import create_deployment, update_deployment_status
from app.db.models import DeploymentStatus

# Create deployment
deployment = await create_deployment(
    git_sha="abc123",
    branch="main",
)

# Update deployment status
deployment = await update_deployment_status(
    deployment.id,
    DeploymentStatus.HEALTHY,
    report_text="Deployed successfully",
)
```

## Database Schema

See `/Users/maksimbozhko/Development/server-agent/database/schema.sql` for the complete schema.

### Key Tables

**chat_threads**
- Tracks conversation threads by platform and chat_id
- Unique index on (platform, chat_id)
- Auto-updates `updated_at` on changes

**chat_messages**
- Messages in threads with role (user/assistant/system)
- References thread_id (cascading delete)
- Optional platform_message_id for deduplication

**message_artifacts**
- Attachments and processed data for messages
- Kind: voice_transcript, image_json, ocr_text, etc.
- Content stored as JSONB, optional URI for files

**reactive_jobs**
- Background processing jobs
- Status: queued → running → done/failed/canceled
- Mode: classify, plan, execute, answer

**approvals**
- Approval requests for jobs
- Status: pending → approved/rejected/superseded

**token_ledger**
- Token usage tracking by scope and provider
- Tracks input, output, and total tokens

**deployments**
- Deployment tracking with git SHA and branch
- Status: building → testing → deploying → healthy/failed

## Testing

Run tests with pytest:

```bash
# Run all database tests
pytest tests/test_db.py -v

# Run with coverage
pytest tests/test_db.py --cov=app/db --cov-report=html

# Run specific test
pytest tests/test_db.py::test_get_or_create_thread -v
```

**Test Database Setup:**

Set the test database URL in environment:

```bash
export TEST_DATABASE_URL="postgresql://localhost/server_agent_test"
```

Or use the default: `postgresql://localhost/server_agent_test`

## Migrations

Apply the initial migration:

```bash
psql -d your_database -f database/migrations/001_initial.sql
```

The migration includes:
- All table definitions
- Indexes for performance
- Triggers for auto-updating timestamps
- Version tracking in `schema_migrations` table

## Best Practices

1. **Always use connection pool** - Never create direct connections
2. **Use transactions for multi-step operations** - Ensure atomicity
3. **Handle UUID types properly** - Use `uuid.UUID` from Python's uuid module
4. **Use enums for status fields** - Ensures type safety
5. **Log errors with context** - All operations include logging
6. **Clean up test data** - Use pytest fixtures for cleanup

## Error Handling

All operations raise exceptions on errors:

```python
try:
    thread = await get_or_create_thread("telegram", "chat_id")
except Exception as e:
    logger.error(f"Failed to get/create thread: {e}")
    # Handle error appropriately
```

Common exceptions:
- `RuntimeError`: Database not connected
- `ValueError`: Invalid input or resource not found
- `asyncpg.PostgresError`: Database-level errors

## Performance Considerations

1. **Connection pooling** - Reuses connections efficiently
2. **Prepared statements** - All queries use parameterized queries
3. **Indexes** - Strategic indexes on foreign keys and common queries
4. **JSONB fields** - Efficient storage and querying of JSON data
5. **Cascading deletes** - Automatic cleanup of related records

## Future Enhancements

- [ ] Add query result caching for read-heavy operations
- [ ] Implement connection pool monitoring
- [ ] Add database migration runner
- [ ] Create database backup utilities
- [ ] Add query performance logging
