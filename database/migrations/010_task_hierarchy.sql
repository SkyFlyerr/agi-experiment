-- Migration 010: Add task hierarchy and ordering support
-- Enables subtasks and ensures proper task execution order

-- Add hierarchy columns to agent_tasks
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES agent_tasks(id);
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS order_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS depth INTEGER NOT NULL DEFAULT 0;

-- Index for parent-child relationships
CREATE INDEX IF NOT EXISTS idx_agent_tasks_parent ON agent_tasks(parent_id);

-- Index for ordering within parent
CREATE INDEX IF NOT EXISTS idx_agent_tasks_parent_order ON agent_tasks(parent_id, order_index);

-- Update the pending priority index to include depth (root tasks first)
DROP INDEX IF EXISTS idx_agent_tasks_pending_priority;
CREATE INDEX idx_agent_tasks_pending_priority ON agent_tasks(status, depth, priority, created_at)
    WHERE status = 'pending';

-- Comments
COMMENT ON COLUMN agent_tasks.parent_id IS 'Parent task ID for subtasks (NULL for root tasks)';
COMMENT ON COLUMN agent_tasks.order_index IS 'Order within parent task (0-based)';
COMMENT ON COLUMN agent_tasks.depth IS 'Nesting depth (0 for root tasks, 1 for subtasks, etc.)';

-- View for easy hierarchical queries
CREATE OR REPLACE VIEW task_tree AS
WITH RECURSIVE task_hierarchy AS (
    -- Root tasks
    SELECT
        id,
        parent_id,
        title,
        description,
        priority,
        status,
        source,
        depth,
        order_index,
        ARRAY[id] as path,
        title as full_path
    FROM agent_tasks
    WHERE parent_id IS NULL

    UNION ALL

    -- Child tasks
    SELECT
        t.id,
        t.parent_id,
        t.title,
        t.description,
        t.priority,
        t.status,
        t.source,
        t.depth,
        t.order_index,
        h.path || t.id,
        h.full_path || ' > ' || t.title
    FROM agent_tasks t
    INNER JOIN task_hierarchy h ON t.parent_id = h.id
)
SELECT * FROM task_hierarchy
ORDER BY path, order_index;
