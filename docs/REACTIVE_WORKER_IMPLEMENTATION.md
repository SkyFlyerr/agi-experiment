# Reactive Worker Implementation

**Phase 3-4: Haiku Classification and Claude Execution**

This document describes the implementation of the reactive worker system with two-phase AI processing.

---

## Architecture Overview

The reactive worker implements a **persistence-first, two-phase AI processing architecture**:

### Phase 1: Haiku Classification (Fast & Cheap)
- **Model**: Claude 3.5 Haiku (`claude-3-5-haiku-20241022`)
- **Purpose**: Quick intent classification
- **Output**: JSON with intent, summary, plan, needs_confirmation, confidence
- **Cost**: ~10x cheaper than Sonnet
- **Speed**: ~2-3x faster than Sonnet

### Phase 2: Claude Execution (Powerful & Accurate)
- **Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Purpose**: Task execution, response generation
- **Input**: Full conversation context + classification results
- **Output**: Natural language response + optional tool calls
- **Capabilities**: Complex reasoning, tool use, multi-step execution

---

## System Components

### 1. AI Module (`app/ai/`)

#### `haiku.py` - Haiku Classifier
```python
async def classify_intent(
    messages: List[ChatMessage],
    trigger_message: ChatMessage,
    job_id: UUID | None = None,
) -> ClassificationResult
```

**Responsibilities:**
- Analyze conversation context
- Classify user intent (question/command/other)
- Determine if confirmation needed
- Return confidence score
- Log token usage to database

**Output Schema:**
```json
{
  "intent": "question|command|other",
  "summary": "One sentence summarizing what user wants",
  "plan": "One sentence describing how to respond",
  "needs_confirmation": true|false,
  "confidence": 0.0-1.0
}
```

#### `claude.py` - Claude Executor
```python
async def execute_task(
    messages: List[ChatMessage],
    intent: str,
    summary: str,
    plan: str,
    job_id: UUID | None = None,
    max_tokens: int = 4000,
) -> ExecutionResult
```

**Responsibilities:**
- Execute task based on classification
- Generate natural language response
- Execute tool calls if needed
- Log token usage to database

**Output:**
```python
ExecutionResult(
    response_text: str,
    tool_calls: list,
    tokens_input: int,
    tokens_output: int,
)
```

#### `context.py` - Context Builder
```python
async def build_conversation_context(
    thread_id: UUID,
    limit: int = 30
) -> List[ChatMessage]
```

**Responsibilities:**
- Fetch recent messages (default: last 30)
- Enrich with artifact summaries (voice, images, OCR)
- Compress to fit token budget
- Return in chronological order

**Artifact Enrichment:**
- Voice transcripts: Preview + duration
- Images: Description + dimensions
- OCR text: Extracted text preview
- Files: Filename + size + mime type

#### `prompts.py` - Prompt Templates
```python
CLASSIFICATION_SYSTEM_PROMPT  # Rules for Haiku
EXECUTION_SYSTEM_PROMPT       # Rules for Claude
PROACTIVE_SYSTEM_PROMPT       # Rules for autonomous operation

build_classification_prompt(messages, trigger_message)
build_execution_prompt(messages, intent, summary, plan)
```

---

### 2. Workers Module (`app/workers/`)

#### `reactive.py` - Reactive Worker Loop
```python
class ReactiveWorker:
    async def start()  # Start background loop
    async def stop()   # Graceful shutdown
```

**Worker Loop (100ms polling):**
1. Poll for pending jobs (`status='queued'`)
2. Pick first job (FIFO order)
3. Mark job as `RUNNING`
4. Route to appropriate handler based on `mode`
5. Update job status to `DONE` or `FAILED`
6. Repeat

**Resilience:**
- Never crashes (catches all exceptions)
- Sleeps 1s on error to avoid tight loop
- Graceful shutdown with 10s timeout

#### `handlers.py` - Job Handlers
```python
async def handle_classify_job(job: ReactiveJob) -> dict
async def handle_execute_job(job: ReactiveJob) -> dict
async def handle_answer_job(job: ReactiveJob) -> dict
```

**Classification Handler:**
1. Fetch thread and trigger message
2. Build conversation context
3. Call Haiku to classify intent
4. Return classification result

**Execution Handler:**
1. Extract classification from job payload
2. Build conversation context
3. If `needs_confirmation=true`:
   - Create approval record
   - Send approval request to user (with OK button)
   - Wait for approval (polls every 2s, timeout 1 hour)
   - If rejected/timeout: abort
4. Call Claude to execute task
5. Send response to user
6. Return execution result

**Answer Handler:**
- Direct answer without AI processing
- Used for simple responses (greetings, acknowledgments)

**Approval Waiting:**
```python
async def wait_for_approval(approval_id: UUID, timeout: int = 3600) -> bool
```
- Polls approval status every 2 seconds
- Returns `True` if approved
- Returns `False` if rejected, superseded, or timeout

---

### 3. Tools Module (`app/tools/`)

#### `executor.py` - Tool Execution
```python
async def execute_bash(command: str, timeout: int = 60) -> dict
async def execute_file_operation(action: str, path: str, content: str) -> dict
async def execute_api_call(url: str, method: str, payload: dict) -> dict
```

**Safety Features:**
- Blocks destructive commands (`rm -rf`, `dd`, `mkfs`, etc.)
- Enforces timeouts on all operations
- Validates file paths (prevents sensitive file access)
- Logs all executions

**Tool Results:**
```python
{
    "status": "success|error",
    "stdout": "...",  # For bash
    "stderr": "...",  # For bash
    "exit_code": 0,   # For bash
    "result": "...",  # For file ops
    "error": "...",   # If failed
}
```

---

## Database Integration

### Token Ledger
All AI calls log tokens to `token_ledger`:
```sql
INSERT INTO token_ledger (scope, provider, tokens_input, tokens_output, tokens_total, meta_json)
VALUES ('reactive', 'haiku', 150, 50, 200, '{"job_id": "...", "model": "..."}')
```

**Scopes:**
- `proactive`: Autonomous agent operations
- `reactive`: User-triggered operations

**Providers:**
- `haiku`: Claude 3.5 Haiku
- `claude`: Claude Sonnet 4

### Job Status Flow
```
QUEUED → RUNNING → DONE
                 ↘ FAILED
```

**Job Modes:**
- `CLASSIFY`: Run Haiku classification
- `EXECUTE`: Run Claude execution
- `ANSWER`: Direct answer (no AI)
- `PLAN`: (Reserved for future use)

---

## Configuration

### Environment Variables

```bash
# Claude Code (Execution)
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...
CLAUDE_MODEL=claude-sonnet-4-20250514

# Haiku (Classification)
HAIKU_API_KEY=  # Optional, falls back to CLAUDE_CODE_OAUTH_TOKEN
HAIKU_MODEL=claude-3-5-haiku-20241022

# Context & Approval
MESSAGE_HISTORY_LIMIT=30
APPROVAL_TIMEOUT_SECONDS=3600
```

### Settings (`app/config.py`)
```python
class Settings(BaseSettings):
    # Claude Code
    CLAUDE_CODE_OAUTH_TOKEN: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Haiku
    HAIKU_API_KEY: str = ""
    HAIKU_MODEL: str = "claude-3-5-haiku-20241022"

    # Context
    MESSAGE_HISTORY_LIMIT: int = 30

    # Approval
    APPROVAL_TIMEOUT_SECONDS: int = 3600
```

---

## Integration with Main App

### `app/main.py` Lifespan
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup
    db = init_db(settings.DATABASE_URL)
    await db.connect()

    await init_bot()

    reactive_worker = ReactiveWorker(poll_interval_ms=100)
    await reactive_worker.start()

    logger.info("Server Agent vNext fully operational")

    yield

    # Shutdown
    await reactive_worker.stop()
    await shutdown_bot()
    await close_db()
```

---

## Complete Flow Example

### User Message: "What's the server uptime?"

**1. Telegram Webhook → Database**
```python
# app/telegram/ingestion.py
thread = await get_or_create_thread("telegram", "123456")
message = await insert_message(thread.id, MessageRole.USER, "What's the server uptime?")
job = await enqueue_job(thread.id, message.id, JobMode.CLASSIFY)
```

**2. Worker → Haiku Classification**
```python
# Worker picks up CLASSIFY job
classification = await classify_intent(messages, trigger_message)
# Result:
# {
#   "intent": "question",
#   "summary": "User asks about server uptime",
#   "plan": "Check server uptime with 'uptime' command",
#   "needs_confirmation": false,
#   "confidence": 0.92
# }
```

**3. Webhook → Enqueue Execution**
```python
# After classification, webhook enqueues EXECUTE job
job = await enqueue_job(
    thread.id,
    message.id,
    JobMode.EXECUTE,
    payload_json={"classification": classification.to_dict()}
)
```

**4. Worker → Claude Execution**
```python
# Worker picks up EXECUTE job
execution = await execute_task(messages, intent, summary, plan)
# Result:
# ExecutionResult(
#   response_text="The server has been up for 5 days, 3 hours, 22 minutes.",
#   tool_calls=[],
#   tokens_input=200,
#   tokens_output=50,
# )
```

**5. Response → User**
```python
# Worker sends response via Telegram
await send_message(
    chat_id=thread.chat_id,
    text=execution.response_text,
    thread_id=thread.id,
)
```

---

## Testing

### Unit Tests
```bash
# Test AI module
pytest tests/test_ai.py -v

# Test reactive worker
pytest tests/test_reactive_worker.py -v
```

### Test Coverage
- **AI Module**: Classification, execution, context building, prompts
- **Workers**: Job handlers, approval flow, worker loop
- **Mocking**: Anthropic API calls, database operations, Telegram responses

### Example Tests
```python
# Test Haiku classification
async def test_classify_intent_question():
    mock_response = {"intent": "question", "summary": "...", ...}
    result = await classify_intent(messages, trigger_message)
    assert result.intent == "question"

# Test approval flow
async def test_wait_for_approval_approved():
    result = await wait_for_approval(approval_id, timeout=10)
    assert result is True
```

---

## Performance Characteristics

### Token Usage
**Haiku Classification:**
- Input: ~150-300 tokens (context + trigger message)
- Output: ~50-100 tokens (JSON response)
- Total: ~200-400 tokens per classification

**Claude Execution:**
- Input: ~500-2000 tokens (full context + prompt)
- Output: ~100-1000 tokens (response)
- Total: ~600-3000 tokens per execution

**Cost Savings:**
- Haiku: $0.25/1M input, $1.25/1M output
- Sonnet: $3/1M input, $15/1M output
- **Savings**: ~90% on classification step

### Latency
**End-to-End Flow:**
1. Telegram → Database: ~50ms
2. Classification (Haiku): ~1-2s
3. Database → Enqueue: ~50ms
4. Execution (Claude): ~2-5s
5. Response → Telegram: ~200ms

**Total**: ~3-8 seconds for complete flow

**With Approval:**
- Add approval wait time (user-dependent)
- Typical: +5-30 seconds

---

## Error Handling

### Resilience Strategy
1. **Worker Loop**: Never crashes (catches all exceptions)
2. **API Timeouts**: 30s for Haiku, 120s for Claude
3. **Job Retries**: Not implemented (jobs marked as FAILED)
4. **Database Errors**: Logged, job marked as FAILED
5. **Telegram Errors**: Logged, continue processing

### Error Recovery
```python
try:
    result = await handle_classify_job(job)
    await update_job_status(job.id, JobStatus.DONE)
except Exception as e:
    logger.error(f"Job failed: {e}")
    await update_job_status(job.id, JobStatus.FAILED)
```

---

## Future Enhancements

### Planned Features
1. **Streaming Responses**: Stream Claude output to user in real-time
2. **Tool Execution**: Actually execute tools returned by Claude
3. **Multi-turn Conversations**: Track conversation state across jobs
4. **Job Retries**: Automatic retry on transient failures
5. **Priority Queues**: Prioritize jobs from master user
6. **Job Cancellation**: Cancel running jobs on user request
7. **Budget Limits**: Enforce daily token limits on reactive operations

### Architecture Improvements
1. **Job Locks**: Use `SELECT FOR UPDATE` to prevent race conditions
2. **Worker Scaling**: Multiple workers for parallel processing
3. **Dead Letter Queue**: Failed jobs moved to DLQ for analysis
4. **Metrics Dashboard**: Real-time job/token metrics

---

## Troubleshooting

### Common Issues

**Worker not processing jobs:**
- Check worker is started in `app/main.py` lifespan
- Check database connection
- Check logs for errors

**Classification fails:**
- Check `HAIKU_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is set
- Check Anthropic API quota
- Check network connectivity

**Execution fails:**
- Check `CLAUDE_CODE_OAUTH_TOKEN` is valid
- Check token budget not exceeded
- Check prompt is well-formed

**Approval timeout:**
- Check `APPROVAL_TIMEOUT_SECONDS` setting
- Check Telegram bot can send messages
- Check user received approval request

### Debug Commands
```bash
# Check worker logs
docker-compose logs -f app | grep "ReactiveWorker"

# Check pending jobs
psql -d server_agent -c "SELECT * FROM reactive_jobs WHERE status='queued';"

# Check token usage
psql -d server_agent -c "SELECT scope, provider, SUM(tokens_total) FROM token_ledger GROUP BY scope, provider;"

# Check failed jobs
psql -d server_agent -c "SELECT * FROM reactive_jobs WHERE status='failed' ORDER BY created_at DESC LIMIT 10;"
```

---

## Summary

The reactive worker implements a **two-phase AI processing architecture** that balances cost, speed, and accuracy:

1. **Haiku Classification**: Fast, cheap intent recognition
2. **Claude Execution**: Powerful, accurate task execution
3. **Approval Flow**: Safe execution of destructive operations
4. **Token Tracking**: Complete visibility into AI costs
5. **Resilience**: Never-crash worker loop with error recovery

This architecture enables the Server Agent to respond intelligently to user requests while maintaining cost efficiency and safety guardrails.
