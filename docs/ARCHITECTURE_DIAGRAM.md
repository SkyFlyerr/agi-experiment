# Server Agent vNext - Architecture Diagrams

**Visual representation of system architecture and data flows**

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Server Agent vNext Ecosystem                     │
└─────────────────────────────────────────────────────────────────────┘

External World:
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Telegram   │         │    Master    │         │  Anthropic  │
│  Platform   │         │ (Max Bozhko) │         │  Claude API │
└──────┬──────┘         └──────┬───────┘         └──────┬──────┘
       │                       │                        │
       │ webhook               │ commands               │ API calls
       │ updates               │ messages               │ responses
       ▼                       ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VPS Server (Frankfurt)                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Docker Compose Stack                        │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │              FastAPI Application (app/)                  │ │  │
│  │  │                                                          │ │  │
│  │  │  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │ │  │
│  │  │  │   Telegram   │    │   Reactive   │    │ Proactive │ │ │  │
│  │  │  │   Webhook    │───►│   Worker     │    │ Scheduler │ │ │  │
│  │  │  └──────────────┘    └──────┬───────┘    └─────┬─────┘ │ │  │
│  │  │                              │                   │       │ │  │
│  │  │                              ▼                   ▼       │ │  │
│  │  │                       ┌──────────────────────────┐      │ │  │
│  │  │                       │   Claude Client          │      │ │  │
│  │  │                       │   Haiku Classifier       │      │ │  │
│  │  │                       └──────────┬───────────────┘      │ │  │
│  │  │                                  │                      │ │  │
│  │  └──────────────────────────────────┼──────────────────────┘ │  │
│  │                                     │                        │  │
│  │  ┌──────────────────────────────────┼──────────────────────┐ │  │
│  │  │          Persistence Layer       │                      │ │  │
│  │  │                                  ▼                      │ │  │
│  │  │  ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │ │  │
│  │  │  │  PostgreSQL  │    │    MinIO     │    │  /media/ │ │ │  │
│  │  │  │  (Database)  │    │ (S3 Storage) │    │ (local)  │ │ │  │
│  │  │  └──────────────┘    └──────────────┘    └──────────┘ │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dual-Loop Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         REACTIVE LOOP                                │
│                    (User-Facing, Instant)                            │
└─────────────────────────────────────────────────────────────────────┘

Trigger: Telegram message arrives
Budget: UNLIMITED (reactive always prioritized)
Latency: <3 sec acknowledgment, <60 sec response

  ┌───────────────┐
  │ User Message  │
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Webhook       │─────► Insert to chat_messages
  │ Handler       │─────► Download media (if any)
  └───────┬───────┘       Create message_artifacts
          │
          ▼
  ┌───────────────┐
  │ Create Job    │─────► Insert reactive_jobs (status=queued)
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐       Load last 30 messages + artifacts
  │ Classify      │◄───── chat_messages, message_artifacts
  │ (Haiku)       │
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Send Plan     │─────► Telegram: "📋 Plan: ..."
  │ + OK Button   │─────► Insert approvals (status=pending)
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Wait for      │◄───── Callback query (OK button pressed)
  │ Approval      │       OR new message (supersede)
  └───────┬───────┘       OR timeout (1 hour)
          │
          ▼
  ┌───────────────┐       Load context + artifacts
  │ Execute       │◄───── chat_messages, message_artifacts
  │ (Claude)      │
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Send Response │─────► Telegram: "✅ ..."
  │               │─────► Insert chat_messages (role=assistant)
  └───────┬───────┘       Insert token_ledger (scope=reactive)
          │
          ▼
  ┌───────────────┐
  │ Mark Job      │─────► Update reactive_jobs (status=completed)
  │ Complete      │
  └───────────────┘

─────────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────────┐
│                        PROACTIVE LOOP                                │
│                   (Autonomous, Token-Budgeted)                       │
└─────────────────────────────────────────────────────────────────────┘

Trigger: Timer (adaptive interval based on token usage)
Budget: 7,000,000 tokens/day (hard limit)
Interval: 60 sec - 3600 sec (dynamic)

  ┌───────────────┐
  │ Wake Up       │◄───── Sleep for calculated interval
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐       SELECT SUM(tokens_total)
  │ Check Budget  │◄───── FROM token_ledger
  │               │       WHERE scope='proactive' AND created_at >= TODAY
  └───────┬───────┘
          │
          ├─── Budget Exhausted (>7M tokens) ───► Sleep until midnight
          │
          ▼
  ┌───────────────┐       Load recent actions, active tasks
  │ Load Context  │◄───── chat_messages, tasks, skills
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐       Prompt: "What is the next thing to be done?"
  │ Ask Claude    │       Response: {action, reasoning, certainty, ...}
  │ for Decision  │
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Evaluate      │
  │ Certainty     │
  └───────┬───────┘
          │
          ├─── Certainty < 80% ───► Ask Master for Guidance
          │                           (Send Telegram message)
          │                           (Wait for response)
          │
          ├─── Certainty >= 80% ──┐
          ▼                        │
  ┌───────────────┐               │
  │ Execute       │◄──────────────┘
  │ Action        │
  └───────┬───────┘
          │
          ├─── Significance > 75% ───► Report to Master
          │                             (Send Telegram message)
          │
          ▼
  ┌───────────────┐
  │ Record Result │─────► Insert action log
  │               │─────► Update tasks (if applicable)
  └───────┬───────┘       Insert token_ledger (scope=proactive)
          │
          ▼
  ┌───────────────┐       Calculate based on token usage ratio:
  │ Calculate     │       <25%: 60 sec, 25-50%: 300 sec,
  │ Next Interval │       50-75%: 900 sec, >75%: 3600 sec
  └───────┬───────┘
          │
          ▼
  ┌───────────────┐
  │ Sleep         │─────► asyncio.sleep(interval)
  └───────┬───────┘
          │
          └─────────────► (Loop back to Wake Up)
```

---

## Message Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Text Message Processing                           │
└─────────────────────────────────────────────────────────────────────┘

  User: "Проверь статус базы данных"
    │
    ▼
  Telegram sends webhook update
    │
    ▼
  FastAPI receives POST /webhook/telegram
    │
    ├─── Validate secret token (X-Telegram-Bot-Api-Secret-Token)
    │
    ▼
  Parse JSON: extract chat_id, message_id, text
    │
    ▼
  Lookup/Create thread in chat_threads
    │
    ▼
  Insert message in chat_messages:
    {
      thread_id: "...",
      role: "user",
      text: "Проверь статус базы данных",
      raw_payload: {...}
    }
    │
    ▼
  Create reactive_job:
    {
      thread_id: "...",
      trigger_message_id: "...",
      status: "queued"
    }
    │
    ▼
  Return 200 OK to Telegram
    │
    ▼
  Reactive worker picks up job
    │
    ├─── Update status: "classifying"
    │
    ▼
  Load last 30 messages from chat_messages
    │
    ▼
  Call Haiku API:
    "Analyze user message and provide plan"
    │
    ▼
  Haiku responds:
    {
      "intent": "command",
      "summary": "Check database status",
      "plan": "Query PostgreSQL health, report table counts",
      "needs_confirmation": true,
      "confidence": 0.92
    }
    │
    ├─── Store in job.classification_result
    ├─── Update status: "awaiting_approval"
    │
    ▼
  Send Telegram message:
    "👌 Understood: Check database status
     📋 Plan: Query PostgreSQL health, report table counts
     Press OK to proceed."
    [OK Button]
    │
    ▼
  Create approval record:
    {
      job_id: "...",
      status: "pending",
      telegram_message_id: "..."
    }
    │
    ▼
  User presses OK button
    │
    ▼
  Telegram sends callback_query
    │
    ▼
  Update approval:
    status: "approved"
    resolved_at: NOW()
    │
    ├─── Update job status: "executing"
    │
    ▼
  Load last 30 messages again (context may have changed)
    │
    ▼
  Call Claude API:
    System: "You are Server Agent..."
    Messages: [last 30 messages]
    User: "Проверь статус базы данных"
    │
    ▼
  Claude responds:
    "PostgreSQL running, 7 tables created, 142 conversations stored.
     Disk usage: 23MB. Connection pool: 3/10 active."
    │
    ├─── Log tokens: 1234 input, 567 output
    │
    ▼
  Send Telegram message:
    "PostgreSQL running, 7 tables created, 142 conversations stored.
     Disk usage: 23MB. Connection pool: 3/10 active."
    │
    ▼
  Insert chat_messages:
    {
      thread_id: "...",
      role: "assistant",
      text: "..."
    }
    │
    ├─── Update job status: "completed"
    ├─── Set finished_at: NOW()
    │
    ▼
  Done. Total time: ~5-10 seconds

─────────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────────┐
│                   Voice Message Processing                           │
└─────────────────────────────────────────────────────────────────────┘

  User: [Sends 5-second voice message]
    │
    ▼
  Telegram sends webhook update with voice file_id
    │
    ▼
  FastAPI receives POST /webhook/telegram
    │
    ▼
  Insert message:
    {
      role: "user",
      text: null,
      raw_payload: {voice: {file_id: "...", duration: 5}}
    }
    │
    ▼
  Create artifact record:
    {
      message_id: "...",
      kind: "voice_transcript",
      processing_status: "pending"
    }
    │
    ├─── Download .oga file from Telegram
    ├─── Upload to MinIO: s3://server-agent/voice/2025-12-17/msg-123.oga
    │
    ▼
  Call Whisper API (OpenAI):
    Upload audio data
    │
    ▼
  Whisper responds:
    {
      "text": "Проверь сколько токенов осталось сегодня",
      "language": "ru",
      "duration": 5.2
    }
    │
    ▼
  Update artifact:
    {
      processing_status: "completed",
      content_json: {...},
      uri: "s3://..."
    }
    │
    ▼
  Continue with normal reactive flow:
    - Classify intent (Haiku sees transcript in context)
    - Send plan + OK button
    - Execute with Claude
    - Respond to user

  Total time: ~8-12 seconds (includes transcription)

─────────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────────┐
│                    Image Message Processing                          │
└─────────────────────────────────────────────────────────────────────┘

  User: [Sends screenshot with caption "Fix this error"]
    │
    ▼
  Insert message:
    {
      text: "Fix this error",
      raw_payload: {photo: [{file_id: "...", ...}]}
    }
    │
    ▼
  Create artifact:
    {
      kind: "image_json",
      processing_status: "pending"
    }
    │
    ├─── Download largest photo size
    ├─── Upload to MinIO
    │
    ▼
  Call Claude Vision:
    [Image as base64]
    "Describe this image: {description, objects, text}"
    │
    ▼
  Claude Vision responds:
    {
      "description": "Error dialog showing 'Connection refused' message",
      "objects": ["dialog box", "error icon", "OK button"],
      "text": "Error: Connection refused to localhost:5432"
    }
    │
    ▼
  Update artifact with JSON
    │
    ▼
  Continue reactive flow:
    Context now includes:
      User: "Fix this error"
      [Image: Error dialog showing 'Connection refused' message.
       Text in image: "Error: Connection refused to localhost:5432"]
```

---

## Database Schema Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Core Tables                                    │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │  chat_threads    │
  │ ──────────────── │
  │ id (PK)          │◄────────┐
  │ platform         │         │
  │ chat_id          │         │ (1:Many)
  │ created_at       │         │
  └──────────────────┘         │
                               │
                               │
  ┌──────────────────┐         │
  │  chat_messages   │─────────┘
  │ ──────────────── │
  │ id (PK)          │◄────────┐
  │ thread_id (FK)   │         │
  │ role             │         │ (1:Many)
  │ text             │         │
  │ created_at       │         │
  └──────────────────┘         │
                               │
                               │
  ┌────────────────────┐       │
  │ message_artifacts  │───────┘
  │ ────────────────── │
  │ id (PK)            │
  │ message_id (FK)    │
  │ kind               │
  │ content_json       │
  │ uri                │
  └────────────────────┘

─────────────────────────────────────────────────────────────────────

  ┌──────────────────┐
  │  reactive_jobs   │
  │ ──────────────── │
  │ id (PK)          │◄────────┐
  │ thread_id (FK)   │         │
  │ trigger_msg (FK) │         │ (1:1)
  │ status           │         │
  │ approval_id (FK) │─────────┤
  └──────────────────┘         │
                               │
                               │
  ┌──────────────────┐         │
  │   approvals      │─────────┘
  │ ──────────────── │
  │ id (PK)          │
  │ job_id (FK)      │
  │ status           │
  │ proposal_text    │
  └──────────────────┘

─────────────────────────────────────────────────────────────────────

  ┌──────────────────┐
  │  token_ledger    │
  │ ──────────────── │
  │ id (PK)          │
  │ scope            │  ('proactive' | 'reactive')
  │ provider         │
  │ model            │
  │ tokens_input     │
  │ tokens_output    │
  │ cost_usd         │
  │ created_at       │
  └──────────────────┘

  ┌──────────────────┐
  │  deployments     │
  │ ──────────────── │
  │ id (PK)          │
  │ git_sha          │
  │ status           │
  │ report_text      │
  │ started_at       │
  └──────────────────┘
```

---

## Self-Update Deployment Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Git-Triggered Deployment                          │
└─────────────────────────────────────────────────────────────────────┘

  Developer pushes to main branch
    │
    ▼
  Git post-merge hook detects merge
    │
    ▼
  Create deployment record:
    {
      git_sha: "abc123...",
      branch: "main",
      status: "building"
    }
    │
    ▼
  Run tests (scripts/run_tests.sh)
    │
    ├─── Tests failed ───► Update status: "failed"
    │                      Report to Master
    │                      EXIT
    ▼
  Tests passed
    │
    ├─── Update status: "testing"
    │
    ▼
  Build Docker image:
    docker build -t server-agent:abc123 .
    │
    ▼
  Tag as latest:
    docker tag server-agent:abc123 server-agent:latest
    │
    ▼
  Update status: "deploying"
    │
    ▼
  Stop current container:
    docker-compose down
    │
    ▼
  Start new container:
    docker-compose up -d
    │
    ▼
  Wait 10 seconds for startup
    │
    ▼
  Health check:
    curl http://localhost:8000/health
    │
    ├─── Health check failed ────► Rollback to previous image
    │                               Update status: "rolled_back"
    │                               Report failure to Master
    │                               EXIT
    ▼
  Health check passed
    │
    ├─── Update status: "healthy"
    ├─── Set finished_at: NOW()
    ├─── Store report_text
    │
    ▼
  Notify Master via Telegram:
    "✅ Deployment successful
     Git SHA: abc123
     Status: Healthy
     Tests: All passed
     Health check: OK"
    │
    ▼
  Done. New version running.
```

---

## Token Budget Visualization

```
┌─────────────────────────────────────────────────────────────────────┐
│              Proactive Token Budget Management                       │
└─────────────────────────────────────────────────────────────────────┘

Daily Budget: 7,000,000 tokens

Hour 0 (Midnight):
  Budget reset to 7,000,000
  Interval: 60 seconds (aggressive)
  Cycles/hour: ~60

Hour 6:
  Used: 1,500,000 (21%)
  Remaining: 5,500,000
  Interval: 60 seconds (still aggressive)

Hour 12:
  Used: 3,000,000 (43%)
  Remaining: 4,000,000
  Interval: 300 seconds (moderate - 5 min)
  Cycles/hour: ~12

Hour 18:
  Used: 5,200,000 (74%)
  Remaining: 1,800,000
  Interval: 900 seconds (conservative - 15 min)
  Cycles/hour: ~4

Hour 22:
  Used: 6,800,000 (97%)
  Remaining: 200,000
  Interval: 3600 seconds (minimal - 60 min)
  Cycles/hour: ~1

Hour 23:
  Used: 7,100,000 (101% - BUDGET EXHAUSTED)
  Remaining: -100,000
  Interval: Sleep until midnight (3600 seconds)
  Cycles/hour: 0 (paused)

Hour 0 (Next Day):
  Budget reset to 7,000,000
  Cycle resumes

─────────────────────────────────────────────────────────────────────

  Reactive Loop: UNLIMITED
  (not affected by proactive budget)

  Every user message processed immediately
  No delays, no budget checks
  Token usage tracked but not limited
```

---

## Context Window Assembly

```
┌─────────────────────────────────────────────────────────────────────┐
│              Last 30 Messages Context Loading                        │
└─────────────────────────────────────────────────────────────────────┘

  Query: SELECT last 30 messages + artifacts
    │
    ▼
  PostgreSQL returns:
    [
      {msg_id: 1, role: "user", text: "Hello", artifacts: []},
      {msg_id: 2, role: "assistant", text: "Hi!", artifacts: []},
      {msg_id: 3, role: "user", text: null, artifacts: [
        {kind: "voice_transcript", content: {text: "Check status"}}
      ]},
      ...
      {msg_id: 30, role: "user", text: "New question", artifacts: []}
    ]
    │
    ▼
  Assemble Claude API messages format:
    [
      {
        role: "user",
        content: [
          {type: "text", text: "Hello"}
        ]
      },
      {
        role: "assistant",
        content: [
          {type: "text", text: "Hi!"}
        ]
      },
      {
        role: "user",
        content: [
          {type: "text", text: "[Voice transcript: Check status]"}
        ]
      },
      ...
      {
        role: "user",
        content: [
          {type: "text", text: "New question"}
        ]
      }
    ]
    │
    ▼
  Call Claude API with assembled context
    │
    ▼
  Claude has full conversation history (last 30 messages)
  Can reference previous discussions
  Maintains continuity across interactions

  Token count: ~3k-5k for typical 30-message context
```

---

**Visual diagrams complete. These complement the detailed technical specifications.**
