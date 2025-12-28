#!/bin/bash
# Setup SSH key for Atman container to access host system
# Run this script on the SERVER as root

set -e

PROJECT_DIR="/root/server-agent"
SECRETS_DIR="$PROJECT_DIR/secrets"
KEY_FILE="$SECRETS_DIR/host_key"

echo "=== Setting up SSH access for Atman container ==="

# Create secrets directory
echo "1. Creating secrets directory..."
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Generate SSH key if not exists
if [ -f "$KEY_FILE" ]; then
    echo "2. SSH key already exists at $KEY_FILE"
else
    echo "2. Generating new SSH key..."
    ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "atman-container"
    echo "   Key generated successfully"
fi

# Set proper permissions (UID 1000 = agent user inside container)
chown 1000:1000 "$KEY_FILE"
chmod 600 "$KEY_FILE"
chmod 644 "$KEY_FILE.pub"

# Add to authorized_keys if not already
echo "3. Adding public key to authorized_keys..."
if grep -q "atman-container" /root/.ssh/authorized_keys 2>/dev/null; then
    echo "   Key already in authorized_keys"
else
    cat "$KEY_FILE.pub" >> /root/.ssh/authorized_keys
    echo "   Key added to authorized_keys"
fi

# Ensure SSH server is running
echo "4. Checking SSH server..."
if systemctl is-active --quiet sshd; then
    echo "   SSH server is running"
else
    echo "   Starting SSH server..."
    systemctl start sshd
    systemctl enable sshd
fi

# Test connection (optional)
echo "5. Testing SSH connection..."
if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@127.0.0.1 "echo 'SSH test successful'" 2>/dev/null; then
    echo "   SSH connection works!"
else
    echo "   WARNING: SSH test failed. Check SSH configuration."
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "1. Restart the container: docker compose -f docker-compose-vnext.yml restart app"
echo "2. From inside container, Atman can now run:"
echo '   ssh -i /app/secrets/host_key -o StrictHostKeyChecking=no root@host.docker.internal "command"'
echo ""
