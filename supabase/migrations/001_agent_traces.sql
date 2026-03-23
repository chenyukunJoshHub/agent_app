-- ────────────────────────────────────────────────────────────────────────────────
-- Migration 001: Agent Traces Table (P0 Minimum Schema)
-- ────────────────────────────────────────────────────────────────────────────────

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Agent traces table for storing conversation metadata
CREATE TABLE IF NOT EXISTS agent_traces (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    text        NOT NULL,
    user_id       text        NOT NULL DEFAULT 'dev_user',
    user_input    text,
    final_answer  text,
    thought_chain jsonb       NOT NULL DEFAULT '[]',
    tool_calls    jsonb       NOT NULL DEFAULT '[]',
    token_usage   jsonb       NOT NULL DEFAULT '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user    ON agent_traces(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_created ON agent_traces(created_at DESC);

-- Comment
COMMENT ON TABLE agent_traces IS 'Stores agent execution traces for observability';
COMMENT ON COLUMN agent_traces.thought_chain IS 'Array of thought events from agent reasoning';
COMMENT ON COLUMN agent_traces.tool_calls IS 'Array of tool invocation records';
COMMENT ON COLUMN agent_traces.token_usage IS 'Token usage statistics';
COMMENT ON COLUMN agent_traces.finish_reason IS 'Agent completion reason (stop, error, interrupted, etc.)';
