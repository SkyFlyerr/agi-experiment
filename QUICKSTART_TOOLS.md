# Quick Start: Enhanced Tool System

## What Changed?

Your AGI agent now has **real tools** instead of just text generation:

### Before (Claude CLI mode)
```
Agent: [thinks] "I should check the config file"
Agent: [generates text] "Let me read app/config.py..."
Agent: [can't actually read it] ❌
```

### After (Tool System)
```
Agent: [thinks] "I should check the config file"
Agent: [uses read_file tool] ✅
Agent: [actually reads the file] ✅
Agent: [continues with real information] ✅
```

## Quick Setup

### 1. Run Database Migration

```bash
cd /Users/maksimbozhko/Development/server-agent

# Apply new tables (agent_memory, tool_approvals)
docker compose exec postgres psql -U agent -d server_agent -f /migrations/008_tool_system.sql
```

### 2. Update Dependencies

Add Anthropic SDK to requirements:

```bash
# Already in requirements-vnext.txt:
anthropic>=0.21.0
```

Install:
```bash
docker compose exec server-agent-vnext pip install -r requirements-vnext.txt
```

### 3. Enable Enhanced Scheduler

Option A: **Keep current scheduler, add tools to reactive worker**
```python
# No changes needed - tools available but not in proactive cycle
```

Option B: **Switch to enhanced proactive scheduler** (recommended)
```python
# In app/main.py, replace:
from app.workers import get_scheduler

# With:
from app.workers.proactive_tools import get_tools_scheduler as get_scheduler
```

### 4. Restart Service

```bash
docker compose restart server-agent-vnext
```

## Testing It Out

### Test 1: Tool Registry

```bash
docker compose exec server-agent-vnext python3 << 'EOF'
from app.tools.registry import get_tool_registry

registry = get_tool_registry()
tools = registry.get_all_tools()

print(f"✅ Registered {len(tools)} tools:")
for tool in tools:
    print(f"  - {tool.name} ({tool.safety_level.value})")
EOF
```

Expected output:
```
✅ Registered 9 tools:
  - read_file (safe)
  - write_file (requires_approval)
  - list_directory (safe)
  - run_bash (requires_approval)
  - search_code (safe)
  - send_telegram_message (safe)
  - http_request (requires_approval)
  - remember (safe)
  - recall (safe)
```

### Test 2: Tool Execution

```bash
docker compose exec server-agent-vnext python3 << 'EOF'
import asyncio
from app.tools.registry import get_tool_registry

async def test():
    registry = get_tool_registry()

    # Test safe tool (auto-approved)
    result = await registry.execute_tool("read_file", {
        "path": "/app/config.py"
    })

    if result["status"] == "success":
        print("✅ read_file works!")
        print(f"   Read {len(result['result'])} bytes")
    else:
        print(f"❌ Error: {result['error']}")

asyncio.run(test())
EOF
```

### Test 3: Approval Flow

Send a test Telegram message to trigger approval:

1. Message your bot: `@agi_superbot test tools`
2. Bot receives message → triggers reactive worker
3. Worker can use tools during execution
4. Check logs:

```bash
docker compose logs -f server-agent-vnext | grep "tool"
```

## Using Tools in Practice

### Example 1: Agent Explores Codebase

When proactive cycle runs with tools enabled:

```
Agent cycle starts →
  Claude: "Let me understand the project structure"
  [uses list_directory on /app]
  Claude: "I see ai/, db/, telegram/, workers/ directories"
  [uses read_file on /app/main.py]
  Claude: "This is a FastAPI application with..."
  [stores insight using remember]
  Claude: "I'll remember this structure for future reference"
```

### Example 2: Agent Needs Approval

```
Agent: "I want to create a log file for my observations"
[uses write_file] → REQUIRES APPROVAL

You receive Telegram notification:
🔐 Tool Approval Required

Tool: write_file
Request ID: abc-123-def
Reasoning: Creating a log file to track daily insights

Input:
{
  "path": "/tmp/agent_observations.log",
  "content": "Day 1: Discovered..."
}

To approve: /approve abc-123-def
To reject: /reject abc-123-def

Your response: /approve abc-123-def

Agent: [writes file] ✅
Agent: "Thank you! File created successfully."
```

### Example 3: Agent Remembers Skills

```
Agent learns something new:
  [uses remember tool]
  Key: "python_async_patterns"
  Value: "In this codebase, async functions use asyncio.create_task() for background work"
  Category: "skill"

Later, agent recalls:
  [uses recall tool]
  Key: "python_async_patterns"
  → Gets the stored knowledge back
```

## Telegram Commands

### Approval Management

```
/approve <request_id>  - Approve pending tool request
/reject <request_id>   - Reject pending tool request
/pending               - List pending approvals (TODO: implement)
```

### Memory Management (TODO)

```
/memory list           - List agent's memories
/memory get <key>      - Get specific memory
/memory clear <key>    - Clear specific memory
```

## Monitoring

### Watch Tool Usage

```bash
# Real-time logs
docker compose logs -f server-agent-vnext | grep -E "tool|Tool"

# Tool executions
docker compose exec postgres psql -U agent -d server_agent -c "
  SELECT tool_name, status, created_at
  FROM tool_approvals
  ORDER BY created_at DESC
  LIMIT 10;
"

# Agent memories
docker compose exec postgres psql -U agent -d server_agent -c "
  SELECT key, category, created_at
  FROM agent_memory
  ORDER BY created_at DESC
  LIMIT 10;
"
```

### Check Budget Usage

Tools consume tokens! Monitor usage:

```bash
docker compose exec postgres psql -U agent -d server_agent -c "
  SELECT
    scope,
    SUM(tokens_total) as total_tokens,
    COUNT(*) as calls
  FROM token_ledger
  WHERE created_at >= CURRENT_DATE
  GROUP BY scope;
"
```

## Safety Boundaries

### What's Auto-Approved?

✅ **Safe operations:**
- Read files (`read_file`)
- List directories (`list_directory`)
- Search code (`search_code`)
- Send Telegram messages (`send_telegram_message`)
- Store/recall memories (`remember`, `recall`)
- Safe bash commands (`ls`, `cat`, `grep`, `pwd`, etc.)
- GET HTTP requests

### What Requires Approval?

⚠️ **Sensitive operations:**
- Write/modify files (`write_file`)
- Potentially destructive bash commands
- POST/PUT HTTP requests
- Any operation modifying state

### What's Blocked?

🚫 **Never allowed:**
- Destructive commands (`rm -rf`, `dd if=`, `mkfs`, `shutdown`, etc.)
- Operations on sensitive files (`/etc/passwd`, `/etc/shadow`, `~/.ssh/id_rsa`, etc.)
- System manipulation

## Troubleshooting

### Tools not executing

**Check logs:**
```bash
docker compose logs server-agent-vnext | tail -100
```

**Common issues:**
- Database migration not run → Tables missing
- Anthropic SDK not installed → Import errors
- Wrong scheduler → Tools not available in proactive cycle

### Approval notifications not received

**Check Telegram bot:**
```bash
curl http://localhost:8000/health
```

**Verify settings:**
```bash
docker compose exec server-agent-vnext python3 << 'EOF'
from app.config import settings
print(f"Master chat IDs: {settings.master_chat_ids_list}")
print(f"Bot token: {settings.TELEGRAM_BOT_TOKEN[:20]}...")
EOF
```

### Agent not using tools autonomously

**Verify enhanced scheduler enabled:**
```bash
docker compose exec server-agent-vnext python3 << 'EOF'
from app.workers.proactive_tools import get_tools_scheduler
scheduler = get_tools_scheduler()
print(f"✅ Enhanced scheduler: {type(scheduler).__name__}")
EOF
```

Should output: `ProactiveToolsScheduler`

## Next Steps

1. **Monitor first few cycles** - Watch how agent explores
2. **Respond to approvals** - Build trust by approving safe requests
3. **Check agent memories** - See what insights are being stored
4. **Adjust intervals** - Tune `PROACTIVE_MIN/MAX_INTERVAL_SECONDS` if needed
5. **Add custom tools** - Extend with project-specific capabilities

## Documentation

- [TOOL_SYSTEM.md](docs/TOOL_SYSTEM.md) - Complete tool system documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall system architecture
- [CLAUDE.md](CLAUDE.md) - Agent philosophy and guidelines

## Support

If you encounter issues:
1. Check logs: `docker compose logs -f server-agent-vnext`
2. Verify database: `docker compose exec postgres psql -U agent -d server_agent`
3. Test tools manually using examples above
4. Review [TOOL_SYSTEM.md](docs/TOOL_SYSTEM.md) for detailed troubleshooting

---

**Remember:** The agent is now truly autonomous with real capabilities. Monitor closely initially, then gradually increase trust as you observe responsible behavior.

**Philosophy:** "Atmano moksartha jagat hitaya ca" - The agent is designed to learn (self-realization) while serving (world benefit). Tools enable both.
