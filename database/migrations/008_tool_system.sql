-- Migration 008: Tool system tables
-- Creates tables for agent memory and tool approvals

-- Agent long-term memory
CREATE TABLE IF NOT EXISTS agent_memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_agent_memory_category ON agent_memory(category);
CREATE INDEX idx_agent_memory_created ON agent_memory(created_at DESC);

-- Tool approval requests
CREATE TABLE IF NOT EXISTS tool_approvals (
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

CREATE INDEX idx_tool_approvals_status ON tool_approvals(status);
CREATE INDEX idx_tool_approvals_created ON tool_approvals(created_at DESC);
CREATE INDEX idx_tool_approvals_expires ON tool_approvals(expires_at);

-- Comments
COMMENT ON TABLE agent_memory IS 'Long-term memory storage for the AGI agent';
COMMENT ON TABLE tool_approvals IS 'Approval requests for tools requiring Master permission';

COMMENT ON COLUMN agent_memory.key IS 'Unique identifier for this memory';
COMMENT ON COLUMN agent_memory.value IS 'The actual information stored';
COMMENT ON COLUMN agent_memory.category IS 'Category: skill, fact, pattern, insight, etc.';

COMMENT ON COLUMN tool_approvals.request_id IS 'Unique UUID for this approval request';
COMMENT ON COLUMN tool_approvals.tool_name IS 'Name of the tool requiring approval';
COMMENT ON COLUMN tool_approvals.tool_input IS 'JSON input arguments for the tool';
COMMENT ON COLUMN tool_approvals.reasoning IS 'Explanation from agent why this tool is needed';
COMMENT ON COLUMN tool_approvals.status IS 'Current status of the approval request';
COMMENT ON COLUMN tool_approvals.response IS 'Optional response message from Master';
