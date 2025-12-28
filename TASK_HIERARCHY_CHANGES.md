# Task Hierarchy System - Changes Summary

## Problem Solved

Agent was "forgetting" tasks from Master after several attempts. For example, when asked to create a dashboard, the agent made 3 attempts, failed, then went to work on self-assigned skill development tasks instead of persisting on Master's task.

## Root Causes Fixed

1. **Flat task structure** - Tasks had no hierarchy, couldn't be broken into subtasks
2. **No strict source priority** - Master tasks could be skipped for self-tasks
3. **No decomposition** - Complex tasks couldn't be split into trackable subtasks

## Changes Made

### 1. Database Migration (`database/migrations/010_task_hierarchy.sql`)

Added to `agent_tasks` table:
- `parent_id UUID` - Reference to parent task (NULL for root tasks)
- `order_index INTEGER` - Order within parent (0-based)
- `depth INTEGER` - Nesting level (0 = root, 1 = subtask, etc.)

New indexes for efficient hierarchical queries.

### 2. Task Module (`app/db/tasks.py`)

**New fields in `AgentTask` model:**
- `parent_id`, `order_index`, `depth`

**Updated query priority:**
```sql
ORDER BY
    CASE source WHEN 'master' THEN 0 ELSE 1 END,  -- Master FIRST
    CASE priority WHEN 'critical' THEN 1 ... END,
    created_at ASC
```

**New functions:**
- `create_subtasks(parent_id, subtasks)` - Bulk create subtasks
- `get_subtasks(parent_id)` - Get all subtasks of a task
- `get_next_pending_subtask(parent_id)` - Get next subtask to execute
- `count_pending_subtasks(parent_id)` - Count remaining subtasks

**Updated behavior:**
- `complete_task()` now auto-completes parent when all subtasks done
- `get_next_pending_task()` returns subtask if parent has pending subtasks

### 3. Task Executor (`app/workers/task_executor.py`)

**Decomposition support:**
- Claude can decompose complex tasks by outputting JSON:
  ```json
  {"decompose": true, "subtasks": [
    {"title": "Step 1", "description": "...", "goal_criteria": "..."},
    {"title": "Step 2", "description": "...", "goal_criteria": "..."}
  ]}
  ```

**New methods:**
- `_check_decomposition(output)` - Parse decomposition from Claude output
- `_handle_decomposition(task, subtasks)` - Create subtasks, notify Master

**Prompt updates:**
- Root tasks (depth=0) get decomposition instructions
- Subtasks (depth>0) are told to complete their specific step

## How It Works Now

1. **Master sends task** → Created as root task with `source='master'`, `priority='high'`
2. **Proactive loop** fetches next pending task (Master tasks ALWAYS first)
3. **Claude analyzes task**:
   - If simple: executes directly
   - If complex: outputs decomposition JSON
4. **If decomposed**:
   - Parent stays pending
   - Subtasks created with same priority/source as parent
   - Each subtask executed in order
   - Parent auto-completes when all subtasks done
5. **If subtask fails**: Retries up to max_attempts, then marked failed
6. **Parent task fails only if**: All subtasks fail OR retries exhausted

## Priority Enforcement

```
1. Master + Critical
2. Master + High
3. Master + Medium
4. Master + Low
5. Self + Critical
6. Self + High
7. Self + Medium
8. Self + Low
```

**Master tasks can NEVER be skipped for self-tasks.**

## Deployment Steps

1. Run migration:
   ```bash
   psql -d agi_agent -f database/migrations/010_task_hierarchy.sql
   ```

2. Restart agent container:
   ```bash
   docker compose restart agi-agent
   ```

## Testing

1. Send task to bot: "Create a simple status dashboard"
2. Expect: Task decomposed into 3-5 subtasks
3. Each subtask should execute in order
4. All subtasks complete → Parent completes
5. Master notified of decomposition and completion

## Files Changed

- `database/migrations/010_task_hierarchy.sql` (NEW)
- `app/db/tasks.py` (MODIFIED)
- `app/workers/task_executor.py` (MODIFIED)
