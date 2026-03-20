-- ============================================================
-- Rollback: 003_add_constraints
-- Description: 回滚数据完整性约束
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 删除所有 CHECK 约束
-- ============================================================
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS chk_token_usage_not_empty,
DROP CONSTRAINT IF EXISTS chk_final_answer_max_length,
DROP CONSTRAINT IF EXISTS chk_user_input_max_length,
DROP CONSTRAINT IF EXISTS chk_tool_calls_max_size,
DROP CONSTRAINT IF EXISTS chk_thought_chain_max_size,
DROP CONSTRAINT IF EXISTS chk_finish_reason_valid,
DROP CONSTRAINT IF EXISTS chk_latency_ms_positive;

COMMIT;

-- ============================================================
-- 验证回滚
-- ============================================================
-- 验证约束是否已删除
-- SELECT conname FROM pg_constraint
-- WHERE conname LIKE 'chk_%' AND conrelid = 'agent_traces'::regclass;
-- 应该返回空结果
