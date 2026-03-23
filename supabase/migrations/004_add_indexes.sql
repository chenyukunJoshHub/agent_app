-- ────────────────────────────────────────────────────────────────────────────────
-- Migration 004: Add Performance Indexes (Phase 2.4)
-- ────────────────────────────────────────────────────────────────────────────────
-- This migration adds performance-optimized indexes for common query patterns.

-- ============================================================
-- Composite Indexes (复合索引)
-- ============================================================

-- 1. User session history query (high frequency)
-- Query pattern: WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

-- 2. Session trace pagination query (high frequency)
-- Query pattern: WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
CREATE INDEX IF NOT EXISTS idx_agent_traces_session_created_covering
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

-- 3. User time range query (medium frequency)
-- Query pattern: WHERE user_id = ? AND created_at > ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_agent_traces_user_created
ON agent_traces(user_id, created_at DESC);

-- ============================================================
-- GIN Indexes (JSONB field indexes)
-- ============================================================

-- 1. Tool calls query (high frequency)
-- Query pattern: WHERE tool_calls @> '[{"name": "web_search"}]'
CREATE INDEX IF NOT EXISTS idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

-- 2. Optimized GIN index for tool_calls (path operations only)
CREATE INDEX IF NOT EXISTS idx_agent_traces_tool_calls_path
ON agent_traces USING GIN (tool_calls jsonb_path_ops);

-- 3. Thought chain query (medium frequency)
-- Query pattern: WHERE thought_chain @> '{"step": "planning"}'
CREATE INDEX IF NOT EXISTS idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);

-- 4. Token usage query (low frequency)
-- Query pattern: WHERE token_usage->>'total_tokens'::int > 5000
CREATE INDEX IF NOT EXISTS idx_agent_traces_token_usage
ON agent_traces USING GIN (token_usage);

-- ============================================================
-- Partial Indexes (部分索引)
-- ============================================================

-- 1. Error traces query (low frequency but important)
-- Query pattern: WHERE finish_reason IN ('error', 'length', 'content_filter')
CREATE INDEX IF NOT EXISTS idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

-- 2. High latency query (performance monitoring)
-- Query pattern: WHERE latency_ms > 10000 ORDER BY latency_ms DESC
CREATE INDEX IF NOT EXISTS idx_agent_traces_high_latency
ON agent_traces(user_id, latency_ms DESC, created_at DESC)
WHERE latency_ms > 10000; -- > 10 seconds

-- 3. Recent sessions query (time series optimization)
-- Query pattern: WHERE created_at > NOW() - INTERVAL '90 days'
CREATE INDEX IF NOT EXISTS idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '90 days';

-- ============================================================
-- Covering Index (覆盖索引)
-- ============================================================

-- Includes frequently queried fields to avoid table lookups
CREATE INDEX IF NOT EXISTS idx_agent_traces_user_session_covering
ON agent_traces(user_id, session_id, created_at DESC)
INCLUDE (
    final_answer,
    latency_ms,
    finish_reason,
    thought_chain,
    tool_calls
);

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON INDEX idx_agent_traces_user_session_created IS 'Composite index for user session history queries';
COMMENT ON INDEX idx_agent_traces_session_created_covering IS 'Covering index for session pagination';
COMMENT ON INDEX idx_agent_traces_user_created IS 'Index for user time range queries';
COMMENT ON INDEX idx_agent_traces_tool_calls IS 'GIN index for tool_calls JSONB field';
COMMENT ON INDEX idx_agent_traces_tool_calls_path IS 'Optimized GIN index for tool_calls path operations';
COMMENT ON INDEX idx_agent_traces_thought_chain IS 'GIN index for thought_chain JSONB field';
COMMENT ON INDEX idx_agent_traces_token_usage IS 'GIN index for token_usage JSONB field';
COMMENT ON INDEX idx_agent_traces_errors IS 'Partial index for error traces';
COMMENT ON INDEX idx_agent_traces_high_latency IS 'Partial index for high latency traces (>10s)';
COMMENT ON INDEX idx_agent_traces_recent IS 'Partial index for recent sessions (90 days)';
COMMENT ON INDEX idx_agent_traces_user_session_covering IS 'Covering index for user session queries with included columns';
