-- ============================================================
-- Migration: 005_enable_rls
-- Description: 启用 Row Level Security
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 启用 RLS
-- ============================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 2. Users 表策略
-- ============================================================

-- SELECT: 用户只能查看自己的信息
CREATE POLICY users_select_own ON users
FOR SELECT
USING (id = current_setting('app.user_id', true));

-- INSERT: 不允许普通用户插入（由系统创建）
CREATE POLICY users_insert_deny ON users
FOR INSERT
WITH CHECK (false);

-- UPDATE: 用户只能更新自己的信息
CREATE POLICY users_update_own ON users
FOR UPDATE
USING (id = current_setting('app.user_id', true));

-- DELETE: 用户不能删除自己的账户（需要管理员操作）
CREATE POLICY users_delete_deny ON users
FOR DELETE
WITH CHECK (false);

-- ============================================================
-- 3. Sessions 表策略
-- ============================================================

-- SELECT: 用户只能查看自己的会话
CREATE POLICY sessions_select_own ON sessions
FOR SELECT
USING (user_id = current_setting('app.user_id', true));

-- INSERT: 用户只能创建自己的会话
CREATE POLICY sessions_insert_own ON sessions
FOR INSERT
WITH CHECK (user_id = current_setting('app.user_id', true));

-- UPDATE: 用户只能更新自己的会话
CREATE POLICY sessions_update_own ON sessions
FOR UPDATE
USING (user_id = current_setting('app.user_id', true));

-- DELETE: 用户只能删除自己的会话
CREATE POLICY sessions_delete_own ON sessions
FOR DELETE
USING (user_id = current_setting('app.user_id', true));

-- ============================================================
-- 4. Agent Traces 表策略
-- ============================================================

-- SELECT: 用户只能查看自己的追踪
CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT
USING (user_id = current_setting('app.user_id', true));

-- INSERT: 用户只能创建自己的追踪
CREATE POLICY agent_traces_insert_own ON agent_traces
FOR INSERT
WITH CHECK (user_id = current_setting('app.user_id', true));

-- UPDATE: 追踪一旦创建不可修改（审计日志）
CREATE POLICY agent_traces_update_deny ON agent_traces
FOR UPDATE
WITH CHECK (false);

-- DELETE: 追踪删除跟随会话（CASCADE）
-- 不需要单独策略，因为外键设置了 ON DELETE CASCADE

-- ============================================================
-- 5. 添加策略注释
-- ============================================================
COMMENT ON POLICY users_select_own ON users IS '用户只能查看自己的信息';
COMMENT ON POLICY users_insert_deny ON users IS '不允许普通用户创建用户（由系统创建）';
COMMENT ON POLICY users_update_own ON users IS '用户只能更新自己的信息';
COMMENT ON POLICY users_delete_deny ON users IS '用户不能删除自己的账户';

COMMENT ON POLICY sessions_select_own ON sessions IS '用户只能查看自己的会话';
COMMENT ON POLICY sessions_insert_own ON sessions IS '用户只能创建自己的会话';
COMMENT ON POLICY sessions_update_own ON sessions IS '用户只能更新自己的会话';
COMMENT ON POLICY sessions_delete_own ON sessions IS '用户只能删除自己的会话';

COMMENT ON POLICY agent_traces_select_own ON agent_traces IS '用户只能查看自己的追踪';
COMMENT ON POLICY agent_traces_insert_own ON agent_traces IS '用户只能创建自己的追踪';
COMMENT ON POLICY agent_traces_update_deny ON agent_traces IS '追踪一旦创建不可修改（审计日志）';

-- ============================================================
-- 6. 创建管理员绕过函数（可选）
-- ============================================================

-- 创建一个函数，允许管理员绕过 RLS
CREATE OR REPLACE FUNCTION app.set_admin_user(user_id text)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.user_id', user_id, true);
    PERFORM set_config('app.is_admin', 'true', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 修改策略以允许管理员绕过
DROP POLICY IF EXISTS users_select_own ON users;
CREATE POLICY users_select_own ON users
FOR SELECT
USING (
    id = current_setting('app.user_id', true)
    OR current_setting('app.is_admin', true) = 'true'
);

COMMIT;

-- ============================================================
-- 验证脚本
-- ============================================================

-- 验证 RLS 是否启用
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE tablename IN ('users', 'sessions', 'agent_traces');

-- 验证策略是否创建
-- SELECT schemaname, tablename, policyname, cmd
-- FROM pg_policies
-- WHERE tablename IN ('users', 'sessions', 'agent_traces')
-- ORDER BY tablename, policyname;

-- 测试 RLS（需要在应用层测试）
-- 1. 设置用户上下文: SET LOCAL app.user_id = 'test_user';
-- 2. 查询数据: SELECT * FROM agent_traces;
-- 3. 验证只返回该用户的数据
