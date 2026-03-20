# Multi-Tool AI Agent 数据库实施计划

> **创建日期**: 2026-03-20
> **负责人**: 数据库专家
> **项目**: Multi-Tool AI Agent
> **数据库**: PostgreSQL 16+ with JSONB
> **预计完成时间**: 1-2个月

---

## 目录

1. [概述](#概述)
2. [Schema 设计](#schema-设计)
3. [约束和索引](#约束和索引)
4. [Row Level Security](#row-level-security)
5. [迁移策略](#迁移策略)
6. [性能优化](#性能优化)
7. [监控与运维](#监控与运维)
8. [测试计划](#测试计划)
9. [风险评估](#风险评估)
10. [时间线](#时间线)

---

## 概述

### 目标

基于数据库审查反馈，实现生产级别的数据库架构，包括：

- 完整的 Schema 设计（users, sessions, agent_traces）
- 数据完整性约束（CHECK, FOREIGN KEY, UNIQUE）
- 性能优化索引（Composite, GIN, Partial, Covering）
- Row Level Security（用户隔离）
- 迁移和回滚策略

### 当前状态

| 组件 | 状态 | 评分 |
|-----|------|------|
| Schema Design | 需要改进 | 8/10 |
| Indexing | 缺失关键索引 | 5/10 |
| Constraints | 缺失约束 | 3/10 |
| Security | 无 RLS | 3/10 |
| Performance | 未优化 | 4/10 |

### 审查反馈优先级

🔴 **P0 - 立即实施**:
1. 添加 Foreign Keys（users, sessions）
2. 添加 CHECK 约束
3. 启用 Row Level Security
4. 添加 GIN 索引（JSONB 字段）

🟡 **P1 - 本周完成**:
5. 添加 Composite 索引
6. 添加 Partial 索引
7. 实现输入验证

---

## Schema 设计

### 完整 Schema

```sql
-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    email text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 用户表索引
CREATE INDEX idx_users_email ON users(email);

-- 用户表注释
COMMENT ON TABLE users IS '用户账户信息';
COMMENT ON COLUMN users.id IS '用户唯一标识符 (UUID 或自定义 ID)';
COMMENT ON COLUMN users.email IS '用户邮箱地址，用于登录和通知';

-- ============================================================
-- 2. 会话表
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text,
    last_message_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 会话表索引
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_user_last_message
ON sessions(user_id, last_message_at DESC NULLS LAST)
INCLUDE (title);

-- 会话表注释
COMMENT ON TABLE sessions IS '用户会话/对话历史';
COMMENT ON COLUMN sessions.title IS '会话标题，可由用户自定义或 AI 生成';
COMMENT ON COLUMN sessions.last_message_at IS '最后一条消息的时间戳，用于排序';

-- ============================================================
-- 3. Agent 追踪表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_traces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_input text,
    final_answer text,
    thought_chain jsonb NOT NULL DEFAULT '[]',
    tool_calls jsonb NOT NULL DEFAULT '[]',
    token_usage jsonb NOT NULL DEFAULT '{}',
    latency_ms integer NOT NULL,
    finish_reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Agent 追踪表注释
COMMENT ON TABLE agent_traces IS 'Agent 执行追踪，用于可观测性和调试';
COMMENT ON COLUMN agent_traces.thought_chain IS 'LLM 推理链，存储为 JSONB 数组';
COMMENT ON COLUMN agent_traces.tool_calls IS '工具调用记录，存储为 JSONB 数组';
COMMENT ON COLUMN agent_traces.token_usage IS 'Token 使用统计，存储为 JSONB 对象';
COMMENT ON COLUMN agent_traces.latency_ms IS '端到端延迟（毫秒）';
COMMENT ON COLUMN agent_traces.finish_reason IS '完成原因: stop, length, tool_calls, content_filter, error, interrupted';
```

### 数据关系图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────────┐
│   users     │───────│  sessions   │───────│  agent_traces   │
│             │ 1:N   │             │ 1:N   │                 │
│ - id (PK)   │       │ - id (PK)   │       │ - id (PK)       │
│ - email     │       │ - user_id   │       │ - session_id    │
│ - created_at│       │ - title     │       │ - user_id       │
│ - updated_at│       │ - last_msg  │       │ - thought_chain │
└─────────────┘       │ - created_at│       │ - tool_calls    │
                      │ - updated_at│       │ - token_usage   │
                      └─────────────┘       │ - latency_ms    │
                                            │ - finish_reason │
                                            │ - created_at    │
                                            └─────────────────┘
```

---

## 约束和索引

### 数据完整性约束

```sql
-- ============================================================
-- CHECK 约束
-- ============================================================

-- 1. 延迟必须为正数
ALTER TABLE agent_traces
ADD CONSTRAINT chk_latency_ms_positive
CHECK (latency_ms >= 0);

-- 2. 完成原因必须是有效值
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

-- 3. JSONB 字段大小限制（防止超大对象）
ALTER TABLE agent_traces
ADD CONSTRAINT chk_thought_chain_max_size
CHECK (pg_column_size(thought_chain) <= 100000); -- 100KB

ALTER TABLE agent_traces
ADD CONSTRAINT chk_tool_calls_max_size
CHECK (pg_column_size(tool_calls) <= 50000); -- 50KB

-- 4. 文本字段长度限制
ALTER TABLE agent_traces
ADD CONSTRAINT chk_user_input_max_length
CHECK (length(coalesce(user_input, '')) <= 10000); -- 10K 字符

ALTER TABLE agent_traces
ADD CONSTRAINT chk_final_answer_max_length
CHECK (length(coalesce(final_answer, '')) <= 50000); -- 50K 字符

-- 5. Token 使用不为空
ALTER TABLE agent_traces
ADD CONSTRAINT chk_token_usage_not_empty
CHECK (token_usage::text != '{}' AND token_usage IS NOT NULL);

-- ============================================================
-- 唯一约束
-- ============================================================

-- 防止同一会话在同一时间产生重复 trace
CREATE UNIQUE INDEX idx_agent_traces_session_created_unique
ON agent_traces(session_id, created_at DESC, id);
```

### 性能优化索引

```sql
-- ============================================================
-- Composite Indexes（复合索引）
-- ============================================================

-- 1. 用户会话历史查询（高频）
-- 查询模式: WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

-- 2. 会话追踪分页查询（高频）
-- 查询模式: WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
CREATE INDEX idx_agent_traces_session_created
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

-- 3. 用户时间范围查询（中频）
-- 查询模式: WHERE user_id = ? AND created_at > ? ORDER BY created_at DESC
CREATE INDEX idx_agent_traces_user_created
ON agent_traces(user_id, created_at DESC);

-- ============================================================
-- GIN Indexes（JSONB 字段索引）
-- ============================================================

-- 1. 工具调用查询（高频）
-- 查询模式: WHERE tool_calls @> '[{"name": "web_search"}]'
CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

-- 2. 推理链查询（中频）
-- 查询模式: WHERE thought_chain @> '{"step": "planning"}'
CREATE INDEX idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);

-- 3. Token 使用查询（低频）
-- 查询模式: WHERE token_usage->>'total_tokens'::int > 5000
CREATE INDEX idx_agent_traces_token_usage
ON agent_traces USING GIN (token_usage);

-- 4. 优化的 GIN 索引（仅支持 @> 操作符，索引更小）
CREATE INDEX idx_agent_traces_tool_calls_path
ON agent_traces USING GIN (tool_calls jsonb_path_ops);

-- ============================================================
-- Partial Indexes（部分索引）
-- ============================================================

-- 1. 错误追踪查询（低频但重要）
-- 查询模式: WHERE finish_reason IN ('error', 'length', 'content_filter')
CREATE INDEX idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

-- 2. 高延迟查询（性能监控）
-- 查询模式: WHERE latency_ms > 10000 ORDER BY latency_ms DESC
CREATE INDEX idx_agent_traces_high_latency
ON agent_traces(user_id, latency_ms DESC, created_at DESC)
WHERE latency_ms > 10000; -- > 10 秒

-- 3. 近期会话查询（时间序列优化）
-- 查询模式: WHERE created_at > NOW() - INTERVAL '90 days'
CREATE INDEX idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '90 days';

-- ============================================================
-- Covering Indexes（覆盖索引）
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
```

### 索引使用验证

```sql
-- 检查索引使用统计
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename IN ('agent_traces', 'sessions', 'users')
ORDER BY idx_scan DESC;

-- 查找未使用的索引（可在 1 周后删除）
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey%'
  AND schemaname = 'public'
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC;
```

---

## Row Level Security

### RLS 策略

```sql
-- ============================================================
-- 启用 RLS
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Users 表策略
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

-- ============================================================
-- Sessions 表策略
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
-- Agent Traces 表策略
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
-- 不需要单独策略
```

### 应用层集成

```python
# ============================================================
-- Python FastAPI 中间件
-- ============================================================

from fastapi import Request
from psycopg import AsyncConnection
from typing import AsyncGenerator

async def set_user_context(conn: AsyncConnection, user_id: str) -> None:
    """为数据库连接设置用户上下文"""
    await conn.execute(
        "SET LOCAL app.user_id = $1",
        (user_id,)
    )

async def get_db_with_user_context(
    request: Request
) -> AsyncGenerator[AsyncConnection, None]:
    """获取带有用户上下文的数据库连接"""
    user_id = request.state.user_id  # 从 JWT 解码获得

    async with pool.connection() as conn:
        await set_user_context(conn, user_id)
        yield conn

# ============================================================
-- 使用示例
-- ============================================================

from fastapi import Depends
from pydantic import BaseModel

class TraceCreate(BaseModel):
    session_id: str
    user_input: str
    # ... 其他字段

@app.post("/api/traces")
async def create_trace(
    trace: TraceCreate,
    db: AsyncConnection = Depends(get_db_with_user_context)
):
    """创建 Agent 追踪

    注意：user_id 会从 JWT token 中自动提取，
    并通过 RLS 策略确保用户只能创建自己的追踪。
    """
    query = """
        INSERT INTO agent_traces (session_id, user_id, user_input, ...)
        VALUES ($1, current_setting('app.user_id', true), $2, ...)
        RETURNING *
    """
    result = await db.execute(query, trace.session_id, trace.user_input, ...)
    return result.fetchone()
```

---

## 迁移策略

### 迁移文件结构

```
supabase/migrations/
├── 001_initial_schema.sql              # 初始 Schema（LangGraph 自动创建）
├── 002_create_users_and_sessions.sql   # 创建 users 和 sessions 表
├── 003_add_constraints.sql             # 添加约束
├── 004_add_indexes.sql                 # 添加索引
├── 005_enable_rls.sql                  # 启用 RLS
└── rollback/
    ├── 002_rollback.sql
    ├── 003_rollback.sql
    ├── 004_rollback.sql
    └── 005_rollback.sql
```

### 迁移脚本

#### `002_create_users_and_sessions.sql`

```sql
-- ============================================================
-- Migration: 002_create_users_and_sessions
-- Description: 创建 users 和 sessions 表，添加外键
-- ============================================================

BEGIN;

-- 创建 users 表
CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    email text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 创建 sessions 表
CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text,
    last_message_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 为现有数据创建默认用户（用于迁移）
INSERT INTO users (id, email)
VALUES ('dev_user', 'dev@example.com')
ON CONFLICT (id) DO NOTHING;

-- 为现有 agent_traces 添加外键（如果已存在数据）
-- 注意：这需要先确保所有 user_id 都在 users 表中
ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_session
FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;

-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

COMMIT;
```

#### `003_add_constraints.sql`

```sql
-- ============================================================
-- Migration: 003_add_constraints
-- Description: 添加数据完整性约束
-- ============================================================

BEGIN;

-- 延迟必须为正数
ALTER TABLE agent_traces
ADD CONSTRAINT chk_latency_ms_positive
CHECK (latency_ms >= 0);

-- 完成原因必须是有效值
ALTER TABLE agent_traces
ADD CONSTRAINT chk_finish_reason_valid
CHECK (
    finish_reason IN (
        'stop', 'length', 'tool_calls',
        'content_filter', 'error', 'interrupted'
    )
);

-- JSONB 字段大小限制
ALTER TABLE agent_traces
ADD CONSTRAINT chk_thought_chain_max_size
CHECK (pg_column_size(thought_chain) <= 100000);

ALTER TABLE agent_traces
ADD CONSTRAINT chk_tool_calls_max_size
CHECK (pg_column_size(tool_calls) <= 50000);

-- 文本字段长度限制
ALTER TABLE agent_traces
ADD CONSTRAINT chk_user_input_max_length
CHECK (length(coalesce(user_input, '')) <= 10000);

ALTER TABLE agent_traces
ADD CONSTRAINT chk_final_answer_max_length
CHECK (length(coalesce(final_answer, '')) <= 50000);

-- Token 使用不为空
ALTER TABLE agent_traces
ADD CONSTRAINT chk_token_usage_not_empty
CHECK (token_usage::text != '{}' AND token_usage IS NOT NULL);

COMMIT;
```

#### `004_add_indexes.sql`

```sql
-- ============================================================
-- Migration: 004_add_indexes
-- Description: 添加性能优化索引
-- ============================================================

BEGIN;

-- 删除旧索引（如果存在）
DROP INDEX IF EXISTS idx_agent_traces_session;
DROP INDEX IF EXISTS idx_agent_traces_user;

-- Composite Indexes
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

CREATE INDEX idx_agent_traces_session_created
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

CREATE INDEX idx_agent_traces_user_created
ON agent_traces(user_id, created_at DESC);

-- GIN Indexes
CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

CREATE INDEX idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);

CREATE INDEX idx_agent_traces_token_usage
ON agent_traces USING GIN (token_usage);

CREATE INDEX idx_agent_traces_tool_calls_path
ON agent_traces USING GIN (tool_calls jsonb_path_ops);

-- Partial Indexes
CREATE INDEX idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

CREATE INDEX idx_agent_traces_high_latency
ON agent_traces(user_id, latency_ms DESC, created_at DESC)
WHERE latency_ms > 10000;

CREATE INDEX idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '90 days';

-- Covering Index
CREATE INDEX idx_agent_traces_user_session_covering
ON agent_traces(user_id, session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason, thought_chain, tool_calls);

-- Unique Index
CREATE UNIQUE INDEX idx_agent_traces_session_created_unique
ON agent_traces(session_id, created_at DESC, id);

-- Sessions 索引
CREATE INDEX idx_sessions_user_last_message
ON sessions(user_id, last_message_at DESC NULLS LAST)
INCLUDE (title);

COMMIT;
```

#### `005_enable_rls.sql`

```sql
-- ============================================================
-- Migration: 005_enable_rls
-- Description: 启用 Row Level Security
-- ============================================================

BEGIN;

-- 启用 RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- Users 表策略
CREATE POLICY users_select_own ON users
FOR SELECT
USING (id = current_setting('app.user_id', true));

CREATE POLICY users_insert_deny ON users
FOR INSERT
WITH CHECK (false);

CREATE POLICY users_update_own ON users
FOR UPDATE
USING (id = current_setting('app.user_id', true));

-- Sessions 表策略
CREATE POLICY sessions_select_own ON sessions
FOR SELECT
USING (user_id = current_setting('app.user_id', true));

CREATE POLICY sessions_insert_own ON sessions
FOR INSERT
WITH CHECK (user_id = current_setting('app.user_id', true));

CREATE POLICY sessions_update_own ON sessions
FOR UPDATE
USING (user_id = current_setting('app.user_id', true));

CREATE POLICY sessions_delete_own ON sessions
FOR DELETE
USING (user_id = current_setting('app.user_id', true));

-- Agent Traces 表策略
CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT
USING (user_id = current_setting('app.user_id', true));

CREATE POLICY agent_traces_insert_own ON agent_traces
FOR INSERT
WITH CHECK (user_id = current_setting('app.user_id', true));

CREATE POLICY agent_traces_update_deny ON agent_traces
FOR UPDATE
WITH CHECK (false);

COMMIT;
```

### 回滚脚本

#### `rollback/002_rollback.sql`

```sql
BEGIN;

-- 删除外键
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS fk_agent_traces_session,
DROP CONSTRAINT IF EXISTS fk_agent_traces_user;

-- 删除表
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS users;

COMMIT;
```

#### `rollback/003_rollback.sql`

```sql
BEGIN;

-- 删除约束
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS chk_token_usage_not_empty,
DROP CONSTRAINT IF EXISTS chk_final_answer_max_length,
DROP CONSTRAINT IF EXISTS chk_user_input_max_length,
DROP CONSTRAINT IF EXISTS chk_tool_calls_max_size,
DROP CONSTRAINT IF EXISTS chk_thought_chain_max_size,
DROP CONSTRAINT IF EXISTS chk_finish_reason_valid,
DROP CONSTRAINT IF EXISTS chk_latency_ms_positive;

COMMIT;
```

#### `rollback/004_rollback.sql`

```sql
BEGIN;

-- 删除索引
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

-- 重建旧索引
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user ON agent_traces(user_id);

COMMIT;
```

#### `rollback/005_rollback.sql`

```sql
BEGIN;

-- 删除策略
DROP POLICY IF EXISTS agent_traces_update_deny ON agent_traces;
DROP POLICY IF EXISTS agent_traces_insert_own ON agent_traces;
DROP POLICY IF EXISTS agent_traces_select_own ON agent_traces;

DROP POLICY IF EXISTS sessions_delete_own ON sessions;
DROP POLICY IF EXISTS sessions_update_own ON sessions;
DROP POLICY IF EXISTS sessions_insert_own ON sessions;
DROP POLICY IF EXISTS sessions_select_own ON sessions;

DROP POLICY IF EXISTS users_update_own ON users;
DROP POLICY IF EXISTS users_insert_deny ON users;
DROP POLICY IF EXISTS users_select_own ON users;

-- 禁用 RLS
ALTER TABLE agent_traces DISABLE ROW LEVEL SECURITY;
ALTER TABLE sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;

COMMIT;
```

---

## 性能优化

### 连接池配置

```python
# ============================================================
-- 连接池配置
-- ============================================================

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

# 开发环境
DEV_POOL_CONFIG = {
    "min_size": 2,
    "max_size": 10,
    "timeout": 30,
    "max_inactive": 300,
    "kwargs": {
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
        "options": "-c statement_timeout=30000"  # 30s 查询超时
    }
}

# 生产环境
PROD_POOL_CONFIG = {
    "min_size": 5,
    "max_size": 20,
    "timeout": 30,
    "max_inactive": 300,
    "kwargs": {
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
        "options": "-c statement_timeout=30000"
    }
}

# 高流量环境
HIGH_TRAFFIC_POOL_CONFIG = {
    "min_size": 10,
    "max_size": 50,
    "timeout": 30,
    "max_inactive": 300,
    "kwargs": {
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
        "options": "-c statement_timeout=30000"
    }
}

# 创建连接池
pool = AsyncConnectionPool(
    DATABASE_URL,
    **PROD_POOL_CONFIG
)

# 创建 Checkpointer 和 Store
checkpointer = AsyncPostgresSaver.from_conn_string(
    DATABASE_URL,
    pool=pool,
    connection_kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    }
)

store = AsyncPostgresStore.from_conn_string(
    DATABASE_URL,
    pool=pool,
    connection_kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    }
)
```

### 查询优化

```sql
-- ============================================================
-- 常见查询模式优化
-- ============================================================

-- 1. 会话历史查询（使用覆盖索引）
-- 使用 idx_agent_traces_session_created (INCLUDE final_answer, latency_ms, finish_reason)
SELECT final_answer, latency_ms, finish_reason
FROM agent_traces
WHERE session_id = $1
ORDER BY created_at DESC
LIMIT 20;

-- 2. 用户会话列表（使用会话表索引）
-- 使用 idx_sessions_user_last_message
SELECT id, title, last_message_at
FROM sessions
WHERE user_id = $1
ORDER BY last_message_at DESC NULLS LAST
LIMIT 20;

-- 3. 工具使用分析（使用 GIN 索引）
-- 使用 idx_agent_traces_tool_calls
SELECT
    jsonb_array_elements(tool_calls)->>'name' as tool_name,
    count(*) as usage_count,
    avg(latency_ms) as avg_latency_ms
FROM agent_traces
WHERE user_id = $1
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY tool_name
ORDER BY usage_count DESC;

-- 4. 错误分析（使用部分索引）
-- 使用 idx_agent_traces_errors
SELECT *
FROM agent_traces
WHERE user_id = $1
  AND finish_reason IN ('error', 'length', 'content_filter')
ORDER BY created_at DESC
LIMIT 50;

-- 5. 高延迟查询（使用部分索引）
-- 使用 idx_agent_traces_high_latency
SELECT *
FROM agent_traces
WHERE user_id = $1
  AND latency_ms > 10000
ORDER BY latency_ms DESC
LIMIT 20;
```

### TOAST 配置

```sql
-- ============================================================
-- TOAST 配置（大字段压缩）
-- ============================================================

-- 调整 JSONB 字段的 TOAST 阈值
ALTER TABLE agent_traces
ALTER COLUMN thought_chain SET (storage = EXTENDED);
ALTER TABLE agent_traces
ALTER COLUMN tool_calls SET (storage = EXTENDED);
ALTER TABLE agent_traces
ALTER COLUMN user_input SET (storage = EXTENDED);
ALTER TABLE agent_traces
ALTER COLUMN final_answer SET (storage = EXTENDED);

-- 监控 TOAST 表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as toast_size
FROM pg_tables
WHERE tablename = 'agent_traces';
```

---

## 监控与运维

### 查询性能监控

```sql
-- ============================================================
-- 启用 pg_stat_statements
-- ============================================================

-- 在 postgresql.conf 中添加：
-- shared_preload_libraries = 'pg_stat_statements'

-- 查找慢查询
SELECT
    query,
    calls,
    total_exec_time / 1000 as total_seconds,
    mean_exec_time as avg_ms,
    max_exec_time as max_ms,
    stddev_exec_time as stddev_ms
FROM pg_stat_statements
WHERE query LIKE '%agent_traces%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 分析特定查询
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT * FROM agent_traces
WHERE user_id = 'user_123'
  AND session_id = 'session_456'
ORDER BY created_at DESC
LIMIT 20;
```

### 表大小监控

```sql
-- ============================================================
-- 监控表和索引大小
-- ============================================================

-- 查看表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE tablename LIKE '%agent%' OR tablename LIKE '%store%' OR tablename LIKE '%checkpoint%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 监控膨胀（需要 VACUUM 的表）
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(bloat_size) as bloat_size
FROM (
    SELECT
        schemaname,
        tablename,
        pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename) as bloat_size
    FROM pg_tables
    WHERE schemaname = 'public'
) bloat
ORDER BY bloat_size DESC;
```

### 自动化维护

```sql
-- ============================================================
-- 自动化维护任务
-- ============================================================

-- 配置自动清理
ALTER TABLE agent_traces SET (
    autovacuum_vacuum_scale_factor = 0.1,     -- 10% 变化时触发
    autovacuum_analyze_scale_factor = 0.05,   -- 5% 变化时触发分析
    autovacuum_vacuum_threshold = 100,        -- 最少 100 条
    autovacuum_analyze_threshold = 50         -- 最少 50 条
);

-- 配置自动清理（会话表）
ALTER TABLE sessions SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- 手动运行 VACUUM ANALYZE（维护窗口）
VACUUM ANALYZE agent_traces;
VACUUM ANALYZE sessions;
VACUUM ANALYZE users;
```

---

## 测试计划

### 单元测试

```python
# ============================================================
-- 数据库单元测试
-- ============================================================

import pytest
from httpx import AsyncClient

class TestDatabaseSchema:
    """测试数据库 Schema"""

    async def test_users_table_exists(self, db_connection):
        """测试 users 表是否存在"""
        result = await db_connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            )
        """)
        assert result is True

    async def test_users_constraints(self, db_connection):
        """测试 users 表约束"""
        # 测试唯一约束
        with pytest.raises(Exception):
            await db_connection.execute("""
                INSERT INTO users (id, email)
                VALUES ('test1', 'test@example.com'),
                       ('test2', 'test@example.com')
            """)

    async def test_sessions_foreign_key(self, db_connection):
        """测试 sessions 外键约束"""
        # 测试级联删除
        user_id = 'test_fk_user'
        await db_connection.execute("""
            INSERT INTO users (id, email)
            VALUES ($1, 'fk@example.com')
        """, user_id)

        await db_connection.execute("""
            INSERT INTO sessions (id, user_id, title)
            VALUES ('test_session', $1, 'Test Session')
        """, user_id)

        # 删除用户应该级联删除会话
        await db_connection.execute("""
            DELETE FROM users WHERE id = $1
        """, user_id)

        count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM sessions WHERE user_id = $1
        """, user_id)
        assert count == 0

class TestDatabaseIndexes:
    """测试数据库索引"""

    async def test_index_exists(self, db_connection):
        """测试索引是否存在"""
        indexes = [
            'idx_agent_traces_user_session_created',
            'idx_agent_traces_tool_calls',
            'idx_agent_traces_thought_chain',
            'idx_sessions_user_last_message'
        ]

        for index_name in indexes:
            result = await db_connection.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = $1
                )
            """, index_name)
            assert result is True, f"Index {index_name} not found"

class TestRowLevelSecurity:
    """测试 Row Level Security"""

    async def test_user_isolation(self, db_connection, auth_headers_user1, auth_headers_user2):
        """测试用户隔离"""
        # 用户 1 创建会话
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/sessions",
                json={"title": "User 1 Session"},
                headers=auth_headers_user1
            )
            assert response.status_code == 200
            session_id = response.json()["id"]

        # 用户 2 不应该能访问用户 1 的会话
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                f"/api/sessions/{session_id}",
                headers=auth_headers_user2
            )
            assert response.status_code == 404

class TestDatabasePerformance:
    """测试数据库性能"""

    async def test_query_performance(self, db_connection):
        """测试查询性能"""
        import time

        # 准备测试数据
        user_id = 'perf_test_user'
        await db_connection.execute("""
            INSERT INTO users (id, email) VALUES ($1, 'perf@example.com')
        """, user_id)

        session_id = 'perf_test_session'
        await db_connection.execute("""
            INSERT INTO sessions (id, user_id, title)
            VALUES ($1, $2, 'Performance Test')
        """, session_id, user_id)

        # 插入 1000 条追踪记录
        for i in range(1000):
            await db_connection.execute("""
                INSERT INTO agent_traces
                (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, session_id, user_id, f'Input {i}', f'Answer {i}', 1000, 'stop')

        # 测试查询性能
        start = time.time()
        result = await db_connection.fetch("""
            SELECT * FROM agent_traces
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT 20
        """, session_id)
        elapsed = time.time() - start

        assert len(result) == 20
        assert elapsed < 0.1  # 应该在 100ms 内完成
```

### 集成测试

```python
# ============================================================
-- 数据库集成测试
-- ============================================================

class TestDatabaseIntegration:
    """数据库集成测试"""

    async def test_full_agent_execution_flow(self, db_connection, auth_headers):
        """测试完整的 Agent 执行流程"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. 创建会话
            response = await client.post(
                "/api/sessions",
                json={"title": "Integration Test Session"},
                headers=auth_headers
            )
            assert response.status_code == 200
            session_id = response.json()["id"]

            # 2. 发送消息
            response = await client.post(
                f"/api/sessions/{session_id}/messages",
                json={"content": "What's the weather today?"},
                headers=auth_headers
            )
            assert response.status_code == 200

            # 3. 验证追踪记录已创建
            traces = await db_connection.fetch("""
                SELECT * FROM agent_traces
                WHERE session_id = $1
                ORDER BY created_at DESC
            """, session_id)
            assert len(traces) > 0

            # 4. 验证追踪数据完整性
            trace = traces[0]
            assert trace['user_input'] == "What's the weather today?"
            assert trace['finish_reason'] in ('stop', 'tool_calls')
            assert trace['latency_ms'] >= 0
            assert trace['tool_calls'] != '[]'
```

### 性能测试

```python
# ============================================================
-- 数据库性能测试
-- ============================================================

import asyncio
from locust import HttpUser, task, between

class DatabaseLoadTest(HttpUser):
    """数据库负载测试"""
    wait_time = between(1, 3)

    def on_start(self):
        """初始化：创建用户和会话"""
        response = self.client.post("/api/auth/register", json={
            "email": f"user{self.user_id}@example.com",
            "password": "password123"
        })
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 创建会话
        response = self.client.post("/api/sessions", json={
            "title": f"Load Test Session {self.user_id}"
        }, headers=self.headers)
        self.session_id = response.json()["id"]

    @task(3)
    def send_message(self):
        """发送消息（高频操作）"""
        self.client.post(
            f"/api/sessions/{self.session_id}/messages",
            json={"content": "Hello, how are you?"},
            headers=self.headers
        )

    @task(1)
    def get_history(self):
        """获取历史记录（低频操作）"""
        self.client.get(
            f"/api/sessions/{self.session_id}/traces",
            headers=self.headers
        )
```

---

## 风险评估

### 潜在风险

| 风险 | 影响 | 概率 | 缓解措施 |
|-----|------|------|----------|
| 迁移失败导致数据丢失 | 高 | 低 | 完整的回滚脚本，迁移前备份 |
| 索引过多影响写入性能 | 中 | 中 | 监控索引使用情况，删除未使用索引 |
| RLS 策略错误导致权限问题 | 高 | 中 | 充分测试，开发环境先验证 |
| JSONB 字段过大影响性能 | 中 | 高 | 添加大小限制约束，监控 TOAST |
| 并发写入导致锁竞争 | 中 | 低 | 连接池配置，监控锁等待 |

### 回滚计划

```sql
-- ============================================================
-- 紧急回滚步骤
-- ============================================================

-- 1. 立即禁用 RLS（如果导致权限问题）
ALTER TABLE agent_traces DISABLE ROW LEVEL SECURITY;
ALTER TABLE sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;

-- 2. 删除问题索引（如果导致性能问题）
DROP INDEX IF EXISTS idx_agent_traces_tool_calls;
DROP INDEX IF EXISTS idx_agent_traces_thought_chain;

-- 3. 放宽约束（如果导致写入失败）
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS chk_thought_chain_max_size;

ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS chk_tool_calls_max_size;

-- 4. 完整回滚（执行回滚脚本）
-- \i supabase/migrations/rollback/005_rollback.sql
-- \i supabase/migrations/rollback/004_rollback.sql
-- \i supabase/migrations/rollback/003_rollback.sql
-- \i supabase/migrations/rollback/002_rollback.sql
```

---

## 时间线

### Phase 1: 基础 Schema（Week 1）

| 任务 | 负责人 | 预计时间 | 状态 |
|-----|-------|----------|------|
| 创建 users 表 | 数据库专家 | 2小时 | ⏳ 待开始 |
| 创建 sessions 表 | 数据库专家 | 2小时 | ⏳ 待开始 |
| 添加外键约束 | 数据库专家 | 2小时 | ⏳ 待开始 |
| 编写迁移脚本 | 数据库专家 | 4小时 | ⏳ 待开始 |
| 单元测试 | QA | 4小时 | ⏳ 待开始 |

### Phase 2: 约束和索引（Week 2）

| 任务 | 负责人 | 预计时间 | 状态 |
|-----|-------|----------|------|
| 添加 CHECK 约束 | 数据库专家 | 4小时 | ⏳ 待开始 |
| 添加 Composite 索引 | 数据库专家 | 4小时 | ⏳ 待开始 |
| 添加 GIN 索引 | 数据库专家 | 4小时 | ⏳ 待开始 |
| 添加 Partial 索引 | 数据库专家 | 2小时 | ⏳ 待开始 |
| 性能测试 | QA | 8小时 | ⏳ 待开始 |

### Phase 3: Row Level Security（Week 3）

| 任务 | 负责人 | 预计时间 | 状态 |
|-----|-------|----------|------|
| 启用 RLS | 数据库专家 | 4小时 | ⏳ 待开始 |
| 创建 RLS 策略 | 数据库专家 | 6小时 | ⏳ 待开始 |
| 应用层集成 | 后端开发 | 8小时 | ⏳ 待开始 |
| 安全测试 | QA | 8小时 | ⏳ 待开始 |

### Phase 4: 优化和监控（Week 4）

| 任务 | 负责人 | 预计时间 | 状态 |
|-----|-------|----------|------|
| 连接池配置 | 后端开发 | 4小时 | ⏳ 待开始 |
| 查询优化 | 数据库专家 | 8小时 | ⏳ 待开始 |
| 监控配置 | DevOps | 8小时 | ⏳ 待开始 |
| 负载测试 | QA | 12小时 | ⏳ 待开始 |

---

## 附录

### A. 完整迁移脚本

见 `supabase/migrations/` 目录。

### B. 性能测试查询

```sql
-- 测试 1: 会话历史查询性能
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM agent_traces
WHERE session_id = 'test_session'
ORDER BY created_at DESC
LIMIT 20;

-- 测试 2: 用户会话列表查询性能
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM sessions
WHERE user_id = 'test_user'
ORDER BY last_message_at DESC NULLS LAST
LIMIT 20;

-- 测试 3: 工具使用分析查询性能
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    jsonb_array_elements(tool_calls)->>'name' as tool_name,
    count(*)
FROM agent_traces
WHERE user_id = 'test_user'
GROUP BY tool_name;

-- 测试 4: GIN 索引查询性能
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM agent_traces
WHERE tool_calls @> '[{"name": "web_search"}]';
```

### C. 监控仪表板配置

```yaml
# Grafana 仪表板配置
dashboard:
  title: "Multi-Tool Agent Database"
  panels:
    - title: "Query Latency"
      query: |
        SELECT
            mean_exec_time as avg_latency_ms
        FROM pg_stat_statements
        WHERE query LIKE '%agent_traces%'

    - title: "Table Sizes"
      query: |
        SELECT
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE tablename LIKE '%agent%'

    - title: "Index Usage"
      query: |
        SELECT
            indexname,
            idx_scan as scans
        FROM pg_stat_user_indexes
        WHERE tablename = 'agent_traces'
        ORDER BY idx_scan DESC

    - title: "Connection Pool"
      query: |
        SELECT
            count(*) as active_connections,
            count(*) FILTER (WHERE state = 'active') as active_queries
        FROM pg_stat_activity
        WHERE datname = current_database()
```

---

**文档版本**: 1.0
**最后更新**: 2026-03-20
**下一步**: 开始 Phase 1 - 基础 Schema 实施
