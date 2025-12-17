#!/bin/bash
# Server Agent vNext - Docker Entrypoint Script
# Configures Claude CLI with OAuth token and starts the application

set -e

echo "[Entrypoint] Starting Server Agent vNext..."

# Configure Claude CLI with OAuth token if provided
if [ -n "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
    echo "[Entrypoint] Configuring Claude CLI with OAuth token..."
    mkdir -p /home/agent/.claude
    echo "$CLAUDE_CODE_OAUTH_TOKEN" > /home/agent/.claude/token
    chmod 600 /home/agent/.claude/token
    echo "[Entrypoint] Claude CLI configured successfully"
else
    echo "[Entrypoint] Warning: CLAUDE_CODE_OAUTH_TOKEN not set, Claude CLI will not work"
fi

# Execute the main command (passed as arguments)
echo "[Entrypoint] Starting application: $@"
exec "$@"
