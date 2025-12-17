# Quick Start Guide - Phase 2: Telegram Webhook Ingestion

This guide will get your Telegram webhook ingestion running in 5 minutes.

## Prerequisites

- Python 3.10+
- PostgreSQL database (Phase 1 must be complete)
- Telegram bot token (from @BotFather)
- Public HTTPS URL for webhook (ngrok, production server, etc.)

## Step 1: Install Dependencies

```bash
cd /Users/maksimbozhko/Development/server-agent
pip install -r requirements.txt
```

**Installed packages:**
- aiogram 3.15.0 (Telegram bot framework)
- asyncpg 0.30.0 (async PostgreSQL driver)
- fastapi 0.115.6 (web framework)
- pytest 8.3.4 (testing)

## Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values
nano .env
```

**Required settings:**

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08
TELEGRAM_WEBHOOK_URL=https://your-domain.com  # Or ngrok URL
TELEGRAM_WEBHOOK_SECRET=your_random_secret_here
MASTER_CHAT_IDS=46808774

# Database
DATABASE_URL=postgresql://agent:agent_password@postgres:5432/server_agent
```

**Generate webhook secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 3: Verify Database Schema

Ensure Phase 1 database tables exist:

```bash
# Connect to database
psql $DATABASE_URL

# Check tables exist
\dt

# Should show:
#  chat_threads
#  chat_messages
#  message_artifacts
#  reactive_jobs
#  approvals
#  token_ledger
#  deployments
```

If tables don't exist, run Phase 1 migrations first.

## Step 4: Run Tests (Optional)

```bash
# Run all Telegram tests
pytest tests/test_telegram.py -v

# Run specific test
pytest tests/test_telegram.py::test_normalize_text_message -v
```

**Expected output:**
```
tests/test_telegram.py::test_normalize_text_message PASSED
tests/test_telegram.py::test_normalize_voice_message PASSED
tests/test_telegram.py::test_normalize_photo_message PASSED
...
========== 12 passed in 2.45s ==========
```

## Step 5: Start the Server

```bash
# Development mode
python -m app.main

# Or with uvicorn (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Server startup logs:**
```
INFO - Starting Server Agent vNext...
INFO - Database pool created (min_size=2, max_size=10)
INFO - Database connected
INFO - Bot initialized successfully
INFO - Webhook set successfully:
INFO -   URL: https://your-domain.com/webhook/telegram
INFO -   Pending updates: 0
INFO -   Max connections: 40
INFO - Telegram bot initialized
INFO - Server Agent vNext fully operational
INFO - Application startup complete.
INFO - Uvicorn running on http://0.0.0.0:8000
```

## Step 6: Verify Webhook Setup

### Check Webhook Info (via Telegram API)

```bash
# Get webhook info
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

**Expected response:**
```json
{
  "ok": true,
  "result": {
    "url": "https://your-domain.com/webhook/telegram",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40
  }
}
```

### Check Health Endpoint

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "telegram": "initialized"
}
```

### Check Webhook Health

```bash
curl http://localhost:8000/webhook/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "service": "webhook",
  "endpoints": ["telegram"]
}
```

## Step 7: Test the Bot

### Send Test Message (Admin Endpoint)

```bash
curl -X POST "http://localhost:8000/admin/test-telegram?chat_id=46808774&text=Hello%20from%20Server%20Agent%21"
```

**Expected response:**
```json
{
  "status": "success",
  "message_id": "12345"
}
```

You should receive the message in Telegram!

### Send Message to Bot

Open Telegram and send a message to your bot:

```
You: Hello, bot!
```

**Server logs:**
```
INFO - Webhook received: update_id=123456789, has_message=True, has_callback=False
INFO - Thread abc-123-def for chat 46808774
INFO - Message xyz-456-abc inserted (platform_id: 789)
INFO - Reactive job ghi-789-jkl enqueued for message xyz-456-abc
```

**Database verification:**
```sql
-- Check message was stored
SELECT * FROM chat_messages ORDER BY created_at DESC LIMIT 1;

-- Check reactive job was enqueued
SELECT * FROM reactive_jobs ORDER BY created_at DESC LIMIT 1;
```

## Step 8: Test Voice Message

Send a voice message to your bot:

```
You: 🎤 (voice note)
```

**Server logs:**
```
INFO - Webhook received: update_id=123456790, has_message=True, has_callback=False
INFO - Message xyz-457-def inserted (platform_id: 790)
INFO - Downloaded voice to /tmp/server-agent-media/uuid_voice.ogg (size: 12345 bytes)
INFO - Artifact created for message xyz-457-def (type: voice, kind: voice_transcript)
INFO - Reactive job enqueued
```

**Verify media download:**
```bash
ls -lh /tmp/server-agent-media/
```

## Troubleshooting

### Issue: Webhook not receiving updates

**Solution 1: Check webhook URL is publicly accessible**
```bash
curl https://your-domain.com/webhook/telegram
```

**Solution 2: Delete and reset webhook**
```bash
# Delete webhook
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"

# Restart server (webhook will be set automatically)
python -m app.main
```

### Issue: Database connection errors

**Check DATABASE_URL:**
```bash
echo $DATABASE_URL
psql $DATABASE_URL -c "SELECT 1"
```

**Check database pool:**
```bash
# View server logs for connection errors
# Look for: "Failed to create database pool"
```

### Issue: Media downloads failing

**Check directory permissions:**
```bash
mkdir -p /tmp/server-agent-media
chmod 755 /tmp/server-agent-media
ls -ld /tmp/server-agent-media
```

**Check bot token has file access:**
```bash
# Send test file to bot, then try to download
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getFile?file_id=<file_id>"
```

### Issue: Secret token mismatch

**Check secret in logs:**
```bash
# Server logs will show:
# WARNING - Webhook secret mismatch: expected=..., got=...
```

**Regenerate and update secret:**
```bash
# Generate new secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update .env file
# Restart server
```

## Development Workflow

### 1. Make Changes to Telegram Module

```bash
# Edit files in app/telegram/
nano app/telegram/normalizer.py
```

### 2. Run Tests

```bash
pytest tests/test_telegram.py -v
```

### 3. Test Locally

```bash
# Use ngrok for local testing
ngrok http 8000

# Update TELEGRAM_WEBHOOK_URL in .env
TELEGRAM_WEBHOOK_URL=https://abc123.ngrok.io

# Restart server
python -m app.main
```

### 4. Check Logs

```bash
# Watch logs in real-time
tail -f logs/server-agent.log

# Or run with verbose logging
LOG_LEVEL=DEBUG python -m app.main
```

## Next Steps: Phase 3 Integration

Once Phase 2 is working, you're ready for Phase 3: Reactive Worker.

**Phase 3 will:**
- Poll for pending jobs (created by Phase 2)
- Process messages in classify mode (Haiku)
- Execute actions in execute mode (Claude Code)
- Send responses via `app.telegram.send_message()`
- Update job status

**Integration points are ready:**
- ✅ Messages persisted with thread_id
- ✅ Jobs enqueued with mode=classify
- ✅ Media artifacts created with status=pending
- ✅ Approval callbacks handled

## Useful Commands

```bash
# Verify Phase 2 implementation
./verify_phase2.sh

# Run specific test
pytest tests/test_telegram.py::test_webhook_endpoint_success -v

# Check database messages
psql $DATABASE_URL -c "SELECT COUNT(*) FROM chat_messages"

# Check reactive jobs
psql $DATABASE_URL -c "SELECT status, COUNT(*) FROM reactive_jobs GROUP BY status"

# View webhook info
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | jq

# Check server health
curl http://localhost:8000/health | jq

# Send test message
curl -X POST "http://localhost:8000/admin/test-telegram?chat_id=46808774&text=Test"
```

## Production Deployment

### Using Docker Compose

```yaml
# docker-compose.yml
services:
  server-agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_WEBHOOK_URL=${TELEGRAM_WEBHOOK_URL}
      - TELEGRAM_WEBHOOK_SECRET=${TELEGRAM_WEBHOOK_SECRET}
    volumes:
      - /tmp/server-agent-media:/tmp/server-agent-media
```

### Using Systemd

```ini
# /etc/systemd/system/server-agent.service
[Unit]
Description=Server Agent vNext
After=network.target postgresql.service

[Service]
Type=simple
User=agent
WorkingDirectory=/opt/server-agent
Environment="PATH=/opt/server-agent/venv/bin"
ExecStart=/opt/server-agent/venv/bin/python -m app.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable server-agent
sudo systemctl start server-agent

# Check status
sudo systemctl status server-agent

# View logs
sudo journalctl -u server-agent -f
```

## Support

**Documentation:**
- `/Users/maksimbozhko/Development/server-agent/TELEGRAM_WEBHOOK_IMPLEMENTATION.md` - Full implementation details
- `/Users/maksimbozhko/Development/server-agent/PHASE2_COMPLETION_SUMMARY.md` - Summary and specs

**Logs:**
- Application logs: Check uvicorn output or systemd journal
- Database logs: Check PostgreSQL logs
- Telegram API: Use getWebhookInfo endpoint

**Testing:**
- Run test suite: `pytest tests/test_telegram.py -v`
- Manual testing: Send messages to bot via Telegram
- Admin endpoint: `/admin/test-telegram`

---

**Ready to go!** 🚀

Your Telegram webhook ingestion is now operational. Send a message to your bot and watch it flow through the system!
