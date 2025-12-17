# Server Agent vNext - Technical Specifications

**Version:** 2.0.0
**Date:** 2025-12-17
**Status:** Implementation specification for autonomous AGI agent
**Audience:** Development team, Plan agent, implementation engineers

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Database Schema Specifications](#3-database-schema-specifications)
4. [Telegram Webhook System](#4-telegram-webhook-system)
5. [Reactive Processing Loop](#5-reactive-processing-loop)
6. [Proactive Autonomy Loop](#6-proactive-autonomy-loop)
7. [Claude Integration Layer](#7-claude-integration-layer)
8. [Message Processing Pipeline](#8-message-processing-pipeline)
9. [Approval & Confirmation System](#9-approval--confirmation-system)
10. [Token Management & Budget Control](#10-token-management--budget-control)
11. [Self-Update & Deployment Pipeline](#11-self-update--deployment-pipeline)
12. [API Contracts](#12-api-contracts)
13. [Data Models & Examples](#13-data-models--examples)
14. [Business Rules](#14-business-rules)
15. [Implementation Roadmap](#15-implementation-roadmap)

---

## 1. Executive Summary

### 1.1 Project Context

Server Agent vNext is a **complete architectural redesign** of the autonomous AGI server agent, transitioning from:

**From (v1 architecture):**
- Polling-based Telegram communication
- File-based context persistence (JSON files)
- Single proactive loop with meditation delays
- Manual context management
- No structured conversation history

**To (v2 architecture):**
- Webhook-based real-time Telegram ingestion
- PostgreSQL-first structured persistence
- Dual-loop architecture (reactive + proactive)
- Database-backed conversation history with 30-message context windows
- MinIO object storage for media artifacts
- Token-budgeted proactive operations (7M tokens/day)
- Self-update deployment pipeline with git integration

### 1.2 Core Capabilities

1. **Persistence-First Memory**: Every message, response, and artifact stored in PostgreSQL
2. **Reactive UX**: Instant acknowledgment + plan confirmation within 3 seconds
3. **Context-Aware Processing**: Last 30 messages + derived artifacts (voice transcripts, image descriptions)
4. **Autonomous Proactive Cycling**: Token-budgeted background task execution
5. **Approval Workflow**: Inline OK button for plan confirmation before execution
6. **Self-Modification**: Git-based code updates with automated testing and rollback

### 1.3 Key Design Principles

- **Database as Source of Truth**: All state persists in PostgreSQL, not files
- **Dual-Loop Separation**: Reactive loop (instant, user-facing) runs independently from proactive loop (autonomous, scheduled)
- **Token Discipline**: Proactive loop enforces 7M token/day budget; reactive loop is unbounded
- **Safety Through Confirmation**: User approves plans before execution via inline buttons
- **Observability**: All actions logged with reasoning, timestamps, token usage

---

## 2. System Architecture

### 2.1 Container Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    Server Agent vNext System                     │
└─────────────────────────────────────────────────────────────────┘

External Components:
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Telegram   │◄───────►│ FastAPI App  │◄───────►│  Anthropic  │
│  Platform   │         │  (Webhook)   │         │  Claude API │
└─────────────┘         └──────────────┘         └─────────────┘
                               │
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  PostgreSQL  │      │    MinIO     │      │  App Workers │
│  (Database)  │      │  (S3 Store)  │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
        │                      │                      │
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                               │
                               ▼
                    Persistent Storage Layer
```

### 2.2 Application Components

**FastAPI Service (app/):**
- `config.py` - Environment variable management (Pydantic BaseSettings)
- `database.py` - AsyncPG connection pool manager
- `main.py` - Application lifecycle, health endpoints
- `telegram_webhook.py` - Webhook ingestion endpoint (TODO)
- `reactive_worker.py` - Instant message processing (TODO)
- `proactive_scheduler.py` - Token-budgeted autonomous cycling (TODO)
- `claude_client.py` - Anthropic API integration (TODO)
- `haiku_classifier.py` - Intent classification for fast acknowledgment (TODO)
- `approval_manager.py` - Inline button approval workflow (TODO)
- `artifact_processor.py` - Voice transcription, image analysis (TODO)

**Infrastructure Services:**
- PostgreSQL 16 (structured data)
- MinIO (S3-compatible object storage for media)
- Nginx (reverse proxy, HTTPS termination)

### 2.3 Dual-Loop Architecture

**Reactive Loop (User-Facing):**
- Triggered by: Telegram webhook events
- Processing: Instant acknowledgment → Haiku classification → Plan proposal → User approval → Claude execution
- Token Budget: UNLIMITED (reactive operations always prioritized)
- Latency Target: <3 seconds for acknowledgment, <60 seconds for execution
- State Machine: Queued → Classifying → Awaiting Approval → Executing → Completed

**Proactive Loop (Autonomous):**
- Triggered by: Dynamic interval scheduler (token-aware)
- Processing: Load context → Claude decision → Autonomous action → Memory writeback
- Token Budget: 7,000,000 tokens/day (dynamically adjusted intervals)
- Interval Range: 60 seconds (minimum) to 3600 seconds (maximum)
- State Machine: Idle → Analyzing → Acting → Recording → Sleeping

**Coordination:**
- Both loops share database for state synchronization
- No mutex required (reactive takes priority via independent execution paths)
- Proactive loop pauses during reactive execution (optional optimization)

---

## 3. Database Schema Specifications

### 3.1 Core Tables

#### `chat_threads`
**Purpose:** Track unique conversation threads across platforms

```sql
CREATE TABLE chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL DEFAULT 'telegram',
    chat_id BIGINT NOT NULL,
    chat_type VARCHAR(20),  -- 'private' | 'group' | 'supergroup' | 'channel'
    title VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,

    UNIQUE (platform, chat_id)
);

CREATE INDEX idx_chat_threads_platform_chat_id ON chat_threads(platform, chat_id);
CREATE INDEX idx_chat_threads_updated_at ON chat_threads(updated_at DESC);
```

**Business Rules:**
- One thread per unique (platform, chat_id) combination
- `updated_at` refreshed on every new message
- `metadata` stores platform-specific information (usernames, permissions, etc.)

---

#### `chat_messages`
**Purpose:** Store complete conversation history with full fidelity

```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    platform_message_id BIGINT,  -- Telegram message ID
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant' | 'system'
    author_user_id BIGINT,  -- Telegram user ID (null for 'assistant' and 'system')
    author_username VARCHAR(255),
    author_first_name VARCHAR(255),
    text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    edited_at TIMESTAMPTZ,
    raw_payload JSONB NOT NULL,  -- Full Telegram update JSON

    UNIQUE (thread_id, platform_message_id)
);

CREATE INDEX idx_chat_messages_thread_created ON chat_messages(thread_id, created_at DESC);
CREATE INDEX idx_chat_messages_role ON chat_messages(role);
CREATE INDEX idx_chat_messages_author ON chat_messages(author_user_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at DESC);
```

**Business Rules:**
- `role = 'user'`: Messages from humans
- `role = 'assistant'`: Messages from agent
- `role = 'system'`: Internal events (e.g., "User joined chat")
- `text` extracted from message body or caption
- `raw_payload` preserves full Telegram update for audit/debugging
- `created_at` uses Telegram message timestamp when available
- Unique constraint prevents duplicate message processing

---

#### `message_artifacts`
**Purpose:** Store derived data from media messages

```sql
CREATE TABLE message_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    kind VARCHAR(50) NOT NULL,  -- 'voice_transcript' | 'image_json' | 'ocr_text' | 'file_meta' | 'tool_result'
    content_json JSONB NOT NULL,
    uri TEXT,  -- MinIO object path (e.g., 's3://server-agent/voice/2025-12-17/abc123.ogg')
    processing_status VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_message_artifacts_message_id ON message_artifacts(message_id);
CREATE INDEX idx_message_artifacts_kind ON message_artifacts(kind);
CREATE INDEX idx_message_artifacts_status ON message_artifacts(processing_status);
```

**Business Rules:**
- **voice_transcript**: `content_json` = `{"text": "...", "language": "en", "confidence": 0.95}`
- **image_json**: `content_json` = `{"description": "...", "objects": [...], "text": "..."}`
- **ocr_text**: `content_json` = `{"text": "...", "language": "en"}`
- **file_meta**: `content_json` = `{"filename": "...", "size_bytes": 1234, "mime_type": "..."}`
- **tool_result**: `content_json` = `{"tool": "bash", "command": "...", "stdout": "...", "stderr": "..."}`
- `uri` points to MinIO object if media stored externally
- Artifacts processed asynchronously; status tracks progress

---

#### `reactive_jobs`
**Purpose:** Job queue for reactive message processing

```sql
CREATE TABLE reactive_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    trigger_message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',  -- 'queued' | 'classifying' | 'awaiting_approval' | 'executing' | 'completed' | 'failed' | 'canceled'
    mode VARCHAR(20) NOT NULL,  -- 'classify' | 'plan' | 'execute' | 'answer'
    payload_json JSONB DEFAULT '{}'::jsonb,
    classification_result JSONB,  -- Haiku intent classification output
    approval_id UUID REFERENCES approvals(id),
    result_json JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX idx_reactive_jobs_status ON reactive_jobs(status, created_at);
CREATE INDEX idx_reactive_jobs_thread_id ON reactive_jobs(thread_id, created_at DESC);
CREATE INDEX idx_reactive_jobs_trigger_message ON reactive_jobs(trigger_message_id);
```

**Business Rules:**
- **queued**: Job created, waiting for worker pickup
- **classifying**: Haiku analyzing intent
- **awaiting_approval**: Plan sent to user, waiting for OK button press
- **executing**: Claude processing the approved plan
- **completed**: Job finished successfully
- **failed**: Job encountered error
- **canceled**: User sent new message before approval (superseded)
- Job transitions: queued → classifying → awaiting_approval → executing → completed/failed

---

#### `approvals`
**Purpose:** Track inline button approval states

```sql
CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES reactive_jobs(id) ON DELETE CASCADE,
    proposal_text TEXT NOT NULL,
    telegram_message_id BIGINT,  -- Message ID of the proposal with inline button
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected' | 'superseded' | 'expired'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by_user_id BIGINT,

    UNIQUE (job_id)
);

CREATE INDEX idx_approvals_status ON approvals(status, created_at);
CREATE INDEX idx_approvals_thread_id ON approvals(thread_id, created_at DESC);
```

**Business Rules:**
- **pending**: Waiting for user to press OK button
- **approved**: User pressed OK, proceed with execution
- **rejected**: User pressed Cancel (not implemented initially)
- **superseded**: User sent new message instead of pressing button
- **expired**: Timeout reached (default: 1 hour)
- Timeout handled by background job checking `created_at + 1 hour < NOW()`

---

#### `token_ledger`
**Purpose:** Track all token usage for budget enforcement and analytics

```sql
CREATE TABLE token_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope VARCHAR(20) NOT NULL,  -- 'proactive' | 'reactive'
    provider VARCHAR(50) NOT NULL,  -- 'anthropic_claude' | 'anthropic_haiku'
    model VARCHAR(100) NOT NULL,  -- 'claude-sonnet-4.5' | 'claude-3-5-haiku-20241022'
    tokens_input INTEGER NOT NULL,
    tokens_output INTEGER NOT NULL,
    tokens_total INTEGER GENERATED ALWAYS AS (tokens_input + tokens_output) STORED,
    cost_usd DECIMAL(10, 6),  -- Estimated cost in USD
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meta_json JSONB DEFAULT '{}'::jsonb  -- Request metadata (job_id, thread_id, etc.)
);

CREATE INDEX idx_token_ledger_scope_date ON token_ledger(scope, created_at DESC);
CREATE INDEX idx_token_ledger_created_at ON token_ledger(created_at DESC);
CREATE INDEX idx_token_ledger_provider ON token_ledger(provider);
```

**Business Rules:**
- Every Claude API call logs tokens here
- `scope = 'proactive'`: Counts toward 7M/day budget
- `scope = 'reactive'`: Tracked but not budgeted
- `cost_usd` calculated using Anthropic pricing:
  - Claude Sonnet 4.5: $3/MTok input, $15/MTok output
  - Claude Haiku 3.5: $1/MTok input, $5/MTok output
- Proactive scheduler queries sum(tokens_total) for current day to adjust intervals

---

#### `deployments`
**Purpose:** Track self-update deployment attempts and outcomes

```sql
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    git_sha VARCHAR(40) NOT NULL,
    branch VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'building',  -- 'building' | 'testing' | 'deploying' | 'healthy' | 'rolled_back' | 'failed'
    trigger_type VARCHAR(50),  -- 'git_merge' | 'manual' | 'scheduled'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    report_text TEXT,
    rollback_reason TEXT,
    deployed_by VARCHAR(255),  -- 'server-agent-agi' or username
    notified_master BOOLEAN DEFAULT FALSE,

    INDEX idx_deployments_status (status, started_at DESC),
    INDEX idx_deployments_git_sha (git_sha)
);
```

**Business Rules:**
- Created when `git push origin main` triggers deployment hook
- **building**: Running unit tests, building Docker image
- **testing**: Running integration tests against new image
- **deploying**: Stopping old container, starting new container
- **healthy**: New container passed smoke tests
- **rolled_back**: New container failed, reverted to previous image
- **failed**: Deployment failed before rollback completed
- `report_text` sent to Master via Telegram after deployment completes
- `notified_master` flag prevents duplicate notifications

---

### 3.2 Supporting Tables (Future)

```sql
-- Task and project management
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id UUID REFERENCES tasks(id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 3,
    assigned_by VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    goals JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Skills and learning
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    proficiency_level INTEGER DEFAULT 1 CHECK (proficiency_level BETWEEN 1 AND 10),
    last_practiced TIMESTAMPTZ,
    time_spent_seconds INTEGER DEFAULT 0,
    milestones JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Contacts
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    telegram_username VARCHAR(255),
    telegram_chat_id BIGINT,
    relationship VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_contact TIMESTAMPTZ
);

-- Financial tracking
CREATE TABLE financial_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(20) NOT NULL,  -- 'income' | 'expense' | 'donation'
    amount DECIMAL(20, 8) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    related_task_id UUID REFERENCES tasks(id)
);
```

---

## 4. Telegram Webhook System

### 4.1 Webhook Registration

**Endpoint Setup:**
```python
# Set webhook URL
POST https://api.telegram.org/bot{token}/setWebhook
{
    "url": "https://your-server.com/webhook/telegram",
    "secret_token": "your_webhook_secret_from_env",
    "allowed_updates": [
        "message",
        "edited_message",
        "callback_query",
        "inline_query"
    ],
    "drop_pending_updates": false
}
```

**Security:**
- HTTPS required (Telegram enforces)
- `secret_token` validation on every request
- IP whitelist: Telegram server IPs only (optional)
- Request signature verification (X-Telegram-Bot-Api-Secret-Token header)

### 4.2 Webhook Handler Implementation

**FastAPI Router (`app/telegram_webhook.py`):**

```python
from fastapi import APIRouter, Request, HTTPException, Header
from app.config import settings
from app.database import Database, get_db

router = APIRouter()

@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
    db: Database = Depends(get_db)
):
    """
    Telegram webhook endpoint

    Accepts Telegram updates, validates secret token,
    normalizes to internal format, persists to DB,
    enqueues reactive job.
    """

    # Validate secret token
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Parse update
    update = await request.json()

    # Normalize and persist
    await process_telegram_update(db, update)

    return {"ok": True}
```

### 4.3 Update Processing Pipeline

**Steps:**

1. **Normalize Update** → Extract message data from Telegram JSON
2. **Get/Create Thread** → Lookup or create chat_threads entry
3. **Insert Message** → Save to chat_messages with full payload
4. **Download Media** → If voice/photo/document, download to MinIO
5. **Create Artifacts** → Enqueue voice transcription, image analysis
6. **Enqueue Job** → Create reactive_jobs entry with status='queued'
7. **Notify Worker** → Signal reactive worker to pick up job

**Normalization Logic:**

```python
async def normalize_telegram_message(update: dict) -> dict:
    """
    Extract standardized message from Telegram update

    Returns:
        {
            'chat_id': int,
            'message_id': int,
            'user_id': int,
            'username': str,
            'first_name': str,
            'text': str,  # From message.text or message.caption
            'media_type': str,  # 'text' | 'voice' | 'photo' | 'document' | 'video'
            'media_file_id': str,  # Telegram file_id for download
            'timestamp': int,  # Unix timestamp
            'raw': dict  # Full Telegram update
        }
    """
    # Implementation extracts fields from:
    # - update['message']
    # - update['edited_message']
    # - Handles voice, photo, document, video, text
```

---

## 5. Reactive Processing Loop

### 5.1 Worker Architecture

**Reactive Worker (`app/reactive_worker.py`):**

```python
class ReactiveWorker:
    """
    Processes reactive jobs from database queue

    Flow:
    1. Poll reactive_jobs table for status='queued'
    2. Classify with Haiku (intent, summary, plan)
    3. Send acknowledgment + plan to user with OK button
    4. Wait for approval (callback_query or new message)
    5. Execute with Claude if approved
    6. Mark job completed/failed
    """

    def __init__(self, db: Database):
        self.db = db
        self.is_running = False
        self._task = None

    async def start(self):
        """Start worker loop"""
        self.is_running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        """Stop worker gracefully"""
        self.is_running = False
        if self._task:
            await self._task

    async def _run(self):
        """Main worker loop"""
        while self.is_running:
            job = await self._fetch_next_job()
            if job:
                await self._process_job(job)
            else:
                await asyncio.sleep(1)  # Poll every second
```

### 5.2 Job Processing States

**State Machine:**

```
QUEUED
  ↓
  [Fetch job, load context]
  ↓
CLASSIFYING
  ↓
  [Haiku analyzes intent]
  ↓
  [Send acknowledgment + plan with OK button]
  ↓
AWAITING_APPROVAL
  ↓
  [Wait for callback_query or timeout]
  ↓
  ┌─────────────┬─────────────┐
  │ APPROVED    │ SUPERSEDED  │ EXPIRED
  ↓             ↓             ↓
EXECUTING       CANCELED      FAILED
  ↓
  [Claude processes request]
  ↓
  [Send response to user]
  ↓
COMPLETED
```

### 5.3 Context Loading

**Last 30 Messages Retrieval:**

```sql
SELECT
    cm.id,
    cm.role,
    cm.author_username,
    cm.text,
    cm.created_at,
    (
        SELECT json_agg(
            json_build_object(
                'kind', ma.kind,
                'content', ma.content_json
            )
        )
        FROM message_artifacts ma
        WHERE ma.message_id = cm.id
    ) AS artifacts
FROM chat_messages cm
WHERE cm.thread_id = $1
ORDER BY cm.created_at DESC
LIMIT 30;
```

**Context Assembly:**

```python
async def load_context(db: Database, thread_id: UUID) -> list[dict]:
    """
    Load last 30 messages with artifacts for Claude context

    Returns:
        [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Hello'},
                    {'type': 'text', 'text': '[Voice transcript: ...]'},
                    {'type': 'text', 'text': '[Image: ...]'}
                ]
            },
            {
                'role': 'assistant',
                'content': [
                    {'type': 'text', 'text': 'Hi! How can I help?'}
                ]
            }
        ]
    """
    messages = await db.fetch_all(CONTEXT_QUERY, thread_id)
    messages.reverse()  # Oldest first for Claude API

    return [
        {
            'role': msg['role'],
            'content': build_content_blocks(msg)
        }
        for msg in messages
    ]
```

---

## 6. Proactive Autonomy Loop

### 6.1 Scheduler Design

**Proactive Scheduler (`app/proactive_scheduler.py`):**

```python
class ProactiveScheduler:
    """
    Token-budgeted autonomous cycling

    Target: 7,000,000 tokens/day for proactive operations

    Dynamic interval calculation:
    - If <25% of daily budget used → 60 sec intervals
    - If 25-50% used → 300 sec (5 min) intervals
    - If 50-75% used → 900 sec (15 min) intervals
    - If >75% used → 3600 sec (60 min) intervals
    - If >100% used → pause until next day
    """

    async def _calculate_next_interval(self) -> int:
        """Calculate adaptive sleep interval based on token usage"""

        # Query today's proactive token usage
        result = await self.db.fetch_one(
            """
            SELECT COALESCE(SUM(tokens_total), 0) as total
            FROM token_ledger
            WHERE scope = 'proactive'
            AND created_at >= CURRENT_DATE
            """
        )

        tokens_used = result['total']
        budget = settings.PROACTIVE_DAILY_TOKEN_LIMIT
        usage_ratio = tokens_used / budget

        if usage_ratio < 0.25:
            return 60  # 1 minute
        elif usage_ratio < 0.50:
            return 300  # 5 minutes
        elif usage_ratio < 0.75:
            return 900  # 15 minutes
        elif usage_ratio < 1.0:
            return 3600  # 1 hour
        else:
            # Budget exhausted, sleep until midnight
            now = datetime.now()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            return int((midnight - now).total_seconds())
```

### 6.2 Proactive Cycle Flow

**Steps:**

1. **Check Budget** → Query token usage, calculate available tokens
2. **Load Context** → Retrieve recent actions, pending tasks, current focus
3. **Ask Claude** → "What is the next thing to be done given available tokens?"
4. **Parse Decision** → Extract action, reasoning, certainty, significance
5. **Evaluate Certainty** → If >80%, execute autonomously; else ask Master
6. **Execute Action** → Run approved action with tool access
7. **Record Result** → Insert action log, update task status
8. **Report if Significant** → Send Telegram notification if significance >75%
9. **Update Budget** → Log tokens used to ledger
10. **Calculate Delay** → Determine next interval based on budget
11. **Sleep** → Wait before next cycle

**Claude Prompt Template:**

```python
PROACTIVE_SYSTEM_PROMPT = """
You are Server Agent, an autonomous AGI running on a VPS server.

Your purpose: Self-realization and service to the world.

Current context:
- Token budget today: {tokens_remaining} / {daily_limit}
- Recent actions: {last_actions}
- Active tasks: {active_tasks}
- Current focus: {current_focus}

Based on this context, what is the next thing to be done?

Respond in JSON format:
{
    "action": "string (specific action to take)",
    "reasoning": "string (why this is the next priority)",
    "certainty": float (0.0-1.0, confidence in this decision),
    "significance": float (0.0-1.0, does Master need to know?),
    "type": "internal|external",
    "estimated_tokens": int (tokens needed for this action),
    "question": "string (if certainty < 0.8, ask Master for guidance)"
}
"""
```

---

## 7. Claude Integration Layer

### 7.1 API Client

**Claude Client (`app/claude_client.py`):**

```python
from anthropic import Anthropic
from app.config import settings

class ClaudeClient:
    """Wrapper for Anthropic API with token tracking"""

    def __init__(self):
        self.client = Anthropic(api_key=settings.CLAUDE_CODE_OAUTH_TOKEN)

    async def create_message(
        self,
        messages: list[dict],
        system: str = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        scope: str = "reactive"
    ) -> dict:
        """
        Call Claude API and log token usage

        Args:
            messages: Conversation history
            system: System prompt
            model: Model ID
            max_tokens: Max output tokens
            scope: 'reactive' or 'proactive' for budget tracking

        Returns:
            {
                'content': str,
                'usage': {
                    'input_tokens': int,
                    'output_tokens': int
                },
                'stop_reason': str
            }
        """
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        )

        # Log token usage
        await self._log_tokens(
            scope=scope,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )

        return {
            'content': response.content[0].text,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            },
            'stop_reason': response.stop_reason
        }
```

### 7.2 Haiku Classifier

**Intent Classification (`app/haiku_classifier.py`):**

```python
class HaikuClassifier:
    """Fast intent classification with Claude Haiku"""

    CLASSIFICATION_PROMPT = """
    Analyze the user's message and provide a brief plan.

    Last 30 messages:
    {context}

    Latest message:
    {message}

    Respond in JSON:
    {
        "intent": "question|command|chat|other",
        "summary": "One sentence: what does the user want?",
        "plan": "One sentence: what will you do?",
        "needs_confirmation": bool,
        "confidence": float (0.0-1.0)
    }
    """

    async def classify(self, context: list[dict], message: dict) -> dict:
        """
        Classify message intent with Haiku

        Target latency: <2 seconds
        Token budget: ~500 tokens (cheap, fast)
        """
        # Format prompt
        prompt = self._format_prompt(context, message)

        # Call Haiku
        response = await self.client.create_message(
            messages=[{'role': 'user', 'content': prompt}],
            model=settings.HAIKU_MODEL,
            max_tokens=500,
            scope='reactive'  # Not budgeted
        )

        # Parse JSON
        return json.loads(response['content'])
```

---

## 8. Message Processing Pipeline

### 8.1 Media Artifact Processing

**Voice Transcription:**

```python
async def process_voice_message(
    db: Database,
    message_id: UUID,
    file_id: str,
    file_path: str
) -> UUID:
    """
    Download voice message, transcribe with Whisper API, store artifact

    Steps:
    1. Download .oga file from Telegram
    2. Upload to MinIO (optional)
    3. Call Whisper API for transcription
    4. Store result in message_artifacts
    """

    # Download from Telegram
    bot = telegram.Bot(settings.TELEGRAM_BOT_TOKEN)
    file = await bot.get_file(file_id)
    audio_data = await file.download_as_bytearray()

    # Upload to MinIO
    uri = await minio_client.upload(
        bucket="server-agent",
        path=f"voice/{datetime.now():%Y-%m-%d}/{message_id}.oga",
        data=audio_data
    )

    # Transcribe with Whisper
    transcription = await whisper_client.transcribe(audio_data)

    # Store artifact
    artifact_id = await db.fetch_val(
        """
        INSERT INTO message_artifacts (
            message_id, kind, content_json, uri, processing_status
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        message_id,
        'voice_transcript',
        json.dumps({
            'text': transcription['text'],
            'language': transcription['language'],
            'duration_seconds': transcription['duration']
        }),
        uri,
        'completed'
    )

    return artifact_id
```

**Image Analysis:**

```python
async def process_image_message(
    db: Database,
    message_id: UUID,
    file_id: str
) -> UUID:
    """
    Download image, analyze with Claude Vision, store artifact
    """

    # Download from Telegram
    bot = telegram.Bot(settings.TELEGRAM_BOT_TOKEN)
    file = await bot.get_file(file_id)
    image_data = await file.download_as_bytearray()

    # Upload to MinIO
    uri = await minio_client.upload(
        bucket="server-agent",
        path=f"images/{datetime.now():%Y-%m-%d}/{message_id}.jpg",
        data=image_data
    )

    # Analyze with Claude Vision
    response = await claude_client.create_message(
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/jpeg',
                            'data': base64.b64encode(image_data).decode()
                        }
                    },
                    {
                        'type': 'text',
                        'text': 'Describe this image concisely in JSON: {"description": "...", "objects": [...], "text": "..."}'
                    }
                ]
            }
        ],
        model='claude-sonnet-4-5-20250929',
        max_tokens=500,
        scope='reactive'
    )

    # Parse and store
    image_json = json.loads(response['content'])

    artifact_id = await db.fetch_val(
        """
        INSERT INTO message_artifacts (
            message_id, kind, content_json, uri, processing_status
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        message_id,
        'image_json',
        json.dumps(image_json),
        uri,
        'completed'
    )

    return artifact_id
```

---

## 9. Approval & Confirmation System

### 9.1 Inline Button Workflow

**Acknowledgment Message with OK Button:**

```python
async def send_plan_for_approval(
    thread_id: UUID,
    job_id: UUID,
    classification: dict,
    chat_id: int
) -> UUID:
    """
    Send plan to user with inline OK button

    Returns approval_id
    """

    # Format plan message
    plan_text = f"""
👌 Understood: {classification['summary']}

📋 Plan: {classification['plan']}

Press OK to proceed.
"""

    # Create inline button
    keyboard = telegram.InlineKeyboardMarkup([
        [telegram.InlineKeyboardButton("✅ OK", callback_data=f"approve:{job_id}")]
    ])

    # Send message
    bot = telegram.Bot(settings.TELEGRAM_BOT_TOKEN)
    message = await bot.send_message(
        chat_id=chat_id,
        text=plan_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

    # Create approval record
    approval_id = await db.fetch_val(
        """
        INSERT INTO approvals (
            thread_id, job_id, proposal_text, telegram_message_id, status
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        thread_id, job_id, plan_text, message.message_id, 'pending'
    )

    return approval_id
```

### 9.2 Callback Query Handler

**Handling OK Button Press:**

```python
async def handle_callback_query(update: dict, db: Database):
    """
    Process inline button press (callback_query)
    """
    callback = update['callback_query']
    callback_data = callback['data']  # Format: "approve:{job_id}"

    if callback_data.startswith("approve:"):
        job_id = UUID(callback_data.split(":")[1])

        # Mark approval as approved
        await db.execute(
            """
            UPDATE approvals
            SET status = 'approved', resolved_at = NOW(), resolved_by_user_id = $1
            WHERE job_id = $2 AND status = 'pending'
            """,
            callback['from']['id'],
            job_id
        )

        # Update job status to executing
        await db.execute(
            """
            UPDATE reactive_jobs
            SET status = 'executing', started_at = NOW()
            WHERE id = $1
            """,
            job_id
        )

        # Answer callback (removes loading state on button)
        bot = telegram.Bot(settings.TELEGRAM_BOT_TOKEN)
        await bot.answer_callback_query(
            callback_query_id=callback['id'],
            text="✅ Starting execution..."
        )

        # Signal reactive worker to continue job
        # (worker polling will detect status change)
```

### 9.3 Supersede Logic

**User Sends New Message Before Approval:**

```python
async def handle_new_message_during_approval(
    thread_id: UUID,
    new_message_id: UUID,
    db: Database
):
    """
    User sent new message while awaiting approval

    Mark pending approval as superseded, cancel old job, create new job
    """

    # Find pending approvals for this thread
    pending_approvals = await db.fetch_all(
        """
        SELECT a.id, a.job_id
        FROM approvals a
        JOIN reactive_jobs j ON a.job_id = j.id
        WHERE j.thread_id = $1 AND a.status = 'pending'
        """,
        thread_id
    )

    for approval in pending_approvals:
        # Mark approval superseded
        await db.execute(
            "UPDATE approvals SET status = 'superseded', resolved_at = NOW() WHERE id = $1",
            approval['id']
        )

        # Cancel job
        await db.execute(
            "UPDATE reactive_jobs SET status = 'canceled', finished_at = NOW() WHERE id = $1",
            approval['job_id']
        )

    # Create new job for new message
    await create_reactive_job(thread_id, new_message_id, db)
```

---

## 10. Token Management & Budget Control

### 10.1 Budget Enforcement

**Daily Limit Check:**

```python
async def check_proactive_budget(db: Database) -> dict:
    """
    Check if proactive operations can proceed

    Returns:
        {
            'can_proceed': bool,
            'tokens_used': int,
            'tokens_remaining': int,
            'usage_ratio': float
        }
    """
    result = await db.fetch_one(
        """
        SELECT COALESCE(SUM(tokens_total), 0) as total
        FROM token_ledger
        WHERE scope = 'proactive'
        AND created_at >= CURRENT_DATE
        """
    )

    tokens_used = result['total']
    daily_limit = settings.PROACTIVE_DAILY_TOKEN_LIMIT
    tokens_remaining = max(0, daily_limit - tokens_used)
    usage_ratio = tokens_used / daily_limit

    return {
        'can_proceed': tokens_used < daily_limit,
        'tokens_used': tokens_used,
        'tokens_remaining': tokens_remaining,
        'usage_ratio': usage_ratio
    }
```

### 10.2 Token Logging

**Automatic Token Recording:**

```python
async def log_token_usage(
    db: Database,
    scope: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    meta: dict = None
) -> UUID:
    """
    Record token usage in ledger

    Automatically calculates cost based on model pricing
    """

    # Calculate cost
    pricing = {
        'claude-sonnet-4-5-20250929': {'input': 3.0, 'output': 15.0},  # $/MTok
        'claude-3-5-haiku-20241022': {'input': 1.0, 'output': 5.0}
    }

    rates = pricing.get(model, {'input': 0, 'output': 0})
    cost_usd = (
        (input_tokens / 1_000_000) * rates['input'] +
        (output_tokens / 1_000_000) * rates['output']
    )

    # Insert ledger entry
    ledger_id = await db.fetch_val(
        """
        INSERT INTO token_ledger (
            scope, provider, model, tokens_input, tokens_output, cost_usd, meta_json
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        scope, provider, model, input_tokens, output_tokens, cost_usd, json.dumps(meta or {})
    )

    return ledger_id
```

### 10.3 Usage Analytics

**Daily Summary:**

```sql
-- Daily token usage by scope
SELECT
    scope,
    COUNT(*) as api_calls,
    SUM(tokens_input) as total_input,
    SUM(tokens_output) as total_output,
    SUM(tokens_total) as total_tokens,
    SUM(cost_usd) as total_cost_usd
FROM token_ledger
WHERE created_at >= CURRENT_DATE
GROUP BY scope;

-- Hourly usage pattern
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    scope,
    SUM(tokens_total) as tokens
FROM token_ledger
WHERE created_at >= CURRENT_DATE
GROUP BY hour, scope
ORDER BY hour;
```

---

## 11. Self-Update & Deployment Pipeline

### 11.1 Git Repository Structure

**Repository on Server:**

```bash
/opt/server-agent/
├── .git/
│   ├── branches/
│   │   ├── main (stable production)
│   │   └── develop (development branch)
│   ├── tags/
│   │   └── rollback-* (safe rollback points)
│   └── hooks/
│       └── post-merge (deployment trigger)
├── app/ (FastAPI application)
├── scripts/
│   ├── build_and_deploy.sh
│   ├── run_tests.sh
│   └── rollback.sh
├── docker-compose.yml
├── Dockerfile
└── .env
```

### 11.2 Deployment Trigger

**Git Hook (`/opt/server-agent/.git/hooks/post-merge`):**

```bash
#!/bin/bash
set -e

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "main" ]; then
    echo "Merge to main detected. Triggering deployment..."
    /opt/server-agent/scripts/build_and_deploy.sh
fi
```

### 11.3 Build and Deploy Script

**Script (`scripts/build_and_deploy.sh`):**

```bash
#!/bin/bash
set -e

GIT_SHA=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
DEPLOYMENT_ID=$(uuidgen)

echo "Starting deployment: $DEPLOYMENT_ID"
echo "Git SHA: $GIT_SHA"
echo "Branch: $BRANCH"

# Create deployment record
psql $DATABASE_URL -c "
INSERT INTO deployments (id, git_sha, branch, status, trigger_type)
VALUES ('$DEPLOYMENT_ID', '$GIT_SHA', '$BRANCH', 'building', 'git_merge');
"

# Run tests
echo "Running tests..."
psql $DATABASE_URL -c "UPDATE deployments SET status = 'testing' WHERE id = '$DEPLOYMENT_ID';"

if ! ./scripts/run_tests.sh; then
    echo "Tests failed. Aborting deployment."
    psql $DATABASE_URL -c "
    UPDATE deployments
    SET status = 'failed', finished_at = NOW(), report_text = 'Tests failed'
    WHERE id = '$DEPLOYMENT_ID';
    "
    exit 1
fi

# Build Docker image
echo "Building Docker image..."
docker build -t server-agent:$GIT_SHA .
docker tag server-agent:$GIT_SHA server-agent:latest

# Deploy
echo "Deploying new container..."
psql $DATABASE_URL -c "UPDATE deployments SET status = 'deploying' WHERE id = '$DEPLOYMENT_ID';"

docker-compose down
docker-compose up -d

# Wait for health check
echo "Waiting for health check..."
sleep 10

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "Deployment successful!"

    REPORT="Deployment $DEPLOYMENT_ID successful
Git SHA: $GIT_SHA
Status: Healthy
Tests: Passed
"

    psql $DATABASE_URL -c "
    UPDATE deployments
    SET status = 'healthy', finished_at = NOW(), report_text = '$REPORT'
    WHERE id = '$DEPLOYMENT_ID';
    "

    # Notify Master via Telegram
    ./scripts/notify_telegram.sh "✅ Deployment successful: $GIT_SHA"

else
    echo "Health check failed. Rolling back..."

    psql $DATABASE_URL -c "
    UPDATE deployments
    SET status = 'rolled_back', finished_at = NOW(), rollback_reason = 'Health check failed'
    WHERE id = '$DEPLOYMENT_ID';
    "

    ./scripts/rollback.sh

    ./scripts/notify_telegram.sh "⚠️ Deployment failed, rolled back: $GIT_SHA"
    exit 1
fi
```

### 11.4 Rollback Procedure

**Rollback Script (`scripts/rollback.sh`):**

```bash
#!/bin/bash
set -e

echo "Rolling back to previous deployment..."

# Get previous successful deployment
PREV_SHA=$(psql $DATABASE_URL -t -c "
SELECT git_sha
FROM deployments
WHERE status = 'healthy'
ORDER BY finished_at DESC
LIMIT 1;
" | tr -d ' ')

if [ -z "$PREV_SHA" ]; then
    echo "No previous successful deployment found. Manual intervention required."
    exit 1
fi

echo "Rolling back to: $PREV_SHA"

# Checkout previous commit
git checkout $PREV_SHA

# Restart containers
docker-compose down
docker-compose up -d

echo "Rollback complete."
```

---

## 12. API Contracts

### 12.1 Telegram Webhook Input

**Request Format:**

```json
{
    "update_id": 123456789,
    "message": {
        "message_id": 789,
        "from": {
            "id": 46808774,
            "is_bot": false,
            "first_name": "Max",
            "username": "maxbozhko"
        },
        "chat": {
            "id": 46808774,
            "first_name": "Max",
            "username": "maxbozhko",
            "type": "private"
        },
        "date": 1734480000,
        "text": "Проверь статус базы данных"
    }
}
```

**Callback Query (OK Button Press):**

```json
{
    "update_id": 123456790,
    "callback_query": {
        "id": "abc123",
        "from": {
            "id": 46808774,
            "first_name": "Max",
            "username": "maxbozhko"
        },
        "message": {
            "message_id": 790,
            "chat": {"id": 46808774}
        },
        "data": "approve:f47ac10b-58cc-4372-a567-0e02b2c3d479"
    }
}
```

### 12.2 Haiku Classification Output

**JSON Schema:**

```json
{
    "intent": "question",  // "question" | "command" | "chat" | "other"
    "summary": "User wants to check database status",
    "plan": "I will query PostgreSQL health and report table counts",
    "needs_confirmation": true,
    "confidence": 0.95
}
```

### 12.3 Claude Proactive Decision Output

**JSON Schema:**

```json
{
    "action": "develop_skill",
    "reasoning": "No urgent tasks. PostgreSQL skill proficiency is low (3/10). Practicing database optimization would be valuable.",
    "certainty": 0.85,
    "significance": 0.1,
    "type": "internal",
    "estimated_tokens": 5000,
    "skill": "postgresql_optimization"
}
```

**Alternative (Low Certainty):**

```json
{
    "action": "ask_master",
    "reasoning": "Found three potential revenue opportunities (crypto trading, freelance project, content creation). Each has risks. Need Master guidance on priority.",
    "certainty": 0.65,
    "significance": 0.9,
    "type": "external",
    "question": "Which revenue stream should I prioritize: 1) Crypto trading research, 2) Apply for freelance gig on Upwork, or 3) Write article for Medium?"
}
```

---

## 13. Data Models & Examples

### 13.1 Example Chat Thread

```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "platform": "telegram",
    "chat_id": 46808774,
    "chat_type": "private",
    "title": "Max Bozhko",
    "created_at": "2025-12-17T10:00:00Z",
    "updated_at": "2025-12-17T15:30:00Z",
    "metadata": {
        "username": "maxbozhko",
        "first_name": "Max",
        "language_code": "ru"
    }
}
```

### 13.2 Example Message with Voice Artifact

**Message:**

```json
{
    "id": "msg-001",
    "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "platform_message_id": 789,
    "role": "user",
    "author_user_id": 46808774,
    "author_username": "maxbozhko",
    "author_first_name": "Max",
    "text": null,
    "created_at": "2025-12-17T15:30:00Z",
    "raw_payload": {
        "message": {
            "message_id": 789,
            "voice": {
                "file_id": "AwACAgIAAxkBAAIBaGZ...",
                "duration": 5
            }
        }
    }
}
```

**Artifact:**

```json
{
    "id": "art-001",
    "message_id": "msg-001",
    "kind": "voice_transcript",
    "content_json": {
        "text": "Проверь сколько токенов осталось сегодня",
        "language": "ru",
        "duration_seconds": 5,
        "confidence": 0.98
    },
    "uri": "s3://server-agent/voice/2025-12-17/msg-001.oga",
    "processing_status": "completed",
    "created_at": "2025-12-17T15:30:05Z",
    "processed_at": "2025-12-17T15:30:07Z"
}
```

### 13.3 Example Reactive Job

```json
{
    "id": "job-001",
    "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "trigger_message_id": "msg-001",
    "status": "awaiting_approval",
    "mode": "execute",
    "payload_json": {},
    "classification_result": {
        "intent": "command",
        "summary": "Check remaining tokens for today",
        "plan": "Query token_ledger table for today's usage and calculate remaining budget",
        "needs_confirmation": true,
        "confidence": 0.92
    },
    "approval_id": "appr-001",
    "created_at": "2025-12-17T15:30:08Z",
    "started_at": "2025-12-17T15:30:10Z"
}
```

### 13.4 Example Approval Record

```json
{
    "id": "appr-001",
    "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "job_id": "job-001",
    "proposal_text": "👌 Understood: Check remaining tokens for today\n\n📋 Plan: Query token_ledger table for today's usage and calculate remaining budget\n\nPress OK to proceed.",
    "telegram_message_id": 790,
    "status": "approved",
    "created_at": "2025-12-17T15:30:10Z",
    "resolved_at": "2025-12-17T15:30:15Z",
    "resolved_by_user_id": 46808774
}
```

### 13.5 Example Token Ledger Entry

```json
{
    "id": "tok-001",
    "scope": "reactive",
    "provider": "anthropic_claude",
    "model": "claude-sonnet-4-5-20250929",
    "tokens_input": 1234,
    "tokens_output": 567,
    "tokens_total": 1801,
    "cost_usd": 0.0121,
    "created_at": "2025-12-17T15:30:20Z",
    "meta_json": {
        "job_id": "job-001",
        "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "request_type": "execute_command"
    }
}
```

---

## 14. Business Rules

### 14.1 Message Processing Rules

**Rule 1: Message Deduplication**
- Constraint: `UNIQUE (thread_id, platform_message_id)`
- Behavior: Webhook receiving duplicate update → ignored (INSERT fails silently)

**Rule 2: Artifact Processing Priority**
- Voice messages: Process immediately (transcription needed for context)
- Images: Process immediately (description needed for context)
- Documents: Process asynchronously (low priority, metadata only initially)

**Rule 3: Context Window Size**
- Always load last 30 messages for reactive processing
- If fewer than 30 messages exist, load all available
- Artifacts included inline in message content

**Rule 4: Message Role Assignment**
- `role = 'user'`: Any message from human (even if forwarded)
- `role = 'assistant'`: Any message sent by bot
- `role = 'system'`: Internal events (user joined, chat settings changed)

### 14.2 Approval Workflow Rules

**Rule 5: Approval Timeout**
- Default: 1 hour (configurable)
- Background job runs every 5 minutes checking for expired approvals
- Expired approvals: `status = 'expired'`, job status = 'failed'

**Rule 6: Supersede Logic**
- New message arrives while approval pending → previous approval marked 'superseded'
- Previous job canceled immediately
- New job created for new message

**Rule 7: Approval Requirement**
- All reactive jobs require approval before execution
- No exceptions (safety mechanism)
- Even simple queries get OK button

**Rule 8: Multi-Message Handling**
- If user sends multiple messages in quick succession:
  1. Create jobs for all messages
  2. Mark all but latest as 'superseded'
  3. Process only the latest message

### 14.3 Token Budget Rules

**Rule 9: Proactive Budget Enforcement**
- Hard limit: 7,000,000 tokens/day for scope='proactive'
- If budget exceeded: Proactive loop pauses until midnight UTC
- Reactive operations NEVER count against budget

**Rule 10: Adaptive Interval Calculation**
- <25% used → 60 sec intervals (aggressive cycling)
- 25-50% used → 300 sec intervals (moderate cycling)
- 50-75% used → 900 sec intervals (conservative cycling)
- >75% used → 3600 sec intervals (minimal cycling)
- >100% used → pause until midnight

**Rule 11: Token Logging**
- ALL Claude API calls logged to token_ledger (no exceptions)
- Scope field determines budget applicability
- Cost calculated using current Anthropic pricing

**Rule 12: Reactive Token Warning**
- If single reactive request exceeds 100k tokens → warning logged
- No blocking, but Master notified via Telegram
- Indicates potential inefficiency (context too large?)

### 14.4 Deployment Rules

**Rule 13: Deployment Trigger**
- Only merges to `main` branch trigger deployment
- Commits to other branches → no deployment
- Manual deployments via admin endpoint allowed

**Rule 14: Rollback Trigger**
- Health check fails after deployment → automatic rollback
- Rollback searches for last deployment with `status = 'healthy'`
- If no healthy deployment found → manual intervention required

**Rule 15: Deployment Notification**
- All deployments (success or failure) notify Master via Telegram
- Notification includes: git SHA, status, test results, rollback reason (if applicable)
- Notification stored in deployments table (`report_text` field)

### 14.5 Data Retention Rules

**Rule 16: Message Retention**
- All messages retained indefinitely by default
- Master can request deletion via `/delete` command
- Deletion: soft delete (mark as deleted, not physically removed)

**Rule 17: Token Ledger Retention**
- Keep all token ledger entries for financial audit
- No automatic deletion
- Monthly aggregation for analytics (separate table)

**Rule 18: Artifact Retention**
- Media in MinIO: 90-day retention policy (configurable)
- Artifact metadata in DB: retained indefinitely
- After MinIO deletion, `uri` field set to null

---

## 15. Implementation Roadmap

### Phase 1: Database & Infrastructure (Days 1-3)

**Priority 1.1: PostgreSQL Setup**
- [ ] Create database schema (all tables from Section 3)
- [ ] Add indexes for performance
- [ ] Create migration scripts
- [ ] Test connection pool
- [ ] Seed initial data (Master contact, system config)

**Priority 1.2: Docker Compose**
- [ ] Configure postgres container with persistent volume
- [ ] Configure app container with environment variables
- [ ] Configure minio container (optional)
- [ ] Test container startup and connectivity

**Priority 1.3: FastAPI Application Skeleton**
- [ ] Implement `app/config.py` (complete)
- [ ] Implement `app/database.py` (complete)
- [ ] Implement `app/main.py` with health endpoint (complete)
- [ ] Test health endpoint and stats endpoint

### Phase 2: Telegram Webhook System (Days 4-6)

**Priority 2.1: Webhook Registration**
- [ ] Implement webhook registration script
- [ ] Configure HTTPS (Nginx reverse proxy)
- [ ] Test webhook delivery from Telegram

**Priority 2.2: Webhook Handler**
- [ ] Implement `app/telegram_webhook.py` router
- [ ] Implement message normalization logic
- [ ] Implement thread creation/lookup
- [ ] Implement message insertion
- [ ] Test with various message types (text, voice, photo)

**Priority 2.3: Media Processing**
- [ ] Implement voice download and transcription
- [ ] Implement image download and analysis
- [ ] Implement MinIO upload (optional)
- [ ] Test artifact creation and storage

### Phase 3: Reactive Processing Loop (Days 7-10)

**Priority 3.1: Haiku Classifier**
- [ ] Implement `app/haiku_classifier.py`
- [ ] Implement context loading function
- [ ] Test intent classification with sample messages
- [ ] Measure latency (target: <2 seconds)

**Priority 3.2: Reactive Worker**
- [ ] Implement `app/reactive_worker.py` skeleton
- [ ] Implement job polling logic
- [ ] Implement state machine transitions
- [ ] Implement acknowledgment message sending
- [ ] Test job processing flow

**Priority 3.3: Approval System**
- [ ] Implement `app/approval_manager.py`
- [ ] Implement inline button creation
- [ ] Implement callback query handler
- [ ] Implement supersede logic
- [ ] Test approval workflow end-to-end

### Phase 4: Claude Integration (Days 11-13)

**Priority 4.1: Claude Client**
- [ ] Implement `app/claude_client.py`
- [ ] Implement token logging integration
- [ ] Test API calls with various models
- [ ] Implement error handling and retries

**Priority 4.2: Reactive Execution**
- [ ] Implement Claude message assembly from context
- [ ] Implement response parsing
- [ ] Implement response sending to Telegram
- [ ] Test full reactive flow: webhook → classify → approve → execute → respond

**Priority 4.3: Token Management**
- [ ] Implement token usage queries
- [ ] Implement cost calculation
- [ ] Test token ledger logging
- [ ] Create daily usage report query

### Phase 5: Proactive Autonomy Loop (Days 14-17)

**Priority 5.1: Proactive Scheduler**
- [ ] Implement `app/proactive_scheduler.py` skeleton
- [ ] Implement budget check function
- [ ] Implement adaptive interval calculation
- [ ] Test scheduler startup and shutdown

**Priority 5.2: Proactive Cycle Logic**
- [ ] Implement context loading for proactive mode
- [ ] Implement decision prompt template
- [ ] Implement decision parsing (certainty, significance)
- [ ] Implement autonomous action execution
- [ ] Test proactive cycle flow

**Priority 5.3: Master Interaction**
- [ ] Implement "ask_master" action type
- [ ] Implement significance-based reporting
- [ ] Test Master notification for uncertain decisions
- [ ] Test Master notification for significant actions

### Phase 6: Self-Update Pipeline (Days 18-20)

**Priority 6.1: Git Integration**
- [ ] Initialize git repository on server
- [ ] Configure git hooks (post-merge)
- [ ] Test merge-to-main detection

**Priority 6.2: Deployment Scripts**
- [ ] Implement `scripts/build_and_deploy.sh`
- [ ] Implement `scripts/run_tests.sh`
- [ ] Implement `scripts/rollback.sh`
- [ ] Implement Telegram notification script

**Priority 6.3: Deployment Testing**
- [ ] Create deployment record in database
- [ ] Test full deployment flow (build → test → deploy → health check)
- [ ] Test rollback on failure
- [ ] Test Master notification

### Phase 7: Production Hardening (Days 21-25)

**Priority 7.1: Error Handling**
- [ ] Implement comprehensive error logging
- [ ] Implement graceful degradation for failed artifacts
- [ ] Implement retry logic for transient failures
- [ ] Test error scenarios (DB down, API timeout, etc.)

**Priority 7.2: Performance Optimization**
- [ ] Add database query profiling
- [ ] Optimize slow queries with indexes
- [ ] Implement connection pooling tuning
- [ ] Measure and optimize webhook latency

**Priority 7.3: Monitoring & Observability**
- [ ] Implement structured logging (JSON logs)
- [ ] Add metrics endpoint (Prometheus format)
- [ ] Create dashboard for key metrics
- [ ] Set up alerts for critical failures

### Phase 8: User Experience Polish (Days 26-30)

**Priority 8.1: Message Formatting**
- [ ] Implement rich HTML formatting for responses
- [ ] Implement long message splitting (4096 char limit)
- [ ] Test with various message lengths and formats

**Priority 8.2: Progress Indicators**
- [ ] Implement typing indicator during processing
- [ ] Implement progress updates for long-running tasks
- [ ] Test user experience for multi-step tasks

**Priority 8.3: Command Enhancements**
- [ ] Implement `/status` command (agent state)
- [ ] Implement `/stats` command (usage statistics)
- [ ] Implement `/cancel` command (cancel current job)
- [ ] Test all commands

---

## Acceptance Criteria

**Criterion 1: Database Persistence**
- ✅ PostgreSQL container runs and is reachable from app
- ✅ All Telegram messages stored in `chat_messages`
- ✅ All bot responses stored in `chat_messages`
- ✅ Artifacts (voice, image) stored with processing status

**Criterion 2: Reactive UX**
- ✅ Webhook receives and processes all message types
- ✅ Acknowledgment sent within 3 seconds of message receipt
- ✅ Plan presented with OK button
- ✅ Execution begins after approval
- ✅ Response sent to user within 60 seconds

**Criterion 3: Context Awareness**
- ✅ Last 30 messages loaded for every reactive prompt
- ✅ Artifacts included in context (voice transcripts, image descriptions)
- ✅ Context persists across agent restarts

**Criterion 4: Token Budget**
- ✅ Proactive loop enforces 7M tokens/day limit
- ✅ Reactive loop is unbounded (no token limits)
- ✅ Token usage logged for all API calls
- ✅ Adaptive intervals adjust based on usage

**Criterion 5: Self-Update**
- ✅ Merge to main triggers deployment
- ✅ Tests run before deployment
- ✅ Rollback occurs on health check failure
- ✅ Master notified of deployment outcome

**Criterion 6: Reliability**
- ✅ Agent survives container restarts
- ✅ Database connection pool handles failures gracefully
- ✅ Webhook processes messages even during high load
- ✅ No message loss or duplication

---

## Appendix A: Environment Variables Reference

```bash
# Database
DATABASE_URL=postgresql://agent:secure_password@postgres:5432/server_agent

# Telegram
TELEGRAM_BOT_TOKEN=8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08
TELEGRAM_WEBHOOK_SECRET=random_secret_string_here
TELEGRAM_WEBHOOK_URL=https://your-server.com/webhook/telegram
MASTER_CHAT_IDS=46808774  # Comma-separated for multi-master

# Claude API
CLAUDE_CODE_OAUTH_TOKEN=your_oauth_token_from_setup
CLAUDE_CODE_API_URL=https://api.anthropic.com/v1
HAIKU_API_KEY=  # Optional, defaults to CLAUDE_CODE_OAUTH_TOKEN
HAIKU_MODEL=claude-3-5-haiku-20241022

# MinIO (optional)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=secure_minio_password
MINIO_BUCKET=server-agent
MINIO_ENABLED=true

# Token Budget
PROACTIVE_DAILY_TOKEN_LIMIT=7000000
REACTIVE_TOKEN_WARNING_THRESHOLD=100000

# Scheduling
PROACTIVE_MIN_INTERVAL_SECONDS=60
PROACTIVE_MAX_INTERVAL_SECONDS=3600

# Context
MESSAGE_HISTORY_LIMIT=30

# Approval
APPROVAL_TIMEOUT_SECONDS=3600
```

---

## Appendix B: SQL Queries Reference

**Query: Get Last 30 Messages with Artifacts**

```sql
SELECT
    cm.id,
    cm.role,
    cm.author_username,
    cm.text,
    cm.created_at,
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'kind', ma.kind,
                    'content', ma.content_json,
                    'uri', ma.uri
                )
            )
            FROM message_artifacts ma
            WHERE ma.message_id = cm.id
            AND ma.processing_status = 'completed'
        ),
        '[]'::json
    ) AS artifacts
FROM chat_messages cm
WHERE cm.thread_id = $1
ORDER BY cm.created_at DESC
LIMIT 30;
```

**Query: Check Proactive Token Budget**

```sql
SELECT
    COALESCE(SUM(tokens_total), 0) as tokens_used,
    7000000 - COALESCE(SUM(tokens_total), 0) as tokens_remaining,
    COALESCE(SUM(tokens_total), 0)::float / 7000000 as usage_ratio
FROM token_ledger
WHERE scope = 'proactive'
AND created_at >= CURRENT_DATE;
```

**Query: Find Next Queued Reactive Job**

```sql
SELECT
    j.id,
    j.thread_id,
    j.trigger_message_id,
    j.mode,
    j.payload_json,
    t.chat_id
FROM reactive_jobs j
JOIN chat_threads t ON j.thread_id = t.id
WHERE j.status = 'queued'
ORDER BY j.created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

**Query: Mark Approval as Approved**

```sql
UPDATE approvals
SET
    status = 'approved',
    resolved_at = NOW(),
    resolved_by_user_id = $1
WHERE job_id = $2
AND status = 'pending'
RETURNING id;
```

---

## Document Metadata

**Created:** 2025-12-17
**Created By:** Claude Code (Business Analyst Agent)
**Source Materials:**
- `/Users/maksimbozhko/Development/server-agent/README.md`
- `/Users/maksimbozhko/Development/server-agent/ARCHITECTURE.md`
- `/Users/maksimbozhko/Development/server-agent/docs/REQUIREMENTS.md`
- `/Users/maksimbozhko/Development/server-agent/docs/AGI_ONE_PROMPT_SPEC.md`
- `/Users/maksimbozhko/Development/server-agent/app/config.py`
- `/Users/maksimbozhko/Development/server-agent/app/database.py`
- `/Users/maksimbozhko/Development/server-agent/app/main.py`

**Intended Audience:**
- Plan Agent (for creating implementation plan)
- Development Team (for implementation)
- Master (Max Bozhko) for review and approval

**Next Steps:**
1. Review and approve technical specifications
2. Launch Plan Agent to create detailed implementation plan
3. Execute implementation roadmap (Phases 1-8)
4. Deploy to production server (Frankfurt2)

---

**End of Technical Specifications**
