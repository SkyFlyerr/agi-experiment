# Server Agent vNext - Clarifications Needed

**Date:** 2025-12-17
**Status:** Questions for Master (Max Bozhko) before implementation

---

## Critical Business Decisions

### 1. Approval Workflow Strictness

**Question:** Should ALL reactive operations require approval, or only certain types?

**Current Spec:** All reactive jobs require OK button press before execution (safety-first approach)

**Alternatives:**
- **Option A (Current):** Every message gets acknowledgment → plan → OK button → execution
  - Pros: Maximum safety, user always in control
  - Cons: Extra click for every interaction, slower UX

- **Option B:** Simple queries auto-execute, only commands require approval
  - Pros: Faster UX for questions
  - Cons: Need to define "simple query" vs "command" boundary

- **Option C:** Trust-based: first 10 interactions require approval, then auto-approve if confidence >90%
  - Pros: Learns Master's preferences
  - Cons: Risk of unwanted actions

**Recommendation:** Start with Option A (all require approval), then evolve to Option B based on experience.

---

### 2. Token Budget Allocation

**Question:** Is 7M tokens/day for proactive operations the right target?

**Context:**
- Claude Sonnet 4.5: ~3k input + 1k output per cycle = 4k tokens/cycle
- 7M tokens/day = ~1,750 proactive cycles per day = 73 cycles/hour = 1.2 cycles/minute (at full utilization)

**Current Spec:** 7,000,000 tokens/day (proactive only, reactive unbounded)

**Considerations:**
- **Cost:** At $3/MTok input + $15/MTok output:
  - 7M tokens = ~$50-80/day (depending on input/output ratio)
  - Monthly cost: ~$1,500-2,400
- **Usage Pattern:** Agent likely won't hit limit daily (intervals increase as budget depletes)
- **Reactive Buffer:** Unlimited reactive tokens could spike costs if Master very active

**Questions for Master:**
1. Is $50-80/day budget acceptable for proactive operations?
2. Should we set a soft limit on reactive tokens (e.g., warn if single request >100k tokens)?
3. Should we implement daily cost alerts (e.g., email if daily spend >$100)?

**Recommendation:**
- Keep 7M/day proactive limit
- Add reactive warning threshold at 100k tokens/request
- Implement daily cost summary sent to Master every midnight

---

### 3. Voice Transcription Service

**Question:** Which transcription service should we use for voice messages?

**Options:**

**Option A: Whisper API (OpenAI)**
- Cost: $0.006/minute
- Quality: Excellent (best in class)
- Languages: 90+ languages
- Integration: Simple REST API
- Cons: Requires OpenAI API key (additional dependency)

**Option B: Google Cloud Speech-to-Text**
- Cost: $0.006-0.024/minute (depending on model)
- Quality: Excellent
- Languages: 125+ languages
- Cons: Requires Google Cloud account setup

**Option C: AssemblyAI**
- Cost: $0.00025/second (~$0.015/minute)
- Quality: Very good
- Languages: 50+ languages
- Pros: Simple API, good for Russian language

**Option D: Local Whisper (self-hosted)**
- Cost: Free (compute only)
- Quality: Good (OpenAI Whisper model)
- Cons: Requires GPU or slow CPU transcription, adds complexity

**Recommendation:** Start with Whisper API (Option A) for simplicity and quality. Cost is negligible compared to Claude API usage.

---

### 4. Image Analysis Approach

**Question:** How deeply should images be analyzed?

**Current Spec:** Claude Vision analyzes images and returns JSON with description, objects, text (OCR)

**Alternatives:**

**Option A (Current): Claude Vision for all images**
- Pros: Single API, high quality, contextual understanding
- Cons: ~1k-2k tokens per image (input tokens for image)
- Cost: Moderate ($3/MTok input = $0.003-0.006 per image)

**Option B: Dedicated OCR + object detection**
- Use Tesseract for text extraction (free)
- Use YOLO for object detection (free, self-hosted)
- Fallback to Claude Vision only if Master explicitly asks
- Pros: Lower cost for routine images
- Cons: More complex, less contextual understanding

**Option C: Lazy analysis**
- Store image reference only, don't analyze by default
- Analyze on-demand when user references the image
- Pros: Zero cost for ignored images
- Cons: Slower response if user asks about image immediately

**Recommendation:** Option A (Claude Vision for all images). Master interaction likely won't include many images, cost impact minimal.

---

### 5. Self-Update Safety Level

**Question:** Should agent be allowed to modify its own code autonomously?

**Context:** Original requirements (REQUIREMENTS.md Section 7) included full self-modification capability.

**Current Spec:** Deployment pipeline triggered by git merge, but who initiates the merge?

**Options:**

**Option A: Master-only code changes**
- Agent can identify bugs and propose fixes
- Master reviews code changes in GitHub/GitLab
- Master manually merges to main
- Pros: Maximum safety
- Cons: Agent not fully autonomous

**Option B: Agent can merge low-risk changes autonomously**
- Define "low-risk": documentation updates, log message improvements, comment additions
- Agent can merge these to main automatically
- Code changes require Master approval
- Pros: Balance of autonomy and safety
- Cons: Need to define risk boundaries clearly

**Option C: Full autonomy with notification**
- Agent can merge any changes to main
- Automatic rollback if deployment fails
- Master notified after successful deployment
- Pros: True AGI autonomy
- Cons: Risk of unexpected behavior changes

**Recommendation:** Start with Option A, evolve to Option B once agent demonstrates reliable judgment. Option C is future goal after 6+ months of stable operation.

---

### 6. MinIO vs. Database-Only Storage

**Question:** Do we need MinIO, or can we store everything in PostgreSQL?

**Current Spec:** MinIO (S3-compatible storage) for media files, PostgreSQL for metadata

**Alternatives:**

**Option A (Current): PostgreSQL + MinIO**
- PostgreSQL: Structured data, metadata
- MinIO: Media files (voice, images, documents)
- Pros: Clean separation, scalable
- Cons: Additional service to manage

**Option B: PostgreSQL only**
- Store media as BYTEA (binary) in PostgreSQL
- Pros: Simpler architecture, one less service
- Cons: Larger database, slower backups, less scalable

**Option C: PostgreSQL + filesystem**
- Store media files on disk (`/opt/server-agent/media/`)
- PostgreSQL stores file paths
- Pros: Simple, no additional service
- Cons: Not S3-compatible, harder to scale

**Recommendation:**
- **Phase 1:** Option C (filesystem) for MVP
- **Phase 2:** Migrate to Option A (MinIO) when media volume grows or multi-server deployment needed

---

### 7. Proactive Action Types

**Question:** What actions should proactive loop be allowed to execute autonomously?

**Current Spec (from REQUIREMENTS.md):**

**SAFE_INTERNAL_ACTIONS (no approval):**
- develop_skill
- meditate
- work_on_task
- update_context

**SAFE_EXTERNAL_ACTIONS (no approval):**
- communicate (send message to Master)
- ask_master (request guidance)

**RISKY_EXTERNAL_ACTIONS (require approval):**
- proactive_outreach (contact external people)
- financial_transaction (spend or earn money)
- infrastructure_change (modify server configuration)

**Questions:**
1. Should agent be able to send messages to Master proactively without approval?
   - Pro: Faster communication (e.g., "Task completed", "Found issue X")
   - Con: Could be annoying if too frequent

2. Should agent be able to start tasks autonomously?
   - Current spec: Agent can work_on_task if self-assigned
   - Alternative: All tasks require Master approval before starting

3. What about code modifications (from Section 7 of REQUIREMENTS.md)?
   - Should modify_code be RISKY (require approval)?
   - Or separate category: LOW_RISK_MOD (documentation) vs HIGH_RISK_MOD (logic changes)?

**Recommendation:**
- communicate action: Require approval if significance >75%, allow autonomous if <75%
- work_on_task: Allow autonomous start, but send notification when started
- modify_code: Always require approval in Phase 1, reconsider after stable operation

---

## Data Schema Questions

### 8. Message Retention Policy

**Question:** How long should we keep messages and artifacts?

**Current Spec:** Indefinite retention (all messages kept forever)

**Considerations:**
- **Storage:** PostgreSQL database will grow continuously
  - Estimated: ~1KB per message + metadata
  - 1000 messages/day = 1MB/day = 365MB/year (negligible)
- **Privacy:** Master may want deletion capability
- **Audit:** Financial/legal reasons may require retention
- **Performance:** Very large tables may slow queries (mitigated by indexes)

**Options:**
- **Option A:** Keep everything forever (current spec)
- **Option B:** Soft delete on request (mark as deleted, don't show in context, but keep in DB)
- **Option C:** Hard delete after N days (e.g., 1 year) with archive export
- **Option D:** Compress/archive old messages (e.g., monthly summaries instead of individual messages)

**Recommendation:** Option B (soft delete on request) with Option D (monthly summary generation) for very old conversations.

---

### 9. Task and Project Schema

**Question:** Do we need full task/project management in Phase 1?

**Current Spec:** Tables defined but marked as "Future" in Section 3.2

**Implementation Scope:**
- Tasks table: For Master-assigned and self-assigned tasks
- Projects table: For multi-task initiatives
- Skills table: For skill development tracking

**Questions:**
1. Should we implement these tables in Phase 1 (database setup)?
   - Pro: Avoid migration later
   - Con: Not used until Phase 5+

2. Or defer until needed?
   - Pro: Faster MVP
   - Con: Requires migration later

**Recommendation:** Implement schema in Phase 1 (cheap to create empty tables), populate in Phase 5+.

---

## Integration Questions

### 10. Telegram User Account (Telethon)

**Question:** Should we implement proactive messaging capability in Phase 1?

**Context:** Original requirements include Telethon for agent to send messages from personal Telegram account

**Current Spec:** Not included in vNext architecture (focused on bot-only)

**Use Cases:**
- Agent contacts external people (collaborators, clients)
- Agent sends updates to groups/channels
- Agent reads messages from other chats for context

**Considerations:**
- **Complexity:** Telethon requires phone number authentication, session management
- **Risk:** Using personal account for bot actions could trigger Telegram spam detection
- **Alternative:** Use bot for all communication, Master forwards to external parties manually

**Recommendation:** Defer Telethon integration to Phase 2+. Bot-only communication sufficient for MVP.

---

### 11. Web UI Priority

**Question:** Should we build Web UI in Phase 1-2, or defer?

**Context:** Original architecture includes web UI for chain-of-thought visualization

**Current Spec:** Not included in Phase 1-8 roadmap

**Use Cases:**
- Master observes agent reasoning in real-time
- Debug decision-making process
- Transparency for external observers

**Alternatives:**
- **Option A:** Build basic web UI in Phase 7 (after core functionality stable)
- **Option B:** Use Telegram for all transparency (send reasoning as messages)
- **Option C:** Defer until Phase 2 (multi-month timeline)

**Recommendation:** Option B (Telegram-only transparency) for Phase 1. Build web UI in Phase 2 if Master requests it.

---

## Performance and Scaling

### 12. Database Indexing Strategy

**Question:** Are the proposed indexes sufficient for performance?

**Current Spec:** Indexes defined in Section 3.1 (thread lookups, message queries, job polling)

**Performance Targets:**
- Message insertion: <50ms
- Context loading (30 messages): <200ms
- Job polling: <100ms
- Token budget check: <50ms

**Questions:**
1. Should we add composite indexes for common query patterns?
   - Example: `(thread_id, created_at DESC, role)` for filtering by role
2. Should we use BRIN indexes for timestamp columns?
   - Pros: Smaller index size for large tables
   - Cons: Slightly slower lookups
3. Should we partition large tables (chat_messages) by date?
   - Pros: Faster queries, easier archiving
   - Cons: More complex schema

**Recommendation:** Start with indexes in spec, add composite indexes based on actual query patterns in production. Defer partitioning until >1M messages.

---

## Clarification Summary

**High Priority (Need answers before Phase 1):**
1. Approval workflow strictness (Question 1)
2. Token budget confirmation (Question 2)
3. Voice transcription service (Question 3)
4. Self-update safety level (Question 5)
5. MinIO vs. filesystem storage (Question 6)

**Medium Priority (Need answers before Phase 3):**
6. Proactive action types (Question 7)
7. Image analysis approach (Question 4)
8. Task/project schema timing (Question 9)

**Low Priority (Can decide during implementation):**
9. Message retention policy (Question 8)
10. Telethon integration timing (Question 10)
11. Web UI priority (Question 11)
12. Database indexing refinements (Question 12)

---

## Recommended Next Steps

1. **Review Technical Specifications** - Read `/Users/maksimbozhko/Development/server-agent/docs/TECHNICAL_SPECIFICATIONS.md`
2. **Answer High Priority Questions** - Provide decisions on Questions 1-6 above
3. **Launch Plan Agent** - Create detailed implementation plan based on approved specs
4. **Begin Phase 1** - Database and infrastructure setup
5. **Iterate** - Adjust based on real-world usage patterns

---

**Master Approval Required Before Proceeding**

Please review and provide guidance on high-priority questions. Implementation can begin once decisions are made.
