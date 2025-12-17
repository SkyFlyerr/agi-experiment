# How to Get Anthropic API Key for Claude Max Subscription

## The Problem

OAuth tokens (`sk-ant-oat01-...`) only work with Claude Code CLI, not with the Anthropic API directly. This is a known limitation:
- [GitHub Issue #5893](https://github.com/anthropics/claude-code/issues/5893)
- [GitHub Issue #5956](https://github.com/anthropics/claude-code/issues/5956)
- [GitHub Issue #6058](https://github.com/anthropics/claude-code/issues/6058)

## The Solution

You need a **regular Anthropic API key** (starts with `sk-ant-api...`) to use the Anthropic API.

### Option 1: Use Your Max Subscription to Create API Credits (Recommended)

Claude Max subscribers can purchase API credits at console.anthropic.com:

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Log in with your Claude Max account
3. Navigate to **API Keys** section
4. Click **Create API Key**
5. Copy the key (starts with `sk-ant-api...`)
6. Add credits to your account if needed

### Option 2: Use Separate API Credits

If you prefer to keep your Max subscription separate from API usage:

1. Create a separate account at [console.anthropic.com](https://console.anthropic.com/)
2. Add payment method
3. Purchase API credits
4. Create an API key

### Option 3: Use Claude Code CLI as Proxy (Complex)

Keep using the OAuth token but run the agent through Claude Code CLI:

**Pros:**
- Uses your Max subscription directly
- No additional API costs

**Cons:**
- Requires Node.js on server
- More complex setup
- CLI overhead
- Less reliable for autonomous operation

## Updating the Server

Once you have an API key:

```bash
# SSH to server
ssh -p 58504 -i ~/.ssh/frankfurt2_ed25519 root@92.246.136.186

# Edit .env file
nano /opt/server-agent/.env

# Change this line:
# ANTHROPIC_API_KEY=sk-ant-oat01-...
# To:
ANTHROPIC_API_KEY=sk-ant-api-YOUR-NEW-KEY-HERE

# Save and exit (Ctrl+X, Y, Enter)

# Restart service
systemctl restart server-agent

# Check logs
tail -f /opt/server-agent/logs/systemd-error.log
```

Within a few seconds, you should see:
```
Claude response received. Tokens used: XXXX
```

And the agent will begin making autonomous decisions!

## Cost Comparison

**Claude Max** ($40-60/month):
- Unlimited conversations in web/mobile apps
- OAuth tokens for Claude Code CLI
- **Cannot** be used for Anthropic API calls

**API Credits**:
- Pay per token (Claude Sonnet ~$3 per million tokens)
- Can be used programmatically
- This agent uses ~100k tokens/day = ~$0.30/day = ~$9/month

**Recommendation:** Get a small amount of API credits ($5-10) to run the agent autonomously. Your Max subscription covers interactive use of Claude Code.

## Current Agent Status

The agent is running and the Telegram bot works! It's just waiting for a valid API key to start making autonomous decisions.

**Working now:**
- ✅ Telegram bot (@agi_superbot)
- ✅ All commands (/status, /task, /help)
- ✅ Manual task assignment
- ✅ State persistence
- ✅ Systemd service

**Waiting for API key:**
- ⏳ Autonomous proactivity loop
- ⏳ Self-directed learning
- ⏳ Skill development

## Questions?

If you prefer to use the OAuth token approach (Option 3), I can implement Claude Code CLI integration, but it will require:
1. Installing Node.js on the server
2. More complex error handling
3. Potential reliability issues

Let me know your preference!
