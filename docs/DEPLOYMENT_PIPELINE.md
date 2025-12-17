# Phase 6: Deployment Pipeline

## Overview

Phase 6 implements a complete automated deployment pipeline for Server Agent vNext with comprehensive build, test, deploy, and rollback automation triggered by git merges to the main branch.

**Key Features:**
- Automated testing (unit + integration + smoke)
- Docker image building and versioning
- Database backup before deployment
- Automated rollback on failure
- Master notifications via Telegram
- Comprehensive logging and reporting
- Zero-downtime deployments (where possible)
- Token budget tracking and enforcement

## Architecture

### Pipeline Flow

```
Git Merge to Main
    ↓
[build_and_deploy.sh] triggered
    ↓
1. Pull latest code
2. Create deployment record
3. Run unit tests
4. Run integration tests
5. Build Docker image
6. Tag previous image for rollback
7. Stop running containers
8. Apply database migrations
9. Start new containers
10. Run smoke tests
    ├─→ Success: Update status → Notify Master
    └─→ Failure: Trigger rollback → Notify Master
```

### Component Overview

| Component | Purpose | Location |
|-----------|---------|----------|
| `build_and_deploy.sh` | Main orchestration pipeline | `scripts/build_and_deploy.sh` |
| `run_tests.sh` | Test suite execution | `scripts/run_tests.sh` |
| `smoke_test.sh` | Post-deployment validation | `scripts/smoke_test.sh` |
| `rollback.sh` | Emergency rollback | `scripts/rollback.sh` |
| `backup_db.sh` | Database backup | `scripts/backup_db.sh` |
| `restore_db.sh` | Database restore | `scripts/restore_db.sh` |
| `deployment_report.sh` | Deployment reporting | `scripts/deployment_report.sh` |
| `setup_git.sh` | Git configuration | `scripts/setup_git.sh` |

### Test Structure

```
tests/
├── unit/                    # Unit tests (existing)
├── integration/             # Integration tests (Phase 6)
│   ├── test_full_flow.py   # End-to-end workflows
│   ├── test_approval_flow.py # Master approval workflows
│   └── test_proactive_cycle.py # Proactive scheduler tests
└── smoke/                   # Smoke tests (Phase 6)
    ├── test_health.py       # Health endpoint checks
    └── test_webhook.py      # Webhook validation
```

## Trigger Mechanisms

### Option 1: Git Hook (Recommended for Self-Hosted)

**Setup:** Configure post-receive hook on server

```bash
# On the VPS server
bash scripts/setup_git.sh /opt/server-agent-vnext

# Creates .git/hooks/post-receive that triggers on push to main
```

**How it works:**
1. Developer pushes to main branch
2. Git post-receive hook executes
3. Calls `scripts/build_and_deploy.sh`
4. Pipeline executes and notifies Master

### Option 2: GitHub Webhook (Recommended for GitHub)

**Setup:** Configure GitHub Actions or webhook

```yaml
# .github/workflows/deploy.yml
name: Deploy on Main Push

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to VPS
        run: |
          ssh -i ${{ secrets.DEPLOY_KEY }} \
              user@server.ip \
              "cd /opt/server-agent-vnext && bash scripts/build_and_deploy.sh"
```

### Option 3: Manual Trigger

```bash
# SSH into server
ssh root@92.246.136.186

# Navigate to repo
cd /opt/server-agent-vnext

# Run deployment manually
bash scripts/build_and_deploy.sh
```

## Deployment Steps in Detail

### Step 0: Pull Latest Code

```bash
git fetch origin main
git checkout -f main
```

**Exit on failure:** Yes (exit code 1)
**Reason:** Cannot proceed without latest code

### Step 1: Database Backup

```bash
bash scripts/backup_db.sh ./backups 7
```

**Exit on failure:** No (continues with deployment)
**Reason:** Backup should not block deployment, but is important for rollback

**Output:**
- Compressed SQL backup: `backups/server_agent_YYYY-MM-DD_HH-MM-SS.sql.gz`
- Old backups pruned (keeps last 7 days)

### Step 2: Run Tests

```bash
bash scripts/run_tests.sh . 70
```

**Exit on failure:** Yes (exit code 1)
**Reason:** Deployment should not proceed if tests fail

**Tests run:**
- Unit tests: `tests/unit/*.py`
- Integration tests: `tests/integration/*.py`
- Smoke tests: `tests/smoke/*.py`

**Coverage requirement:** 70% minimum (configurable)

### Step 3: Build Docker Image

```bash
docker build -t server-agent-vnext:latest \
  --build-arg BUILD_DATE="$(date)" \
  --build-arg VCS_REF="$GIT_SHA" \
  .
```

**Exit on failure:** Yes (exit code 2)
**Reason:** Cannot deploy without valid image

**Image tagging:** `server-agent-vnext:latest`

### Step 4: Tag Rollback Image

```bash
docker tag server-agent-vnext:latest server-agent-vnext:rollback
```

**Exit on failure:** No (warning only)
**Reason:** Enables emergency rollback if needed

### Step 5: Stop Running Containers

```bash
docker compose -f docker-compose-vnext.yml down
```

**Exit on failure:** Yes (exit code 3)
**Reason:** Must stop old containers before starting new ones

### Step 6: Apply Database Migrations

```bash
# Example with Alembic:
docker run --rm --network server_agent_vnext_network \
  -e DATABASE_URL="$DATABASE_URL" \
  server-agent-vnext:latest \
  alembic upgrade head
```

**Exit on failure:** Depends on migration tool
**Reason:** Schema changes must succeed before app starts

### Step 7: Start New Containers

```bash
docker compose -f docker-compose-vnext.yml up -d
```

**Exit on failure:** Yes (exit code 3)
**Reason:** Cannot continue without running containers

### Step 8: Wait for Startup

```bash
sleep 10  # Allow containers to stabilize
```

**Duration:** 10 seconds (configurable via `STARTUP_WAIT`)
**Purpose:** Give services time to initialize before testing

### Step 9: Run Smoke Tests

```bash
bash scripts/smoke_test.sh
```

**Exit on failure:** Triggers rollback
**Reason:** Smoke tests validate system is functional

**Tests include:**
- Health endpoint check
- Database connectivity
- Telegram bot status
- API responsiveness
- Resource usage validation

### Step 10: Generate Report

```bash
bash scripts/deployment_report.sh telegram
```

**Output:** Telegram notification with deployment summary
**Includes:**
- Git SHA and branch
- Test status
- Build status
- Smoke test results
- Deployment duration

## Rollback Procedure

### Automatic Rollback (on Smoke Test Failure)

When smoke tests fail, automatic rollback is triggered:

```bash
bash scripts/rollback.sh
```

**Steps:**
1. Stop current containers
2. Restore previous Docker image (`server-agent-vnext:rollback`)
3. Start containers with rollback image
4. Wait for startup (10s)
5. Run smoke tests on rollback
6. If success: Log rollback completion, notify Master
7. If failure: Alert Master urgently (CRITICAL)

**Master notification:**
```
🚨 CRITICAL: Rollback Failed!

System may be in unstable state.
Previous version failed to start.

Please investigate manually.
```

### Manual Rollback (User-Initiated)

For manual rollback to previous version:

```bash
bash scripts/rollback.sh
```

## Database Management

### Backup

Automatic backup before every deployment:

```bash
bash scripts/backup_db.sh ./backups 7
```

**Features:**
- Timestamped backups: `server_agent_2024-12-18_14-30-45.sql.gz`
- Automatic compression with gzip
- Automatic rotation (keeps last 7 days by default)
- Full transaction dump (consistent state)

**Storage location:**
```
backups/
├── server_agent_2024-12-18_10-00-00.sql.gz
├── server_agent_2024-12-18_11-00-00.sql.gz
└── server_agent_2024-12-18_12-00-00.sql.gz
```

### Restore

Manual database restore from backup:

```bash
bash scripts/restore_db.sh ./backups/server_agent_2024-12-18_10-00-00.sql.gz
```

**Important notes:**
- Asks for confirmation before overwriting
- Decompresses automatically if needed
- Verifies restore success with test query

## Git Configuration

### First-Time Setup

```bash
# On the VPS server
bash scripts/setup_git.sh /opt/server-agent-vnext \
  --github-url "https://github.com/user/server-agent-vnext.git" \
  --git-email "agent@server-agent.local" \
  --git-name "Server Agent vNext"
```

**Configuration:**
- User email/name
- Remote URL
- SSH keys for authentication
- Post-receive hook setup

### Continuous Integration

For GitHub Actions or other CI/CD:

```bash
export TELEGRAM_API_TOKEN="your-bot-token"
export MASTER_CHAT_ID="46808774"
export DATABASE_URL="postgresql://user:pass@host/db"

bash scripts/build_and_deploy.sh
```

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Deployment complete, services healthy |
| 1 | Test Failed | Tests failed, deployment aborted, no changes made |
| 2 | Build Failed | Docker build failed, deployment aborted |
| 3 | Deploy Failed | Container startup failed, no rollback available |
| 4 | Smoke Failed | Smoke tests failed, automatic rollback executed |

## Master Notifications

### Success Notification

```
✅ DEPLOYMENT SUCCESSFUL ✅

Git SHA: abc1234
Branch: main
Duration: 145s

All systems operational.
```

### Failure Notification

```
❌ DEPLOYMENT FAILED ❌

Unit tests failed during deployment.
Check test logs for details.
```

### Rollback Notification

```
⚠️ WARNING ⚠️

Deployment failed - system rolled back to previous version.
Smoke tests failed on new deployment.
```

### Critical Notification

```
🚨 CRITICAL 🚨

Rollback image not available!
Please restore manually.
```

## Monitoring and Logs

### Deployment Log

Each deployment creates a timestamped log:

```
logs/deployment_2024-12-18_14-30-45.log
```

**Contents:**
- All command output
- Status changes
- Error messages
- Test results
- Smoke test output

### Application Logs

```
logs/app.log              # Main application logs
logs/telegram.log         # Telegram bot logs (if enabled)
logs/reactive.log         # Reactive worker logs (if enabled)
logs/proactive.log        # Proactive scheduler logs (if enabled)
```

### Log Rotation

Docker container logs are automatically rotated:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"      # Rotate at 100MB
    max-file: "5"          # Keep 5 files
```

## Troubleshooting

### Deployment Hangs

**Symptoms:** `git fetch` or `docker build` appears stuck

**Solution:**
```bash
# SSH into server
ssh root@92.246.136.186

# Check running processes
ps aux | grep -E "git|docker"

# Kill stuck process if necessary
kill -9 <PID>

# Retry deployment
bash scripts/build_and_deploy.sh
```

### Smoke Tests Fail

**Symptoms:** Deployment succeeds but smoke tests fail, triggering rollback

**Investigation:**
```bash
# Check application logs
docker logs server_agent_vnext_app | tail -50

# Check health endpoint
curl http://localhost:8000/health

# Check database connectivity
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT 1"
```

### Rollback Fails

**Symptoms:** Automatic rollback also fails, critical alert sent

**Manual Recovery:**
```bash
# SSH into server
ssh root@92.246.136.186

# Check available images
docker images | grep server-agent-vnext

# Manually start previous version
docker compose -f docker-compose-vnext.yml up -d

# Verify health
curl http://localhost:8000/health
```

### Database Restore Needed

```bash
# List available backups
ls -lh backups/

# Restore from specific backup
bash scripts/restore_db.sh ./backups/server_agent_2024-12-18_10-00-00.sql.gz

# Verify restore
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT COUNT(*) FROM information_schema.tables"
```

## Performance Considerations

### Deployment Time

Typical deployment takes 2-5 minutes:

- Code pull: 5-10s
- Database backup: 30-60s (depends on DB size)
- Tests: 30-120s (depends on test count)
- Build: 60-120s (depends on image size)
- Containers: 10-20s
- Smoke tests: 10-30s

### Resource Usage

During deployment:

- CPU: Can spike to 100% during build
- Memory: 500MB-2GB (more during build)
- Disk I/O: High during backup and build

**Recommendation:** Schedule deployments during low-traffic periods

## Security Considerations

### Secrets Management

```bash
# Never commit secrets
git status | grep .env

# Use .env.example instead
cp .env.example .env
# Edit .env with actual values
```

### SSH Keys

```bash
# Generated automatically by setup_git.sh
ls -la ~/.ssh/id_ed25519

# Add public key to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and paste into GitHub settings
```

### Database Backups

```bash
# Backups contain sensitive data
chmod 600 backups/*.sql.gz

# Consider encrypted storage for sensitive environments
```

## Best Practices

### Before Deployment

1. Verify all tests pass locally
2. Review git diff for unexpected changes
3. Backup important data manually
4. Notify team of deployment
5. Ensure Master is available for approval if needed

### During Deployment

1. Monitor logs in real-time
2. Check health endpoint during startup
3. Verify database connectivity
4. Confirm no errors in application logs

### After Deployment

1. Run manual smoke tests
2. Check critical user workflows
3. Monitor system resources
4. Review deployment logs
5. Document any issues encountered

## Advanced Configuration

### Custom Test Coverage Threshold

```bash
COVERAGE_THRESHOLD=80 bash scripts/build_and_deploy.sh
```

### Custom Startup Wait

```bash
STARTUP_WAIT=30 bash scripts/build_and_deploy.sh
```

### Custom Database Backup Retention

```bash
bash scripts/backup_db.sh ./backups 14  # Keep 14 days
```

### Disable Telegram Notifications

```bash
TELEGRAM_API_TOKEN="" bash scripts/build_and_deploy.sh
```

## Integration with CI/CD

### GitHub Actions

See `.github/workflows/deploy.yml` for GitHub Actions integration

### GitLab CI

```yaml
deploy:
  stage: deploy
  script:
    - ssh root@server "cd /opt/server-agent-vnext && bash scripts/build_and_deploy.sh"
  only:
    - main
```

### Jenkins

```groovy
pipeline {
    stages {
        stage('Deploy') {
            steps {
                sh '''
                    ssh root@server "cd /opt/server-agent-vnext && bash scripts/build_and_deploy.sh"
                '''
            }
        }
    }
}
```

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/current/backup.html)
- [Pytest Documentation](https://docs.pytest.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

---

**Last Updated:** 2024-12-18
**Phase:** 6 - Self-Update Pipeline
**Status:** Complete
