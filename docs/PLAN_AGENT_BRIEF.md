# Plan Agent Brief - Server Agent vNext Implementation

**Purpose:** Input document for @agent-Plan to create detailed implementation plan
**Project:** Server Agent vNext v2.0.0
**Date:** 2025-12-17

---

## Context for Plan Agent

You are creating an implementation plan for a **complete architectural redesign** of an autonomous AGI server agent. This is not an incremental update - it's a ground-up rebuild with new architecture, database schema, and processing model.

### What Already Exists

**Completed:**
- `app/config.py` - Environment variable management with Pydantic Settings ✅
- `app/database.py` - AsyncPG connection pool manager ✅
- `app/main.py` - FastAPI application skeleton with health endpoint ✅
- Docker Compose configuration (partial)
- `.env.example` template

**Legacy Code (to be replaced/refactored):**
- `src/telegram_bot.py` - Polling-based bot (replace with webhook)
- `src/reactive_loop.py` - File-based context (replace with DB-backed)
- `src/proactivity_loop.py` - JSON context files (replace with DB-backed)
- `src/state_manager.py` - File-based state (replace with PostgreSQL)

**Infrastructure Available:**
- VPS Server: Frankfurt (IP: 92.246.136.186)
- PostgreSQL 16 ready to deploy via Docker Compose
- Telegram Bot: @agi_superbot (token available in .env)
- Claude API: Anthropic OAuth token configured
- MinIO: Can be added to Docker Compose

---

## Source Documents (Read These)

**Primary Specifications:**
1. **`TECHNICAL_SPECIFICATIONS.md`** - 150+ page comprehensive spec
   - Complete database schema with all tables, indexes, constraints
   - API contracts (Telegram webhook, Haiku, Claude prompts)
   - Business rules (18+ detailed rules)
   - Data models with JSON examples
   - 8-phase implementation roadmap

2. **`CLARIFICATIONS_NEEDED.md`** - 12 business decisions
   - High-priority questions (approval workflow, token budget, storage, self-update)
   - Medium-priority questions (action types, image analysis, schema timing)
   - Low-priority questions (retention, Telethon, web UI, indexing)

3. **`BA_ANALYSIS_SUMMARY.md`** - Executive summary
   - Transformation overview (v1 → v2)
   - Key business rules
   - Risk assessment
   - Success metrics

4. **`ARCHITECTURE_DIAGRAM.md`** - Visual diagrams
   - System overview
   - Dual-loop architecture
   - Message processing flows
   - Database relationships

**Original Requirements (for context):**
5. **`docs/REQUIREMENTS.md`** - Original consolidated requirements
6. **`docs/AGI_ONE_PROMPT_SPEC.md`** - AGI One-Prompt build spec
7. **`README.md`** - Original project philosophy and goals

---

## Implementation Scope

### What Needs to Be Built

**Phase 1: Database & Infrastructure (Days 1-3)**
- PostgreSQL schema creation (10+ tables)
- Docker Compose setup (postgres, app, optional minio)
- Database migration scripts
- Connection pool testing

**Phase 2: Telegram Webhook System (Days 4-6)**
- Webhook registration with Telegram
- HTTPS setup (Nginx reverse proxy)
- Webhook handler endpoint (`app/telegram_webhook.py`)
- Message normalization logic
- Media download (voice, images, documents)
- Thread creation/lookup

**Phase 3: Reactive Processing Loop (Days 7-10)**
- Haiku classifier (`app/haiku_classifier.py`)
- Reactive worker (`app/reactive_worker.py`)
- Approval manager (`app/approval_manager.py`)
- Context loading (last 30 messages + artifacts)
- Job polling and state machine
- Inline button handling (callback queries)

**Phase 4: Claude Integration (Days 11-13)**
- Claude client (`app/claude_client.py`)
- Token usage logging
- Context assembly for Claude API
- Response parsing and sending
- Error handling and retries

**Phase 5: Proactive Autonomy Loop (Days 14-17)**
- Proactive scheduler (`app/proactive_scheduler.py`)
- Token budget tracking
- Adaptive interval calculation
- Decision prompt templates
- Autonomous action execution
- Significance-based reporting

**Phase 6: Self-Update Pipeline (Days 18-20)**
- Git repository setup on server
- Git hooks (post-merge)
- Deployment script (`scripts/build_and_deploy.sh`)
- Test runner (`scripts/run_tests.sh`)
- Rollback mechanism (`scripts/rollback.sh`)
- Master notification script

**Phase 7: Production Hardening (Days 21-25)**
- Error handling and logging
- Performance optimization (query profiling, indexes)
- Monitoring and observability
- Connection pool tuning
- Retry logic for transient failures

**Phase 8: UX Polish (Days 26-30)**
- Rich HTML formatting for Telegram messages
- Long message splitting (4096 char limit)
- Typing indicators
- Progress updates for long-running tasks
- Command enhancements (`/status`, `/stats`, `/cancel`)

---

## Key Constraints

### Technical Constraints

1. **Database Schema Must Be Complete in Phase 1**
   - All tables defined in TECHNICAL_SPECIFICATIONS.md Section 3.1
   - Indexes created for performance
   - Foreign key constraints enforced
   - No schema changes allowed after Phase 2 (migration complexity)

2. **Webhook Must Work Before Reactive Loop**
   - Phase 2 (webhook) must be complete before Phase 3 (reactive worker)
   - Cannot test reactive loop without webhook ingestion

3. **Token Logging Required from Day 1 of API Integration**
   - All Claude API calls must log to `token_ledger`
   - Budget tracking depends on accurate logging
   - Retroactive logging is impossible

4. **Deployment Pipeline Must Not Break Development**
   - Git hooks only trigger on main branch merges
   - Development work happens on feature branches
   - Rollback mechanism must be tested before first production deployment

### Business Constraints

1. **Zero Message Loss Tolerance**
   - Every webhook update must result in database entry
   - Failures must be logged and alerted
   - Idempotency required (duplicate updates handled gracefully)

2. **Reactive Loop Prioritized Over Proactive**
   - User messages always processed immediately
   - Proactive loop can pause, reactive cannot
   - Reactive token usage unbounded (user experience > cost)

3. **Approval Required for All Reactive Operations (Phase 1)**
   - No exceptions - all jobs need OK button press
   - Can evolve to selective approval in future phases
   - Safety first approach

4. **Self-Update Requires Master Approval (Phase 1)**
   - Agent identifies bugs and proposes fixes
   - Master reviews and merges to main
   - Autonomous merging is future goal (not Phase 1)

---

## Dependencies & Prerequisites

### External Services Required

1. **Telegram Bot API**
   - Bot token: Available in `.env`
   - Webhook URL: Requires HTTPS (Nginx + Let's Encrypt)
   - Secret token: Generate random string for webhook validation

2. **Anthropic Claude API**
   - OAuth token: Available in `.env`
   - Models: claude-sonnet-4-5-20250929, claude-3-5-haiku-20241022
   - Rate limits: Monitor and handle 429 errors

3. **Whisper API (OpenAI) - Optional in Phase 1**
   - API key: Needs to be obtained
   - Cost: $0.006/minute for voice transcription
   - Alternative: Defer voice processing to Phase 2+

4. **MinIO (Optional in Phase 1)**
   - Can use filesystem storage initially (`/opt/server-agent/media/`)
   - Migrate to MinIO in Phase 2+ when media volume grows

### Infrastructure Requirements

1. **VPS Server (Frankfurt)**
   - IP: 92.246.136.186
   - OS: Ubuntu
   - Resources: 2 cores, 4GB RAM, 60GB storage
   - SSH access: root with password (rotate to key-based auth)

2. **Docker & Docker Compose**
   - Already installed on server
   - Version: Latest stable

3. **Nginx**
   - For HTTPS reverse proxy
   - Let's Encrypt for SSL certificates
   - Configuration: Proxy /webhook/telegram to app:8000

4. **Domain Name (Optional but Recommended)**
   - Telegram requires HTTPS for webhooks
   - Can use IP + self-signed cert, but domain preferred
   - Example: server-agent.yourdomain.com

---

## Risk Mitigation Strategies

### High Risks

**Risk 1: Webhook Delivery Failures**
- Mitigation: Implement polling fallback mode
- Mitigation: Log all webhook errors with full payload
- Mitigation: Alert Master on repeated failures

**Risk 2: Token Budget Overage**
- Mitigation: Implement reactive token warning (100k threshold)
- Mitigation: Daily cost summary sent to Master
- Mitigation: Emergency pause mechanism if daily cost >$200

**Risk 3: Deployment Rollback Failure**
- Mitigation: Test rollback mechanism before first production use
- Mitigation: Manual intervention procedure documented
- Mitigation: Keep last 3 healthy images (not just 1)

### Medium Risks

**Risk 4: Database Connection Pool Exhaustion**
- Mitigation: Start with conservative pool size (max=10)
- Mitigation: Monitor active connections via `/stats` endpoint
- Mitigation: Implement connection timeout (60 seconds)

**Risk 5: Artifact Processing Delays**
- Mitigation: Async artifact processing (non-blocking)
- Mitigation: Proceed with partial context if artifacts pending
- Mitigation: Set artifact processing timeout (30 seconds)

---

## Success Criteria (Acceptance Tests)

### Phase 1 Complete When:
- [ ] PostgreSQL container running and reachable
- [ ] All tables created with correct schema
- [ ] Health endpoint returns database connection status
- [ ] Can insert and query messages manually via psql

### Phase 2 Complete When:
- [ ] Webhook receives updates from Telegram
- [ ] Text messages inserted into `chat_messages`
- [ ] Voice messages downloaded and stored
- [ ] Images downloaded and stored
- [ ] Jobs created in `reactive_jobs`

### Phase 3 Complete When:
- [ ] Haiku classifies intent within 3 seconds
- [ ] Plan sent to user with OK button
- [ ] Pressing OK triggers job execution
- [ ] New message supersedes pending approval
- [ ] Approval timeout works after 1 hour

### Phase 4 Complete When:
- [ ] Claude generates responses from context
- [ ] Responses sent to Telegram
- [ ] Tokens logged to `token_ledger`
- [ ] Full reactive flow works end-to-end (webhook → response)

### Phase 5 Complete When:
- [ ] Proactive loop cycles autonomously
- [ ] Token budget enforced (pauses at 7M)
- [ ] Adaptive intervals adjust based on usage
- [ ] Agent can develop skills autonomously
- [ ] Uncertain decisions ask Master for guidance

### Phase 6 Complete When:
- [ ] Merge to main triggers deployment
- [ ] Tests run before deployment
- [ ] New container starts successfully
- [ ] Failed deployment rolls back automatically
- [ ] Master receives deployment notifications

### Phase 7 Complete When:
- [ ] All error scenarios logged properly
- [ ] Database queries optimized (all <200ms)
- [ ] Monitoring dashboard shows key metrics
- [ ] Agent survives container restarts gracefully

### Phase 8 Complete When:
- [ ] Long messages split correctly (<4096 chars)
- [ ] Rich HTML formatting works
- [ ] All commands functional (`/status`, `/stats`, `/cancel`)
- [ ] User experience feels polished

---

## Recommended Planning Approach

### Phase Grouping

**Group 1: Foundation (Phases 1-2)**
- Can work in parallel: Database setup while configuring webhook
- Critical path: HTTPS setup → Webhook registration → Testing
- Estimated: 5-7 days

**Group 2: Core Functionality (Phases 3-4)**
- Sequential: Reactive worker depends on webhook ingestion
- Critical path: Haiku integration → Approval system → Claude integration
- Estimated: 7-9 days

**Group 3: Autonomy (Phase 5)**
- Parallel to reactive loop (separate worker)
- Critical path: Token budget system → Decision loop → Action execution
- Estimated: 4-5 days

**Group 4: Deployment & Polish (Phases 6-8)**
- Can work in parallel: Deployment pipeline while doing UX polish
- Critical path: Git hooks → Deployment script → Testing
- Estimated: 9-11 days

**Total: 25-32 days (4-5 weeks)**

### Task Breakdown Strategy

For each phase, create tasks in this order:

1. **Setup/Configuration** - Environment, dependencies, configs
2. **Core Implementation** - Main logic, business rules
3. **Integration** - Connect to external services, database
4. **Testing** - Unit tests, integration tests, manual testing
5. **Documentation** - Code comments, API docs, deployment notes

### Milestone Markers

- **Milestone 1 (End of Phase 2):** "Webhook receives and persists messages"
- **Milestone 2 (End of Phase 4):** "Full reactive loop operational"
- **Milestone 3 (End of Phase 5):** "Proactive loop autonomous"
- **Milestone 4 (End of Phase 6):** "Self-update pipeline functional"
- **Milestone 5 (End of Phase 8):** "Production-ready v2.0.0"

---

## Plan Agent Instructions

### What to Produce

Create a **detailed implementation plan** with:

1. **Phase-by-phase breakdown** (8 phases as outlined above)
2. **Task list for each phase** with:
   - Task title (clear, actionable)
   - Task description (what needs to be done)
   - Dependencies (which tasks must complete first)
   - Estimated time (hours or days)
   - Files to create/modify
   - Testing requirements

3. **Critical path analysis**
   - Identify longest dependency chain
   - Highlight parallel work opportunities
   - Flag blocking tasks

4. **Risk mitigation tasks**
   - Testing and validation steps
   - Rollback procedures
   - Error handling requirements

5. **Delivery milestones**
   - Clear acceptance criteria per phase
   - Demo-able functionality at each milestone

### Format

Use structured format:

```markdown
## Phase 1: Database & Infrastructure (Days 1-3)

### Overview
[Brief description of phase goals and deliverables]

### Tasks

#### Task 1.1: Create PostgreSQL Schema
**Description:** Implement all tables from TECHNICAL_SPECIFICATIONS.md Section 3.1
**Dependencies:** None
**Estimated Time:** 4-6 hours
**Files:**
- Create: `scripts/migrations/001_initial_schema.sql`
- Create: `scripts/migrations/run_migrations.sh`
**Testing:**
- Manual: Run migration script, verify tables exist
- Manual: Test foreign key constraints with sample data
**Acceptance:**
- [ ] All 10+ tables created
- [ ] All indexes created
- [ ] Can insert sample data and query successfully

#### Task 1.2: ...
[Continue for all tasks in phase]

### Phase Acceptance Criteria
- [ ] PostgreSQL container running
- [ ] All tables created
- [ ] Health endpoint functional

### Estimated Phase Duration: 2-3 days
```

### Thoroughness Level

Use **"very thorough"** mode:
- Include ALL tasks from TECHNICAL_SPECIFICATIONS.md roadmap
- Add testing tasks for each implementation task
- Include configuration and deployment tasks
- Don't skip "obvious" tasks (e.g., creating directories, installing packages)
- Break large tasks into smaller subtasks (max 4-6 hours per task)

### Key Considerations

1. **Dependencies are critical** - Mark all task dependencies clearly
2. **Testing at every step** - Every implementation task should have corresponding test tasks
3. **Deployment considerations** - Include tasks for deploying to server, not just local development
4. **Documentation** - Include tasks for updating docs as implementation progresses
5. **Rollback plans** - For risky changes, include rollback task immediately after

---

## Questions for Plan Agent

If you need clarification during planning:

1. **High-priority questions:** Check `CLARIFICATIONS_NEEDED.md` - Master needs to answer these
2. **Technical questions:** Check `TECHNICAL_SPECIFICATIONS.md` for detailed specs
3. **Architecture questions:** Check `ARCHITECTURE_DIAGRAM.md` for visual flows
4. **Implementation details:** Make reasonable assumptions, document them in plan

**Do not block on unanswered questions.** Document assumptions and continue planning. Master will review and clarify before implementation begins.

---

## Output Location

Create plan in:
- `/Users/maksimbozhko/Development/server-agent/docs/IMPLEMENTATION_PLAN.md`

Include:
- Table of contents
- Phase-by-phase breakdown (as detailed above)
- Critical path diagram (text-based)
- Timeline estimate (with ranges)
- Resource requirements (what Master needs to provide)
- Next steps (what to do after plan approved)

---

**Ready for Plan Agent execution. All source documents available in `/Users/maksimbozhko/Development/server-agent/docs/`**

**Estimated plan creation time:** 30-60 minutes for very thorough breakdown
**Estimated implementation time:** 25-32 days (4-5 weeks) based on this planning brief
