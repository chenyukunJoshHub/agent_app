-- ============================================================
-- Migration: 004_add_indexes
-- Description: 添加性能优化索引
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 删除旧索引（如果存在）
-- ============================================================
DROP INDEX IF EXISTS idx_agent_traces_session;
DROP INDEX IF EXISTS idx_agent_traces_user;

-- ============================================================
-- 2. Composite Indexes（复合索引）
-- ============================================================

-- 用户会话历史查询（高频）
-- 查询模式: WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

-- 会话追踪分页查询（高频）
-- 查询模式: WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
-- 使用 INCLUDE 子句创建覆盖索引，避免表回查
CREATE INDEX idx_agent_traces_session_created
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

-- 用户时间范围查询（中频）
-- 查询模式: WHERE user_id = ? AND created_at > ? ORDER BY created_at DESC
CREATE INDEX idx_agent_traces_user_created
ON agent_traces(user_id, created_at DESC);

-- ============================================================
-- 3. GIN Indexes（JSONB 字段索引）
-- ============================================================

-- 工具调用查询（高频）
-- 查询模式: WHERE tool_calls @> '[{"name": "web_search"}]'
CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

-- 推理链查询（中频）
-- 查询模式: WHERE thought_chain @> '{"step": "planning"}'
CREATE INDEX idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);

-- Token 使用查询（低频）
-- 查询模式: WHERE token_usage->>'total_tokens'::int > 5000
CREATE INDEX idx_agent_traces_token_usage
ON agent_traces USING GIN (token_usage);

-- 优化的 GIN 索引（仅支持 @> 操作符，索引更小）
CREATE INDEX idx_agent_traces_tool_calls_path
ON agent_traces USING GIN (tool_calls jsonb_path_ops);

-- ============================================================
-- 4. Partial Indexes（部分索引）
-- ============================================================

-- 错误追踪查询（低频但重要）
-- 查询模式: WHERE finish_reason IN ('error', 'length', 'content_filter')
CREATE INDEX idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

-- 高延迟查询（性能监控）
-- 查询模式: WHERE latency_ms > 10000 ORDER BY latency_ms DESC
CREATE INDEX idx_agent_traces_high_latency
ON agent_traces(user_id, latency_ms DESC, created_at DESC)
WHERE latency_ms > 10000; -- > 10 秒

-- 近期会话查询（时间序列优化）
-- 查询模式: WHERE created_at > NOW() - INTERVAL '90 days'
CREATE INDEX idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '90 days';

-- ============================================================
-- 5. Covering Indexes（覆盖索引）
-- ============================================================

-- 包含常用查询字段，避免表回查
CREATE INDEX idx_agent_traces_user_session_covering
ON agent_traces(user_id, session_id, created_at DESC)
INCLUDE (
    final_answer,
    latency_ms,
    finish_reason,
    thought_chain,
    tool_calls
);

-- ============================================================
-- 6. Unique Indexes（唯一索引）
-- ============================================================

-- 防止同一会话在同一时间产生重复 trace
CREATE UNIQUE INDEX idx_agent_traces_session_created_unique
ON agent_traces(session_id, created_at DESC, id);

-- ============================================================
-- 7. Sessions 表索引
-- ============================================================

-- 会话搜索索引（覆盖索引）
CREATE INDEX idx_sessions_user_last_message
ON sessions(user_id, last_message_at DESC NULLS LAST)
INCLUDE (title);

-- ============================================================
-- 8. 添加索引注释
-- ============================================================
COMMENT ON INDEX idx_agent_traces_user_session_created IS '用户会话历史查询的复合索引';
COMMENT ON INDEX idx_agent_traces_session_created IS '会话追踪分页查询的覆盖索引';
COMMENT ON INDEX idx_agent_traces_user_created IS '用户时间范围查询的复合索引';
COMMENT ON INDEX idx_agent_traces_tool_calls IS '工具调用的 GIN 索引';
COMMENT ON INDEX idx_agent_traces_thought_chain IS '推理链的 GIN 索引';
COMMENT ON INDEX idx_agent_traces_token_usage IS 'Token 使用的 GIN 索引';
COMMENT ON INDEX idx_agent_traces_tool_calls_path IS '工具调用的优化 GIN 索引（仅 @> 操作）';
COMMENT ON INDEX idx_agent_traces_errors IS '错误追踪的部分索引';
COMMENT ON INDEX idx_agent_traces_high_latency IS '高延迟查询的部分索引';
COMMENT ON INDEX idx_agent_traces_recent IS '近期会话的部分索引（90天内）';
COMMENT ON INDEX idx_agent_traces_user_session_covering IS '用户会话的覆盖索引';
COMMENT ON INDEX idx_agent_traces_session_created_unique IS '防止重复 trace 的唯一索引';
COMMENT ON INDEX idx_sessions_user_last_message IS '用户会话列表的覆盖索引';

COMMIT;

-- ============================================================
-- 验证脚本
-- ============================================================

-- 验证所有索引是否创建成功
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('agent_traces', 'sessions')
-- ORDER BY indexname;

-- 查看索引大小
-- SELECT
--     indexname,
--     pg_size_pretty(pg_relation_size(indexrelid)) as index_size
-- FROM pg_stat_user_indexes
-- WHERE tablename IN ('agent_traces', 'sessions')
-- ORDER BY pg_relation_size(indexrelid) DESC;

-- 测试索引使用（执行 EXPLAIN ANALYZE）
-- EXPLAIN (ANALYZE, BUFFERS)
-- SELECT * FROM agent_traces
-- WHERE session_id = 'test_session'
-- ORDER BY created_at DESC
-- LIMIT 20;
