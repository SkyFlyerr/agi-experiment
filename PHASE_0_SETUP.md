# Phase 0: Foundation & Dependencies - Setup Guide

## Overview

Phase 0 establishes the complete infrastructure foundation for Server Agent vNext. This includes all necessary dependencies, configuration templates, and containerized deployment configuration.

**Deliverables Status:** ✅ COMPLETE

## Files Created

### 1. `requirements-vnext.txt` (1.9 KB)
Complete Python dependency specification for Server Agent vNext.

**Key Dependencies:**
- **Database**: `asyncpg` (async PostgreSQL), `psycopg2-binary` (sync fallback)
- **Telegram**: `aiogram==3.4.0` (modern async bot framework)
- **Web**: `fastapi`, `uvicorn`, `pydantic-settings`
- **HTTP**: `aiohttp`, `httpx` (async client libraries)
- **AI**: `anthropic` (Claude API integration)
- **Testing**: `pytest`, `pytest-asyncio`, `pytest-cov`
- **Optional**: `minio` (object storage), `openai` (media processing)

**Total Dependencies:** 18 core + optional packages
**Python Version:** 3.11+ recommended

### 2. `.env.vnext.example` (5.6 KB)
Comprehensive environment configuration template with 50+ configuration variables.

**Sections:**
```
DATABASE CONFIGURATION
  - DATABASE_URL, DATABASE_URL_SYNC
  - Connection pool settings
  - Pool overflow configuration

TELEGRAM BOT
  - Bot token, webhook configuration
  - Master chat IDs
  - Rate limiting
  - Optional user account credentials

CLAUDE API
  - OAuth token for Claude Code
  - API endpoint configuration
  - Token limits

HAIKU/SMALL MODEL
  - API key for fallback model
  - Model identifier
  - Token budget

TOKEN BUDGET & RATE LIMITING
  - Daily token limit
  - Warning thresholds
  - Safety buffers

PROACTIVE SCHEDULING
  - Cycle intervals (min/max)
  - Thinking cooldown
  - Response timeouts

APPROVAL & INTERACTION
  - Approval timeouts
  - Certainty/significance thresholds

MESSAGE HISTORY
  - Context window size
  - Summary thresholds

MINIO STORAGE (Optional)
  - Object storage configuration
  - S3-compatible settings

LOGGING & DEBUGGING
  - Log levels and directories
  - Request/query logging
  - Log rotation

APPLICATION SETTINGS
  - Environment (dev/staging/prod)
  - Port/host configuration
  - CORS settings
  - Request size limits

SELF-SUFFICIENCY & REVENUE
  - Revenue generation features
  - Charity donation settings

RESOURCE MANAGEMENT
  - CPU/memory/disk alert thresholds
  - Monitoring intervals

SECURITY
  - HTTPS requirements
  - IP whitelisting
  - Rate limiting
```

### 3. `.env.postgres.vnext.example` (645 B)
PostgreSQL-specific configuration for Docker Compose.

**Configuration:**
```
POSTGRES_USER=server_agent
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=server_agent_vnext
POSTGRES_PORT=5432
```

### 4. `docker-compose-vnext.yml` (4.4 KB)
Complete Docker Compose configuration with three services.

**Services:**

#### PostgreSQL (Primary)
- Image: `postgres:16-alpine` (lightweight)
- Container: `server_agent_vnext_postgres`
- Port: `127.0.0.1:5432` (localhost only)
- Health Check: `pg_isready` verification
- Volume: `server_agent_vnext_pgdata` (persistent)
- Resource Limits: 1 CPU, 1GB RAM
- Logging: JSON driver with rotation

#### FastAPI Application
- Build: Multi-stage Docker build from `Dockerfile`
- Container: `server_agent_vnext_app`
- Port: `127.0.0.1:8000` (localhost only)
- Dependencies: Waits for postgres health check
- Environment: From `.env.vnext`
- Volumes:
  - Read-only app code mount
  - Persistent logs directory
  - Persistent data directory
- Health Check: HTTP `/health` endpoint
- Resource Limits: 2 CPU, 2GB RAM
- Logging: JSON driver with 100MB max per file, 5 files retained

#### MinIO Object Storage (Optional)
- Commented out by default
- Image: `minio/latest`
- Ports: 9000 (API), 9001 (Web UI)
- For: S3-compatible media/data storage
- Uncomment to enable

**Network:** Custom bridge network `server_agent_vnext_network`

### 5. `Dockerfile` (2.3 KB)
Multi-stage production-ready Dockerfile for the FastAPI application.

**Build Strategy:**
```
Stage 1: Builder
  - Python 3.11-slim base
  - Install build dependencies (gcc, postgresql-client)
  - Generate wheel files for faster installation

Stage 2: Runtime
  - Python 3.11-slim base
  - Copy pre-built wheels from builder
  - Install only runtime dependencies
  - Create non-root user (agent:1000)
  - Copy application code
  - Expose port 8000
  - Set health check
```

**Features:**
- Non-root user execution for security
- Health check endpoint verification
- Volume mounts for logs and data
- Development mode: auto-reload enabled
- Production mode: configurable with uvloop and worker processes
- Resource constraints specified in docker-compose

## Setup Instructions

### Step 1: Copy Configuration Files

```bash
cd /Users/maksimbozhko/Development/server-agent

# Copy environment templates
cp .env.vnext.example .env.vnext
cp .env.postgres.vnext.example .env.postgres.vnext
```

### Step 2: Configure Environment Variables

Edit `.env.vnext` with your actual values:

```bash
# Required: Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_NAME=agi_superbot
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
MASTER_CHAT_IDS=46808774

# Required: Claude API
CLAUDE_CODE_OAUTH_TOKEN=your_oauth_token

# Required: Database (keep default for local development)
DATABASE_URL=postgresql+asyncpg://server_agent:your_secure_password_here@postgres:5432/server_agent_vnext
```

Edit `.env.postgres.vnext`:

```bash
POSTGRES_PASSWORD=your_secure_password_here  # Must match DATABASE_URL
```

### Step 3: Build Docker Images

```bash
docker compose -f docker-compose-vnext.yml build
```

### Step 4: Start Services

```bash
docker compose -f docker-compose-vnext.yml up -d
```

### Step 5: Verify Services

```bash
# Check all services running
docker compose -f docker-compose-vnext.yml ps

# Check app health
curl http://localhost:8000/health

# Check database connection
docker compose -f docker-compose-vnext.yml exec app pg_isready -h postgres
```

## Dependency Details

### Core Dependencies

| Package | Version | Purpose | Type |
|---------|---------|---------|------|
| asyncpg | 0.29.0 | PostgreSQL async driver | Database |
| aiogram | 3.4.0 | Telegram bot framework | Telegram |
| fastapi | 0.115.6 | Web framework | Web |
| uvicorn | 0.34.0 | ASGI server | Web |
| aiohttp | 3.9.1 | Async HTTP client | HTTP |
| anthropic | 0.42.0 | Claude API | AI |
| pydantic | 2.10.5 | Data validation | Config |
| pytest | 7.4.3 | Testing framework | Testing |

### Optional Dependencies

| Package | Purpose | Enable By |
|---------|---------|-----------|
| minio | Object storage | Uncomment in docker-compose + MINIO_ENABLED=true |
| openai | Media processing | Uncomment + add to .env |

## Architecture Flow

```
User/Master (Telegram)
    ↓
Telegram Webhook (FastAPI)
    ↓
Telegram Handler (aiogram)
    ↓
Agent Logic / Decision Making
    ↓
Claude API (Anthropic)
    ↓
Database (PostgreSQL)
    ↓
Background Tasks (asyncpg)
    ↓
Telegram Messages (aiogram)
    ↓
Response to Master
```

## Security Considerations

### ✅ Implemented

- **Non-root user**: Application runs as `agent:1000` user, not root
- **Secrets management**: All secrets in `.env` files (not committed)
- **Health checks**: Automatic container health verification
- **Resource limits**: CPU and memory constraints prevent resource exhaustion
- **Localhost binding**: Database and app ports only accessible locally (127.0.0.1)
- **Logging**: Structured JSON logging with rotation

### ⚠️ Before Production Deployment

1. **Change PostgreSQL password** in `.env.postgres.vnext`
2. **Configure HTTPS** for Telegram webhook (required by Telegram API)
3. **Set unique webhook secret** (use secure random generation)
4. **Configure IP allowlist** in `TRUSTED_IPS` if needed
5. **Enable rate limiting** with `RATE_LIMIT_ENABLED=true`
6. **Use environment**: Set `ENV=production`
7. **Configure log rotation** and remote log forwarding
8. **Set up monitoring** for resource usage
9. **Configure backup strategy** for PostgreSQL volumes

## Testing the Setup

### Test 1: Database Connection

```bash
docker compose -f docker-compose-vnext.yml exec app \
  python -c "import asyncpg; print('asyncpg imported successfully')"
```

### Test 2: FastAPI Server

```bash
curl http://localhost:8000/health
# Expected response: {"status": "healthy"} or similar
```

### Test 3: Telegram Bot Integration

```bash
# This will be tested once app/main.py is implemented
# Send test message to bot via Telegram
```

### Test 4: PostgreSQL Persistence

```bash
# Check database exists
docker compose -f docker-compose-vnext.yml exec app \
  psql -h postgres -U server_agent -d server_agent_vnext -c "\l"
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose-vnext.yml logs app

# Check health status
docker compose -f docker-compose-vnext.yml ps
```

### Database connection failed

```bash
# Verify database is ready
docker compose -f docker-compose-vnext.yml logs postgres

# Test connection manually
docker compose -f docker-compose-vnext.yml exec postgres \
  pg_isready -U server_agent -d server_agent_vnext
```

### Port already in use

```bash
# Find process using port 8000
lsof -i :8000

# Or use different port in .env.vnext
APP_PORT=8001
```

## Next Steps (Phase 1)

Phase 1 will implement:

1. **FastAPI Application Structure**
   - Main application entry point (`app/main.py`)
   - Request/response models
   - Error handling middleware

2. **Database Models & Migrations**
   - SQLAlchemy models
   - Alembic migrations
   - Schema initialization

3. **Telegram Bot Integration**
   - Webhook handler
   - Message routing
   - Command processing

4. **Claude Integration**
   - API client wrapper
   - Token tracking
   - Error handling

5. **Proactive Loop System**
   - Background task scheduling
   - Decision-making framework
   - State management

## Health Check Endpoints

After Phase 1 implementation, these endpoints will be available:

```
GET  /health              - Application health status
GET  /health/postgres     - Database connectivity
GET  /metrics             - Prometheus metrics (optional)
POST /telegram/webhook    - Telegram update handler
GET  /api/status          - Agent status and stats
GET  /api/token-budget    - Token usage and budget
```

## Documentation Files

- **CLAUDE.md** - Project-level guidelines and principles
- **PHASE_0_SETUP.md** - This file (setup and configuration)
- **PHASE_1_IMPLEMENTATION.md** - Next phase tasks (to be created)
- **ARCHITECTURE.md** - System design and patterns (to be created)
- **OPERATIONS.md** - Deployment and maintenance (to be created)

## Support

For issues or questions:
1. Check this document's Troubleshooting section
2. Review Docker Compose logs
3. Verify environment variables match template
4. Consult project CLAUDE.md for principles
