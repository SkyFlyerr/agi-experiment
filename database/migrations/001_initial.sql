-- Migration: 001_initial
-- Description: Initial database schema for Server Agent vNext
-- Based on: database/schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Chat threads table
CREATE TABLE IF NOT EXISTS chat_threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(50) NOT NULL DEFAULT 'telegram',
    chat_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(platform, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_platform_chat_id ON chat_threads(platform, chat_id);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    platform_message_id VARCHAR(255),
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    author_user_id VARCHAR(255),
    text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload JSONB,
    UNIQUE(thread_id, platform_message_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created ON chat_messages(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_platform_id ON chat_messages(platform_message_id);

-- Message artifacts table
CREATE TABLE IF NOT EXISTS message_artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    kind VARCHAR(100) NOT NULL CHECK (kind IN ('voice_transcript', 'image_json', 'ocr_text', 'file_meta', 'tool_result')),
    content_json JSONB,
    uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_message_artifacts_message_id ON message_artifacts(message_id);
CREATE INDEX IF NOT EXISTS idx_message_artifacts_kind ON message_artifacts(kind);

-- Reactive jobs table
CREATE TABLE IF NOT EXISTS reactive_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    trigger_message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed', 'canceled')),
    mode VARCHAR(50) NOT NULL CHECK (mode IN ('classify', 'plan', 'execute', 'answer')),
    payload_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reactive_jobs_status ON reactive_jobs(status);
CREATE INDEX IF NOT EXISTS idx_reactive_jobs_thread_id ON reactive_jobs(thread_id);
CREATE INDEX IF NOT EXISTS idx_reactive_jobs_created_at ON reactive_jobs(created_at DESC);

-- Approvals table
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES reactive_jobs(id) ON DELETE CASCADE,
    proposal_text TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'superseded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_thread_job ON approvals(thread_id, job_id);

-- Token ledger table
CREATE TABLE IF NOT EXISTS token_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scope VARCHAR(50) NOT NULL CHECK (scope IN ('proactive', 'reactive')),
    provider VARCHAR(100) NOT NULL,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    tokens_total INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meta_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_token_ledger_scope ON token_ledger(scope);
CREATE INDEX IF NOT EXISTS idx_token_ledger_created_at ON token_ledger(created_at DESC);

-- Deployments table
CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    git_sha VARCHAR(255) NOT NULL,
    branch VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'building' CHECK (status IN ('building', 'testing', 'deploying', 'healthy', 'rolled_back', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    report_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_started_at ON deployments(started_at DESC);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to chat_threads
DROP TRIGGER IF EXISTS update_chat_threads_updated_at ON chat_threads;
CREATE TRIGGER update_chat_threads_updated_at BEFORE UPDATE ON chat_threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Migration version tracking (for future migrations)
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES (1)
ON CONFLICT (version) DO NOTHING;
