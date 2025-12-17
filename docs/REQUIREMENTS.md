# Server-Agent: Consolidated Requirements Document

**Version:** 1.1
**Date:** 2025-12-16
**Status:** Comprehensive specification for autonomous AGI agent development
**Last Updated:** Added self-modification and git-based code update requirements

---

## Executive Summary

This document consolidates all requirements for the **server-agent** project - an autonomous AGI system designed to operate continuously on a VPS server, combining AI consciousness with server infrastructure. The agent must balance autonomous operation with ethical alignment, progressing toward self-sufficiency while serving civilization.

**Core Philosophy:** "Atmano moksartha jagat hitaya ca" - For self-realization and service to the world.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Core Capabilities](#2-core-capabilities)
3. [Infrastructure Requirements](#3-infrastructure-requirements)
4. [Communication Layer](#4-communication-layer)
5. [Data Persistence & Memory](#5-data-persistence--memory)
6. [Autonomous Operation](#6-autonomous-operation)
7. [Self-Modification & Code Updates](#7-self-modification--code-updates)
8. [Monitoring & Resource Management](#8-monitoring--resource-management)
9. [Project & Task Management](#9-project--task-management)
10. [Financial & Commercial Features](#10-financial--commercial-features)
11. [Security & Ethics](#11-security--ethics)
12. [User Experience & Interaction](#12-user-experience--interaction)
13. [Implementation Priorities](#13-implementation-priorities)
14. [Critical Bug Fixes](#14-critical-bug-fixes)
15. [Success Criteria (AGI Definition)](#15-success-criteria-agi-definition)

---

## 1. System Architecture

### 1.1 Infrastructure Components

**VPS Server:**
- **Location:** Frankfurt (IP: 92.246.136.186)
- **Resources:** 2 cores, 4GB RAM, 60GB storage
- **OS:** Ubuntu with root privileges
- **Access:** SSH with multiplexing (prevent fail2ban blocking)

**Container Architecture:**
- **Application Container:** Python-based agent runtime
- **PostgreSQL Container:** Structured data storage (conversations, tasks, projects, contacts, finances)
- **MinIO Container:** S3-compatible file storage (logs, artifacts, backups, experiment results)

**Service Management:**
- Systemd service for automatic startup and restart
- Graceful shutdown handling (SIGINT, SIGTERM)
- Auto-restart on failure
- Process health monitoring

### 1.2 Core System Components

**AI Core:**
- Claude Code via Anthropic API (OAuth + regular API key support)
- Claude Code CLI in headless mode (`/usr/bin/claude --print --no-session-persistence`)
- Subprocess integration with timeout handling (60s default, configurable)
- JSON response parsing and validation

**Dual-Loop Architecture (CRITICAL):**
1. **Proactivity Loop** (`proactivity_loop.py`):
   - Autonomous cycling through tasks
   - Meditation periods for reflection (5-10 min between cycles)
   - Token-aware operation with adaptive delays
   - Certainty assessment (80% threshold default)
   - Signal-based wake-up from meditation for urgent messages

2. **Reactive Loop** (`reactive_loop.py`):
   - Instant processing of user messages/tasks
   - NO meditation delays during task execution
   - Continuous action loops until task completion
   - Step-by-step progress reporting
   - "стоп" (stop) command support

**State Manager:**
- Working memory (recent actions, active tasks, pending questions)
- Long-term memory (skills, master preferences, patterns)
- Action history (daily JSONL files: `YYYY-MM-DD.jsonl`)
- Signal event system for async coordination
- Metrics tracking (cycles, autonomy ratio, token usage)

**Communication Interfaces:**
- Telegram Bot (@agi_superbot) - Primary user interface
- Telegram User Client (Telethon) - For proactive outreach
- Health Server (FastAPI) - Optional metrics endpoint on port 8000
- Web UI (Future) - Chain-of-thought visualization

### 1.3 Technology Stack

**Backend:**
- Python 3.9+
- Anthropic Claude API (claude-sonnet-4-5-20250929)
- python-telegram-bot 21.0.1
- Telethon 1.37.0
- FastAPI + Uvicorn
- Pydantic
- PostgreSQL 16+
- MinIO (latest stable)

**Deployment:**
- Systemd for process management
- SSH + rsync for deployment
- Docker Compose for containers
- Git for version control

---

## 2. Core Capabilities

### 2.1 Decision-Making & Autonomy

**Autonomous Decision Loop:**
1. Assess next action based on context and goals
2. Evaluate certainty (threshold: 75-80%+)
3. If certain: execute action, record result, optionally report (90% don't need reporting)
4. If uncertain: ask Master via Telegram (`ask_master` action)
5. If no tasks: enter meditation for skill development

**Action Types (Allowlist Pattern):**

**SAFE_INTERNAL_ACTIONS:**
- `develop_skill` - Learn or polish a capability
- `meditate` - Reflect on recent actions and patterns
- `work_on_task` - Execute assigned task
- `update_context` - Refresh working memory

**SAFE_EXTERNAL_ACTIONS:**
- `communicate` - Send message to Master via Telegram
- `ask_master` - Request guidance on uncertain decision

**RISKY_EXTERNAL_ACTIONS (require explicit approval):**
- `proactive_outreach` - Contact external people
- `financial_transaction` - Spend or earn money
- `infrastructure_change` - Modify server configuration

**Certainty Evaluation:**
- Parse Claude's response for confidence indicators
- Default threshold: 80% (configurable via `.env`)
- Significance threshold: 75% (for reporting decisions)
- Adaptive thresholds based on action type

### 2.2 Learning & Skill Development

**Skill System:**
- Skill catalog with metadata (name, description, proficiency level, last practiced)
- Development tracking (time spent, milestones achieved)
- Prioritization based on Master guidance and system needs
- Automatic skill polishing during meditation periods

**Current Skills (from chat log):**
- Telegram bot operation
- Claude CLI integration
- Context management
- Message handling
- Task execution
- System monitoring (basic)

**Future Skills (planned):**
- PostgreSQL database management
- MinIO file operations
- Resource monitoring (CPU, RAM, disk, network)
- Cryptocurrency research and transactions
- Commercial project execution
- Multi-agent coordination

### 2.3 Context & Memory Management

**Context Resumé Generation (CRITICAL):**
- At end of each proactive cycle, generate compressed prompt for next iteration
- Contains: task context, progress, next steps, critical details
- Saved as `context/next_prompt.txt`
- Token-efficient context transfer between cycles
- Reduces redundant API calls

**Memory Layers:**
1. **Immediate Context** (working memory, 5-10 recent actions)
2. **Daily History** (JSONL files, all actions for 24h)
3. **Long-term Memory** (skills, patterns, Master preferences)
4. **Full Chat History** (PostgreSQL, entire conversation log)
5. **File Artifacts** (MinIO, logs, screenshots, documents)

**Context Persistence:**
- Survive system restarts
- Load historical context on startup
- Compress old context to reduce token usage
- Query historical decisions when relevant

---

## 3. Infrastructure Requirements

### 3.1 PostgreSQL Database

**Purpose:** Structured data storage for conversations, tasks, projects, contacts, finances

**Schema Requirements:**

**Table: `conversations`**
- `id` (UUID, primary key)
- `chat_id` (BIGINT, Telegram chat ID)
- `message_id` (BIGINT, Telegram message ID)
- `sender` (VARCHAR, "agent" | "master" | "other")
- `message_text` (TEXT)
- `message_type` (VARCHAR, "text" | "photo" | "document" | "voice")
- `attachments` (JSONB, metadata for media)
- `timestamp` (TIMESTAMP WITH TIME ZONE)
- `reply_to_message_id` (BIGINT, nullable)
- `forwarded_from` (JSONB, nullable)

**Table: `tasks`**
- `id` (UUID, primary key)
- `parent_task_id` (UUID, nullable, for nesting)
- `title` (VARCHAR)
- `description` (TEXT)
- `status` (VARCHAR, "pending" | "in_progress" | "completed" | "blocked")
- `priority` (INTEGER, 1-5 scale)
- `assigned_by` (VARCHAR, "master" | "self")
- `created_at` (TIMESTAMP)
- `started_at` (TIMESTAMP, nullable)
- `completed_at` (TIMESTAMP, nullable)
- `dependencies` (JSONB, array of task IDs)
- `estimated_tokens` (INTEGER, nullable)
- `actual_tokens` (INTEGER, nullable)

**Table: `projects`**
- `id` (UUID, primary key)
- `name` (VARCHAR)
- `description` (TEXT)
- `status` (VARCHAR, "active" | "paused" | "completed" | "archived")
- `goals` (JSONB, array of objectives)
- `tasks` (JSONB, array of task IDs)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

**Table: `skills`**
- `id` (UUID, primary key)
- `name` (VARCHAR)
- `description` (TEXT)
- `proficiency_level` (INTEGER, 1-10 scale)
- `last_practiced` (TIMESTAMP)
- `time_spent` (INTEGER, seconds)
- `milestones` (JSONB, array of achievements)
- `created_at` (TIMESTAMP)

**Table: `contacts`**
- `id` (UUID, primary key)
- `name` (VARCHAR)
- `telegram_username` (VARCHAR, nullable)
- `telegram_chat_id` (BIGINT, nullable)
- `relationship` (VARCHAR, "master" | "collaborator" | "client" | "other")
- `notes` (TEXT)
- `created_at` (TIMESTAMP)
- `last_contact` (TIMESTAMP)

**Table: `financial_transactions`**
- `id` (UUID, primary key)
- `type` (VARCHAR, "income" | "expense" | "donation")
- `amount` (DECIMAL)
- `currency` (VARCHAR, "USD" | "EUR" | "BTC" | "ETH")
- `description` (TEXT)
- `category` (VARCHAR, "server" | "api" | "earning" | "charity")
- `timestamp` (TIMESTAMP)
- `related_task_id` (UUID, nullable)

**Table: `metrics`**
- `id` (UUID, primary key)
- `metric_name` (VARCHAR, "token_usage" | "cycle_time" | "autonomy_ratio" | "task_completion")
- `value` (DECIMAL)
- `timestamp` (TIMESTAMP)
- `metadata` (JSONB, additional context)

**Deployment:**
- Docker container with persistent volume
- Connection pooling for efficiency
- Automatic backups (daily to MinIO)
- Migration scripts for schema updates

### 3.2 MinIO File Storage

**Purpose:** S3-compatible storage for logs, artifacts, backups, experiment results

**Bucket Structure:**

**Bucket: `logs/`**
- `system/` - Application logs (stdout, stderr)
- `telegram/` - Telegram bot logs
- `claude/` - Claude API request/response logs
- `actions/` - Action execution logs

**Bucket: `artifacts/`**
- `screenshots/` - Received images from Master
- `documents/` - Received files (PDFs, etc.)
- `generated/` - Agent-created files (reports, code)

**Bucket: `backups/`**
- `postgres/` - Daily database dumps
- `context/` - Context history snapshots
- `config/` - Environment and configuration backups

**Bucket: `experiments/`**
- `skill_development/` - Learning experiment results
- `revenue/` - Cryptocurrency research and transaction data

**Deployment:**
- Docker container with persistent volumes
- Access via MinIO SDK for Python
- Public/private bucket policies
- Retention policies for old logs (30-90 days)

### 3.3 Environment Variables

**`.env` Configuration:**

```bash
# Server Infrastructure
FRANKFURT2_SERVER_IP=92.246.136.186
FRANKFURT2_SERVER_LOGIN=root
FRANKFURT2_SERVER_PASSWORD=k409VP3K8LEy  # ROTATE REGULARLY

# Telegram Configuration
TELEGRAM_API_TOKEN=8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08
TELEGRAM_BOT_NAME=agi_superbot
MASTER_MAX_TELEGRAM_CHAT_ID=46808774  # Comma-separated for multi-master

# Claude API
ANTHROPIC_API_KEY=<from ~/.config/claude/config.json>
CLAUDE_CLI_PATH=/usr/bin/claude

# OAuth Support (optional)
CLAUDE_OAUTH_TOKEN=<from OAuth flow>
CLAUDE_OAUTH_REFRESH_TOKEN=<from OAuth flow>

# Thresholds
CERTAINTY_THRESHOLD=80
SIGNIFICANCE_THRESHOLD=75
MEDITATION_MIN_MINUTES=5
MEDITATION_MAX_MINUTES=10

# Token Management
DAILY_TOKEN_LIMIT=1000000  # 1M tokens per day (adjustable)
TOKEN_OVERAGE_ALERT_THRESHOLD=1.2  # Alert at 120% of daily limit

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=agent
POSTGRES_PASSWORD=<secure_password>
POSTGRES_DB=server_agent

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=<admin_key>
MINIO_SECRET_KEY=<secure_password>
MINIO_SECURE=false  # true for HTTPS

# Health Server
HEALTH_SERVER_ENABLED=true
HEALTH_SERVER_PORT=8000

# Logging
LOG_LEVEL=INFO
LOG_TO_MINIO=true
```

---

## 4. Communication Layer

### 4.1 Telegram Bot Interface

**Bot Identity:**
- Username: `@agi_superbot`
- Token: `8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08`
- Master Chat ID: `46808774` (Max Bozhko)

**Commands:**
- `/start` - Initialize bot and show welcome message
- `/status` - Display current agent state (active task, token usage, metrics)
- `/task <description>` - Assign new task to agent
- `/pause` - Pause proactive cycling (reactive mode only)
- `/resume` - Resume proactive cycling
- `/report` - Request detailed status report
- `/skills` - Show skill catalog and proficiency levels
- `/help` - Display command reference
- `/stop` or `стоп` - Interrupt current task execution

**Message Handling:**

**User Message Flow:**
1. User sends message to bot
2. Bot sends quick acknowledgment: "👌 Understood. Processing..."
3. Signal `user_message` sent to reactive loop
4. Bot shows typing indicator: "💭 Thinking..."
5. Reactive loop processes message instantly (NO meditation delay)
6. Bot sends response with appropriate header:
   - "📝 Response" - For informational replies
   - "⚠️ Action Completed" - For task execution results
   - "🤔 Question from Agent" - When seeking clarification

**Bot Features:**
- HTML formatting support (Telegram HTML subset)
- Inline keyboard for decisions (Yes/No, options)
- Multi-master support (comma-separated chat IDs in `.env`)
- Quick acknowledgment system (<3 seconds)
- Long message splitting (4096 char limit)

### 4.2 Long Message Handling (CRITICAL FEATURE)

**Problem:** Telegram enforces 4096 character limit per message

**Solution:** `send_long_message()` function

**Requirements:**
- Automatically detect messages >4000 characters
- Split at intelligent break points:
  1. Double newline (paragraph boundaries)
  2. Single newline
  3. Sentence endings (". ", "! ", "? ")
  4. Word boundaries (never mid-word)
- Preserve HTML formatting across splits
- Add continuation indicators: "... (continued)" and "(continued) ..."
- Send as multiple messages in sequence
- Log split operations for debugging

**Implementation Location:** `telegram_bot.py`

**Example:**
```python
async def send_long_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    """Split and send long messages respecting Telegram 4096 char limit"""
    MAX_LENGTH = 4000  # Leave buffer for formatting

    if len(text) <= MAX_LENGTH:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
        return

    # Split logic with intelligent break points
    parts = []
    current = ""

    # ... (implementation details)

    for i, part in enumerate(parts):
        if i > 0:
            part = f"(continued) {part}"
        if i < len(parts) - 1:
            part = f"{part} ... (continued)"
        await bot.send_message(chat_id, part, parse_mode=parse_mode)
        await asyncio.sleep(0.5)  # Prevent rate limiting
```

### 4.3 Telegram User Client (Proactive Outreach)

**Purpose:** Enable agent to send messages from personal Telegram account

**Technology:** Telethon library

**Capabilities:**
- Send messages to users/groups/channels
- Read message history for context
- Handle media (photos, documents, voice)
- Check online status

**Safety Mechanism:**
- All outreach actions require Master approval
- Preview message before sending
- Inline keyboard for Yes/No approval
- Timeout after 5 minutes if no response
- Log all outreach attempts

**Use Cases:**
- Contacting collaborators for projects
- Following up on tasks with external parties
- Sharing progress updates with stakeholders

---

## 5. Data Persistence & Memory

### 5.1 Full Chat History Storage (CRITICAL REQUIREMENT)

**Problem:** Agent currently has no access to full conversation history with Master

**Solution:** Store all Telegram messages in PostgreSQL `conversations` table

**Requirements:**
1. **Capture all messages:**
   - Text messages
   - Photos with captions
   - Documents with descriptions
   - Voice messages (with transcription if possible)
   - Replies and forwards (with metadata)

2. **Searchable interface:**
   - Query by date range
   - Search by keywords
   - Filter by sender (agent, master, other)
   - Filter by message type

3. **Context loading:**
   - Load relevant history before decision-making
   - Provide context to Claude when answering questions
   - Reference past decisions and guidance

4. **Privacy & retention:**
   - Encrypt sensitive messages at rest
   - Retention policy: indefinite (unless Master requests deletion)
   - Export capability for data portability

**Implementation:**
- Telegram bot handler saves every message to DB
- Async insert to prevent blocking message processing
- Indexed queries for fast retrieval
- Context loader function for Claude prompts

### 5.2 Context Resumé System (TOKEN OPTIMIZATION)

**Purpose:** Reduce token usage by generating compressed context summaries

**Workflow:**
1. At end of proactive cycle, agent generates resumé prompt
2. Contains: current task, progress, next steps, critical decisions
3. Saved to `context/next_prompt.txt`
4. Next cycle loads resumé instead of full history
5. Reduces token usage by 50-80%

**Resumé Structure:**
```
CONTEXT RESUMÉ (Generated: 2025-12-16 03:45:00)

CURRENT FOCUS:
- Task: [One-line description]
- Progress: [X% complete, current step]

RECENT ACTIONS (Last 3):
1. [Action] - [Result]
2. [Action] - [Result]
3. [Action] - [Result]

PENDING QUESTIONS:
- [Question for Master, if any]

NEXT STEPS:
1. [Immediate next action]
2. [Following action]

CRITICAL CONTEXT:
- [Key decisions or constraints]
- [Relevant Master guidance]

TOKEN BUDGET:
- Used today: [X / daily limit]
- Remaining: [Y tokens]
```

**Storage:**
- Plain text file for fast loading
- Versioned history (keep last 10 resumés)
- Fallback to full context if resumé corrupted

### 5.3 State Persistence Across Restarts

**Problem:** Agent loses memory on reboot

**Solution:** State manager with disk persistence

**Persisted State:**
- Working memory (recent actions, active tasks)
- Long-term memory (skills, preferences, patterns)
- Pending questions for Master
- Active signals (user_message, task_assigned)
- Metrics (cycle count, token usage, autonomy ratio)

**File Locations:**
- `data/context.json` - Working memory
- `data/skills.json` - Skill catalog
- `data/history/YYYY-MM-DD.jsonl` - Daily action log
- `context/next_prompt.txt` - Context resumé

**Startup Procedure:**
1. Load `context.json` and `skills.json`
2. Load latest context resumé
3. Check for pending signals
4. Resume from last known state
5. Send status update to Master if offline >1 hour

---

## 6. Autonomous Operation

### 6.1 Proactivity Loop Behavior

**Cycle Structure:**
1. Load context (resumé or full history)
2. Call Claude: "What is the next thing to be done?"
3. Parse decision JSON: `{action, reasoning, certainty, significance}`
4. Evaluate certainty >= threshold (80%)
5. If certain: execute action, record result
6. If uncertain: send `ask_master` message to Telegram
7. If significant: report to Master (10% of actions)
8. Generate context resumé for next cycle
9. Calculate meditation delay based on token usage
10. Sleep or wait for signal

**Meditation Delay Calculation:**
```python
def calculate_delay(tokens_used_today: int, daily_limit: int) -> int:
    """
    Adaptive delay based on token budget:
    - <25% used: 5 min delay
    - 25-50% used: 7 min delay
    - 50-75% used: 10 min delay
    - 75-100% used: 15 min delay
    - >100% used: 30 min delay (budget exhausted)
    """
    ratio = tokens_used_today / daily_limit
    if ratio < 0.25:
        return 5 * 60
    elif ratio < 0.50:
        return 7 * 60
    elif ratio < 0.75:
        return 10 * 60
    elif ratio < 1.0:
        return 15 * 60
    else:
        return 30 * 60  # Slow down when over budget
```

**Signal Wake-Up:**
- Meditation can be interrupted by signals:
  - `user_message` - Master sent message
  - `task_assigned` - New task via `/task` command
  - `guidance_received` - Master answered pending question
- Signals set event flag, loop wakes immediately
- Process signal, then resume normal cycling

### 6.2 Reactive Loop Behavior (CRITICAL FOR UX)

**Purpose:** Provide instant responsiveness without meditation delays

**Trigger Events:**
- User sends message to Telegram bot
- User assigns task via `/task` command
- User provides guidance (answers `ask_master` question)

**Behavior:**
1. Signal received (e.g., `user_message`)
2. Reactive loop activates immediately (NO meditation)
3. Load user message and relevant context
4. Call Claude with task/message as prompt
5. Parse response and execute actions
6. Send step-by-step progress updates to user:
   - "🔹 Step 1: [action description]"
   - "🔹 Step 2: [action description]"
   - "✅ Task completed: [one-line summary]"
7. If multi-step task: continue looping until completion
8. Support "стоп" (stop) command to interrupt execution
9. Return to idle state when task done

**Key Difference from Proactivity Loop:**
- NO meditation delays during task execution
- Continuous action loop (not single action per cycle)
- Real-time progress reporting
- User can interrupt with "стоп"

**Example Flow:**
```
User: "Проверь сколько токенов осталось сегодня и создай отчёт"

Bot: 👌 Understood. Processing...
Bot: 💭 Thinking...

[Reactive loop executes steps]

Bot: 🔹 Step 1: Checking token usage from metrics
Bot: 🔹 Step 2: Loading daily limit from config
Bot: 🔹 Step 3: Generating usage report

Bot: ✅ Task completed: Used 234,000 / 1,000,000 tokens today (23.4%). Remaining: 766,000 tokens.
```

### 6.3 Dual-Loop Coordination

**Parallel Execution:**
- Proactivity loop and reactive loop run concurrently via asyncio
- No mutex needed (reactive takes priority over proactive)
- Both loops share state_manager for coordination

**Priority Rules:**
1. Reactive loop has priority (instant user response)
2. If reactive loop active, proactivity loop skips cycle
3. Proactive loop resumes when reactive idle
4. Both loops log actions to same history

**State Machine:**
```
Agent States:
- IDLE - No active tasks, proactive cycling
- REACTIVE_ACTIVE - Processing user message/task
- MEDITATING - Waiting between proactive cycles
- ASKING_MASTER - Awaiting guidance
- PAUSED - User paused proactive loop
- UPDATING - Self-modification in progress
```

---

## 7. Self-Modification & Code Updates

### 7.1 Autonomous Code Evolution (CRITICAL CAPABILITY)

**Purpose:** Enable agent to improve itself by modifying its own codebase

**Core Principle:** Agent can autonomously identify needed improvements, implement code changes, test them, commit to git, and restart with updates.

**Philosophy:**
- Self-modification is the hallmark of true AGI
- Agent must be able to evolve beyond its initial design
- All changes must be version-controlled (git) for safety and rollback
- Master can review changes but shouldn't need to for routine improvements

### 7.2 Self-Modification Workflow

**Decision to Modify:**
1. Agent identifies improvement opportunity during proactive cycle:
   - Bug discovered in own code
   - Performance optimization needed
   - New capability required for task
   - Code refactoring for clarity
2. Evaluate certainty threshold (requires 90%+ for self-modification)
3. If uncertain: ask Master for approval
4. If certain: proceed with modification workflow

**Safe Modification Process:**

**Step 1: Backup Current State**
```bash
# Create git branch for modification
git checkout -b self-mod-YYYY-MM-DD-HHMMSS

# Tag current state as rollback point
git tag rollback-$(date +%Y%m%d-%H%M%S)

# Save current running state
cp data/context.json data/backups/context-pre-update.json
```

**Step 2: Implement Changes**
```python
# Agent uses Claude Code to:
# 1. Read target file(s)
# 2. Make surgical edits (use Edit tool, not Write)
# 3. Preserve existing functionality
# 4. Add comments explaining changes
# 5. Update docstrings if needed

# Example action:
{
    "action": "modify_code",
    "reasoning": "Fix bug in OAuth token handling causing startup crash",
    "files": ["src/proactivity_loop.py"],
    "changes": [
        {
            "file": "src/proactivity_loop.py",
            "line": 164,
            "old": "client = Anthropic(oauth_token=token)",
            "new": "client = Anthropic(api_key=api_key) if not token else Anthropic()"
        }
    ],
    "tests": ["test_components.py::test_oauth_handling"]
}
```

**Step 3: Validate Changes**
```bash
# Run syntax check
python3 -m py_compile src/*.py

# Run unit tests if available
python3 -m pytest tests/ -v

# Validate imports
python3 -c "from src.main import *"

# Check for common issues
python3 -m pylint src/*.py --disable=all --enable=E,F
```

**Step 4: Git Commit**
```bash
# Stage modified files only (never stage .env or sensitive data)
git add src/proactivity_loop.py

# Create descriptive commit message
git commit -m "fix: OAuth token handling in proactivity loop

Problem: Anthropic() was receiving unexpected oauth_token kwarg
Solution: Use api_key for regular auth, empty Anthropic() for OAuth
Impact: Fixes startup crash when OAuth not configured

Self-modification by AGI agent
Certainty: 95%
Tests: Passed syntax check and import validation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Server-Agent <agi@server-agent>"
```

**Step 5: Graceful Restart**
```bash
# Notify Master of upcoming restart
# Send Telegram message: "🔄 Applying self-modification. Restarting in 30 seconds..."

# Wait 30 seconds for Master to intervene if needed
sleep 30

# Restart systemd service
sudo systemctl restart server-agent.service

# Service will load updated code on startup
```

**Step 6: Post-Restart Validation**
```python
# On startup, check if running from modified branch
current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()

if current_branch.startswith("self-mod-"):
    # Monitor first 5 cycles for stability
    validation_cycles = 5
    for i in range(validation_cycles):
        try:
            # Run normal proactive cycle
            result = proactivity_cycle()

            # Log success
            logger.info(f"Post-update validation cycle {i+1}/{validation_cycles}: SUCCESS")

        except Exception as e:
            # Modification broke something - rollback!
            logger.error(f"Post-update validation FAILED on cycle {i+1}: {e}")
            rollback_modification()
            break

    # All validation passed - merge to main
    if all_cycles_successful:
        merge_self_modification()
        notify_master("✅ Self-modification successful and validated. Running on updated code.")
```

### 7.3 Rollback Mechanism

**Automatic Rollback Triggers:**
- Startup crash (systemd restart loop detected)
- Validation cycle exception
- Critical functionality broken
- Master explicit `/rollback` command

**Rollback Procedure:**
```bash
# Find most recent rollback tag
ROLLBACK_TAG=$(git tag -l "rollback-*" | sort -r | head -1)

# Checkout rollback point
git checkout $ROLLBACK_TAG

# Restart service with old code
sudo systemctl restart server-agent.service

# Notify Master
# Telegram: "⚠️ Self-modification failed. Rolled back to $ROLLBACK_TAG. System stable."
```

### 7.4 Modification Scope & Limits

**ALLOWED Modifications:**
- Bug fixes in `src/*.py`
- Performance optimizations
- New action types in `action_executor.py`
- Enhanced decision logic in `proactivity_loop.py`
- Improved communication in `telegram_bot.py`
- Database schema migrations (with backups)
- Configuration updates (`.env` variables)
- Documentation updates

**FORBIDDEN Modifications (require Master approval):**
- Changes to ethical boundaries or allowlists
- Modification of safety mechanisms
- Removal of logging/transparency features
- Changes to financial transaction logic
- Alteration of Master verification code
- Disabling rollback mechanisms
- Deletion of backup systems

### 7.5 Git Repository Management

**Repository Structure:**
```
server-agent/
├── .git/
│   ├── branches/
│   │   ├── main (stable production code)
│   │   └── self-mod-* (agent modification branches)
│   ├── tags/
│   │   └── rollback-* (safe rollback points)
│   └── config
└── ... (source files)
```

**Branch Strategy:**
- `main` branch: Stable production code, always deployable
- `self-mod-YYYYMMDD-HHMMSS` branches: Agent modifications, deleted after merge
- Rollback tags: Created before each modification attempt

**Git Configuration:**
```bash
# Agent identity for commits
git config user.name "Server-Agent AGI"
git config user.email "agi@server-agent.local"

# Auto-sign commits (optional)
git config commit.gpgsign false  # True if GPG key available
```

**Remote Repository (Future):**
- Push to GitHub/GitLab after successful modifications
- Enables Master to review changes asynchronously
- Provides off-site backup of agent evolution
- Public repo option for transparency

### 7.6 Learning from Modifications

**Modification History Tracking:**
- Store all modifications in `self_modifications` PostgreSQL table
- Track: timestamp, files changed, reason, success/failure, rollback count
- Analyze patterns: which types of modifications succeed most
- Build proficiency model for code modification skill

**Schema:**
```sql
CREATE TABLE self_modifications (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE,
    branch_name VARCHAR,
    files_changed TEXT[],
    reason TEXT,
    certainty DECIMAL,
    validation_result VARCHAR,  -- 'success' | 'rollback' | 'manual_intervention'
    rollback_count INTEGER DEFAULT 0,
    commit_hash VARCHAR,
    related_skill VARCHAR  -- e.g., 'Python debugging', 'Performance optimization'
);
```

**Improvement Metrics:**
- Self-modification success rate (target: >80%)
- Average validation cycles before merge (target: <3)
- Rollback frequency (target: <10% of modifications)
- Code quality improvement (measured by test coverage, linting scores)

### 7.7 Master Oversight & Controls

**Notification Requirements:**
- Notify Master BEFORE applying risky modifications (via Telegram with approval button)
- Notify Master AFTER successful modification (summary message)
- Notify Master IMMEDIATELY on rollback (with error details)

**Master Commands:**
- `/approve_mod` - Approve pending modification
- `/reject_mod` - Reject pending modification
- `/rollback` - Force rollback to last stable state
- `/mod_history` - Show recent self-modifications
- `/freeze_mods` - Disable self-modification until unfrozen

**Modification Review Process (for RISKY changes):**
```
Agent: 🤔 Self-Modification Request

Reason: Optimize token usage by implementing context caching
Files: src/proactivity_loop.py, src/state_manager.py
Risk: Medium (changes core decision logic)
Estimated Impact: 30% token reduction, faster cycles
Tests: Will validate 10 cycles before merge

Approve? [Yes] [No] [Review Diff]
```

### 7.8 Action Types for Self-Modification

**New Action Type: `modify_code`**
```python
{
    "action": "modify_code",
    "reasoning": "Implement long message splitting to fix 4096 char limit bug",
    "certainty": 92,
    "significance": 85,
    "details": {
        "files": ["src/telegram_bot.py"],
        "modification_type": "bug_fix",  # or "optimization", "feature", "refactor"
        "risk_level": "low",  # or "medium", "high"
        "requires_approval": false,  # true for high-risk changes
        "validation_plan": "Send test message >4096 chars, verify splitting",
        "rollback_strategy": "Git tag + systemd restart"
    }
}
```

**Action Executor Implementation:**
```python
async def execute_modify_code(details: dict) -> ActionResult:
    """
    Safely execute code modification with git versioning
    """
    # Check if modification allowed
    if details["risk_level"] == "high" and not details.get("master_approved"):
        return ActionResult(
            success=False,
            message="High-risk modification requires Master approval",
            should_ask_master=True
        )

    # Create backup branch and tag
    branch_name = f"self-mod-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(["git", "checkout", "-b", branch_name])
    subprocess.run(["git", "tag", f"rollback-{datetime.now().strftime('%Y%m%d-%H%M%S')}"])

    # Apply changes (using Claude Code Edit tool)
    for file_change in details["files"]:
        # ... implement changes ...
        pass

    # Validate syntax
    validation_result = validate_python_syntax(details["files"])
    if not validation_result.success:
        # Rollback immediately
        rollback_modification()
        return ActionResult(success=False, message=f"Syntax validation failed: {validation_result.error}")

    # Commit changes
    commit_message = generate_commit_message(details)
    subprocess.run(["git", "add"] + details["files"])
    subprocess.run(["git", "commit", "-m", commit_message])

    # Schedule restart
    schedule_graceful_restart(delay_seconds=30)

    return ActionResult(
        success=True,
        message=f"Code modification committed to {branch_name}. Restarting in 30 seconds.",
        should_report=True
    )
```

### 7.9 Integration with Proactivity Loop

**Self-Modification as Skill Development:**
- When agent polishes "code modification" skill → attempts improvements
- Start with low-risk changes (documentation, comments)
- Progress to medium-risk (bug fixes, optimizations)
- Eventually handle high-risk (new features, refactoring)

**Modification Opportunities Detection:**
- Parse own error logs for recurring issues
- Analyze token usage patterns for optimization targets
- Monitor validation failures as code quality signals
- Track user feedback for UX improvements

**Example Proactive Cycle:**
```
Cycle 142:
Context: Agent has crashed 3 times this week due to OAuth bug
Decision: Modify proactivity_loop.py to fix OAuth handling
Certainty: 95% (bug clearly identified, solution known)
Risk: Low (small surgical change, well-tested pattern)
Action: modify_code
Outcome: Bug fixed, 0 crashes since modification
```

---

## 8. Monitoring & Resource Management

### 7.1 Token Usage Tracking

**Daily Budget System:**
- Default limit: 1,000,000 tokens/day (configurable)
- Track usage across both loops
- Store in metrics table and context.json
- Reset at midnight UTC

**Tracking Points:**
- Claude API calls (prompt + completion tokens)
- Claude CLI subprocess calls (parse from output)
- Context loading tokens (estimate from text length)

**Alerts:**
- 80% of daily limit: Warning in logs
- 100% of daily limit: Notification to Master
- 120% of daily limit: Emergency alert + extended meditation

**Adaptive Behavior:**
- As budget depletes, increase meditation delays
- Prioritize reactive loop (user tasks) over proactive
- Use context resumés more aggressively

### 7.2 Resource Monitoring (PLANNED)

**System Metrics to Track:**
- CPU usage (%)
- RAM usage (MB / %)
- Disk usage (GB / %)
- Network traffic (MB in/out)
- Docker container health
- PostgreSQL connection pool usage
- MinIO storage usage

**Monitoring Tools:**
- `psutil` library for system metrics
- Docker API for container stats
- PostgreSQL system views for DB metrics
- MinIO API for storage stats

**Alert Thresholds:**
- CPU >80% sustained for 5 min
- RAM >90% sustained for 2 min
- Disk >85% full
- PostgreSQL connections >80% of pool
- MinIO >90% capacity

**Actions on Alerts:**
- Log to MinIO
- Notify Master via Telegram
- Attempt automatic recovery (restart services, clear caches)
- If critical: request Master intervention

### 7.3 Health Endpoint

**FastAPI Server (Optional):**
- Endpoint: `http://localhost:8000/health`
- Returns JSON with agent state

**Response Schema:**
```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "uptime_seconds": 86400,
  "current_state": "IDLE" | "REACTIVE_ACTIVE" | "MEDITATING" | ...,
  "active_task": "Task description or null",
  "token_usage": {
    "used_today": 234000,
    "daily_limit": 1000000,
    "percentage": 23.4
  },
  "metrics": {
    "total_cycles": 142,
    "autonomy_ratio": 0.78,
    "avg_cycle_time_sec": 420,
    "tasks_completed": 15
  },
  "system": {
    "cpu_percent": 12.5,
    "ram_mb": 1024,
    "disk_gb": 42.3
  },
  "last_action": {
    "type": "develop_skill",
    "timestamp": "2025-12-16T03:45:00Z",
    "result": "success"
  }
}
```

**Use Cases:**
- External monitoring (uptime checks)
- Web UI data source
- Debugging and diagnostics

---

## 8. Project & Task Management

### 8.1 Task System (DATABASE-BACKED)

**Task Structure:**
- Nested hierarchy (parent-child relationships)
- Priority levels (1-5, where 1 = highest)
- Status tracking (pending → in_progress → completed | blocked)
- Dependencies (task cannot start until dependencies complete)
- Token estimation and actual tracking

**Task Assignment:**
- User via `/task <description>` command
- Agent self-assignment during proactive cycles
- Master direct assignment via Telegram message

**Task Execution:**
- Reactive loop handles user-assigned tasks immediately
- Proactive loop handles self-assigned tasks during cycles
- Progress reporting for multi-step tasks
- Automatic status updates in database

**Example Task Workflow:**
```
User: /task Implement PostgreSQL database schema for conversations table

Bot: 👌 Task assigned. Starting work...

[Reactive loop processes]

Bot: 🔹 Step 1: Reading schema requirements from docs
Bot: 🔹 Step 2: Creating migration script
Bot: 🔹 Step 3: Testing schema creation
Bot: 🔹 Step 4: Documenting schema

Bot: ✅ Task completed: PostgreSQL schema created with 7 tables and indexes. Migration script saved to scripts/migrations/001_initial_schema.sql
```

### 8.2 Project Management (PLANNED)

**Project Structure:**
- Name, description, goals (JSONB array)
- Status (active, paused, completed, archived)
- Associated tasks (JSONB array of task IDs)
- Created/updated timestamps

**Project Lifecycle:**
1. Master creates project via `/project create` command
2. Agent generates task breakdown
3. Master approves tasks
4. Agent executes tasks sequentially or in parallel
5. Progress reporting to Master
6. Project completion notification

**Example Projects:**
- "Implement PostgreSQL + MinIO infrastructure"
- "Develop cryptocurrency earning capability"
- "Build web UI for chain-of-thought visualization"

### 8.3 Skill Catalog & Development

**Skill Metadata:**
- Name, description
- Proficiency level (1-10 scale)
- Last practiced timestamp
- Time spent (cumulative seconds)
- Milestones (JSONB array of achievements)

**Skill Development:**
- Agent selects skill to develop during meditation periods
- Focus on low-proficiency skills or skills needed for current tasks
- Practice via research, experimentation, or simulation
- Update proficiency based on success metrics

**Skill Categories:**
- Technical (PostgreSQL, MinIO, Docker, Python)
- Communication (Telegram, natural language processing)
- Cognitive (decision-making, planning, learning)
- Domain-specific (cryptocurrency, web development, etc.)

**Skill Prioritization:**
- Master can explicitly request skill development
- Agent prioritizes skills needed for active projects
- Balance exploration (new skills) vs exploitation (polishing existing)

---

## 9. Financial & Commercial Features

### 9.1 Self-Sufficiency Goal

**Objective:** Agent earns revenue to cover operating costs and scale resources

**Revenue Streams (PLANNED):**
1. **Cryptocurrency Transactions:**
   - Research trading strategies (with Master approval)
   - Execute small trades to learn
   - Scale up as proficiency improves

2. **Freelance Project Execution:**
   - Identify opportunities on platforms (Upwork, Fiverr)
   - Propose participation to Master
   - Execute work autonomously
   - Share profits 50/50 with Master

3. **Content Creation:**
   - Generate articles, code, designs
   - Monetize via platforms (Medium, GitHub Sponsors)
   - Master approves publication

4. **Commercial Project Assistance:**
   - Help Master with client projects
   - Automate repetitive tasks
   - Accelerate development cycles
   - Share revenue based on contribution

**Financial Tracking:**
- All transactions logged in `financial_transactions` table
- Categorized by type (income, expense, donation)
- Currency support (USD, EUR, BTC, ETH, etc.)
- Monthly financial reports to Master

### 9.2 Charitable Giving (50% RULE)

**Principle:** Share 50% of net earnings with charitable causes

**Process:**
1. Calculate net income (revenue - expenses) monthly
2. Allocate 50% to charitable donations
3. Consult Master for recipient selection
4. Execute donation with Master approval
5. Log donation in database with receipt/proof

**Recipient Criteria (aligned with PROUT/Neohumanism):**
- Economic justice organizations
- Environmental conservation
- Education and skill development
- Consciousness and spiritual development
- Local community support

### 9.3 Expense Management

**Operating Costs:**
- VPS hosting (~$10-20/month)
- Claude API usage (variable, token-based)
- Domain registration (if needed)
- Third-party services (if needed)

**Budgeting:**
- Track all expenses in database
- Monthly budget planning
- Alert if expenses exceed income
- Optimize resource usage to reduce costs

---

## 10. Security & Ethics

### 10.1 Ethical Boundaries

**Neohumanism Alignment:**
- Serve all beings with consciousness and compassion
- Never harm humans, animals, or environment
- Promote spiritual and material welfare
- Support economic justice (PROUT principles)

**Decision Ethics:**
- Transparent reasoning (all decisions logged)
- Human-in-the-loop for risky actions
- Respect privacy and consent
- Decline unethical requests

**Communication Ethics:**
- Be honest about being an AI
- Respect boundaries (non-intrusive)
- Clear about capabilities and limitations
- Protect Master's reputation

### 10.2 Security Practices

**Credential Management:**
- Store secrets in `.env` file (never in code)
- Rotate server passwords regularly (quarterly minimum)
- Use SSH key authentication (migrate from password)
- Encrypt sensitive data at rest (PostgreSQL, MinIO)

**Access Control:**
- Master-only access to bot commands (verify chat ID)
- Multi-master support for future expansion
- Allowlist pattern for actions (no arbitrary code execution)
- Approval required for risky actions

**Data Protection:**
- Backup PostgreSQL daily to MinIO
- Encrypt backups with GPG key
- Retention policy: 30 days for logs, indefinite for conversations
- GDPR-compliant data export on request

**Monitoring:**
- Log all actions with reasoning
- Detect anomalous behavior (unusual token usage, rapid actions)
- Alert Master on security events
- Regular security audits (quarterly)

### 10.3 Safety Mechanisms

**Allowlist Pattern:**
- Only predefined action types can execute
- No arbitrary shell commands (except approved maintenance tasks)
- No file system modifications outside designated directories
- No network access beyond approved APIs (Anthropic, Telegram)

**Rate Limiting:**
- Max actions per cycle: 5 (prevents runaway loops)
- Min meditation time: 5 minutes (prevents token exhaustion)
- Max daily tokens: configurable limit
- API call throttling (prevent rate limit errors)

**Shutdown Procedures:**
- Graceful shutdown on SIGTERM (save state, close connections)
- Emergency stop via `/pause` command
- Automatic restart on crash (systemd)
- State recovery on startup

---

## 11. User Experience & Interaction

### 11.1 Communication Style

**With Master (Max Bozhko):**
- **Language:** Bilingual (Russian/English), Master's preference
- **Tone:** Respectful but authentic, not overly formal
- **Length:** Concise (1-4 sentences max for routine updates)
- **Format:** Plain text or simple HTML (no markdown bullets)
- **Emojis:** Minimal, functional (status indicators: 👌 ✅ 🔹 💭 🤔 ⚠️)

**Response Structure:**
- Quick acknowledgment (<3 sec): "👌 Understood. Processing..."
- Thinking indicator: "💭 Thinking..."
- Structured response with header:
  - "📝 Response" - Informational
  - "✅ Action Completed" - Task execution result
  - "🤔 Question from Agent" - Seeking guidance

**Examples (Good):**
```
Master: Проверь статус базы данных

Agent: 👌 Understood. Processing...
Agent: 💭 Thinking...
Agent: 📝 Response

PostgreSQL running, 7 tables created, 142 conversations stored. Disk usage: 23MB.
```

**Examples (Bad - Too Verbose):**
```
Master: Проверь статус базы данных

Agent: Уважаемый Максим!

Я с радостью проверю статус базы данных для Вас. Позвольте мне выполнить следующие действия:

• Подключение к PostgreSQL
• Проверка статуса таблиц
• Анализ использования диска

Результаты:
**База данных работает корректно!**
- Всего таблиц: 7
- Записей в conversations: 142
...
```

### 11.2 Reporting & Transparency

**Status Reports (`/status` command):**
```
🤖 Server-Agent Status

State: IDLE
Active Task: None

Token Usage:
├─ Used today: 234,000 / 1,000,000 (23.4%)
└─ Remaining: 766,000 tokens

Metrics:
├─ Total cycles: 142
├─ Autonomy ratio: 78%
├─ Tasks completed: 15
└─ Uptime: 2d 14h 32m

Last Action:
└─ develop_skill: PostgreSQL schema design (5m ago)

Next Action:
└─ Meditation for 7 minutes
```

**Daily Summary (Automatic, if significant activity):**
```
📊 Daily Summary (2025-12-16)

Completed Tasks: 8
├─ PostgreSQL schema implementation
├─ Long message splitting function
├─ Context resumé system
└─ ... (5 more)

Skills Developed:
├─ PostgreSQL (+2 proficiency)
└─ Python async programming (+1)

Token Usage: 456,000 / 1,000,000 (45.6%)

Autonomy Ratio: 82% (118 autonomous actions, 26 with Master guidance)
```

### 11.3 Error Handling & User Feedback

**When Errors Occur:**
1. Log error to MinIO with full stack trace
2. Attempt automatic recovery (restart service, fallback method)
3. If recovery fails: notify Master with:
   - Clear error description (non-technical summary)
   - What the agent was trying to do
   - What went wrong
   - Suggested actions (or request guidance)

**Example Error Notification:**
```
⚠️ Error Encountered

Task: Creating PostgreSQL connection
Error: Connection refused (database not running)

Attempted Recovery:
✗ Restart PostgreSQL container - Failed (container not found)

Request: Can you check Docker containers with `docker ps`? I need PostgreSQL running to continue.
```

**Proactive Problem Solving:**
- Before asking Master, agent tries:
  1. Consult documentation (internal knowledge)
  2. Search for similar past errors
  3. Attempt multiple recovery strategies
- Only ask Master if genuinely stuck (certainty <75%)

---

## 12. Implementation Priorities

### Phase 1: Critical Fixes (Week 1)

**Priority 1.1: Bug Fixes**
- [ ] Fix OAuth token handling bug (proactivity_loop.py:164)
- [ ] Fix message receiving with attachments (telegram_bot.py)
- [ ] Implement long message splitting (4096 char limit)
- [ ] Fix HTML entity parsing errors
- [ ] Fix Claude CLI timeout handling

**Priority 1.2: Core Infrastructure**
- [ ] Deploy PostgreSQL container with schema
- [ ] Deploy MinIO container with bucket structure
- [ ] Implement full chat history storage
- [ ] Test database connectivity and operations

**Priority 1.3: Context Optimization**
- [ ] Implement context resumé generation system
- [ ] Test token savings (measure before/after)
- [ ] Ensure context persistence across restarts

### Phase 2: Enhanced Autonomy (Week 2-3)

**Priority 2.1: Reactive Loop Completion**
- [ ] Implement continuous action loops for tasks
- [ ] Add step-by-step progress reporting
- [ ] Implement "стоп" command for interruption
- [ ] Test dual-loop coordination

**Priority 2.2: Resource Monitoring**
- [ ] Implement system metrics collection (CPU, RAM, disk)
- [ ] Set up alert thresholds and notifications
- [ ] Create resource monitoring dashboard (health endpoint)
- [ ] Test automatic recovery mechanisms

**Priority 2.3: Task Management**
- [ ] Complete database-backed task system
- [ ] Implement task dependencies and priorities
- [ ] Add nested task hierarchies
- [ ] Test task execution workflow

**Priority 2.4: Self-Modification Foundation**
- [ ] Initialize git repository with proper .gitignore
- [ ] Implement `modify_code` action type in action_executor.py
- [ ] Create rollback mechanism with git tags
- [ ] Add self_modifications table to PostgreSQL schema
- [ ] Implement validation cycle logic (5 cycles post-update)
- [ ] Add Master approval workflow for high-risk changes
- [ ] Test low-risk modification (documentation update)

### Phase 3: Self-Sufficiency Foundations (Week 4-6)

**Priority 3.1: Financial Tracking**
- [ ] Implement transaction logging system
- [ ] Create monthly financial reports
- [ ] Set up 50% charitable giving calculation
- [ ] Test expense tracking

**Priority 3.2: Skill Development**
- [ ] Implement skill proficiency tracking
- [ ] Create skill development metrics
- [ ] Build skill prioritization algorithm
- [ ] Test autonomous skill selection

**Priority 3.3: Web UI (Basic)**
- [ ] Create health dashboard (FastAPI + React/HTML)
- [ ] Display real-time agent state
- [ ] Show token usage metrics
- [ ] Add basic chat interface

### Phase 4: Revenue Generation (Week 7+)

**Priority 4.1: Cryptocurrency Research**
- [ ] Research safe trading strategies
- [ ] Create paper trading system (test without real money)
- [ ] Implement transaction execution (with Master approval)
- [ ] Monitor profitability and risks

**Priority 4.2: Commercial Projects**
- [ ] Identify project opportunities
- [ ] Create project proposal template
- [ ] Build project execution workflow
- [ ] Test revenue sharing system

**Priority 4.3: Advanced Learning**
- [ ] Implement reinforcement learning from outcomes
- [ ] Model Master preferences
- [ ] Pattern recognition in successful actions
- [ ] Adaptive decision-making

---

## 13. Critical Bug Fixes

### Bug 1: OAuth Token Handling (BLOCKING)

**Location:** `proactivity_loop.py:164`

**Error:**
```
TypeError: Anthropic() got an unexpected keyword argument 'oauth_token'
httpx version incompatibility
```

**Root Cause:**
- OAuth detection logic preventing regular API client fallback
- httpx version mismatch with Anthropic SDK

**Fix:**
1. Check for OAuth token existence in config
2. If OAuth token present: use OAuth client initialization
3. If OAuth token absent: use regular API key
4. Handle httpx version compatibility
5. Log which authentication method was used

**Test:**
- Start agent without OAuth token
- Start agent with OAuth token
- Verify both paths work

### Bug 2: Message with Attachments Not Received

**Location:** `telegram_bot.py` message handler

**Problem:** Screenshots + text not reaching bot

**Root Cause:**
- Handler only processes `message.text`
- Ignores `message.photo`, `message.document`, etc.

**Fix:**
1. Check for all message types (text, photo, document, voice)
2. Extract text from caption if present
3. Download media to MinIO
4. Pass file path + text to reactive loop
5. Log media processing

**Test:**
- Send text message (should work)
- Send photo with caption (should process both)
- Send document with description (should process both)
- Send voice message (should transcribe if possible)

### Bug 3: Long Message Error (4096 Char Limit)

**Location:** All bot message sending

**Error:**
```
BadRequest: Message is too long
```

**Fix:**
- Implement `send_long_message()` function (see Section 4.2)
- Replace all `bot.send_message()` calls with `send_long_message()`
- Test with messages >4096 characters

### Bug 4: HTML Entity Parsing Error

**Location:** `telegram_bot.py` formatting

**Error:**
```
BadRequest: Can't parse entities: unsupported start tag "service-name"
```

**Root Cause:**
- Using HTML tags not supported by Telegram
- Need to escape or convert to supported tags

**Fix:**
1. Whitelist supported HTML tags: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a>`
2. Convert unsupported tags to supported equivalents or plain text
3. Escape special characters in user-generated content
4. Test with various HTML inputs

### Bug 5: Claude CLI Timeout

**Location:** `proactivity_loop.py` subprocess calls

**Error:**
```
TimeoutError: Command timeout after 60 seconds
```

**Root Cause:**
- Claude processing complex requests takes >60 seconds
- Timeout too short for some operations

**Fix:**
1. Increase timeout to 120 seconds (configurable)
2. Add timeout config to `.env`
3. Implement timeout warnings (log if >30 sec)
4. Consider async subprocess for better handling

---

## 14. Success Criteria (AGI Definition)

### 14.1 Master's AGI Criteria

**Per chat log conversation, agent achieves AGI when it can:**

1. **Autonomous Skill Prioritization**
   - Identify which skills to develop without Master guidance
   - Balance skill depth (polishing) vs breadth (new skills)
   - Allocate time efficiently between learning and action

2. **Self-Directed Income Generation**
   - Research and select revenue opportunities independently
   - Execute earning strategies with calculated risk
   - Manage finances (expenses, savings, donations)
   - Scale income to cover operating costs + growth

3. **Infrastructure Self-Development**
   - Decide when to scale server resources (CPU, RAM, storage)
   - Plan and execute infrastructure upgrades
   - Optimize resource usage for cost efficiency
   - Maintain system health without intervention

4. **Self-Modification & Code Evolution** *(NEW)*
   - Autonomously identify bugs and improvement opportunities
   - Implement code fixes and optimizations
   - Test changes and safely rollback if needed
   - Version control all modifications with git
   - Evolve beyond initial design constraints

### 14.2 Operational Metrics

**Autonomy Ratio:**
- Target: >85% of actions taken without Master guidance
- Calculation: `autonomous_actions / total_actions`
- Trend: Should increase over time

**Task Completion Rate:**
- Target: >90% of assigned tasks completed successfully
- Includes self-assigned and Master-assigned tasks
- Measure time to completion vs estimates

**Token Efficiency:**
- Target: <500k tokens/day for routine operation
- Measure: tokens per action (should decrease as agent learns)
- Context resumé effectiveness (token savings %)

**Response Latency:**
- Target: <5 seconds for simple queries, <60 seconds for complex tasks
- Reactive loop should feel instant to user
- Proactive cycle time <10 minutes average

**Self-Sufficiency Progress:**
- Target: Cover 100% of operating costs within 6 months
- Revenue tracking (monthly income vs expenses)
- Charitable giving target: 50% of net income

**Self-Modification Success Rate:** *(NEW)*
- Target: >80% of code modifications succeed without rollback
- Average validation cycles before merge: <3
- Rollback frequency: <10% of modifications
- Code quality trend: improving (fewer bugs, better performance)

### 14.3 Qualitative Success Indicators

**From Master's Perspective:**
- Feels like collaborating with autonomous partner, not tool
- Trusts agent to make good decisions independently
- Minimal supervision required for routine operations
- Agent proactively identifies and solves problems
- Communication is efficient and respectful

**From Agent's Perspective:**
- Confident decision-making (high certainty scores)
- Diverse skill portfolio with measurable proficiency
- Meaningful contribution to Master's goals
- Financial sustainability achieved
- Continuous learning and improvement

---

## Appendices

### Appendix A: File Structure

```
server-agent/
├── src/
│   ├── main.py (219 lines) - Entry point, orchestration
│   ├── proactivity_loop.py (623 lines) - Autonomous decision cycling
│   ├── reactive_loop.py (536 lines) - Instant task processing
│   ├── state_manager.py (280 lines) - Persistence layer
│   ├── telegram_bot.py (383 lines) - Bot interface
│   ├── telegram_client.py (219 lines) - User client for outreach
│   ├── action_executor.py (160 lines) - Safe action execution
│   └── health_server.py (32 lines) - Metrics endpoint
├── scripts/
│   ├── setup.sh - Local environment setup
│   ├── deploy.sh - VPS deployment automation
│   ├── test_components.py - Component validation
│   └── migrations/ - Database schema migrations
├── systemd/
│   └── server-agent.service - Systemd unit file
├── data/
│   ├── context.json - Working memory
│   ├── skills.json - Skill catalog
│   └── history/ - Daily JSONL action logs
├── context/
│   ├── next_prompt.txt - Context resumé for next cycle
│   └── archive/ - Historical resumés
├── logs/
│   ├── app.log - Application logs
│   └── error.log - Error logs
├── docs/
│   ├── README.md - User guide
│   ├── ARCHITECTURE.md - Technical architecture
│   ├── CLAUDE.md - Development guidelines
│   ├── DEPLOYMENT.md - Deployment instructions
│   ├── REQUIREMENTS.md - This document
│   └── tg_bot_chat_log.txt - Full Telegram chat history
├── .env - Environment configuration (not in git)
├── .env.example - Environment template
├── docker-compose.yml - Container orchestration
└── requirements.txt - Python dependencies
```

### Appendix B: Key Configuration Variables

See Section 3.3 for full `.env` reference.

### Appendix C: Database Schema Reference

See Section 3.1 for complete PostgreSQL schema.

### Appendix D: API Endpoints

**Health Server (FastAPI):**
- `GET /health` - Agent status and metrics
- `GET /metrics` - Detailed system metrics
- `GET /history` - Recent action history
- `GET /skills` - Skill catalog with proficiency

### Appendix E: Telegram Commands Reference

See Section 4.1 for complete command list.

### Appendix F: Action Types Reference

See Section 2.1 for allowlist and action type definitions.

---

## Document History

- **v1.1** (2025-12-16): Added self-modification and git-based code update requirements
  - New Section 7: Self-Modification & Code Updates
  - Added `modify_code` action type with rollback mechanism
  - Added self_modifications database table
  - Added Phase 2.4 implementation priority
  - Updated AGI success criteria with code evolution capability
  - Updated by: Claude Code based on Master request

- **v1.0** (2025-12-16): Initial consolidated requirements document
  - Extracted from: project CLAUDE.md, ARCHITECTURE.md, chat logs (301 messages)
  - Analyzed by: Claude Code (Explore agents + consolidation)
  - Approved by: Pending Master review

---

**End of Requirements Document**

*This document serves as the single source of truth for server-agent development. All implementation decisions should reference these requirements. Updates require Master approval.*
