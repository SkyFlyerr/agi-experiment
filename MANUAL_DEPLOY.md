# Manual Deployment Instructions

## Issue

SSH connection to 92.246.136.186 is being reset during key exchange. This is likely due to:
1. **fail2ban** blocking the IP after multiple connection attempts
2. **Firewall rules** blocking certain IPs
3. **SSH daemon** configuration requiring specific settings

## Solution Options

### Option 1: Deploy from Terminal with Server Access

If you have SSH access from your terminal (not blocked by fail2ban):

```bash
cd /Users/maksimbozhko/Development/server-agent
./deploy.sh
```

The script will:
1. Create /opt/server-agent directory
2. Sync all files
3. Setup Python venv
4. Install dependencies
5. Configure systemd service
6. Start the agent
7. Send you a Telegram message

### Option 2: Check and Fix Firewall/fail2ban

```bash
# SSH to server (from a non-blocked IP or console)
ssh root@92.246.136.186

# Check fail2ban status
fail2ban-client status sshd

# If your IP is banned, unban it
fail2ban-client set sshd unbanip YOUR_IP_HERE

# Check firewall rules
ufw status
iptables -L -n

# If needed, allow your IP
ufw allow from YOUR_IP_HERE to any port 22
```

### Option 3: Use DigitalOcean Console

1. Log into DigitalOcean
2. Access the Frankfurt2 droplet console (web-based terminal)
3. Run these commands:

```bash
# Create deployment directory
mkdir -p /opt/server-agent
cd /opt/server-agent

# You'll need to upload files manually via:
# - DigitalOcean's web file upload
# - Or use git to clone from a repository
# - Or use wget/curl to download a tarball
```

### Option 4: Create Deployment Tarball (Recommended for Now)

Since SSH is blocked, let's create a tarball you can upload via web console:

```bash
# On local machine
cd /Users/maksimbozhko/Development/server-agent
tar -czf server-agent-deploy.tar.gz \
  --exclude='venv' \
  --exclude='data' \
  --exclude='logs' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  .

# This creates: server-agent-deploy.tar.gz
```

Then:
1. Upload `server-agent-deploy.tar.gz` to server via DigitalOcean console or SCP
2. On server, run:

```bash
# Extract
mkdir -p /opt/server-agent
cd /opt/server-agent
tar -xzf ~/server-agent-deploy.tar.gz

# Setup
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p data/history data/skills logs

# Install systemd service
cp systemd/server-agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable server-agent
systemctl start server-agent

# Check status
systemctl status server-agent

# View logs
tail -f logs/agent.log
```

### Option 5: Fix SSH Access First

If you want to properly fix SSH access:

```bash
# From DigitalOcean console or non-blocked IP:

# 1. Check fail2ban
fail2ban-client status sshd
fail2ban-client get sshd banned

# 2. Unban if needed
fail2ban-client set sshd unbanip YOUR_CURRENT_IP

# 3. Check SSH config
cat /etc/ssh/sshd_config | grep -E "PermitRootLogin|PasswordAuthentication"

# 4. Restart SSH if needed
systemctl restart sshd

# 5. Check firewall
ufw status verbose
iptables -L INPUT -n --line-numbers
```

## Quick Deploy Command (If SSH Works)

If you can access SSH:

```bash
cd /Users/maksimbozhko/Development/server-agent && ./deploy.sh
```

## What Happens After Deployment

Once deployed and running, the agent will:

1. **Send Telegram Message**: "🤖 Server-Agent Online" to your Telegram (@agi_superbot)
2. **Start Proactivity Loop**: Begin autonomous decision-making
3. **First Cycle**: Within 5-10 minutes, make first decision
4. **Log Activity**: All actions logged to /opt/server-agent/logs/agent.log

## Verifying Deployment

### Via Telegram
```
Message: @agi_superbot
Commands:
  /start  - Should respond with welcome message
  /status - Shows agent state
  /help   - Shows available commands
```

### Via Server
```bash
# Check service
systemctl status server-agent

# View logs
tail -f /opt/server-agent/logs/agent.log
journalctl -u server-agent -f

# Check state
cat /opt/server-agent/data/context.json | python3 -m json.tool
```

## Troubleshooting

### Service won't start
```bash
journalctl -u server-agent -n 50
```

### No Telegram message
```bash
# Check if bot is running
tail -f /opt/server-agent/logs/agent.log | grep -i telegram

# Test bot manually
cd /opt/server-agent
source venv/bin/activate
python src/telegram_bot.py
```

### Permission errors
```bash
chmod -R 755 /opt/server-agent
chown -R root:root /opt/server-agent
```

## Current Status

**Issue**: SSH connection reset during key exchange
**Likely cause**: fail2ban or firewall blocking connections
**Action needed**: Access server via DigitalOcean console or from non-blocked IP

## Next Steps

1. **Check server access** - Try SSH from terminal or use DigitalOcean console
2. **Run deploy.sh** - If SSH works
3. **Or follow Option 4** - Create tarball and upload manually
4. **Wait for Telegram** - Agent will message you within 5 minutes of starting
