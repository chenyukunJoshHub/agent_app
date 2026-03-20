-- ============================================================
-- Rollback: 004_add_indexes
-- Description: 回滚性能优化索引
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 删除 agent_traces 表的索引
-- ============================================================
DROP INDEX IF EXISTS idx_sessions_user_last_message;
DROP INDEX IF EXISTS idx_agent_traces_user_session_covering;
DROP INDEX IF EXISTS idx_agent_traces_session_created_unique;
DROP INDEX IF EXISTS idx_agent_traces_recent;
DROP INDEX IF EXISTS idx_agent_traces_high_latency;
DROP INDEX IF EXISTS idx_agent_traces_errors;
DROP INDEX IF EXISTS idx_agent_traces_tool_calls_path;
DROP INDEX IF EXISTS idx_agent_traces_token_usage;
DROP INDEX IF EXISTS idx_agent_traces_thought_chain;
DROP INDEX IF EXISTS idx_agent_traces_tool_calls;
DROP INDEX IF EXISTS idx_agent_traces_user_created;
DROP INDEX IF EXISTS idx_agent_traces_session_created;
DROP INDEX IF EXISTS idx_agent_traces_user_session_created;

-- ============================================================
-- 2. 重建旧索引（如果需要）
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user ON agent_traces(user_id);

COMMIT;

-- ============================================================
-- 验证回滚
-- ============================================================
-- 验证新索引是否已删除
-- SELECT indexname FROM pg_indexes
-- WHERE tablename = 'agent_traces'
-- AND indexname LIKE 'idx_agent_traces_%'
-- ORDER BY indexname;

-- 验证旧索引是否存在
-- SELECT indexname FROM pg_indexes
-- WHERE tablename = 'agent_traces'
-- AND indexname IN ('idx_agent_traces_session', 'idx_agent_traces_user');
