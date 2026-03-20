-- ============================================================
-- Migration: 002_create_users_and_sessions
-- Description: 创建 users 和 sessions 表，添加外键
-- Author: Database Expert
-- Date: 2026-03-20
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 创建 users 表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    email text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. 创建 sessions 表
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text,
    last_message_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. 为现有数据创建默认用户（用于迁移）
-- ============================================================
INSERT INTO users (id, email)
VALUES ('dev_user', 'dev@example.com')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 4. 为现有 agent_traces 添加外键
-- ============================================================
-- 注意：如果 agent_traces 已存在数据，需要先确保所有 user_id 都在 users 表中

-- 添加用户外键
ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 添加会话外键
-- 注意：如果 agent_traces 引用的 session_id 不在 sessions 表中，需要先创建
DO $$
DECLARE
    distinct_session RECORD;
BEGIN
    -- 为 agent_traces 中存在但 sessions 中不存在的 session_id 创建会话记录
    FOR distinct_session IN
        SELECT DISTINCT session_id, user_id
        FROM agent_traces
        WHERE session_id NOT IN (SELECT id FROM sessions)
    LOOP
        INSERT INTO sessions (id, user_id, title)
        VALUES (distinct_session.session_id, distinct_session.user_id, 'Migrated Session')
        ON CONFLICT (id) DO NOTHING;
    END LOOP;
END $$;

ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_session
FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;

-- ============================================================
-- 5. 创建索引
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- ============================================================
-- 6. 添加表注释
-- ============================================================
COMMENT ON TABLE users IS '用户账户信息';
COMMENT ON COLUMN users.id IS '用户唯一标识符 (UUID 或自定义 ID)';
COMMENT ON COLUMN users.email IS '用户邮箱地址，用于登录和通知';

COMMENT ON TABLE sessions IS '用户会话/对话历史';
COMMENT ON COLUMN sessions.id IS '会话唯一标识符';
COMMENT ON COLUMN sessions.user_id IS '关联的用户 ID';
COMMENT ON COLUMN sessions.title IS '会话标题，可由用户自定义或 AI 生成';
COMMENT ON COLUMN sessions.last_message_at IS '最后一条消息的时间戳，用于排序';

COMMIT;

-- ============================================================
-- 验证脚本
-- ============================================================
-- 验证表是否创建成功
-- SELECT tablename FROM pg_tables WHERE tablename IN ('users', 'sessions');

-- 验证外键是否创建成功
-- SELECT conname FROM pg_constraint WHERE conname LIKE 'fk_agent_traces%';

-- 验证索引是否创建成功
-- SELECT indexname FROM pg_indexes WHERE indexname LIKE 'idx_users_%' OR indexname LIKE 'idx_sessions_%';
