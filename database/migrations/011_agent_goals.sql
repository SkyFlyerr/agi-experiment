-- Migration 011: Add Goals table for high-level objectives
-- Goals persist until fully achieved, tasks are steps toward goals

CREATE TABLE IF NOT EXISTS agent_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Goal definition
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    success_criteria TEXT NOT NULL,  -- How to verify goal is achieved

    -- Source and priority
    source TEXT NOT NULL CHECK (source IN ('master', 'self')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'failed', 'paused')),

    -- Progress tracking
    total_tasks INTEGER NOT NULL DEFAULT 0,
    completed_tasks INTEGER NOT NULL DEFAULT 0,
    failed_tasks INTEGER NOT NULL DEFAULT 0,

    -- Verification
    verified_by_master BOOLEAN NOT NULL DEFAULT FALSE,
    master_feedback TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Link to conversation
    thread_id UUID
);

-- Add goal_id to tasks
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS goal_id UUID REFERENCES agent_goals(id);

-- Index for active goals
CREATE INDEX IF NOT EXISTS idx_agent_goals_active ON agent_goals(status, priority, created_at)
    WHERE status = 'active';

-- Index for tasks by goal
CREATE INDEX IF NOT EXISTS idx_agent_tasks_goal ON agent_tasks(goal_id);

-- Trigger to update goal progress when task status changes
CREATE OR REPLACE FUNCTION update_goal_progress()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.goal_id IS NOT NULL THEN
        UPDATE agent_goals SET
            total_tasks = (SELECT COUNT(*) FROM agent_tasks WHERE goal_id = NEW.goal_id),
            completed_tasks = (SELECT COUNT(*) FROM agent_tasks WHERE goal_id = NEW.goal_id AND status = 'completed'),
            failed_tasks = (SELECT COUNT(*) FROM agent_tasks WHERE goal_id = NEW.goal_id AND status = 'failed'),
            updated_at = NOW()
        WHERE id = NEW.goal_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_goal_progress ON agent_tasks;
CREATE TRIGGER trigger_update_goal_progress
    AFTER INSERT OR UPDATE OF status ON agent_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_goal_progress();

-- Comments
COMMENT ON TABLE agent_goals IS 'High-level objectives that persist until fully achieved';
COMMENT ON COLUMN agent_goals.success_criteria IS 'Verifiable criteria for goal completion (e.g., "Dashboard accessible at URL")';
COMMENT ON COLUMN agent_goals.verified_by_master IS 'Whether Master confirmed goal achievement';
