-- ────────────────────────────────────────────────────────────────────────────────
-- Migration 003: Add Constraints (Phase 2.4)
-- ────────────────────────────────────────────────────────────────────────────────
-- This migration adds CHECK constraints to ensure data integrity.

-- ============================================================
-- CHECK Constraints for agent_traces table
-- ============================================================

-- 1. Latency must be non-negative
ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_latency_ms_positive
CHECK (latency_ms IS NULL OR latency_ms >= 0);

-- 2. Finish reason must be a valid value
ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_finish_reason_valid
CHECK (
    finish_reason IS NULL  -- Allow NULL for P0 compatibility
    OR finish_reason IN (
        'stop',           -- Normal completion
        'length',         -- Max tokens reached
        'tool_calls',     -- Waiting for tool calls
        'content_filter', -- Content filtered
        'error',          -- Error occurred
        'interrupted'     -- User interrupted
    )
);

-- 3. JSONB field size limits (prevent oversized objects)
ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_thought_chain_max_size
CHECK (pg_column_size(thought_chain) <= 100000); -- 100KB

ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_tool_calls_max_size
CHECK (pg_column_size(tool_calls) <= 50000); -- 50KB

ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_token_usage_max_size
CHECK (pg_column_size(token_usage) <= 10000); -- 10KB

-- 4. Text field length limits
ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_user_input_max_length
CHECK (user_input IS NULL OR length(user_input) <= 10000); -- 10K characters

ALTER TABLE agent_traces
ADD CONSTRAINT IF NOT EXISTS chk_final_answer_max_length
CHECK (final_answer IS NULL OR length(final_answer) <= 50000); -- 50K characters

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON CONSTRAINT chk_latency_ms_positive ON agent_traces IS 'Ensures latency is non-negative';
COMMENT ON CONSTRAINT chk_finish_reason_valid ON agent_traces IS 'Ensures finish_reason is a valid value';
COMMENT ON CONSTRAINT chk_thought_chain_max_size ON agent_traces IS 'Limits thought_chain to 100KB';
COMMENT ON CONSTRAINT chk_tool_calls_max_size ON agent_traces IS 'Limits tool_calls to 50KB';
COMMENT ON CONSTRAINT chk_token_usage_max_size ON agent_traces IS 'Limits token_usage to 10KB';
COMMENT ON CONSTRAINT chk_user_input_max_length ON agent_traces IS 'Limits user_input to 10K characters';
COMMENT ON CONSTRAINT chk_final_answer_max_length ON agent_traces IS 'Limits final_answer to 50K characters';
