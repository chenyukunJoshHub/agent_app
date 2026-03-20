-- ============================================================
-- Migration: 003_add_constraints
-- Description: 添加数据完整性约束
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 延迟必须为正数
-- ============================================================
ALTER TABLE agent_traces
ADD CONSTRAINT chk_latency_ms_positive
CHECK (latency_ms >= 0);

-- ============================================================
-- 2. 完成原因必须是有效值
-- ============================================================
ALTER TABLE agent_traces
ADD CONSTRAINT chk_finish_reason_valid
CHECK (
    finish_reason IN (
        'stop',           -- 正常完成
        'length',         -- 达到最大长度
        'tool_calls',     -- 等待工具调用
        'content_filter', -- 内容过滤
        'error',          -- 错误
        'interrupted'     -- 用户中断
    )
);

-- ============================================================
-- 3. JSONB 字段大小限制（防止超大对象）
-- ============================================================
ALTER TABLE agent_traces
ADD CONSTRAINT chk_thought_chain_max_size
CHECK (pg_column_size(thought_chain) <= 100000); -- 100KB

ALTER TABLE agent_traces
ADD CONSTRAINT chk_tool_calls_max_size
CHECK (pg_column_size(tool_calls) <= 50000); -- 50KB

-- ============================================================
-- 4. 文本字段长度限制
-- ============================================================
ALTER TABLE agent_traces
ADD CONSTRAINT chk_user_input_max_length
CHECK (length(coalesce(user_input, '')) <= 10000); -- 10K 字符

ALTER TABLE agent_traces
ADD CONSTRAINT chk_final_answer_max_length
CHECK (length(coalesce(final_answer, '')) <= 50000); -- 50K 字符

-- ============================================================
-- 5. Token 使用不为空
-- ============================================================
ALTER TABLE agent_traces
ADD CONSTRAINT chk_token_usage_not_empty
CHECK (token_usage::text != '{}' AND token_usage IS NOT NULL);

-- ============================================================
-- 6. 添加约束注释
-- ============================================================
COMMENT ON CONSTRAINT chk_latency_ms_positive ON agent_traces IS '确保延迟时间非负';
COMMENT ON CONSTRAINT chk_finish_reason_valid ON agent_traces IS '确保完成原因在允许的枚举值内';
COMMENT ON CONSTRAINT chk_thought_chain_max_size ON agent_traces IS '限制推理链 JSONB 大小为 100KB';
COMMENT ON CONSTRAINT chk_tool_calls_max_size ON agent_traces IS '限制工具调用 JSONB 大小为 50KB';
COMMENT ON CONSTRAINT chk_user_input_max_length ON agent_traces IS '限制用户输入为 10K 字符';
COMMENT ON CONSTRAINT chk_final_answer_max_length ON agent_traces IS '限制最终答案为 50K 字符';
COMMENT ON CONSTRAINT chk_token_usage_not_empty ON agent_traces IS '确保 token_usage 对象不为空';

COMMIT;

-- ============================================================
-- 验证脚本
-- ============================================================
-- 验证约束是否创建成功
-- SELECT conname FROM pg_constraint WHERE conname LIKE 'chk_%' AND conrelid = 'agent_traces'::regclass;

-- 测试约束
-- INSERT INTO agent_traces (session_id, user_id, user_input, final_answer, thought_chain, tool_calls, token_usage, latency_ms, finish_reason)
-- VALUES ('test', 'dev_user', 'test', 'test', '[]', '[]', '{}', -1, 'stop');
-- 应该失败：latency_ms 不能为负数
