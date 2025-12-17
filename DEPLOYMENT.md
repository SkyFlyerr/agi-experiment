# Deployment Guide

## Quick Deployment to VPS

### Prerequisites

- VPS running Ubuntu (Frankfurt2 server: 92.246.136.186)
- SSH access with root privileges
- Python 3.9+ installed on server
- Telegram bot token and Anthropic API key

### Step 1: Prepare Local Environment

```bash
# Ensure .env is configured with production values
cp .env.example .env
nano .env

# Add ANTHROPIC_API_KEY to .env
# Verify all credentials are correct
```

### Step 2: Copy Files to Server

```bash
# From local machine, sync files to server
# (Using SSH multiplexing to prevent fail2ban blocking)

rsync -avz --exclude 'venv' --exclude 'data' --exclude 'logs' --exclude '.git' \
  --exclude '__pycache__' --exclude '*.pyc' \
  ./ root@92.246.136.186:/opt/server-agent/

# Verify files copied
ssh root@92.246.136.186 'ls -la /opt/server-agent/'
```

### Step 3: Setup on Server

```bash
# SSH to server
ssh root@92.246.136.186

# Navigate to project
cd /opt/server-agent

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create data and log directories
mkdir -p data/history data/skills logs

# Verify installation
python3 -c "import telegram, anthropic, dotenv; print('✅ All packages installed')"
```

### Step 4: Configure Environment

```bash
# Edit .env file on server
nano .env

# Ensure these are set:
# TELEGRAM_API_TOKEN=8461713456:AAEb7IRQdpTxdlIuUxfFKJ0OHM1BRu30A08
# TELEGRAM_BOT_NAME=agi_superbot
# MASTER_MAX_TELEGRAM_CHAT_ID=46808774
# ANTHROPIC_API_KEY=your_actual_key_here
# ENV=production

# Test configuration
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Token:', os.getenv('TELEGRAM_API_TOKEN')[:20]+'...')"
```

### Step 5: Test Run

```bash
# Test the agent manually first
cd /opt/server-agent
source venv/bin/activate
python src/main.py

# You should receive a Telegram message: "🤖 Server-Agent Online"
# Test commands: /status, /help

# Stop with Ctrl+C
```

### Step 6: Setup Systemd Service

```bash
# Copy systemd service file
cp systemd/server-agent.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable service to start on boot
systemctl enable server-agent

# Start the service
systemctl start server-agent

# Check status
systemctl status server-agent

# View logs
journalctl -u server-agent -f
```

### Step 7: Verify Operation

```bash
# Check if service is running
systemctl status server-agent

# View application logs
tail -f /opt/server-agent/logs/agent.log

# Check Telegram bot
# Send /status to @agi_superbot
```

## Monitoring

### Check Service Status

```bash
# Service status
systemctl status server-agent

# View recent logs
journalctl -u server-agent -n 50

# Follow logs in real-time
journalctl -u server-agent -f

# Application logs
tail -f /opt/server-agent/logs/agent.log
```

### Check Agent State

```bash
# View current context
cat /opt/server-agent/data/context.json | python3 -m json.tool

# View today's action history
cat /opt/server-agent/data/history/$(date +%Y-%m-%d).jsonl

# Check learned skills
ls -la /opt/server-agent/data/skills/
```

## Maintenance

### Update Code

```bash
# From local machine, sync updated code
rsync -avz --exclude 'venv' --exclude 'data' --exclude 'logs' \
  ./ root@92.246.136.186:/opt/server-agent/

# On server, restart service
ssh root@92.246.136.186 'systemctl restart server-agent'

# Verify restart
ssh root@92.246.136.186 'systemctl status server-agent'
```

### Restart Service

```bash
# Restart
systemctl restart server-agent

# Stop
systemctl stop server-agent

# Start
systemctl start server-agent
```

### Backup Data

```bash
# On server, backup data directory
cd /opt/server-agent
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Copy backup to local machine
rsync -avz root@92.246.136.186:/opt/server-agent/backup-*.tar.gz ./backups/
```

### View Logs

```bash
# Systemd logs
journalctl -u server-agent -n 100

# Application logs
tail -100 /opt/server-agent/logs/agent.log

# Error logs
tail -100 /opt/server-agent/logs/systemd-error.log
```

## Troubleshooting

### Service won't start

```bash
# Check service status
systemctl status server-agent

# Check logs for errors
journalctl -u server-agent -n 50

# Test manually
cd /opt/server-agent
source venv/bin/activate
python src/main.py
```

### Telegram bot not responding

```bash
# Verify bot token
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TELEGRAM_API_TOKEN'))"

# Test bot manually
cd /opt/server-agent
source venv/bin/activate
python src/telegram_bot.py
```

### High CPU/Memory usage

```bash
# Check resource usage
top
htop

# Increase delay between cycles
# Edit .env: MIN_DELAY_MINUTES=10
systemctl restart server-agent
```

### Token limit exceeded

```bash
# Check current token usage
cat data/context.json | grep token_usage_24h

# Increase daily limit or reduce cycle frequency
# Edit .env: DAILY_TOKEN_LIMIT=150000
systemctl restart server-agent
```

## Security

### Rotate Credentials

```bash
# Edit .env with new credentials
nano /opt/server-agent/.env

# Restart service
systemctl restart server-agent
```

### Update Dependencies

```bash
cd /opt/server-agent
source venv/bin/activate
pip install --upgrade -r requirements.txt
systemctl restart server-agent
```

### File Permissions

```bash
# Ensure .env is secure
chmod 600 /opt/server-agent/.env

# Ensure data directory is private
chmod 700 /opt/server-agent/data
```

## Scaling

### Increase Resources

If the agent needs more resources:

```bash
# Check current usage
df -h
free -h
top

# Upgrade VPS plan if needed
# Update CLAUDE.md with new specs
```

### Multiple Instances

To run multiple specialized agents:

```bash
# Create separate directories
mkdir /opt/server-agent-{skill-developer,task-executor}

# Copy code and configure different .env files
# Create separate systemd services
# Coordinate via shared Supabase or messaging
```

## Monitoring Dashboard (Future)

The Web UI will provide:
- Real-time chain of thought
- Live metrics dashboard
- Action history viewer
- Skill management interface

Access at: `http://92.246.136.186:8080` (when implemented)

## Auto-Deployment Script

Create `deploy.sh` for one-command deployment:

```bash
#!/bin/bash
# Quick deployment script

echo "Deploying Server-Agent to production..."

# Sync files
rsync -avz --exclude 'venv' --exclude 'data' --exclude 'logs' \
  ./ root@92.246.136.186:/opt/server-agent/

# Restart service
ssh root@92.246.136.186 'systemctl restart server-agent'

# Check status
ssh root@92.246.136.186 'systemctl status server-agent'

echo "Deployment complete!"
```

## Production Checklist

Before going live:

- [ ] .env configured with production credentials
- [ ] ANTHROPIC_API_KEY is valid and has credits
- [ ] Telegram bot token is correct
- [ ] Master chat ID is correct
- [ ] Systemd service is enabled
- [ ] Service starts successfully
- [ ] Telegram bot responds to /start
- [ ] First proactivity cycle completes
- [ ] Logs are being written
- [ ] Data is being persisted
- [ ] Backup system is in place
- [ ] Monitoring is configured

## Next Steps After Deployment

1. **Monitor first 24 hours**
   - Watch logs continuously
   - Check token usage
   - Verify autonomous decisions
   - Test Master intervention

2. **Gradual autonomy increase**
   - Start with longer delays (30+ min)
   - Gradually decrease as confidence builds
   - Monitor decision quality

3. **Skill development**
   - Assign learning tasks
   - Review learned skills
   - Guide skill priorities

4. **Revenue experiments**
   - Research earning opportunities
   - Test small revenue tasks
   - Track earnings accurately

5. **Web UI deployment**
   - Implement FastAPI backend
   - Deploy React frontend
   - Configure reverse proxy (nginx)
   - Enable HTTPS with Let's Encrypt
