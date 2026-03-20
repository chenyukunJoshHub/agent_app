-- ============================================================
-- Rollback: 005_enable_rls
-- Description: 回滚 Row Level Security
-- Author: Database Expert
-- Date: 2026-03-20
-- WARNING: 禁用 RLS 将导致所有用户可以访问所有数据
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 删除策略
-- ============================================================
DROP POLICY IF EXISTS agent_traces_update_deny ON agent_traces;
DROP POLICY IF EXISTS agent_traces_insert_own ON agent_traces;
DROP POLICY IF EXISTS agent_traces_select_own ON agent_traces;

DROP POLICY IF EXISTS sessions_delete_own ON sessions;
DROP POLICY IF EXISTS sessions_update_own ON sessions;
DROP POLICY IF EXISTS sessions_insert_own ON sessions;
DROP POLICY IF EXISTS sessions_select_own ON sessions;

DROP POLICY IF EXISTS users_delete_deny ON users;
DROP POLICY IF EXISTS users_update_own ON users;
DROP POLICY IF EXISTS users_insert_deny ON users;
DROP POLICY IF EXISTS users_select_own ON users;

-- ============================================================
-- 2. 禁用 RLS
-- ============================================================
ALTER TABLE agent_traces DISABLE ROW LEVEL SECURITY;
ALTER TABLE sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;

-- ============================================================
-- 3. 删除管理员绕过函数（如果存在）
-- ============================================================
DROP FUNCTION IF EXISTS app.set_admin_user(text);

COMMIT;

-- ============================================================
-- 验证回滚
-- ============================================================
-- 验证 RLS 是否已禁用
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE tablename IN ('users', 'sessions', 'agent_traces');
-- rowsecurity 应该为 false

-- 验证策略是否已删除
-- SELECT schemaname, tablename, policyname
-- FROM pg_policies
-- WHERE tablename IN ('users', 'sessions', 'agent_traces');
-- 应该返回空结果
