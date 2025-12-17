# Deployment Scripts for Server Agent vNext

This directory contains all scripts needed for automated deployment, testing, and rollback of Server Agent vNext.

## Quick Start

### 1. Initial Setup

```bash
# Configure git repository on VPS
bash scripts/setup_git.sh /opt/server-agent-vnext \
  --github-url "https://github.com/user/server-agent-vnext.git"
```

### 2. Manual Deployment

```bash
# Deploy the latest code
cd /opt/server-agent-vnext
bash scripts/build_and_deploy.sh
```

### 3. Watch Deployment

```bash
# Monitor deployment log
tail -f logs/deployment_*.log
```

## Scripts Overview

### Core Deployment Scripts

#### `build_and_deploy.sh` - Main Deployment Pipeline
**Purpose:** Complete deployment orchestration

**Usage:**
```bash
bash build_and_deploy.sh
```

**Environment Variables:**
- `REPO_PATH` - Repository path (default: current directory)
- `DOCKER_IMAGE_BASE` - Base Docker image name (default: server-agent-vnext)
- `COVERAGE_THRESHOLD` - Minimum test coverage % (default: 70)
- `API_URL` - Application API URL (default: http://localhost:8000)
- `TELEGRAM_API_TOKEN` - Bot token for notifications
- `MASTER_CHAT_ID` - Master's Telegram chat ID

**Output:**
- Deployment log: `logs/deployment_YYYY-MM-DD_HH-MM-SS.log`
- Exit codes: 0=success, 1=test_failed, 2=build_failed, 3=deploy_failed, 4=smoke_failed

**What it does:**
1. Pulls latest code from git
2. Backs up database
3. Runs test suite
4. Builds Docker image
5. Tags previous image for rollback
6. Stops old containers
7. Starts new containers
8. Validates with smoke tests
9. Sends notification to Master

---

#### `run_tests.sh` - Test Suite Execution
**Purpose:** Run unit, integration, and smoke tests with coverage reporting

**Usage:**
```bash
bash run_tests.sh . 70
```

**Arguments:**
- `$1` - Project root (default: current directory)
- `$2` - Coverage threshold % (default: 70)

**Environment Variables:**
- `VERBOSE` - Set to "true" for detailed output

**Output:**
- Coverage reports: `coverage/` directory
- JUnit XML: `coverage/*_results.xml`
- Coverage HTML: `coverage/all_coverage/index.html`

**Exit codes:**
- 0 = All tests passed
- 1 = Tests failed

---

#### `smoke_test.sh` - Post-Deployment Validation
**Purpose:** Validate deployed system is healthy and operational

**Usage:**
```bash
bash smoke_test.sh
```

**Environment Variables:**
- `API_URL` - Application URL (default: http://localhost:8000)
- `HEALTH_CHECK_TIMEOUT` - Request timeout in seconds (default: 5)

**Tests:**
- Health endpoint (HTTP 200)
- Database connectivity
- Telegram bot initialization
- API responsiveness
- Resource usage validation
- Log file analysis

**Exit codes:**
- 0 = All smoke tests passed
- 1 = One or more tests failed

---

#### `rollback.sh` - Emergency Rollback
**Purpose:** Rollback to previous version if deployment fails

**Usage:**
```bash
bash rollback.sh
```

**Environment Variables:**
- `DOCKER_COMPOSE_FILE` - Compose file path
- `API_URL` - Application URL for validation
- `TELEGRAM_API_TOKEN` - For Master notifications

**What it does:**
1. Stops current containers
2. Restores previous Docker image
3. Starts containers with rollback image
4. Validates with smoke tests
5. Notifies Master of status

**Exit codes:**
- 0 = Rollback successful
- 1 = Rollback failed (CRITICAL)

---

### Database Scripts

#### `backup_db.sh` - Database Backup
**Purpose:** Create timestamped, compressed database backups

**Usage:**
```bash
bash backup_db.sh ./backups 7
```

**Arguments:**
- `$1` - Backup directory (default: ./backups)
- `$2` - Days to retain (default: 7)

**Output:**
- Backup file: `backups/server_agent_YYYY-MM-DD_HH-MM-SS.sql.gz`
- Compressed with gzip
- Old backups automatically deleted

**Environment Variables:**
- `DB_HOST` - Database host (default: postgres)
- `DB_PORT` - Database port (default: 5432)
- `DB_NAME` - Database name (default: server_agent)
- `DB_USER` - Database user (default: agent)

---

#### `restore_db.sh` - Database Restore
**Purpose:** Restore database from backup file

**Usage:**
```bash
bash restore_db.sh ./backups/server_agent_2024-12-18_10-30-45.sql.gz
```

**Arguments:**
- `$1` - Backup file path (required)

**Environment Variables:**
- `DB_HOST` - Database host (default: postgres)
- `DB_PORT` - Database port (default: 5432)
- `DB_NAME` - Database name (default: server_agent)
- `DB_USER` - Database user (default: agent)

**What it does:**
1. Asks for confirmation (5 second countdown)
2. Decompresses backup if needed
3. Restores database
4. Verifies restore success

---

### Reporting Scripts

#### `deployment_report.sh` - Deployment Reporting
**Purpose:** Generate formatted deployment reports

**Usage:**
```bash
bash deployment_report.sh text
bash deployment_report.sh json
bash deployment_report.sh telegram
```

**Arguments:**
- `$1` - Report format: text, json, or telegram

**Output:**
- Text format: Human-readable report
- JSON format: Machine-parseable format
- Telegram format: Formatted for Telegram message + sends notification

**Environment Variables:**
- `BUILD_STATUS` - Build status (success/failed)
- `TEST_STATUS` - Test status (success/failed)
- `DEPLOYMENT_STATUS` - Deployment status
- `SMOKE_TEST_STATUS` - Smoke test status
- `GIT_SHA` - Git commit SHA
- `GIT_BRANCH` - Git branch
- `DEPLOY_DURATION` - Deployment duration in seconds
- `TELEGRAM_API_TOKEN` - Bot token for sending
- `MASTER_CHAT_ID` - Recipient chat ID

---

### Configuration Scripts

#### `setup_git.sh` - Git Repository Setup
**Purpose:** Initialize and configure git repository for deployment

**Usage:**
```bash
bash setup_git.sh /opt/server-agent-vnext
```

**Arguments:**
- `$1` - Repository path (default: current directory)

**What it does:**
1. Initializes git if needed
2. Configures git user (email/name)
3. Sets up remotes
4. Generates/configures SSH keys
5. Creates post-receive hook
6. Sets git preferences

**Environment Variables:**
- `GIT_USER_EMAIL` - Git user email (default: agent@server-agent.local)
- `GIT_USER_NAME` - Git user name (default: Server Agent vNext)
- `GITHUB_URL` - GitHub repository URL
- `GITHUB_REMOTE` - Remote name (default: origin)

---

#### `post-receive` - Git Hook
**Purpose:** Automatically trigger deployment when code is pushed

**Installation:**
```bash
# Placed automatically by setup_git.sh
# Or manually:
cp scripts/post-receive .git/hooks/
chmod +x .git/hooks/post-receive
```

**How it works:**
1. Detects push to main branch
2. Triggers build_and_deploy.sh
3. Runs in background (doesn't block git push)
4. Master receives notifications

---

## Environment Setup

### Required Environment Variables

```bash
# Database
export DB_HOST="postgres"
export DB_PORT="5432"
export DB_NAME="server_agent"
export DB_USER="agent"
export DB_PASSWORD="your_password"  # Set in .env file, not shell!

# Telegram (for notifications)
export TELEGRAM_API_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export MASTER_CHAT_ID="46808774"

# Docker
export DOCKER_IMAGE_BASE="server-agent-vnext"
export DOCKER_COMPOSE_FILE="./docker-compose-vnext.yml"

# API
export API_URL="http://localhost:8000"

# Testing
export COVERAGE_THRESHOLD="70"
```

### Load Environment Variables

```bash
# From .env file (recommended)
set -a
source .env
set +a

# Then run scripts
bash scripts/build_and_deploy.sh
```

---

## Common Tasks

### Deploy New Code

```bash
# Quick deploy with status updates
bash scripts/build_and_deploy.sh

# Deploy with custom coverage threshold
COVERAGE_THRESHOLD=80 bash scripts/build_and_deploy.sh

# Deploy without Telegram notifications
TELEGRAM_API_TOKEN="" bash scripts/build_and_deploy.sh
```

### Run Tests Only (No Deployment)

```bash
bash scripts/run_tests.sh . 70
```

### Check Deployment Health

```bash
bash scripts/smoke_test.sh
```

### Create Manual Backup

```bash
bash scripts/backup_db.sh ./backups 14
```

### Restore from Backup

```bash
# List available backups
ls -lh backups/

# Restore specific backup
bash scripts/restore_db.sh ./backups/server_agent_2024-12-18_10-30-45.sql.gz
```

### Manual Rollback

```bash
bash scripts/rollback.sh
```

### View Deployment Logs

```bash
# Latest deployment
tail -f logs/deployment_*.log | sort | tail -1

# All deployments
ls -lh logs/deployment_*.log

# Follow in real-time
tail -f logs/deployment_$(ls -1 logs | grep deployment | tail -1).log
```

---

## Troubleshooting

### Deployment Fails at Tests

**Problem:** Test suite fails, deployment aborts

**Solution:**
```bash
# Run tests locally to debug
bash scripts/run_tests.sh . 70

# View coverage report
open coverage/all_coverage/index.html

# Fix failing tests, then retry
bash scripts/build_and_deploy.sh
```

### Docker Build Fails

**Problem:** "Docker build failed"

**Solution:**
```bash
# Check Docker status
docker version

# Check image disk space
docker system df

# Clean up unused images
docker image prune -a

# Retry build
bash scripts/build_and_deploy.sh
```

### Smoke Tests Fail

**Problem:** Deployment succeeds, smoke tests fail

**Solution:**
```bash
# Check application logs
docker logs server_agent_vnext_app | tail -50

# Check health endpoint
curl http://localhost:8000/health

# Check database
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT 1"

# Manually trigger rollback
bash scripts/rollback.sh
```

### Database Restore Issues

**Problem:** "Failed to restore database"

**Solution:**
```bash
# List available backups
ls -lh backups/

# Verify backup file
gzip -t backups/server_agent_*.sql.gz

# Restore with verbose output
bash -x scripts/restore_db.sh ./backups/server_agent_*.sql.gz

# Check database after restore
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT COUNT(*) FROM information_schema.tables"
```

---

## Best Practices

### Before Deploying

1. **Commit all changes:**
   ```bash
   git add .
   git commit -m "feature: description"
   ```

2. **Run tests locally:**
   ```bash
   bash scripts/run_tests.sh . 70
   ```

3. **Review changes:**
   ```bash
   git log -5
   git diff main...HEAD
   ```

4. **Backup current database:**
   ```bash
   bash scripts/backup_db.sh ./backups 30
   ```

### During Deployment

1. **Monitor progress:**
   ```bash
   tail -f logs/deployment_*.log
   ```

2. **Check health:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Verify no errors:**
   ```bash
   docker logs server_agent_vnext_app
   ```

### After Deployment

1. **Verify functionality:**
   ```bash
   bash scripts/smoke_test.sh
   ```

2. **Check resources:**
   ```bash
   docker stats
   ```

3. **Review logs:**
   ```bash
   tail -50 logs/app.log
   ```

---

## Performance Tips

### Speed Up Deployment

1. **Parallel testing:**
   ```bash
   # Use pytest-xdist for parallel test execution
   ```

2. **Cache Docker layers:**
   - Keep Dockerfile efficient
   - Order commands from least to most frequently changed

3. **Minimize database backup:**
   - For large databases, consider incremental backups
   - Compress with maximum compression (takes longer but smaller file)

### Monitor Resource Usage

```bash
# Check container resources
docker stats

# Check disk space
df -h

# Check memory
free -h

# Clean up unused Docker resources
docker system prune -a
```

---

## References

- **Docker Documentation:** https://docs.docker.com/
- **PostgreSQL Backup:** https://www.postgresql.org/docs/current/backup.html
- **Pytest Documentation:** https://docs.pytest.org/
- **Telegram Bot API:** https://core.telegram.org/bots/api

---

**Last Updated:** 2024-12-18
**Version:** Phase 6
**Status:** Production Ready
