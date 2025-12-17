# Phase 6 Deployment - Quick Start Guide

## 60-Second Setup

### 1. Copy to VPS
```bash
scp -r /path/to/server-agent root@92.246.136.186:/opt/server-agent-vnext
ssh root@92.246.136.186
cd /opt/server-agent-vnext
```

### 2. Setup Git (First Time Only)
```bash
bash scripts/setup_git.sh /opt/server-agent-vnext
```

### 3. Configure Environment
```bash
cp .env.vnext.example .env.vnext
cp .env.postgres.vnext.example .env.postgres.vnext
# Edit with actual values:
# - TELEGRAM_API_TOKEN
# - TELEGRAM_WEBHOOK_SECRET
# - MASTER_CHAT_IDS
# - DATABASE passwords
```

### 4. Deploy
```bash
bash scripts/build_and_deploy.sh
```

**That's it!** Future deployments are automatic on git push to main.

---

## Common Commands

### Deploy Latest Code
```bash
cd /opt/server-agent-vnext
bash scripts/build_and_deploy.sh
```

### Run Tests Only
```bash
bash scripts/run_tests.sh . 70
```

### Check Health
```bash
bash scripts/smoke_test.sh
```

### Backup Database
```bash
bash scripts/backup_db.sh ./backups 7
```

### Restore Database
```bash
bash scripts/restore_db.sh ./backups/server_agent_2024-12-18_10-30-45.sql.gz
```

### Manual Rollback
```bash
bash scripts/rollback.sh
```

### View Deployment Logs
```bash
tail -f logs/deployment_*.log | sort | tail -1
```

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | ✅ Success | System healthy |
| 1 | ❌ Tests failed | Deployment aborted |
| 2 | ❌ Build failed | No changes made |
| 3 | ❌ Deploy failed | Manual intervention needed |
| 4 | ❌ Rollback failed | CRITICAL - Manual intervention |

---

## Troubleshooting

### Build Fails
```bash
docker system df
docker image prune -a
bash scripts/build_and_deploy.sh
```

### Health Endpoint Fails
```bash
docker logs server_agent_vnext_app | tail -50
curl http://localhost:8000/health
```

### Database Issues
```bash
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT 1"
```

### Emergency Rollback
```bash
bash scripts/rollback.sh
```

---

## Monitoring

### Watch Deployment
```bash
tail -f logs/deployment_*.log
```

### Check Container Status
```bash
docker compose -f docker-compose-vnext.yml ps
```

### View Logs
```bash
docker logs server_agent_vnext_app
docker logs server_agent_vnext_postgres
```

### Check Health
```bash
curl http://localhost:8000/health
```

---

## Automation Setup

### GitHub Webhook (Optional)

1. Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy
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
              root@92.246.136.186 \
              "cd /opt/server-agent-vnext && bash scripts/build_and_deploy.sh"
```

2. Add SSH key to GitHub Secrets:
- Secret name: `DEPLOY_KEY`
- Value: Contents of `~/.ssh/id_ed25519`

3. Push to main and watch deployment happen automatically!

### Git Hook (Self-Hosted)

Post-receive hook automatically created by `setup_git.sh`:
```bash
.git/hooks/post-receive
```

Push to main and deployment starts automatically on server.

---

## File Structure

```
/opt/server-agent-vnext/
├── scripts/                      # Deployment scripts
│   ├── build_and_deploy.sh      # Main pipeline
│   ├── run_tests.sh             # Test execution
│   ├── smoke_test.sh            # Health validation
│   ├── rollback.sh              # Rollback script
│   ├── backup_db.sh             # Database backup
│   ├── restore_db.sh            # Database restore
│   ├── setup_git.sh             # Git configuration
│   ├── deployment_report.sh     # Report generation
│   ├── post-receive             # Git hook
│   └── README.md                # Script documentation
├── tests/                        # Test suites
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   │   ├── test_full_flow.py
│   │   ├── test_approval_flow.py
│   │   └── test_proactive_cycle.py
│   └── smoke/                   # Smoke tests
│       ├── test_health.py
│       └── test_webhook.py
├── docs/
│   └── DEPLOYMENT_PIPELINE.md   # Complete guide
├── logs/                         # Deployment logs
├── backups/                      # Database backups
├── docker-compose-vnext.yml     # Docker configuration
├── Dockerfile                    # Build configuration
├── .env.vnext.example           # Example env file
└── .env.postgres.vnext.example  # Example database env
```

---

## Verification Checklist

After deployment:

- [ ] Check health endpoint: `curl http://localhost:8000/health`
- [ ] View application logs: `docker logs server_agent_vnext_app`
- [ ] Run smoke tests: `bash scripts/smoke_test.sh`
- [ ] Check database: `docker exec server_agent_vnext_postgres psql -U agent -d server_agent -c "SELECT 1"`
- [ ] Verify Telegram bot: Send test message
- [ ] Check resource usage: `docker stats`

---

## Environment Variables Quick Reference

```bash
# Telegram (Required for notifications)
TELEGRAM_API_TOKEN="your_bot_token"
MASTER_CHAT_ID="46808774"
TELEGRAM_WEBHOOK_SECRET="your_webhook_secret"

# Database (Required)
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="server_agent"
DB_USER="agent"
DB_PASSWORD="your_password"

# Docker (Required)
DOCKER_IMAGE_BASE="server-agent-vnext"
DOCKER_COMPOSE_FILE="./docker-compose-vnext.yml"

# Testing (Optional)
COVERAGE_THRESHOLD="70"
VERBOSE="false"

# API (Required)
API_URL="http://localhost:8000"

# Deployment (Optional)
STARTUP_WAIT="10"
DEPLOYMENT_TIMEOUT="300"
```

---

## Key Features

✅ **Automated** - Deploy on git push
✅ **Safe** - Database backups + rollback
✅ **Tested** - Unit + integration + smoke tests
✅ **Monitored** - Comprehensive logging
✅ **Notified** - Master gets Telegram updates
✅ **Recoverable** - Automatic rollback on failure
✅ **Idempotent** - Safe to run multiple times

---

## Need Help?

1. **Script Reference:** `scripts/README.md`
2. **Complete Guide:** `docs/DEPLOYMENT_PIPELINE.md`
3. **Summary:** `PHASE_6_SUMMARY.md`

---

**Phase 6 Status:** ✅ COMPLETE
**Ready for Production:** YES
**Last Updated:** 2024-12-18
