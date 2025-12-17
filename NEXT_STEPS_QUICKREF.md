# Server Agent vNext - Next Steps Quick Reference

**Status:** 🟡 Deployed but not operational
**Location:** Frankfurt server (92.246.136.186)
**Last Updated:** 2024-12-18

---

## Critical Issues to Fix

### 🔥 ISSUE #1: Claude API Key (HIGH PRIORITY)

**Problem:** Using OAuth token instead of API key

**Fix (10 minutes):**
```bash
# 1. SSH to server
ssh root@92.246.136.186

# 2. Edit environment file
cd /root/server-agent
nano .env.vnext

# 3. Update this line:
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ACTUAL_KEY_HERE

# 4. Restart application
docker compose -f docker-compose-vnext.yml restart app

# 5. Verify
docker logs server_agent_vnext_app | grep -i "claude\|anthropic"
```

**Get API Key:** https://console.anthropic.com/settings/keys

---

### 🔥 ISSUE #2: Telegram Webhook HTTPS (MEDIUM PRIORITY)

**Problem:** Telegram requires HTTPS for webhooks

**Fix (1-2 hours):**

#### Step 1: Domain Setup (5 min)
```bash
# Register subdomain in DNS:
# server-agent.intelligency.studio → 92.246.136.186
```

#### Step 2: Install Nginx (5 min)
```bash
ssh root@92.246.136.186

apt update
apt install -y nginx certbot python3-certbot-nginx

# Create nginx config
nano /etc/nginx/sites-available/server-agent
```

**Nginx Config:**
```nginx
server {
    server_name server-agent.intelligency.studio;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/server-agent /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

#### Step 3: SSL Certificate (5 min)
```bash
certbot --nginx -d server-agent.intelligency.studio
# Choose redirect HTTP to HTTPS
```

#### Step 4: Update Webhook (2 min)
```bash
# Get webhook secret from .env.vnext
WEBHOOK_SECRET=$(grep TELEGRAM_WEBHOOK_SECRET /root/server-agent/.env.vnext | cut -d= -f2)
BOT_TOKEN=$(grep TELEGRAM_API_TOKEN /root/server-agent/.env.vnext | cut -d= -f2)

# Set webhook
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -d "url=https://server-agent.intelligency.studio/webhook/telegram" \
  -d "secret_token=${WEBHOOK_SECRET}"

# Verify
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

---

## Testing After Fixes

### Test #1: Health Check
```bash
curl http://92.246.136.186:8000/health
# Expected: {"status": "healthy", "database": "connected"}
```

### Test #2: Telegram Bot
```
# Send to @agi_superbot:
/start

# Expected response:
"🤖 Server-Agent Online"
```

### Test #3: Approval Flow
```
# Send to @agi_superbot:
/status

# Expected:
- Bot responds with current status
- Shows pending approvals (if any)
- Shows last proactive cycle time
```

### Test #4: Proactive Cycle
```bash
# Check logs for autonomous activity
docker logs server_agent_vnext_app | grep -i "proactive\|cycle"

# Expected:
- Proactive scheduler running
- Cycles executing on schedule
```

---

## Common Commands

### SSH to Server
```bash
ssh root@92.246.136.186
# Password: k409VP3K8LEy (rotate regularly!)
```

### Check Status
```bash
# Container status
docker ps --filter "name=server_agent_vnext"

# Health check
curl http://localhost:8000/health

# Application logs
docker logs server_agent_vnext_app --tail 50 -f

# Database check
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT COUNT(*) FROM threads"
```

### Deployment
```bash
# Deploy latest code
cd /root/server-agent
bash scripts/build_and_deploy.sh

# Quick restart (no rebuild)
docker compose -f docker-compose-vnext.yml restart app

# Full restart
docker compose -f docker-compose-vnext.yml down
docker compose -f docker-compose-vnext.yml up -d
```

### Backup & Restore
```bash
# Create backup
bash scripts/backup_db.sh ./backups 7

# Restore from backup
bash scripts/restore_db.sh ./backups/server_agent_2024-12-18.sql.gz

# List backups
ls -lh ./backups/
```

### Logs
```bash
# Application logs
docker logs server_agent_vnext_app

# Deployment logs
ls -lh logs/deployment_*.log
tail -f logs/deployment_*.log | tail -1

# Database logs
docker logs server_agent_vnext_postgres
```

### Emergency Rollback
```bash
cd /root/server-agent
bash scripts/rollback.sh
```

---

## Environment Files

### `.env.vnext` (Application Config)
```bash
# Telegram
TELEGRAM_API_TOKEN=8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08
TELEGRAM_BOT_NAME=agi_superbot
MASTER_CHAT_IDS=46808774
TELEGRAM_WEBHOOK_SECRET=your_secret_here

# Claude API (FIX THIS!)
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY_HERE

# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=server_agent
DB_USER=agent
DB_PASSWORD=your_password

# App Settings
ENV=production
LOG_LEVEL=INFO
```

### `.env.postgres.vnext` (Database Config)
```bash
POSTGRES_USER=agent
POSTGRES_PASSWORD=your_password
POSTGRES_DB=server_agent
```

---

## Quick Health Check Script

Save as `check_health.sh`:
```bash
#!/bin/bash
echo "=== SERVER AGENT VNEXT HEALTH CHECK ==="
echo ""
echo "Containers:"
docker ps --filter "name=server_agent_vnext" --format "{{.Names}}: {{.Status}}"
echo ""
echo "Health endpoint:"
curl -s http://localhost:8000/health | jq '.'
echo ""
echo "Database:"
docker exec server_agent_vnext_postgres \
  psql -U agent -d server_agent -c "SELECT COUNT(*) FROM threads" -t
echo "threads in database"
echo ""
echo "Recent logs:"
docker logs server_agent_vnext_app --tail 5
```

---

## Monitoring URLs (After HTTPS Setup)

- **Application:** https://server-agent.intelligency.studio/
- **Health Check:** https://server-agent.intelligency.studio/health
- **Stats:** https://server-agent.intelligency.studio/stats
- **Webhook:** https://server-agent.intelligency.studio/webhook/telegram

---

## Support Resources

| Resource | Location |
|----------|----------|
| Complete deployment guide | `docs/DEPLOYMENT_PIPELINE.md` |
| Quick start | `DEPLOYMENT_QUICK_START.md` |
| Completion report | `DEPLOYMENT_COMPLETION_REPORT.md` |
| Architecture | `ARCHITECTURE.md` |
| Phase summaries | `PHASE_*_SUMMARY.md` |
| Scripts documentation | `scripts/README.md` |

---

## Priority Order

**DO THIS FIRST:**
1. ✅ Fix Claude API key (10 min) - ENABLES AI FUNCTIONALITY
2. ✅ Test basic AI operation (5 min)
3. ✅ Set up domain + HTTPS (1-2 hours) - ENABLES TELEGRAM
4. ✅ Configure webhook (5 min)
5. ✅ End-to-end test with Telegram (10 min)

**DO THIS NEXT:**
- Enable MinIO storage (optional, 30 min)
- Set up monitoring alerts (1 hour)
- Configure backup automation (30 min)
- Security hardening (1-2 hours)

---

## Success Criteria

System is fully operational when:
- ✅ Containers healthy
- ✅ Health endpoint returns 200
- ✅ Database accessible
- ✅ Claude API calls succeed
- ✅ Telegram webhook receives messages
- ✅ Master can send commands
- ✅ Approvals are processed
- ✅ Proactive cycles run autonomously

---

**Last Updated:** 2024-12-18
**Next Review:** After fixing both critical issues
