-- ============================================================
-- Rollback: 002_create_users_and_sessions
-- Description: 回滚 users 和 sessions 表创建
-- Author: Database Expert
-- Date: 2026-03-20
-- WARNING: 此操作将删除 users 和 sessions 表及其所有数据
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 删除外键约束
-- ============================================================
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS fk_agent_traces_session,
DROP CONSTRAINT IF EXISTS fk_agent_traces_user;

-- ============================================================
-- 2. 删除索引
-- ============================================================
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_sessions_user_id;
DROP INDEX IF EXISTS idx_sessions_user_last_message;

-- ============================================================
-- 3. 删除表
-- ============================================================
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

COMMIT;

-- ============================================================
-- 验证回滚
-- ============================================================
-- 验证表是否已删除
-- SELECT tablename FROM pg_tables WHERE tablename IN ('users', 'sessions');
-- 应该返回空结果

-- 验证外键是否已删除
-- SELECT conname FROM pg_constraint WHERE conname LIKE 'fk_agent_traces%';
-- 应该返回空结果
