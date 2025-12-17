================================================================================
                    PHASE 0: FOUNDATION & DEPENDENCIES
                            Quick Start Guide
================================================================================

Welcome to Phase 0 of Server Agent vNext!

This phase establishes the complete foundation with dependencies, configuration,
and Docker infrastructure for an autonomous AGI agent.

================================================================================
WHAT YOU GOT (9 Files)
================================================================================

CONFIGURATION & DEPLOYMENT:
  1. requirements-vnext.txt          → Python dependencies (18 core packages)
  2. .env.vnext.example              → App configuration template (55 variables)
  3. .env.postgres.vnext.example     → Database configuration
  4. docker-compose-vnext.yml        → Docker service orchestration
  5. Dockerfile                      → Multi-stage production build

DOCUMENTATION:
  6. PHASE_0_SETUP.md                → Complete setup guide (START HERE)
  7. PHASE_0_CHECKLIST.md            → Quick reference
  8. PHASE_0_SUMMARY.txt             → Executive overview
  9. PHASE_0_INDEX.md                → Navigation guide

================================================================================
START HERE (5 MINUTES)
================================================================================

Step 1: Read the Setup Guide
  → Open: PHASE_0_SETUP.md
  → Time: 10 minutes
  → Covers: Architecture, dependencies, configuration

Step 2: Copy Configuration Templates
  $ cp .env.vnext.example .env.vnext
  $ cp .env.postgres.vnext.example .env.postgres.vnext

Step 3: Edit Configuration Files
  $ nano .env.vnext
  $ nano .env.postgres.vnext

  Required Values to Configure:
    - TELEGRAM_BOT_TOKEN (from @BotFather)
    - MASTER_CHAT_IDS (your Telegram ID)
    - CLAUDE_CODE_OAUTH_TOKEN (from Claude setup)
    - Database password (same in both files)

Step 4: Build & Start Services
  $ docker compose -f docker-compose-vnext.yml build
  $ docker compose -f docker-compose-vnext.yml up -d

Step 5: Verify Everything Works
  $ curl http://localhost:8000/health
  $ docker compose -f docker-compose-vnext.yml ps

Expected Output:
  - PostgreSQL running on localhost:5432
  - FastAPI running on localhost:8000
  - Both services marked as "Up"

================================================================================
FILE GUIDE
================================================================================

MUST READ FIRST:
  → PHASE_0_SETUP.md
    Complete guide with troubleshooting

FOR QUICK REFERENCE:
  → PHASE_0_CHECKLIST.md
    Checklist and quick commands

FOR OVERVIEW:
  → PHASE_0_SUMMARY.txt
    Executive summary of all features

FOR NAVIGATION:
  → PHASE_0_INDEX.md
    Index and file organization

FOR CONFIGURATION:
  → .env.vnext.example
    App settings (55 variables documented)

  → .env.postgres.vnext.example
    Database settings (4 variables)

  → requirements-vnext.txt
    Python packages to install

FOR DEPLOYMENT:
  → docker-compose-vnext.yml
    Service orchestration

  → Dockerfile
    Container build definition

================================================================================
KEY FEATURES
================================================================================

Database:
  ✓ PostgreSQL 16 (Alpine - lightweight)
  ✓ asyncpg for high-performance async access
  ✓ Connection pooling configured
  ✓ Persistent data volumes

Application:
  ✓ FastAPI for modern web framework
  ✓ uvicorn ASGI server
  ✓ Non-root user execution
  ✓ Health check endpoint

Telegram:
  ✓ aiogram 3.x (async bot framework)
  ✓ Webhook support for production
  ✓ Multi-master support
  ✓ Rate limiting configured

Claude API:
  ✓ Anthropic SDK integrated
  ✓ Token budget tracking
  ✓ OAuth token support
  ✓ Haiku fallback model

Testing:
  ✓ pytest + pytest-asyncio
  ✓ Code coverage (pytest-cov)
  ✓ All async operations testable

Security:
  ✓ Non-root container user (agent:1000)
  ✓ Localhost-only ports (127.0.0.1)
  ✓ Secrets in .env files
  ✓ Health checks for availability
  ✓ Resource limits per container

================================================================================
ENVIRONMENT VARIABLES (55 TOTAL)
================================================================================

MUST CONFIGURE (4 required):
  TELEGRAM_BOT_TOKEN           → Bot token from @BotFather
  MASTER_CHAT_IDS              → Your Telegram chat ID
  CLAUDE_CODE_OAUTH_TOKEN      → Claude OAuth token
  POSTGRES_PASSWORD            → Database password

SHOULD CONFIGURE (4 recommended):
  TELEGRAM_WEBHOOK_URL         → Your domain URL (production)
  TELEGRAM_WEBHOOK_SECRET      → Unique webhook secret
  PROACTIVE_DAILY_TOKEN_LIMIT  → Token budget (3M default)
  ENV                          → development or production

OPTIONAL (47 others):
  - Database pool settings
  - Logging configuration
  - MinIO object storage
  - Revenue features
  - Resource monitoring
  - Security settings
  See .env.vnext.example for complete list with descriptions

================================================================================
DOCKER SERVICES
================================================================================

SERVICE 1: PostgreSQL Database
  Container:    server_agent_vnext_postgres
  Image:        postgres:16-alpine
  Port:         127.0.0.1:5432 (localhost only)
  Health Check: pg_isready -U $user -d $db
  Data Volume:  server_agent_vnext_pgdata
  Status:       Primary database (required)

SERVICE 2: FastAPI Application
  Container:    server_agent_vnext_app
  Build:        Multi-stage Dockerfile
  Port:         127.0.0.1:8000 (localhost only)
  Health Check: HTTP GET /health
  Depends On:   PostgreSQL (waits for health check)
  Status:       Main application (required)

SERVICE 3: MinIO (Optional)
  Container:    server_agent_vnext_minio
  Image:        minio/latest
  Ports:        9000 (API), 9001 (Web UI)
  Status:       Commented out by default
  Enable:       Uncomment docker-compose-vnext.yml + set MINIO_ENABLED=true

================================================================================
SECURITY CHECKLIST
================================================================================

Development (Local):
  ✓ Non-root user in container
  ✓ Localhost-only port binding
  ✓ Health checks enabled
  ✓ Secrets in .env files

Production (Before Deploying):
  ⚠️  Set ENV=production
  ⚠️  Configure HTTPS for Telegram webhook
  ⚠️  Set TELEGRAM_WEBHOOK_URL to your domain
  ⚠️  Enable WEBHOOK_HTTPS_ONLY=true
  ⚠️  Set up database backups
  ⚠️  Configure log forwarding
  ⚠️  Enable monitoring and alerting
  ⚠️  Rotate secrets regularly

================================================================================
TROUBLESHOOTING
================================================================================

Problem: Container won't start
Solution: Check logs
  $ docker compose -f docker-compose-vnext.yml logs app

Problem: Database connection failed
Solution: Verify PostgreSQL is healthy
  $ docker compose -f docker-compose-vnext.yml ps
  Look for "healthy" status

Problem: Port 8000 already in use
Solution: Change APP_PORT in .env.vnext or kill process
  $ lsof -i :8000
  $ kill -9 <PID>

Problem: Build fails
Solution: Clean build without cache
  $ docker compose -f docker-compose-vnext.yml build --no-cache

Problem: Health check fails
Solution: Wait for startup (30s) and check logs
  $ docker compose -f docker-compose-vnext.yml logs -f app
  Look for startup errors

See PHASE_0_SETUP.md Troubleshooting section for more details

================================================================================
VERIFICATION COMMANDS
================================================================================

Check all services running:
  $ docker compose -f docker-compose-vnext.yml ps

Check app health:
  $ curl http://localhost:8000/health

Check database connection:
  $ docker compose -f docker-compose-vnext.yml exec app \
    psql -h postgres -U server_agent -d server_agent_vnext -c "\l"

View application logs:
  $ docker compose -f docker-compose-vnext.yml logs -f app

View database logs:
  $ docker compose -f docker-compose-vnext.yml logs -f postgres

Stop services:
  $ docker compose -f docker-compose-vnext.yml down

Remove volumes (clean slate):
  $ docker compose -f docker-compose-vnext.yml down -v

================================================================================
NEXT STEPS
================================================================================

Immediate (Next 5 min):
  1. Read PHASE_0_SETUP.md
  2. Copy .env templates
  3. Configure required values
  4. Test docker build

Before Production:
  1. Configure HTTPS for webhook
  2. Set up database backups
  3. Configure monitoring
  4. Update security settings
  5. Set ENV=production

Phase 1 (Application):
  1. Create FastAPI entry point
  2. Add database models
  3. Integrate Telegram bot
  4. Integrate Claude API
  5. Build proactive loop

================================================================================
SUPPORT
================================================================================

Documentation:
  PHASE_0_SETUP.md      → Full setup guide
  PHASE_0_CHECKLIST.md  → Quick reference
  PHASE_0_SUMMARY.txt   → Overview
  PHASE_0_INDEX.md      → Navigation

For Questions:
  1. Check the setup guide (PHASE_0_SETUP.md)
  2. Review troubleshooting section
  3. Check project CLAUDE.md for principles

For Bug Reports:
  1. Provide error logs
  2. Show configuration (mask secrets)
  3. List Docker version and OS

================================================================================
STATUS: PHASE 0 COMPLETE
================================================================================

All files created and validated. Ready for Phase 1 implementation.

Next: Read PHASE_0_SETUP.md to begin configuration and deployment.

Good luck! 🚀
