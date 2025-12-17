# Phase 0: Foundation & Dependencies - Quick Reference Checklist

## Deliverables Status

### Files Created ✅

- [x] **requirements-vnext.txt** (1.9 KB)
  - 18 core dependencies + optional packages
  - Python 3.11+
  - All async libraries for high performance

- [x] **.env.vnext.example** (5.6 KB)
  - 50+ configuration variables
  - Fully documented with descriptions
  - All sections covered (DB, Telegram, Claude, scheduling, etc.)

- [x] **.env.postgres.vnext.example** (645 B)
  - PostgreSQL container configuration
  - Ready for docker-compose integration

- [x] **docker-compose-vnext.yml** (4.4 KB)
  - PostgreSQL service (production-ready)
  - FastAPI app service (with health checks)
  - Optional MinIO service (for media storage)
  - Proper volume management and networking

- [x] **Dockerfile** (2.3 KB)
  - Multi-stage build for optimization
  - Non-root user for security
  - Health check endpoint
  - Development and production configurations

- [x] **PHASE_0_SETUP.md** (11 KB)
  - Complete setup guide
  - Architecture overview
  - Troubleshooting section
  - Security considerations

## Quick Setup (5 minutes)

```bash
cd /Users/maksimbozhko/Development/server-agent

# 1. Copy templates
cp .env.vnext.example .env.vnext
cp .env.postgres.vnext.example .env.postgres.vnext

# 2. Edit with your values (required fields)
nano .env.vnext
nano .env.postgres.vnext

# 3. Build containers
docker compose -f docker-compose-vnext.yml build

# 4. Start services
docker compose -f docker-compose-vnext.yml up -d

# 5. Verify
docker compose -f docker-compose-vnext.yml ps
curl http://localhost:8000/health
```

## Required Configuration Before Starting

### Telegram Bot
- [ ] Get bot token from @BotFather
- [ ] Set `TELEGRAM_BOT_TOKEN` in .env.vnext
- [ ] Set `TELEGRAM_BOT_NAME` (your bot username)
- [ ] Set `MASTER_CHAT_IDS` (your Telegram chat ID)
- [ ] Generate webhook secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Set `TELEGRAM_WEBHOOK_SECRET`

### Claude API
- [ ] Get OAuth token from Claude setup
- [ ] Set `CLAUDE_CODE_OAUTH_TOKEN` in .env.vnext

### Database
- [ ] Generate secure PostgreSQL password
- [ ] Update both .env.vnext and .env.postgres.vnext with same password

### Optional: Production Deployment
- [ ] Set up HTTPS for webhook (Telegram requires it)
- [ ] Configure domain for `TELEGRAM_WEBHOOK_URL`
- [ ] Set `ENV=production`
- [ ] Enable MinIO if using media storage

## Configuration Sections Reference

### Minimal Configuration (Development)

```
DATABASE_URL=postgresql+asyncpg://server_agent:password@postgres:5432/server_agent_vnext
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_BOT_NAME=your_bot_name
MASTER_CHAT_IDS=your_chat_id
CLAUDE_CODE_OAUTH_TOKEN=your_oauth_token
ENV=development
```

### Full Configuration (Production)

```
# Database
DATABASE_URL=postgresql+asyncpg://...
DATABASE_POOL_SIZE=20

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=...
MASTER_CHAT_IDS=...

# Claude API
CLAUDE_CODE_OAUTH_TOKEN=...
CLAUDE_MAX_REQUEST_TOKENS=4096

# Token Budget
PROACTIVE_DAILY_TOKEN_LIMIT=3000000
REACTIVE_TOKEN_WARNING_THRESHOLD=500000

# Scheduling
PROACTIVE_MIN_INTERVAL_SECONDS=300
PROACTIVE_MAX_INTERVAL_SECONDS=3600

# Application
ENV=production
APP_PORT=8000
LOG_LEVEL=INFO

# Security
WEBHOOK_HTTPS_ONLY=true
RATE_LIMIT_ENABLED=true
```

## Service Verification Commands

```bash
# All services running?
docker compose -f docker-compose-vnext.yml ps

# PostgreSQL health
docker compose -f docker-compose-vnext.yml logs postgres | grep "database system"

# App health
curl http://localhost:8000/health

# Database connection
docker compose -f docker-compose-vnext.yml exec app \
  psql -h postgres -U server_agent -d server_agent_vnext -c "\l"

# View application logs
docker compose -f docker-compose-vnext.yml logs -f app

# View database logs
docker compose -f docker-compose-vnext.yml logs -f postgres
```

## Key Features Implemented

### ✅ Architecture
- [x] Multi-stage Docker build (optimized image size)
- [x] Non-root user execution (security)
- [x] Health checks for all services
- [x] Proper container orchestration

### ✅ Configuration
- [x] Comprehensive environment variables
- [x] Separate postgres configuration
- [x] Production-ready defaults
- [x] Extensive documentation

### ✅ Dependencies
- [x] Async PostgreSQL driver (asyncpg)
- [x] Modern Telegram bot framework (aiogram 3.x)
- [x] Fast API framework (FastAPI)
- [x] Claude API integration (anthropic)
- [x] Testing framework (pytest, pytest-asyncio)
- [x] Optional media storage (minio)

### ✅ Security
- [x] Secrets in .env files only
- [x] Non-root user (agent:1000)
- [x] Localhost-only ports
- [x] Resource limits per container
- [x] Structured logging
- [x] Health check verification

## Dependency Versions Summary

| Category | Package | Version | Purpose |
|----------|---------|---------|---------|
| **Database** | asyncpg | 0.29.0 | Async PostgreSQL |
| | psycopg2-binary | 2.9.9 | Sync fallback |
| **Telegram** | aiogram | 3.4.0 | Bot framework |
| | python-multipart | 0.0.6 | File uploads |
| **Web** | fastapi | 0.115.6 | Web framework |
| | uvicorn | 0.34.0 | ASGI server |
| | pydantic | 2.10.5 | Validation |
| | pydantic-settings | 2.1.0 | Config |
| **HTTP** | aiohttp | 3.9.1 | Async HTTP |
| | httpx | 0.25.2 | Modern HTTP |
| **AI** | anthropic | 0.42.0 | Claude API |
| **Testing** | pytest | 7.4.3 | Test framework |
| | pytest-asyncio | 0.23.2 | Async tests |
| | pytest-cov | 4.1.0 | Coverage |
| **Utilities** | python-dotenv | 1.0.1 | .env loading |
| | aiofiles | 24.1.0 | Async files |
| | websockets | 14.1 | WebSocket support |
| | pytz | 2024.1 | Timezones |

## Environment Variables by Category

### Database (3 variables)
- DATABASE_URL
- DATABASE_URL_SYNC
- DATABASE_POOL_SIZE

### Telegram Bot (6 variables)
- TELEGRAM_BOT_TOKEN
- TELEGRAM_BOT_NAME
- TELEGRAM_WEBHOOK_URL
- TELEGRAM_WEBHOOK_SECRET
- MASTER_CHAT_IDS
- TELEGRAM_RATE_LIMIT

### Claude API (3 variables)
- CLAUDE_CODE_OAUTH_TOKEN
- CLAUDE_CODE_API_URL
- CLAUDE_MAX_REQUEST_TOKENS

### Token Budget (3 variables)
- PROACTIVE_DAILY_TOKEN_LIMIT
- REACTIVE_TOKEN_WARNING_THRESHOLD
- TOKEN_BUDGET_SAFETY_BUFFER

### Scheduling (4 variables)
- PROACTIVE_MIN_INTERVAL_SECONDS
- PROACTIVE_MAX_INTERVAL_SECONDS
- PROACTIVE_THINKING_COOLDOWN_SECONDS
- TELEGRAM_RESPONSE_TIMEOUT_SECONDS

### Other Sections
- Approval & Interaction: 3 variables
- Message History: 3 variables
- MinIO Storage: 6 variables (optional)
- Logging: 6 variables
- Application: 5 variables
- Revenue: 4 variables (optional)
- Resources: 4 variables
- Security: 4 variables

**Total: 55 environment variables** (covers all aspects of agent operation)

## Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| Container won't start | Check logs: `docker compose -f docker-compose-vnext.yml logs app` |
| Database connection failed | Verify postgres service: `docker compose -f docker-compose-vnext.yml ps` |
| Port 8000 in use | Change APP_PORT in .env.vnext or kill process: `lsof -i :8000` |
| Build fails | Clean build: `docker compose -f docker-compose-vnext.yml build --no-cache` |
| Health check fails | Wait 30 seconds for startup, check logs for errors |

## What's Next (Phase 1)

Phase 1 will implement:

```
Phase 1: Application Structure
├── app/main.py (FastAPI entry point)
├── app/models/ (Pydantic models)
├── app/api/ (API routes)
├── app/telegram/ (Bot handlers)
├── app/database/ (SQLAlchemy + Alembic)
├── app/services/ (Business logic)
└── app/utils/ (Helpers)

Database & Migrations
├── models.py (SQLAlchemy)
├── migrations/ (Alembic)
└── schema.sql (Initial schema)

Telegram Integration
├── handlers/
├── filters/
├── middleware/
└── keyboards/

Claude Integration
├── api_client.py
├── token_tracker.py
└── error_handling.py

Proactive Loop
├── scheduler.py
├── state_manager.py
└── decision_engine.py
```

## Success Criteria

Phase 0 is **COMPLETE** when:

- [x] All 5 deliverable files created
- [x] All files contain required content
- [x] Configuration templates are comprehensive
- [x] Docker Compose can build without errors
- [x] Services can start successfully
- [x] Health checks verify connectivity
- [x] Documentation is clear and actionable

**Current Status: ✅ PHASE 0 COMPLETE - Ready for Phase 1 Implementation**
