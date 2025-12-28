-- Migration 009: Agent tasks queue with priority support
-- Tasks from Master have highest priority

-- Agent task queue
CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    source TEXT NOT NULL CHECK (source IN ('master', 'self')),
    goal_criteria TEXT,  -- How to verify task completion
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_result TEXT,  -- Result of last attempt (truncated to 5000 chars)
    thread_id UUID,  -- Link to conversation thread
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Indexes for efficient task queue queries
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_priority ON agent_tasks(priority);
CREATE INDEX idx_agent_tasks_source ON agent_tasks(source);
CREATE INDEX idx_agent_tasks_created ON agent_tasks(created_at DESC);

-- Composite index for the most common query: get pending tasks by priority
CREATE INDEX idx_agent_tasks_pending_priority ON agent_tasks(status, priority, created_at)
    WHERE status = 'pending';

-- Foreign key to threads table if it exists
-- ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_thread
--     FOREIGN KEY (thread_id) REFERENCES threads(id);

-- Comments
COMMENT ON TABLE agent_tasks IS 'Task queue for autonomous AGI agent with Master priority';

COMMENT ON COLUMN agent_tasks.id IS 'Unique task identifier (UUID)';
COMMENT ON COLUMN agent_tasks.title IS 'Short task title';
COMMENT ON COLUMN agent_tasks.description IS 'Detailed task description';
COMMENT ON COLUMN agent_tasks.priority IS 'Task priority: critical > high > medium > low';
COMMENT ON COLUMN agent_tasks.status IS 'Current status: pending, running, completed, failed, cancelled';
COMMENT ON COLUMN agent_tasks.source IS 'Task source: master (from Master) or self (self-determined)';
COMMENT ON COLUMN agent_tasks.goal_criteria IS 'Criteria to verify task completion';
COMMENT ON COLUMN agent_tasks.attempts IS 'Number of execution attempts';
COMMENT ON COLUMN agent_tasks.max_attempts IS 'Maximum allowed attempts before marking as failed';
COMMENT ON COLUMN agent_tasks.last_result IS 'Result or error from last execution attempt';
COMMENT ON COLUMN agent_tasks.thread_id IS 'Optional link to conversation thread';
COMMENT ON COLUMN agent_tasks.created_at IS 'When task was created';
COMMENT ON COLUMN agent_tasks.started_at IS 'When task execution started';
COMMENT ON COLUMN agent_tasks.completed_at IS 'When task was completed or failed';
