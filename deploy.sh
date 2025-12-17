#!/bin/bash

# Server-Agent Deployment Script
# Run this from a machine that can access the VPS

set -e  # Exit on error

SERVER_IP="92.246.136.186"
SERVER_PORT="58504"
SERVER_USER="root"
# SSH key path on the local machine
SSH_KEY_PATH="/Users/maksimbozhko/.ssh/frankfurt2_ed25519"
DEPLOY_DIR="/opt/server-agent"

echo "🤖 Server-Agent Deployment to $SERVER_IP"
echo "==========================================="
echo ""

# We deploy with SSH key auth.
USE_SSHPASS=false

# Function to run SSH command
run_ssh() {
    ssh \
        -i "$SSH_KEY_PATH" \
        -p "$SERVER_PORT" \
        -o StrictHostKeyChecking=no \
        -o IdentitiesOnly=yes \
        "$SERVER_USER@$SERVER_IP" "$@"
}

# Function to run rsync
run_rsync() {
    rsync -avz --exclude 'venv' --exclude 'data' --exclude 'logs' --exclude '.git' \
        --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' \
        -e "ssh -i $SSH_KEY_PATH -p $SERVER_PORT -o StrictHostKeyChecking=no -o IdentitiesOnly=yes" \
        "$@"
}

echo "Step 1: Creating deployment directory..."
run_ssh "mkdir -p $DEPLOY_DIR"
echo "✅ Directory created"

echo ""
echo "Step 2: Syncing files to server..."
run_rsync ./ "$SERVER_USER@$SERVER_IP:$DEPLOY_DIR/"
echo "✅ Files synced"

echo ""
echo "Step 3: Setting up Python environment..."
run_ssh "cd $DEPLOY_DIR && python3 -m venv venv"
echo "✅ Virtual environment created"

echo ""
echo "Step 4: Installing dependencies..."
run_ssh "cd $DEPLOY_DIR && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
echo "✅ Dependencies installed"

echo ""
echo "Step 5: Creating data directories..."
run_ssh "cd $DEPLOY_DIR && mkdir -p data/history data/skills logs"
echo "✅ Directories created"

echo ""
echo "Step 6: Setting up systemd service..."
run_ssh "cp $DEPLOY_DIR/systemd/server-agent.service /etc/systemd/system/"
run_ssh "systemctl daemon-reload"
echo "✅ Systemd service configured"

echo ""
echo "Step 7: Enabling and restarting service..."
run_ssh "systemctl enable server-agent"
run_ssh "systemctl restart server-agent"
echo "✅ Service restarted"

echo ""
echo "Step 8: Checking service status..."
run_ssh "systemctl status server-agent --no-pager" || true

echo ""
echo "Step 9: Checking logs..."
sleep 3
run_ssh "tail -20 $DEPLOY_DIR/logs/agent.log" || echo "No logs yet (service may still be starting)"

echo ""
echo "==========================================="
echo "✅ Deployment complete!"
echo ""
echo "The agent should send you a Telegram message shortly."
echo ""
echo "To monitor:"
echo "  ssh root@$SERVER_IP"
echo "  journalctl -u server-agent -f"
echo "  tail -f /opt/server-agent/logs/agent.log"
echo ""
echo "To check status:"
echo "  systemctl status server-agent"
echo ""
echo "Telegram bot: @agi_superbot"
echo "Commands: /start, /status, /help"
echo "==========================================="
