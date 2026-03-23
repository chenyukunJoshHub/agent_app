-- ────────────────────────────────────────────────────────────────────────────────
-- Migration 005: Enable Row Level Security (Phase 2.4)
-- ────────────────────────────────────────────────────────────────────────────────
-- This migration enables Row Level Security (RLS) to ensure users can only
-- access their own data.

-- ============================================================
-- Enable RLS on tables
-- ============================================================

-- Note: We only enable RLS on agent_traces for P0
-- users and sessions tables will be added in P1

ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- RLS Policies for agent_traces
-- ============================================================

-- 1. SELECT: Users can only view their own traces
CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT
TO PUBLIC
USING (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.user_id', true) = 'dev_user'  -- Dev user can see all
);

-- 2. INSERT: Users can only insert traces with their own user_id
CREATE POLICY agent_traces_insert_own ON agent_traces
FOR INSERT
TO PUBLIC
WITH CHECK (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.user_id', true) = 'dev_user'
);

-- 3. UPDATE: Users can only update their own traces
CREATE POLICY agent_traces_update_own ON agent_traces
FOR UPDATE
TO PUBLIC
USING (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.user_id', true) = 'dev_user'
);

-- 4. DELETE: Users can only delete their own traces
CREATE POLICY agent_traces_delete_own ON agent_traces
FOR DELETE
TO PUBLIC
USING (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.user_id', true) = 'dev_user'
);

-- ============================================================
-- Helper function for setting user context
-- ============================================================

-- Function to set the user_id for RLS
CREATE OR REPLACE FUNCTION set_user_context(user_id text)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.user_id', user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to public
GRANT EXECUTE ON FUNCTION set_user_context(text) TO PUBLIC;

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON POLICY agent_traces_select_own ON agent_traces IS 'Users can only select their own traces';
COMMENT ON POLICY agent_traces_insert_own ON agent_traces IS 'Users can only insert traces with their own user_id';
COMMENT ON POLICY agent_traces_update_own ON agent_traces IS 'Users can only update their own traces';
COMMENT ON POLICY agent_traces_delete_own ON agent_traces IS 'Users can only delete their own traces';
COMMENT ON FUNCTION set_user_context(text) IS 'Helper function to set user_id for RLS policies';
