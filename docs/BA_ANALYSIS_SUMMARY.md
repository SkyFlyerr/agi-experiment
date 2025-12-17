# Business Analysis Summary - Server Agent vNext

**Date:** 2025-12-17
**Analyst:** Claude Code (Business Analyst Agent)
**Project:** Server Agent vNext (v2.0.0 architectural redesign)

---

## Executive Summary

Server Agent vNext is a **complete architectural transformation** from file-based, polling-driven operation to a **database-first, webhook-driven, dual-loop autonomous AGI system**.

### Key Transformation

| Aspect | v1 (Current) | v2 (vNext) |
|--------|--------------|------------|
| **Communication** | Polling-based | Webhook-based (real-time) |
| **Memory** | JSON files | PostgreSQL database |
| **Context** | Manual file loading | Last 30 messages auto-loaded |
| **Architecture** | Single loop with meditation | Dual loops (reactive + proactive) |
| **Media** | Not processed | Voice transcripts, image analysis |
| **UX** | Delayed responses | <3 sec acknowledgment + approval |
| **Token Budget** | Manual tracking | Automated 7M/day enforcement |
| **Deployment** | Manual rsync | Git-triggered CI/CD with rollback |

---

## Deliverables Created

### 1. Technical Specifications (`TECHNICAL_SPECIFICATIONS.md`)

**Comprehensive 150+ page specification covering:**

- **System Architecture** - Container topology, dual-loop design, component breakdown
- **Database Schema** - 10+ tables with complete field definitions, indexes, constraints
- **API Contracts** - Telegram webhook format, Haiku classification output, Claude prompts
- **Business Rules** - 18+ detailed rules for message processing, approvals, token budgets
- **Data Models** - JSON examples for all major entities (messages, jobs, approvals, artifacts)
- **Implementation Roadmap** - 8 phases, 30 days, 50+ tasks with priorities

**Key Sections:**

1. **Database Schema (Section 3)** - Complete SQL schema with:
   - `chat_threads`, `chat_messages`, `message_artifacts`
   - `reactive_jobs`, `approvals`
   - `token_ledger`, `deployments`
   - Supporting tables: `tasks`, `projects`, `skills`, `contacts`, `financial_transactions`

2. **Telegram Webhook System (Section 4)** - Webhook registration, validation, processing pipeline

3. **Reactive Processing Loop (Section 5)** - Instant message handling with Haiku classification and approval workflow

4. **Proactive Autonomy Loop (Section 6)** - Token-budgeted autonomous cycling with adaptive intervals

5. **Message Processing Pipeline (Section 8)** - Voice transcription, image analysis, artifact storage

6. **Token Management (Section 10)** - Budget enforcement, ledger logging, cost tracking

7. **Self-Update Pipeline (Section 11)** - Git-triggered deployment with automated testing and rollback

### 2. Clarifications Document (`CLARIFICATIONS_NEEDED.md`)

**12 critical business decisions requiring Master input:**

**High Priority:**
1. Approval workflow strictness (all messages or selective?)
2. Token budget confirmation (7M/day acceptable cost?)
3. Voice transcription service (Whisper API vs alternatives)
4. Self-update safety level (autonomous code changes?)
5. Storage architecture (MinIO vs filesystem vs PostgreSQL-only)

**Medium Priority:**
6. Proactive action types (what can agent do without approval?)
7. Image analysis depth (Claude Vision for all images?)
8. Task/project schema timing (Phase 1 or later?)

**Low Priority:**
9. Message retention policy (keep forever or time-limited?)
10. Telegram user account integration (Telethon in Phase 1?)
11. Web UI priority (build now or defer?)
12. Database indexing refinements (partitioning for scale?)

### 3. This Summary (`BA_ANALYSIS_SUMMARY.md`)

Quick reference for stakeholders and Plan agent.

---

## Key Business Rules

### Message Processing

**Rule 1: Every message persisted**
- No message loss tolerance
- Full Telegram payload stored in `raw_payload` JSONB field
- Unique constraint on `(thread_id, platform_message_id)` prevents duplicates

**Rule 2: 30-message context window**
- All Claude prompts include last 30 messages from thread
- Artifacts (voice transcripts, image descriptions) inline in context
- Token-efficient (typically 3k-5k tokens for full context)

**Rule 3: Artifact processing priority**
- Voice: Immediate transcription (blocking, needed for context)
- Images: Immediate analysis (blocking, needed for context)
- Documents: Async metadata extraction (non-blocking)

### Approval Workflow

**Rule 4: All reactive jobs require approval**
- No exceptions in Phase 1 (safety-first)
- User receives acknowledgment + plan + OK button
- Execution begins only after button press

**Rule 5: Supersede logic**
- New message cancels pending approval
- Previous job marked 'superseded', new job created
- Prevents stale approvals from executing

**Rule 6: Approval timeout**
- Default: 1 hour
- Background job marks expired approvals as 'failed'
- Prevents indefinite pending states

### Token Budget

**Rule 7: Proactive budget hard limit**
- 7,000,000 tokens/day for scope='proactive'
- If exceeded, proactive loop pauses until midnight UTC
- Reactive operations NEVER count against budget

**Rule 8: Adaptive intervals**
- <25% budget used → 60 sec cycles (aggressive)
- 25-50% used → 300 sec cycles (moderate)
- 50-75% used → 900 sec cycles (conservative)
- >75% used → 3600 sec cycles (minimal)
- >100% used → pause until midnight

**Rule 9: All API calls logged**
- Every Claude API call recorded in `token_ledger`
- Includes: scope, model, input/output tokens, estimated cost
- Enables budget tracking and cost analytics

### Deployment

**Rule 10: Merge to main triggers deployment**
- Git hook detects merge, runs `build_and_deploy.sh`
- Only main branch triggers deployment (other branches ignored)

**Rule 11: Automatic rollback on failure**
- Health check fails → rollback to last healthy deployment
- Rollback searches `deployments` table for `status = 'healthy'`
- No healthy deployment found → manual intervention required

**Rule 12: Master notification always**
- All deployments (success or failure) notify Master via Telegram
- Notification includes: git SHA, test results, deployment status, rollback reason

---

## Data Schema Highlights

### Core Tables

**`chat_threads`** - Unique conversation contexts
- Tracks platform (telegram), chat_id, chat_type
- One thread per unique (platform, chat_id)
- `updated_at` refreshed on every new message

**`chat_messages`** - Complete conversation history
- role: 'user' | 'assistant' | 'system'
- Full text + raw Telegram payload (JSONB)
- Foreign key to thread
- Unique constraint: (thread_id, platform_message_id)

**`message_artifacts`** - Derived media data
- kind: 'voice_transcript' | 'image_json' | 'ocr_text' | 'file_meta'
- content_json: Structured artifact data
- uri: MinIO object path (optional)
- processing_status: 'pending' | 'processing' | 'completed' | 'failed'

**`reactive_jobs`** - Message processing queue
- status: 'queued' → 'classifying' → 'awaiting_approval' → 'executing' → 'completed'
- classification_result: Haiku output (intent, summary, plan)
- approval_id: Link to approval record

**`approvals`** - Inline button state
- status: 'pending' | 'approved' | 'rejected' | 'superseded' | 'expired'
- proposal_text: Plan shown to user
- telegram_message_id: Message with OK button
- resolved_at: When button pressed or superseded

**`token_ledger`** - Usage tracking
- scope: 'proactive' | 'reactive'
- tokens_input, tokens_output, tokens_total
- cost_usd: Estimated cost ($3/MTok input, $15/MTok output for Sonnet 4.5)
- meta_json: Request metadata (job_id, thread_id, etc.)

### Example Data Flow

**User sends voice message:**

1. **Webhook receives update** → `telegram_webhook.py` processes
2. **Thread created/found** → Insert/select from `chat_threads`
3. **Message inserted** → `chat_messages` with role='user', text=null, raw_payload={...}
4. **Voice downloaded** → Telegram API downloads .oga file
5. **Transcription queued** → `message_artifacts` created with status='pending'
6. **Whisper API called** → Voice transcribed to text
7. **Artifact updated** → status='completed', content_json={'text': '...', 'language': 'ru'}
8. **Job created** → `reactive_jobs` with trigger_message_id, status='queued'
9. **Worker picks up job** → Loads last 30 messages + artifacts
10. **Haiku classifies** → Intent: "question", plan: "Check database status"
11. **Approval sent** → Telegram message with OK button, `approvals` record created
12. **User presses OK** → Callback query updates approval status='approved'
13. **Claude executes** → Loads context, runs query, generates response
14. **Response sent** → Telegram message, `chat_messages` with role='assistant'
15. **Token logged** → `token_ledger` entry with scope='reactive'
16. **Job completed** → status='completed', finished_at=NOW()

---

## Implementation Complexity Assessment

### Database Setup (Phase 1)
**Complexity:** LOW
**Time:** 2-3 days
**Dependencies:** PostgreSQL 16, Docker Compose
**Risk:** Low (standard schema design)

### Telegram Webhook (Phase 2)
**Complexity:** MEDIUM
**Time:** 3-4 days
**Dependencies:** HTTPS setup (Nginx), Telegram bot token
**Risk:** Medium (webhook delivery reliability)

### Reactive Loop (Phase 3)
**Complexity:** HIGH
**Time:** 4-5 days
**Dependencies:** Haiku API, approval system, job polling
**Risk:** Medium (state machine complexity)

### Claude Integration (Phase 4)
**Complexity:** MEDIUM
**Time:** 3-4 days
**Dependencies:** Anthropic API, token logging
**Risk:** Low (straightforward API integration)

### Proactive Loop (Phase 5)
**Complexity:** HIGH
**Time:** 4-5 days
**Dependencies:** Budget tracking, adaptive scheduling
**Risk:** Medium (token budget enforcement logic)

### Self-Update Pipeline (Phase 6)
**Complexity:** HIGH
**Time:** 3-4 days
**Dependencies:** Git hooks, Docker build, rollback mechanism
**Risk:** High (deployment automation, potential for breakage)

**Total Estimated Time:** 20-25 days for full implementation

---

## Risk Assessment

### High Risks

**Risk 1: Webhook Reliability**
- Problem: Telegram webhooks can fail (network issues, server downtime)
- Mitigation: Implement webhook retry queue, polling fallback mode
- Impact: Message loss if webhook fails silently

**Risk 2: Token Budget Overage**
- Problem: Reactive loop unbounded, could spike costs if Master very active
- Mitigation: Add reactive token warning threshold (100k/request)
- Impact: Unexpected high API costs

**Risk 3: Deployment Rollback Failure**
- Problem: No healthy deployment to rollback to (first deployment fails)
- Mitigation: Manual intervention procedure documented, Master notified
- Impact: Service downtime until manual fix

### Medium Risks

**Risk 4: Database Connection Pool Exhaustion**
- Problem: High message volume → pool exhausted → webhook errors
- Mitigation: Connection pool sizing (min=2, max=10), monitoring
- Impact: Degraded performance, failed message processing

**Risk 5: Artifact Processing Delays**
- Problem: Whisper API slow or rate-limited → context incomplete
- Mitigation: Async artifact processing, proceed with partial context
- Impact: Lower quality responses until artifacts ready

### Low Risks

**Risk 6: Message Deduplication Failures**
- Problem: Telegram sends duplicate updates → duplicate messages in DB
- Mitigation: Unique constraint on (thread_id, platform_message_id)
- Impact: INSERT error, gracefully handled

---

## Success Metrics

### User Experience Metrics

**Target: <3 second acknowledgment**
- Measure: Time from webhook receipt to acknowledgment sent
- Goal: 95th percentile <3 seconds

**Target: <60 second response**
- Measure: Time from approval to final response sent
- Goal: 95th percentile <60 seconds

**Target: Zero message loss**
- Measure: All webhook updates result in DB entry
- Goal: 100% success rate

### System Performance Metrics

**Target: 7M tokens/day proactive budget**
- Measure: Sum of proactive scope tokens per day
- Goal: Never exceed 7.1M tokens/day

**Target: <$100/day API cost**
- Measure: Sum of cost_usd from token_ledger per day
- Goal: 95th percentile <$100/day

**Target: >99% deployment success**
- Measure: Deployments with status='healthy' / total deployments
- Goal: <1% rollback rate

### Autonomy Metrics

**Target: >80% autonomous proactive actions**
- Measure: Actions with certainty >0.8 / total proactive actions
- Goal: Agent operates mostly independently

**Target: <10 Master interventions/day**
- Measure: Count of approvals + ask_master actions
- Goal: Agent handles routine operations without interrupting Master

---

## Next Steps for Implementation

### Immediate (Before Coding)

1. **Master Reviews Specifications**
   - Read `TECHNICAL_SPECIFICATIONS.md` (comprehensive)
   - Answer high-priority questions in `CLARIFICATIONS_NEEDED.md`
   - Approve or request revisions

2. **Finalize Architecture Decisions**
   - Confirm: Approval workflow (all messages require OK?)
   - Confirm: Token budget (7M/day acceptable?)
   - Confirm: Storage approach (MinIO, filesystem, or PostgreSQL?)
   - Confirm: Self-update safety level (autonomous or Master-approved?)

3. **Launch Plan Agent**
   - Input: Approved technical specifications
   - Output: Detailed implementation plan with task breakdown
   - Tools: Use @agent-Plan with thoroughness: "very thorough"

### Phase 1: Foundation (Days 1-3)

4. **Setup Development Environment**
   - Install PostgreSQL 16 via Docker Compose
   - Create database schema (all tables from spec)
   - Test connection pool and basic queries

5. **Implement Core Modules**
   - `app/config.py` ✅ (already complete)
   - `app/database.py` ✅ (already complete)
   - `app/main.py` ✅ (already complete)

6. **Setup Infrastructure**
   - Configure Nginx reverse proxy for HTTPS
   - Register Telegram webhook
   - Test webhook delivery

### Phase 2-8: Full Implementation (Days 4-30)

7. **Follow Implementation Roadmap**
   - Phase 2: Telegram webhook system (Days 4-6)
   - Phase 3: Reactive processing loop (Days 7-10)
   - Phase 4: Claude integration (Days 11-13)
   - Phase 5: Proactive autonomy loop (Days 14-17)
   - Phase 6: Self-update pipeline (Days 18-20)
   - Phase 7: Production hardening (Days 21-25)
   - Phase 8: UX polish (Days 26-30)

8. **Launch & Monitor**
   - Deploy to Frankfurt server (92.246.136.186)
   - Monitor metrics (token usage, response latency, error rate)
   - Iterate based on real-world usage

---

## Business Analyst Recommendations

### High Priority Recommendations

**Recommendation 1: Start with Strict Approval Workflow**
- Require OK button for ALL reactive operations in Phase 1
- Prevents accidental unwanted actions
- Evolve to selective approval after 2-4 weeks of stable operation

**Recommendation 2: Implement Token Cost Alerts**
- Daily summary at midnight: total tokens used, cost, budget status
- Real-time alert if single request >100k tokens
- Gives Master visibility into spending patterns

**Recommendation 3: Use Filesystem Storage Initially**
- Defer MinIO to Phase 2 (multi-month timeline)
- Store media in `/opt/server-agent/media/` directory
- Migrate to MinIO when media volume grows or multi-server deployment needed

**Recommendation 4: Master-Approved Code Changes Only (Phase 1)**
- Agent can identify bugs and propose fixes
- Master reviews and merges via GitHub/GitLab
- Enables full autonomy (agent merges) after 3-6 months of stable operation

**Recommendation 5: Implement Web UI in Phase 2**
- Use Telegram for all transparency in Phase 1
- Build web UI for chain-of-thought visualization after core functionality stable
- Reduces initial complexity, focuses on core AGI capabilities

### Medium Priority Recommendations

**Recommendation 6: Gradual Autonomy Expansion**
- Start with conservative certainty threshold (90%)
- Lower to 80% after 100+ successful autonomous actions
- Track autonomy ratio, aim for >85% autonomous over time

**Recommendation 7: Optimize Context Loading**
- Start with 30 messages (spec default)
- Monitor token usage, adjust if excessive
- Consider summarization for very old messages (>1 month)

**Recommendation 8: Implement Task/Project Schema in Phase 1**
- Cheap to create empty tables during initial schema setup
- Avoids migration later when needed
- Populate in Phase 5+ when proactive loop uses task management

---

## Files Created

1. **`/Users/maksimbozhko/Development/server-agent/docs/TECHNICAL_SPECIFICATIONS.md`**
   - 150+ page comprehensive specification
   - Database schema, API contracts, business rules, data models
   - Implementation roadmap with 8 phases, 50+ tasks

2. **`/Users/maksimbozhko/Development/server-agent/docs/CLARIFICATIONS_NEEDED.md`**
   - 12 critical business decisions
   - High/medium/low priority categorization
   - Recommendations for each decision

3. **`/Users/maksimbozhko/Development/server-agent/docs/BA_ANALYSIS_SUMMARY.md`**
   - This file
   - Executive summary, key rules, data flow examples
   - Risk assessment, success metrics, next steps

---

## Approval Required

**Master (Max Bozhko):** Please review the deliverables above and provide approval or feedback.

**Questions for Master:**
1. Are the technical specifications aligned with your vision for Server Agent vNext?
2. Which high-priority clarifications (Questions 1-6) need answers before starting implementation?
3. Should we launch the Plan agent to create detailed implementation plan?
4. Any concerns or requested changes to the proposed architecture?

**Ready to Proceed:** Upon approval, we can:
- Launch @agent-Plan for detailed task breakdown
- Begin Phase 1 implementation (database and infrastructure)
- Establish development workflow (git branches, testing, deployment)

---

**Business Analysis Complete**

All requirements processed, specifications documented, clarifications identified. Ready for planning and implementation phases.

**Generated by:** Claude Code Business Analyst Agent
**Date:** 2025-12-17
**Project:** Server Agent vNext v2.0.0
