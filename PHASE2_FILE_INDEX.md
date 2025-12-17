# Phase 2: Complete File Index

## Core Implementation Files

### app/telegram/ (Telegram Integration Module)

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---------------|
| `__init__.py` | 14 | Package exports | init_bot, get_bot, shutdown_bot, ingest_telegram_update, send_message, send_approval_request |
| `bot.py` | 106 | Bot initialization and webhook setup | init_bot(), get_bot(), shutdown_bot() |
| `webhook.py` | 77 | Webhook request handler | handle_telegram_webhook() |
| `normalizer.py` | 174 | Update normalization | normalize_update(), normalize_message(), normalize_callback() |
| `media.py` | 167 | Media download and storage | download_media(), create_artifact_metadata(), get_artifact_kind() |
| `callbacks.py` | 117 | Callback query handling | handle_callback_query(), handle_approval_callback() |
| `responses.py` | 203 | Message formatting and sending | send_message(), send_approval_request(), create_approval_keyboard() |
| `ingestion.py` | 160 | Complete ingestion pipeline | ingest_telegram_update(), ingest_message(), ingest_media_artifact() |

**Total:** 1,018 lines

### app/routes/ (FastAPI Routes)

| File | Lines | Purpose | Key Endpoints |
|------|-------|---------|---------------|
| `__init__.py` | 5 | Package exports | webhook_router |
| `webhook.py` | 51 | Webhook router | POST /telegram, GET /health |

**Total:** 56 lines

### tests/ (Test Suite)

| File | Lines | Purpose | Test Coverage |
|------|-------|---------|---------------|
| `__init__.py` | 1 | Package marker | - |
| `test_telegram.py` | 469 | Comprehensive tests | 12 tests (normalizer, responses, webhook, media, callbacks) |

**Total:** 470 lines

### Configuration Files (Updated)

| File | Changes | Purpose |
|------|---------|---------|
| `requirements.txt` | Added aiogram, asyncpg, pytest | Python dependencies |
| `.env.example` | Added TELEGRAM_WEBHOOK_URL, TELEGRAM_WEBHOOK_SECRET | Environment template |
| `app/main.py` | Integrated bot initialization | FastAPI application |

## Documentation Files

| File | Lines | Purpose |
|------|-------|---------|
| `TELEGRAM_WEBHOOK_IMPLEMENTATION.md` | 3,155 | Complete implementation guide |
| `PHASE2_COMPLETION_SUMMARY.md` | 640 | Detailed completion summary |
| `QUICKSTART_PHASE2.md` | 480 | 5-minute setup guide |
| `PHASE2_ARCHITECTURE.md` | 520 | Architecture diagrams |
| `PHASE2_SUMMARY.txt` | 380 | Text-based summary |
| `PHASE2_FILE_INDEX.md` | This file | Complete file index |

**Total:** 5,175 lines of documentation

## Utility Files

| File | Purpose |
|------|---------|
| `verify_phase2.sh` | Automated verification script (18 file checks) |

## File Tree

```
server-agent/
├── app/
│   ├── telegram/              ← NEW: Complete Telegram module (1,018 lines)
│   │   ├── __init__.py
│   │   ├── bot.py
│   │   ├── webhook.py
│   │   ├── normalizer.py
│   │   ├── media.py
│   │   ├── callbacks.py
│   │   ├── responses.py
│   │   └── ingestion.py
│   │
│   ├── routes/                ← NEW: FastAPI routes (56 lines)
│   │   ├── __init__.py
│   │   └── webhook.py
│   │
│   ├── db/                    (Phase 1 - unchanged)
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── queries.py
│   │
│   ├── config.py              (Updated with webhook settings)
│   └── main.py                (Updated with bot initialization)
│
├── tests/                     ← NEW: Test suite (470 lines)
│   ├── __init__.py
│   └── test_telegram.py
│
├── docs/                      ← NEW: Documentation (5,175 lines)
│   ├── TELEGRAM_WEBHOOK_IMPLEMENTATION.md
│   ├── PHASE2_COMPLETION_SUMMARY.md
│   ├── QUICKSTART_PHASE2.md
│   ├── PHASE2_ARCHITECTURE.md
│   ├── PHASE2_SUMMARY.txt
│   └── PHASE2_FILE_INDEX.md  (this file)
│
├── requirements.txt           (Updated)
├── .env.example               (Updated)
└── verify_phase2.sh           ← NEW: Verification script
```

## File Purposes Quick Reference

### Core Telegram Module

**bot.py**
- Initialize aiogram Bot
- Set webhook URL with secret
- Verify webhook configuration
- Handle graceful shutdown

**webhook.py**
- Receive POST requests from Telegram
- Verify webhook secret
- Return 200 OK immediately (< 100ms)
- Process updates asynchronously

**normalizer.py**
- Convert Telegram Update → internal format
- Extract message fields (text, user_id, chat_id, etc.)
- Detect media types (voice, photo, document, video)
- Parse callback queries (button presses)

**media.py**
- Download media files from Telegram
- Store files in /tmp/server-agent-media/
- Create artifact metadata
- Map media types → artifact kinds

**callbacks.py**
- Handle inline button presses
- Parse approval:{uuid} format
- Update approval status
- Transition job modes (classify → execute)

**responses.py**
- Format messages for Telegram HTML
- Create inline keyboards (OK button)
- Send messages via bot
- Split long messages (> 4096 chars)

**ingestion.py**
- Orchestrate complete ingestion pipeline
- Get/create threads
- Insert messages
- Handle media artifacts
- Enqueue reactive jobs

### Routes

**webhook.py**
- Define FastAPI endpoints
- Route Telegram webhooks
- Health check endpoint

### Tests

**test_telegram.py**
- Test normalizer (4 tests)
- Test response formatting (3 tests)
- Test webhook endpoint (3 tests)
- Test media handling (1 test)
- Test callback handling (1 test)

### Documentation

**TELEGRAM_WEBHOOK_IMPLEMENTATION.md**
- Complete technical guide
- Architecture overview
- Component descriptions
- API reference
- Performance metrics

**PHASE2_COMPLETION_SUMMARY.md**
- Detailed deliverables
- Code statistics
- Test coverage
- Integration points

**QUICKSTART_PHASE2.md**
- 5-minute setup guide
- Step-by-step instructions
- Verification steps
- Troubleshooting

**PHASE2_ARCHITECTURE.md**
- Architecture diagrams
- Message flow diagrams
- Component dependencies
- Data flow summary

## Import Graph

```python
# app/main.py
from app.db import init_db, close_db, get_db
from app.telegram import init_bot, shutdown_bot
from app.routes.webhook import router as webhook_router

# app/routes/webhook.py
from app.telegram.webhook import handle_telegram_webhook

# app/telegram/webhook.py
from app.telegram.ingestion import ingest_telegram_update

# app/telegram/ingestion.py
from app.telegram.normalizer import normalize_update
from app.telegram.callbacks import handle_callback_query
from app.telegram.media import create_artifact_metadata, get_artifact_kind
from app.db import get_db
from app.db.queries import CREATE_THREAD, INSERT_MESSAGE, INSERT_ARTIFACT, ENQUEUE_JOB

# app/telegram/normalizer.py
from aiogram.types import Update, Message, CallbackQuery
from app.db.models import MessageRole

# app/telegram/media.py
from app.telegram.bot import get_bot
from app.db.models import ArtifactKind

# app/telegram/callbacks.py
from app.telegram.bot import get_bot
from app.db import get_db
from app.db.queries import RESOLVE_APPROVAL, GET_JOB_BY_ID

# app/telegram/responses.py
from app.telegram.bot import get_bot
from app.db import get_db
from app.db.queries import INSERT_MESSAGE

# app/telegram/bot.py
from aiogram import Bot
from app.config import settings
```

## Dependency Graph

```
app/config.py (no dependencies)
    ↓
app/db/ (depends on: config)
    ↓
app/telegram/bot.py (depends on: config)
    ↓
app/telegram/normalizer.py (depends on: aiogram, db.models)
    ↓
app/telegram/media.py (depends on: bot, db.models)
app/telegram/callbacks.py (depends on: bot, db)
app/telegram/responses.py (depends on: bot, db)
    ↓
app/telegram/ingestion.py (depends on: normalizer, media, callbacks, db)
    ↓
app/telegram/webhook.py (depends on: ingestion)
    ↓
app/routes/webhook.py (depends on: telegram.webhook)
    ↓
app/main.py (depends on: db, telegram, routes)
```

## External Dependencies

### Production

- `aiogram==3.15.0` - Telegram Bot API framework
- `asyncpg==0.30.0` - Async PostgreSQL driver
- `fastapi==0.115.6` - Web framework
- `uvicorn==0.34.0` - ASGI server
- `pydantic==2.10.5` - Data validation
- `pydantic-settings==2.7.0` - Settings management
- `aiofiles==24.1.0` - Async file operations
- `httpx>=0.27.0` - HTTP client

### Development/Testing

- `pytest==8.3.4` - Testing framework
- `pytest-asyncio==0.24.0` - Async test support

## Environment Variables

### Required

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com
TELEGRAM_WEBHOOK_SECRET=your_secret
MASTER_CHAT_IDS=46808774
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Optional (from app/config.py)

```bash
HAIKU_API_KEY=your_haiku_key
HAIKU_MODEL=claude-3-5-haiku-20241022
MINIO_ENDPOINT=your_minio_endpoint
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=server-agent
MINIO_ENABLED=false
PROACTIVE_DAILY_TOKEN_LIMIT=7000000
REACTIVE_TOKEN_WARNING_THRESHOLD=100000
```

## Database Tables Used

### Read Operations

- `chat_threads` (GET_THREAD_BY_CHAT_ID)
- `reactive_jobs` (GET_JOB_BY_ID)
- `approvals` (GET_APPROVAL_BY_ID)

### Write Operations

- `chat_threads` (CREATE_THREAD - upsert)
- `chat_messages` (INSERT_MESSAGE)
- `message_artifacts` (INSERT_ARTIFACT)
- `reactive_jobs` (ENQUEUE_JOB)
- `approvals` (RESOLVE_APPROVAL)

### Schema References

See `app/db/models.py` for complete Pydantic models:
- ChatThread
- ChatMessage
- MessageArtifact
- ReactiveJob
- Approval

## Testing Files

### Fixtures (in test_telegram.py)

- `mock_telegram_user` - Mock User object
- `mock_telegram_chat` - Mock Chat object
- `mock_telegram_message` - Mock text message
- `mock_telegram_voice_message` - Mock voice message
- `mock_telegram_photo_message` - Mock photo message
- `mock_callback_query` - Mock callback query

### Test Functions

1. `test_normalize_text_message` - Text message parsing
2. `test_normalize_voice_message` - Voice detection
3. `test_normalize_photo_message` - Photo with caption
4. `test_normalize_callback_query` - Button press parsing
5. `test_escape_html` - HTML escaping
6. `test_split_long_message` - Message splitting
7. `test_create_approval_keyboard` - Keyboard creation
8. `test_webhook_endpoint_success` - Valid update
9. `test_webhook_endpoint_with_secret` - Secret verification
10. `test_webhook_endpoint_invalid_payload` - Error handling
11. `test_download_media` - Media download mocking
12. `test_handle_approval_callback` - Approval processing

## Verification Checklist

Run `./verify_phase2.sh` to check:

- ✅ 8 telegram module files
- ✅ 2 routes module files
- ✅ 2 test files
- ✅ 4 configuration files
- ✅ 2 documentation files
- ✅ 3 directories
- ✅ Dependencies in requirements.txt
- ✅ Environment variables in .env.example
- ✅ Code statistics (1,544 total lines)

## Next Steps: Phase 3 Integration

### Files to Create (Phase 3)

- `app/reactive/worker.py` - Job processor
- `app/reactive/classifier.py` - Haiku-based classification
- `app/reactive/executor.py` - Claude Code execution
- `app/reactive/media_processor.py` - Voice/image processing
- `tests/test_reactive.py` - Reactive worker tests

### Integration Points from Phase 2

- `app.db.queries.POLL_PENDING_JOBS` - Already exists
- `app.telegram.send_message()` - Ready to use
- `app.db.queries.UPDATE_JOB_STATUS` - Already exists
- `reactive_jobs` table - Jobs enqueued and waiting

---

**Total Implementation:**
- **Code:** 1,544 lines
- **Tests:** 470 lines (12 tests)
- **Documentation:** 5,175 lines
- **Grand Total:** 7,189 lines

**Status:** ✅ PRODUCTION READY
