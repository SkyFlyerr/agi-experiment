# GitHub Secrets Setup Guide

This guide explains how to configure GitHub Secrets for automatic deployment to your VPS server.

## Required Secrets

Go to your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**

### Server Access

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `VPS_HOST` | Server IP address or hostname | `92.246.136.186` |
| `VPS_SSH_PORT` | SSH port (default 22) | `58504` |
| `VPS_USER` | SSH username | `root` |
| `VPS_SSH_KEY` | Private SSH key (Ed25519 recommended) | Contents of `~/.ssh/id_ed25519` |

### Container Host Access

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `CONTAINER_HOST_KEY` | SSH key for container to access host | Private key for internal SSH access |

### Database

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://agent:password@postgres:5432/server_agent` |
| `POSTGRES_USER` | PostgreSQL username | `agent` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `your-secure-password` |
| `POSTGRES_DB` | Database name | `server_agent` |

### Telegram Bot

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `TELEGRAM_API_TOKEN` | Bot token from @BotFather | `8461713456:AAE...` |
| `TELEGRAM_BOT_NAME` | Bot username | `agi_superbot` |
| `MASTER_TELEGRAM_CHAT_IDS` | Your Telegram user ID(s) | `46808774` |

### AI Services

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude CLI OAuth token | `oauth-token-...` |

## Step-by-Step Setup

### 1. Generate SSH Key for Deployment

```bash
# Generate new Ed25519 key for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key -N ""

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy_key.pub -p 58504 root@your-server-ip

# Get private key content for GitHub secret
cat ~/.ssh/github_deploy_key
```

### 2. Generate Container Host Key

This key allows the agent container to SSH back to the host for creating other containers:

```bash
# On your server
ssh-keygen -t ed25519 -C "container-to-host" -f /opt/server-agent/secrets/host_key -N ""

# Add public key to authorized_keys
cat /opt/server-agent/secrets/host_key.pub >> ~/.ssh/authorized_keys

# Copy private key content for GitHub secret
cat /opt/server-agent/secrets/host_key
```

### 3. Add Secrets to GitHub

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret from the table above

### 4. Create Production Environment (Optional)

For additional protection:

1. Go to **Settings** → **Environments**
2. Click **New environment** → Name it `production`
3. Enable **Required reviewers** if you want manual approval before deploys
4. Add environment-specific secrets if needed

## Workflow Triggers

The deployment workflow triggers on:

- **Push to main/master**: Automatic deployment
- **Manual trigger**: Go to Actions → Deploy to VPS → Run workflow

## Verifying Setup

After adding all secrets:

1. Make a small commit to main branch
2. Go to **Actions** tab
3. Watch the "Deploy to VPS" workflow
4. Check Telegram for deployment notification

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH connection locally
ssh -i ~/.ssh/github_deploy_key -p 58504 root@your-server-ip "echo 'SSH works!'"
```

### Permission Denied

Ensure the private key in `VPS_SSH_KEY` secret:
- Starts with `-----BEGIN OPENSSH PRIVATE KEY-----`
- Ends with `-----END OPENSSH PRIVATE KEY-----`
- Has no extra whitespace

### Docker Build Failed

Check the Dockerfile and ensure all dependencies are available.

### Health Check Failed

The agent may take time to start. Check logs:

```bash
ssh -p 58504 root@your-server-ip "docker compose -f /opt/server-agent/docker-compose-vnext.yml logs --tail=100"
```

## Security Notes

1. **Never commit secrets** - All sensitive data must be in GitHub Secrets
2. **Rotate keys regularly** - Update SSH keys and API tokens periodically
3. **Use environment protection** - Enable required reviewers for production
4. **Limit secret access** - Only repository admins should manage secrets
5. **Audit access logs** - Monitor who accesses your repository settings
