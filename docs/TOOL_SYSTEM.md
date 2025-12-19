# Tool System Documentation

## Overview

The AGI agent now has a comprehensive tool system that allows Claude to autonomously interact with the server environment, read and write files, execute commands, and communicate - all with built-in safety controls and approval workflows.

## Architecture

### Components

1. **Tool Registry** (`app/tools/registry.py`)
   - Central registry of all available tools
   - Tool definitions with input schemas
   - Safety level classification
   - Tool executors (actual implementation)

2. **Claude API Client** (`app/ai/claude_tools.py`)
   - Uses Anthropic Python SDK with native tool support
   - Handles multi-turn tool execution loops
   - Auto-approves safe tools
   - Requests approval for sensitive operations

3. **Approval System** (`app/tools/approval.py`)
   - Manages approval requests for sensitive tools
   - Notifies Master via Telegram
   - Tracks approval status (pending/approved/rejected/expired)
   - Timeout management

4. **Tool Executors** (`app/tools/executor.py`)
   - Safe bash command execution
   - File operations with path validation
   - HTTP API calls
   - Built-in safety checks

5. **Enhanced Proactive Scheduler** (`app/workers/proactive_tools.py`)
   - Uses Claude with tool support
   - Autonomous exploration and learning
   - Dynamic interval adjustment based on token budget

## Available Tools

### File System Tools

#### `read_file`
- **Safety**: SAFE (auto-approved)
- **Purpose**: Read contents of files
- **Input**: `{path: string, encoding?: string}`
- **Use cases**: Examine code, configuration, logs

#### `write_file`
- **Safety**: REQUIRES_APPROVAL
- **Purpose**: Write content to files
- **Input**: `{path: string, content: string, encoding?: string}`
- **Use cases**: Create new files, update configuration

#### `list_directory`
- **Safety**: SAFE (auto-approved)
- **Purpose**: List directory contents
- **Input**: `{path: string, recursive?: boolean}`
- **Use cases**: Explore file structure

### Shell Execution Tools

#### `run_bash`
- **Safety**: REQUIRES_APPROVAL (auto-approved for safe commands)
- **Purpose**: Execute bash commands
- **Input**: `{command: string, timeout?: integer, working_dir?: string}`
- **Safe commands** (auto-approved):
  - `ls`, `cat`, `grep`, `find`, `echo`, `pwd`, `whoami`, `date`, `which`
- **Blocked commands**:
  - `rm -rf`, `dd if=`, `mkfs`, `shutdown`, `reboot`, etc.

#### `search_code`
- **Safety**: SAFE (auto-approved)
- **Purpose**: Search for patterns in code using grep
- **Input**: `{pattern: string, path?: string, file_pattern?: string, case_sensitive?: boolean}`
- **Use cases**: Find function definitions, imports, usage patterns

### Communication Tools

#### `send_telegram_message`
- **Safety**: SAFE (auto-approved)
- **Purpose**: Send message to Master via Telegram
- **Input**: `{text: string, chat_id?: string}`
- **Use cases**: Report results, ask questions, share insights

### API Tools

#### `http_request`
- **Safety**: REQUIRES_APPROVAL (auto-approved for GET requests)
- **Purpose**: Make HTTP API requests
- **Input**: `{url: string, method?: string, payload?: object, headers?: object, timeout?: integer}`
- **Use cases**: Interact with external services, APIs, webhooks

### Memory Tools

#### `remember`
- **Safety**: SAFE (auto-approved)
- **Purpose**: Store information in long-term memory
- **Input**: `{key: string, value: string, category?: string}`
- **Use cases**: Store facts, patterns, insights, skills

#### `recall`
- **Safety**: SAFE (auto-approved)
- **Purpose**: Retrieve information from long-term memory
- **Input**: `{key: string, category?: string}`
- **Use cases**: Access previously stored information

## Safety Levels

### SAFE
- Tools that cannot cause harm
- Auto-approved for execution
- Examples: `read_file`, `list_directory`, `search_code`, `remember`, `recall`

### REQUIRES_APPROVAL
- Tools that modify state or consume resources
- Auto-approved if considered safe (read-only bash commands, GET requests)
- Requires Master approval for risky operations
- Examples: `write_file`, `run_bash` (some commands), `http_request` (POST/PUT)

### DANGEROUS
- Tools that are never auto-approved
- Currently not used (reserved for future highly sensitive operations)

## Approval Workflow

### Flow

1. **Agent requests tool use**
   - Claude decides to use a tool that requires approval
   - Tool input is validated

2. **Approval request created**
   - Request stored in database with unique ID
   - Telegram notification sent to Master
   - Includes: tool name, input, reasoning, request ID

3. **Master responds**
   - Approve: `/approve <request_id>`
   - Reject: `/reject <request_id>`
   - Timeout: Request expires after configured timeout (default: 1 hour)

4. **Tool execution**
   - If approved: Tool executes, result returned to Claude
   - If rejected: Error returned to Claude
   - If expired: Error returned

### Database Schema

```sql
CREATE TABLE tool_approvals (
    request_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    tool_input JSONB NOT NULL,
    reasoning TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    responded_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    response TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE agent_memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);
```

## Usage Examples

### Autonomous Exploration

The agent can now autonomously explore the codebase:

```python
# Claude decides to explore
# Tool call: read_file
await registry.execute_tool("read_file", {
    "path": "/Users/maksimbozhko/Development/server-agent/app/config.py"
})

# Tool call: search_code
await registry.execute_tool("search_code", {
    "pattern": "class.*Config",
    "path": ".",
    "file_pattern": "*.py"
})
```

### Learning and Skill Development

The agent can practice skills and remember insights:

```python
# Agent experiments with bash
await registry.execute_tool("run_bash", {
    "command": "ls -la app/"
})

# Agent remembers the pattern
await registry.execute_tool("remember", {
    "key": "project_structure",
    "value": "app/ contains: ai/, db/, telegram/, workers/, tools/",
    "category": "skill"
})

# Later recalls
await registry.execute_tool("recall", {
    "key": "project_structure"
})
```

### Communication with Master

The agent can proactively communicate:

```python
# Report discovery
await registry.execute_tool("send_telegram_message", {
    "text": "🔍 <b>Discovery</b>\n\nI found a performance optimization opportunity in app/workers/reactive.py"
})
```

### File Modifications (with approval)

```python
# Agent wants to create a new file
# This triggers approval request
await registry.execute_tool("write_file", {
    "path": "/tmp/agent_notes.txt",
    "content": "My learning notes from today's exploration..."
})

# Master receives notification:
# 🔐 Tool Approval Required
# Tool: write_file
# Request ID: abc-123-def
# Reasoning: Storing daily learning notes for future reference
# Input: {path: "/tmp/agent_notes.txt", content: "..."}
#
# To approve: /approve abc-123-def
# To reject: /reject abc-123-def
```

## Integration with Proactive Scheduler

The enhanced proactive scheduler (`ProactiveToolsScheduler`) uses the tool system:

```python
# In app/workers/proactive_tools.py

# Each cycle:
1. Check token budget
2. Build context (recent actions, token stats, current focus)
3. Call Claude with tools enabled
4. Claude autonomously:
   - Reads files to understand codebase
   - Searches for patterns
   - Executes safe commands
   - Stores insights in memory
   - Communicates with Master when significant
5. Update working memory with results
```

## Configuration

### Environment Variables

```env
# Token budget
PROACTIVE_DAILY_TOKEN_LIMIT=7000000

# Scheduling
PROACTIVE_MIN_INTERVAL_SECONDS=60
PROACTIVE_MAX_INTERVAL_SECONDS=3600

# Approval timeout
APPROVAL_TIMEOUT_SECONDS=3600
```

### Enabling/Disabling Tools

To enable enhanced proactive scheduler:

```python
# In app/main.py
from app.workers.proactive_tools import get_tools_scheduler

# Instead of:
# proactive_scheduler = get_scheduler()

# Use:
proactive_scheduler = get_tools_scheduler()
```

## Testing

Run tool system tests:

```bash
pytest tests/test_tool_system.py -v
```

Test coverage:
- Tool registry initialization
- Tool execution (safe and dangerous)
- Approval flow (create, approve, reject)
- Safety boundaries (destructive commands, sensitive files)

## Adding New Tools

### Step 1: Define Tool

```python
# In app/tools/registry.py

self.register_tool(
    ToolDefinition(
        name="my_new_tool",
        description="Description of what this tool does",
        input_schema={
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                },
                "param2": {
                    "type": "integer",
                    "description": "Second parameter",
                    "default": 42
                }
            },
            "required": ["param1"]
        },
        safety_level=ToolSafety.SAFE  # or REQUIRES_APPROVAL
    ),
    self._execute_my_new_tool
)
```

### Step 2: Implement Executor

```python
async def _execute_my_new_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute my_new_tool"""
    try:
        param1 = args["param1"]
        param2 = args.get("param2", 42)

        # Tool implementation
        result = do_something(param1, param2)

        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error in my_new_tool: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
```

### Step 3: Add Tests

```python
# In tests/test_tool_system.py

@pytest.mark.asyncio
async def test_my_new_tool():
    registry = ToolRegistry()

    result = await registry.execute_tool(
        "my_new_tool",
        {"param1": "test"}
    )

    assert result["status"] == "success"
```

## Security Considerations

### Command Injection Prevention

All bash commands are checked against a blacklist:
- `rm -rf`, `dd if=`, `mkfs`, `shutdown`, `reboot`, etc.

### Path Traversal Prevention

File operations validate paths:
- Block operations on `/etc/passwd`, `/etc/shadow`, `~/.ssh/id_rsa`, etc.
- Resolve paths to prevent `../` attacks

### Token Budget Management

- Daily token limits prevent runaway costs
- Dynamic intervals adjust based on usage
- Budget warnings and notifications

### Approval Timeouts

- Pending approvals expire after configured timeout
- Prevents stale approval requests from accumulating

## Monitoring

### Logs

All tool executions are logged:
```
INFO - Executing safe tool: read_file
INFO - Claude wants to use tool: run_bash
WARNING - Blocked potentially destructive command: rm -rf /
INFO - Approval request sent to Master
```

### Database Queries

```sql
-- Get recent tool approvals
SELECT * FROM tool_approvals ORDER BY created_at DESC LIMIT 10;

-- Get pending approvals
SELECT * FROM tool_approvals WHERE status = 'pending';

-- Get agent memory
SELECT * FROM agent_memory ORDER BY created_at DESC;

-- Get agent memory by category
SELECT * FROM agent_memory WHERE category = 'skill';
```

## Troubleshooting

### Tool execution fails

Check logs for errors:
```bash
docker compose logs -f server-agent-vnext
```

### Approval not received

Check Telegram bot status:
```bash
curl http://localhost:8000/health
```

### Tools not working in proactive cycle

Verify enhanced scheduler is enabled:
```python
# Should be using get_tools_scheduler()
from app.workers.proactive_tools import get_tools_scheduler
```

## Future Enhancements

Potential improvements:
- Tool usage analytics dashboard
- Custom tool plugins system
- Tool execution sandboxing (Docker containers)
- Batch tool execution
- Tool chaining/composition
- Learning from tool execution patterns
- Dynamic safety level adjustment based on history

## References

- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [CLAUDE.md](../CLAUDE.md) - Project philosophy and guidelines
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Overall system architecture
