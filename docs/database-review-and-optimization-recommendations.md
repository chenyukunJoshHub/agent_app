# Multi-Tool AI Agent Database Design Review & Optimization Recommendations

> **Review Date**: 2026-03-20
> **Reviewer**: PostgreSQL Database Specialist
> **Project**: Multi-Tool AI Agent (LangChain/LangGraph-based)
> **Database**: PostgreSQL (via Supabase)

---

## Executive Summary

This database design is **well-architected for its use case** with proper separation of concerns between short-term memory (checkpoints), long-term memory (store), and observability (agent_traces). However, there are **critical performance and scalability improvements** needed for production readiness.

**Overall Assessment**: 7/10
- Schema Design: 8/10 (good separation, proper types)
- Indexing: 5/10 (missing critical indexes, no GIN indexes)
- Data Isolation: 9/10 (excellent namespace design)
- Performance: 4/10 (jsonb fields unoptimized, no query patterns analyzed)
- Scalability: 6/10 (good foundation, missing partitioning/archiving)
- Security: 3/10 (no RLS, no constraints mentioned)

**Critical Priority Items**:
1. Add GIN indexes for jsonb fields (HIGH)
2. Implement composite indexes for common query patterns (HIGH)
3. Add database constraints and foreign keys (CRITICAL)
4. Implement Row Level Security (CRITICAL)
5. Add data retention policies (HIGH)
6. Create proper migration system (HIGH)

---

## 1. Schema Design Review

### 1.1 Current Schema Analysis

#### **Checkpoint Tables (LangGraph Auto-Created)** ✅
```sql
-- Framework-managed, no manual intervention needed
checkpoints
checkpoint_blobs
checkpoint_writes
checkpoint_migrations
```

**Assessment**: Excellent. LangGraph handles these correctly with:
- Proper versioning (parent_id chaining for HIL resume)
- Appropriate data types (JSONB for state)
- Automatic migration management

**Recommendations**: None - framework-managed

---

#### **Store Table (LangGraph Auto-Created)** ✅
```sql
-- Framework-managed key-value store
store (
  namespace tuple[],
  key text,
  value jsonb
)
```

**Assessment**: Good design for flexible long-term memory storage.

**Recommendations**:
- Monitor table size - consider partitioning by namespace if > 10M rows
- Add partial indexes for frequently accessed namespaces (see §2.2)

---

#### **Agent Traces Table (Manual)** ⚠️
```sql
CREATE TABLE IF NOT EXISTS agent_traces (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    text        NOT NULL,
    user_id       text        NOT NULL DEFAULT 'dev_user',
    user_input    text,
    final_answer  text,
    thought_chain jsonb       NOT NULL DEFAULT '[]',
    tool_calls    jsonb       NOT NULL DEFAULT '[]',
    token_usage   jsonb       NOT NULL DEFAULT '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user ON agent_traces(user_id);
```

**Critical Issues**:

1. **Missing Foreign Keys** (CRITICAL)
   ```sql
   -- Current: No relationship to users or sessions
   -- Recommended:
   ALTER TABLE agent_traces
   ADD CONSTRAINT fk_agent_traces_user
   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

   ALTER TABLE agent_traces
   ADD CONSTRAINT fk_agent_traces_session
   FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;
   ```

2. **Missing Constraints** (HIGH)
   ```sql
   -- Add data integrity constraints
   ALTER TABLE agent_traces
   ADD CONSTRAINT chk_latency_ms_positive CHECK (latency_ms >= 0),
   ADD CONSTRAINT chk_finish_reason_valid
   CHECK (finish_reason IN ('stop', 'length', 'tool_calls', 'content_filter', 'error', 'interrupted')),
   ADD CONSTRAINT chk_token_usage_not_empty CHECK (token_usage::text != '{}');
   ```

3. **Missing Unique Constraints** (MEDIUM)
   ```sql
   -- Prevent duplicate traces within same session
   CREATE UNIQUE INDEX idx_agent_traces_session_created
   ON agent_traces(session_id, created_at DESC);
   ```

4. **Text Fields Without Length Limits** (LOW)
   - `user_input`, `final_answer` are unbounded `text`
   - Consider adding CHECK constraints for max length:
   ```sql
   ALTER TABLE agent_traces
   ADD CONSTRAINT chk_user_input_max_length CHECK (length(user_input) <= 10000),
   ADD CONSTRAINT chk_final_answer_max_length CHECK (length(final_answer) <= 50000);
   ```

---

### 1.2 Recommended Schema Improvements

#### **Add Users Table** (CRITICAL)
```sql
CREATE TABLE IF NOT EXISTS users (
    id        text PRIMARY KEY,  -- Using text to match current user_id type
    email     text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Index for email lookups
CREATE INDEX idx_users_email ON users(email);
```

#### **Add Sessions Table** (HIGH)
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id             text PRIMARY KEY,  -- Using text to match session_id
    user_id        text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title          text,  -- Optional session title
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz
);

-- Index for user's sessions
CREATE INDEX idx_sessions_user_created ON sessions(user_id, created_at DESC);
```

#### **Improved Agent Traces Table**
```sql
-- Drop existing indexes first
DROP INDEX IF EXISTS idx_agent_traces_session;
DROP INDEX IF EXISTS idx_agent_traces_user;

-- Add foreign keys and constraints
ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
ADD CONSTRAINT fk_agent_traces_session
FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
ADD CONSTRAINT chk_latency_ms_positive CHECK (latency_ms >= 0),
ADD CONSTRAINT chk_finish_reason_valid
CHECK (finish_reason IN ('stop', 'length', 'tool_calls', 'content_filter', 'error', 'interrupted'));

-- Create better composite indexes (see §2.3)
```

---

## 2. Index Design Review

### 2.1 Current Indexes

```sql
-- Current indexes
idx_agent_traces_session ON agent_traces(session_id)
idx_agent_traces_user ON agent_traces(user_id)
```

**Assessment**: Basic but insufficient for production workloads.

**Missing Indexes**:
- No composite indexes for common query patterns
- No GIN indexes for jsonb fields
- No time-based indexes for analytics queries
- No partial indexes for common filters

---

### 2.2 Recommended Indexes

#### **Composite Indexes** (HIGH)
```sql
-- For "user's session history" queries
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

-- For "session traces with pagination" queries
CREATE INDEX idx_agent_traces_session_created
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

-- For "analytics by time range" queries
CREATE INDEX idx_agent_traces_user_created
ON agent_traces(user_id, created_at DESC);

-- For "error analysis" queries
CREATE INDEX idx_agent_traces_finish_reason
ON agent_traces(finish_reason, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');
```

**Why Composite Indexes?**
- Covering indexes (`INCLUDE`) avoid table lookups
- Column order matters: equality columns first, then range columns
- `(user_id, session_id, created_at)` supports: `WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC`

---

#### **GIN Indexes for JSONB** (CRITICAL)
```sql
-- For querying tool_calls jsonb array
CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

-- For querying token_usage jsonb object
CREATE INDEX idx_agent_traces_token_usage
ON agent_traces USING GIN (token_usage);

-- For querying thought_chain jsonb array
CREATE INDEX idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);

-- More efficient GIN index with jsonb_path_ops (for contains queries only)
CREATE INDEX idx_agent_traces_tool_calls_path
ON agent_traces USING GIN (tool_calls jsonb_path_ops);
```

**Query Patterns Enabled**:
```sql
-- Find sessions that used a specific tool
SELECT * FROM agent_traces
WHERE tool_calls @> '[{"name": "web_search"}]';

-- Find high token usage traces
SELECT * FROM agent_traces
WHERE token_usage->>'total_tokens'::int > 5000;

-- Analyze tool usage patterns
SELECT
    jsonb_array_elements(tool_calls)->>'name' as tool_name,
    count(*)
FROM agent_traces
GROUP BY tool_name
ORDER BY count DESC;
```

---

#### **Partial Indexes** (HIGH)
```sql
-- For "failed traces" queries (common for debugging)
CREATE INDEX idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

-- For "high latency" queries (performance monitoring)
CREATE INDEX idx_agent_traces_high_latency
ON agent_traces(user_id, latency_ms DESC, created_at DESC)
WHERE latency_ms > 10000;  -- > 10 seconds

-- For "recent sessions" queries
CREATE INDEX idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '30 days';
```

**Why Partial Indexes?**
- Smaller index size = faster queries
- Automatically exclude old data
- Perfect for time-series data

---

#### **Store Table Indexes** (MEDIUM)
```sql
-- For profile lookups (most common long-term memory query)
CREATE INDEX idx_store_profile
ON store((namespace::text[]), key)
WHERE namespace::text[] = ARRAY['profile', ANY_VALUE];

-- For procedural memory lookups
CREATE INDEX idx_store_procedural
ON store((namespace::text[]), key)
WHERE namespace::text[] = ARRAY['procedural', ANY_VALUE];

-- For fewshot examples (global namespace)
CREATE INDEX idx_store_fewshot
ON store(key)
WHERE namespace::text[] = ARRAY['fewshot', 'global'];
```

**Note**: These indexes use `::text[]` casting because LangGraph stores `namespace` as a tuple. The exact syntax may need adjustment based on actual storage format.

---

### 2.3 Index Usage Verification

After adding indexes, verify they're being used:

```sql
-- Check index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename IN ('agent_traces', 'store', 'checkpoints')
ORDER BY idx_scan DESC;

-- Find unused indexes (safe to drop after monitoring period)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey%'
  AND schemaname = 'public';
```

---

## 3. Data Isolation Review

### 3.1 Current Design

**Short Memory (Checkpoints)**:
- Isolation: `thread_id = session_id`
- ✅ Correct - each session has independent conversation history

**Long Memory (Store)**:
- Isolation: `(namespace, key)` where `namespace = (type, user_id)`
- ✅ Excellent design - multi-dimensional isolation

**Namespace Design**:
```
("profile", user_id)      → User profile and preferences
("procedural", user_id)   → Procedural memory (skills)
("fewshot", "global")     → Global fewshot examples
```

**Assessment**: 9/10 - Well-designed for multi-tenant scenarios.

---

### 3.2 Recommended Improvements

#### **Add Namespace Validation** (HIGH)
```sql
-- Create a custom type for namespace types
CREATE TYPE namespace_type AS ENUM (
    'profile', 'procedural', 'fewshot', 'semantic'
);

-- Add check constraint to store table
ALTER TABLE store
ADD CONSTRAINT chk_namespace_valid
CHECK (
    namespace::text()[1] IN ('profile', 'procedural', 'fewshot', 'semantic')
    AND (
        (namespace::text()[1] = 'fewshot' AND namespace::text()[2] = 'global')
        OR (namespace::text()[1] != 'fewshot')
    )
);
```

#### **Add Row Level Security** (CRITICAL)
```sql
-- Enable RLS on agent_traces
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own traces
CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT
USING (user_id = current_setting('app.current_user_id', true));

-- Policy: Users can only insert their own traces
CREATE POLICY agent_traces_insert_own ON agent_traces
FOR INSERT
WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- Enable RLS on store table
ALTER TABLE store ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own namespace data
CREATE POLICY store_select_own ON store
FOR SELECT
USING (
    namespace::text()[2] = current_setting('app.current_user_id', true)
    OR namespace::text()[1] = 'fewshot'  -- Allow access to global fewshot
);

-- Policy: Users can only insert to their own namespace
CREATE POLICY store_insert_own ON store
FOR INSERT
WITH CHECK (
    namespace::text()[2] = current_setting('app.current_user_id', true)
);
```

**Application Integration**:
```python
# Set user context in connection
await connection.execute(
    "SET LOCAL app.current_user_id = %s",
    (user_id,)
)
```

---

## 4. Performance Considerations

### 4.1 JSONB Field Performance

**Current Schema**:
```sql
thought_chain jsonb NOT NULL DEFAULT '[]',
tool_calls    jsonb NOT NULL DEFAULT '[]',
token_usage   jsonb NOT NULL DEFAULT '{}',
```

**Performance Issues**:
- JSONB fields are stored inline, bloating table size
- No compression for large JSONB documents
- Querying requires full table scans without GIN indexes

**Optimizations**:

1. **Add GIN Indexes** (already covered in §2.2)
2. **Consider TOAST storage** (automatic for large JSONB)
3. **Use jsonb_path_ops for contains queries** (smaller indexes)

**Monitoring JSONB Size**:
```sql
-- Monitor jsonb field sizes
SELECT
    avg(pg_column_size(thought_chain)) as avg_thought_chain_size,
    avg(pg_column_size(tool_calls)) as avg_tool_calls_size,
    avg(pg_column_size(token_usage)) as avg_token_usage_size,
    avg(pg_column_size(thought_chain + tool_calls + token_usage)) as avg_total_jsonb_size
FROM agent_traces;

-- Find traces with unusually large jsonb
SELECT
    id,
    session_id,
    pg_column_size(thought_chain) as thought_chain_size,
    pg_column_size(tool_calls) as tool_calls_size,
    pg_column_size(token_usage) as token_usage_size
FROM agent_traces
WHERE pg_column_size(thought_chain + tool_calls + token_usage) > 100000  -- > 100KB
ORDER BY thought_chain_size + tool_calls_size + token_usage_size DESC
LIMIT 10;
```

---

### 4.2 Query Pattern Analysis

**Common Query Patterns** (based on architecture doc):

1. **Session History** (HIGH frequency)
   ```sql
   SELECT * FROM agent_traces
   WHERE session_id = $1
   ORDER BY created_at DESC;
   ```
   ✅ Covered by `idx_agent_traces_session_created`

2. **User's Recent Sessions** (HIGH frequency)
   ```sql
   SELECT DISTINCT session_id, max(created_at)
   FROM agent_traces
   WHERE user_id = $1
   GROUP BY session_id
   ORDER BY max(created_at) DESC
   LIMIT 20;
   ```
   ⚠️ Requires index: `CREATE INDEX idx_agent_traces_user_session_created ON agent_traces(user_id, session_id, created_at DESC);`

3. **Tool Usage Analytics** (MEDIUM frequency)
   ```sql
   SELECT
       jsonb_array_elements(tool_calls)->>'name' as tool_name,
       count(*),
       avg(latency_ms)
   FROM agent_traces
   WHERE user_id = $1
   GROUP BY tool_name;
   ```
   ✅ Covered by `idx_agent_traces_tool_calls` (GIN)

4. **Error Analysis** (LOW frequency, but critical)
   ```sql
   SELECT * FROM agent_traces
   WHERE user_id = $1
     AND finish_reason IN ('error', 'length')
   ORDER BY created_at DESC;
   ```
   ✅ Covered by `idx_agent_traces_errors` (partial index)

---

### 4.3 Connection Pooling Configuration

**Current Setup** (from docs):
```python
checkpointer = AsyncPostgresSaver.from_conn_string(
    DB_URI,
    connection_kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    },
)
```

**Recommendations**:

```python
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Configure connection pool
pool = AsyncConnectionPool(
    DB_URI,
    min_size=5,           # Minimum connections
    max_size=20,          # Maximum connections
    timeout=30,           # Connection timeout
    max_inactive=300,     # Close inactive connections after 5 min
    kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
        "options": "-c statement_timeout=30000"  # 30s query timeout
    }
)

checkpointer = AsyncPostgresSaver.from_conn_string(
    DB_URI,
    pool=pool,  # Reuse pool
    connection_kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    },
)
```

**Pool Sizing**:
- Development: `min_size=2, max_size=10`
- Production: `min_size=5, max_size=20` (adjust based on concurrency)
- High-traffic: `min_size=10, max_size=50`

---

## 5. Scalability Considerations

### 5.1 Data Growth Projections

**Estimated Growth** (per user per day):
- Checkpoints: ~50KB per turn × 20 turns = 1MB/day
- Store: ~10KB (profile only, rarely changes)
- Agent Traces: ~5KB per turn × 20 turns = 100KB/day

**1 Year Projection** (1000 active users):
- Checkpoints: 365GB
- Store: 10MB (negligible)
- Agent Traces: 36.5GB

**Total**: ~400GB/year for 1000 users

---

### 5.2 Partitioning Strategy

#### **Partition Agent Traces by Time** (HIGH)
```sql
-- Convert to partitioned table
-- Step 1: Create a new partitioned table
CREATE TABLE agent_traces_partitioned (
    id            uuid        NOT NULL DEFAULT gen_random_uuid(),
    session_id    text        NOT NULL,
    user_id       text        NOT NULL,
    user_input    text,
    final_answer  text,
    thought_chain jsonb       NOT NULL DEFAULT '[]',
    tool_calls    jsonb       NOT NULL DEFAULT '[]',
    token_usage   jsonb       NOT NULL DEFAULT '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);

-- Step 2: Create partitions (one per month)
CREATE TABLE agent_traces_2026_03 PARTITION OF agent_traces_partitioned
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE agent_traces_2026_04 PARTITION OF agent_traces_partitioned
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Step 3: Create indexes on partitioned table
CREATE INDEX idx_agent_traces_partitioned_user_session_created
ON agent_traces_partitioned(user_id, session_id, created_at DESC);

-- Step 4: Migrate data (can be done online)
INSERT INTO agent_traces_partitioned
SELECT * FROM agent_traces;

-- Step 5: Rename tables
ALTER TABLE agent_traces RENAME TO agent_traces_old;
ALTER TABLE agent_traces_partitioned RENAME TO agent_traces;
```

**Benefits**:
- Faster queries (query pruning)
- Easier archival (drop old partitions)
- Better maintenance (VACUUM per partition)

---

#### **Partition Checkpoints by Thread + Time** (MEDIUM)
```sql
-- Checkpoints are managed by LangGraph, but you can:
-- 1. Archive old checkpoints to cold storage
-- 2. Create a materialized view for recent checkpoints

CREATE MATERIALIZED VIEW recent_checkpoints AS
SELECT *
FROM checkpoints
WHERE created_at > NOW() - INTERVAL '90 days'
WITH DATA;

-- Refresh daily (can be automated)
REFRESH MATERIALIZED VIEW CONCURRENTLY recent_checkpoints;

-- Create indexes on MV
CREATE INDEX idx_recent_checkpoints_thread_step
ON recent_checkpoints(thread_id, step DESC);
```

---

### 5.3 Archival Strategy

#### **Automated Archival** (HIGH)
```sql
-- Function to archive old data
CREATE OR REPLACE FUNCTION archive_old_traces()
RETURNS void AS $$
BEGIN
    -- Archive traces older than 6 months to separate table
    INSERT INTO agent_traces_archive
    SELECT * FROM agent_traces
    WHERE created_at < NOW() - INTERVAL '6 months';

    -- Delete archived data from main table
    DELETE FROM agent_traces
    WHERE created_at < NOW() - INTERVAL '6 months';
END;
$$ LANGUAGE plpgsql;

-- Schedule with pg_cron (if available)
-- SELECT cron.schedule('archive-traces', '0 2 * * *', 'SELECT archive_old_traces()');
```

#### **Archive Table Structure**
```sql
CREATE TABLE agent_traces_archive (
    LIKE agent_traces INCLUDING ALL
);

-- Create minimal indexes for archive
CREATE INDEX idx_agent_traces_archive_user_created
ON agent_traces_archive(user_id, created_at DESC);

-- Compress archive table
ALTER TABLE agent_traces_archive SET (autovacuum_vacuum_scale_factor = 0.1);
```

---

## 6. Security Considerations

### 6.1 Row Level Security (RLS)

**Status**: ❌ Not implemented

**Recommendations** (from §3.2):
- Enable RLS on `agent_traces`, `store`, `sessions`, `users`
- Create policies for SELECT, INSERT, UPDATE, DELETE
- Use `current_setting('app.current_user_id')` for user context

---

### 6.2 Input Validation

**Current Issues**:
- No validation on `user_input` length (potential DoS)
- No validation on `finish_reason` values
- No sanitization of JSONB content

**Recommendations**:
```python
from pydantic import BaseModel, Field, validator

class AgentTraceCreate(BaseModel):
    session_id: str = Field(..., max_length=255)
    user_id: str = Field(..., max_length=255)
    user_input: str = Field(..., max_length=10000)
    final_answer: str = Field(..., max_length=50000)
    thought_chain: list = Field(default_factory=list)
    tool_calls: list = Field(default_factory=list)
    token_usage: dict = Field(default_factory=dict)
    latency_ms: int = Field(..., ge=0)
    finish_reason: str = Field(
        ...,
        regex="^(stop|length|tool_calls|content_filter|error|interrupted)$"
    )

    @validator('token_usage')
    def validate_token_usage(cls, v):
        if not v:
            raise ValueError('token_usage cannot be empty')
        return v
```

---

### 6.3 SQL Injection Prevention

**Current Code** (from docs):
```python
# ⚠️ Potentially vulnerable if user_id is not sanitized
store.aget(namespace=("profile", user_id), key="episodic")
```

**Recommendations**:
```python
from psycopg import sql

# ✅ Safe: Use parameterized queries
async def safe_get_profile(user_id: str) -> Optional[EpisodicData]:
    query = sql.SQL("""
        SELECT value FROM store
        WHERE namespace = %s AND key = %s
    """)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, [("profile", user_id), "episodic"])
            result = await cur.fetchone()
            return EpisodicData(**result[0]) if result else None
```

---

## 7. Monitoring & Observability

### 7.1 Query Performance Monitoring

```sql
-- Enable pg_stat_statements (in postgresql.conf)
shared_preload_libraries = 'pg_stat_statements'

-- Find slow queries
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

-- Analyze specific query
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT * FROM agent_traces
WHERE user_id = 'user_123'
  AND session_id = 'session_456'
ORDER BY created_at DESC
LIMIT 20;
```

---

### 7.2 Table Size Monitoring

```sql
-- Monitor table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE tablename LIKE '%agent%' OR tablename LIKE '%store%' OR tablename LIKE '%checkpoint%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor bloat (tables needing VACUUM)
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as bloat_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY (pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) DESC;
```

---

### 7.3 Index Usage Monitoring

```sql
-- Find unused indexes (after 1 week of monitoring)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size('public' || '.' || indexname)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%pkey%'
  AND schemaname = 'public'
  AND indexname NOT LIKE 'idx_agent_traces_%'  -- Don't drop agent_traces indexes yet
ORDER BY pg_relation_size('public' || '.' || indexname) DESC;
```

---

## 8. Migration Strategy

### 8.1 Recommended Migration Order

1. **Phase 1: Foundation** (Week 1)
   - Create `users` table
   - Create `sessions` table
   - Add foreign keys to `agent_traces`
   - Add basic constraints

2. **Phase 2: Performance** (Week 2)
   - Add composite indexes
   - Add GIN indexes for jsonb
   - Add partial indexes for common queries

3. **Phase 3: Security** (Week 3)
   - Enable RLS on all tables
   - Create RLS policies
   - Add input validation in application

4. **Phase 4: Scalability** (Week 4)
   - Implement partitioning for `agent_traces`
   - Create archival strategy
   - Set up automated maintenance

---

### 8.2 Migration SQL Script

```sql
-- /migrations/002_improve_agent_traces.sql
BEGIN;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id        text PRIMARY KEY,
    email     text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id             text PRIMARY KEY,
    user_id        text NOT NULL,
    title          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz
);

-- Add foreign keys to agent_traces
ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE agent_traces
ADD CONSTRAINT fk_agent_traces_session
FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;

-- Add constraints
ALTER TABLE agent_traces
ADD CONSTRAINT chk_latency_ms_positive CHECK (latency_ms >= 0),
ADD CONSTRAINT chk_finish_reason_valid
CHECK (finish_reason IN ('stop', 'length', 'tool_calls', 'content_filter', 'error', 'interrupted'));

-- Drop old indexes
DROP INDEX IF EXISTS idx_agent_traces_session;
DROP INDEX IF EXISTS idx_agent_traces_user;

-- Create new indexes
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC);

CREATE INDEX idx_agent_traces_session_created
ON agent_traces(session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason);

CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

CREATE INDEX idx_agent_traces_errors
ON agent_traces(user_id, created_at DESC)
WHERE finish_reason IN ('error', 'length', 'content_filter');

COMMIT;
```

---

### 8.3 Rollback Strategy

```sql
-- /migrations/002_improve_agent_traces_rollback.sql
BEGIN;

-- Drop indexes
DROP INDEX IF EXISTS idx_agent_traces_tool_calls;
DROP INDEX IF EXISTS idx_agent_traces_errors;
DROP INDEX IF EXISTS idx_agent_traces_session_created;
DROP INDEX IF EXISTS idx_agent_traces_user_session_created;

-- Drop constraints
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS chk_finish_reason_valid,
DROP CONSTRAINT IF EXISTS chk_latency_ms_positive;

-- Drop foreign keys
ALTER TABLE agent_traces
DROP CONSTRAINT IF EXISTS fk_agent_traces_session,
DROP CONSTRAINT IF EXISTS fk_agent_traces_user;

-- Drop tables
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS users;

-- Recreate old indexes
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user ON agent_traces(user_id);

COMMIT;
```

---

## 9. Action Items Summary

### 9.1 Critical Priority (Implement Immediately)

1. **Add Foreign Keys** (CRITICAL)
   - Create `users` table
   - Create `sessions` table
   - Add FKs to `agent_traces`

2. **Add Constraints** (CRITICAL)
   - `latency_ms >= 0`
   - `finish_reason` valid values
   - `token_usage` not empty

3. **Enable Row Level Security** (CRITICAL)
   - Enable RLS on all tables
   - Create user isolation policies

4. **Add GIN Indexes** (HIGH)
   - `idx_agent_traces_tool_calls`
   - `idx_agent_traces_token_usage`
   - `idx_agent_traces_thought_chain`

---

### 9.2 High Priority (Implement This Week)

5. **Add Composite Indexes** (HIGH)
   - `idx_agent_traces_user_session_created`
   - `idx_agent_traces_session_created INCLUDE (...)`

6. **Add Partial Indexes** (HIGH)
   - `idx_agent_traces_errors`
   - `idx_agent_traces_high_latency`

7. **Implement Input Validation** (HIGH)
   - Pydantic models for all inputs
   - Length limits on text fields

8. **Set Up Monitoring** (HIGH)
   - Enable `pg_stat_statements`
   - Create monitoring queries
   - Set up alerts for slow queries

---

### 9.3 Medium Priority (Implement This Month)

9. **Implement Partitioning** (MEDIUM)
   - Partition `agent_traces` by time
   - Create automated partition management

10. **Create Archival Strategy** (MEDIUM)
    - Archive old data to separate table
    - Automate archival process

11. **Optimize Connection Pooling** (MEDIUM)
    - Configure proper pool sizes
    - Add connection timeouts

12. **Add Store Table Indexes** (MEDIUM)
    - Partial indexes for common namespaces
    - Monitor and adjust based on usage

---

### 9.4 Low Priority (Implement Next Quarter)

13. **Create Materialized Views** (LOW)
    - Recent checkpoints MV
    - Analytics MVs

14. **Implement Caching** (LOW)
    - Cache frequent queries
    - Consider Redis for hot data

15. **Optimize JSONB Storage** (LOW)
    - Consider TOAST configuration
    - Monitor and optimize large documents

---

## 10. Conclusion

The current database design is **solid for development and early production**, but requires several improvements before handling significant traffic or sensitive data.

**Key Strengths**:
- Clean separation of concerns (checkpoint/store/traces)
- Proper use of PostgreSQL features (JSONB, UUIDs)
- Good namespace design for multi-tenant isolation

**Key Weaknesses**:
- Missing foreign keys and constraints
- No RLS for security
- Insufficient indexing for query performance
- No data retention or archival strategy

**Recommended Next Steps**:
1. Implement critical items immediately (foreign keys, RLS, GIN indexes)
2. Set up monitoring to identify actual query patterns
3. Optimize indexes based on real usage data
4. Plan for scalability (partitioning, archival) as data grows

**Estimated Effort**:
- Critical items: 2-3 days
- High priority items: 1 week
- Medium priority items: 2-3 weeks
- Low priority items: Ongoing

---

## Appendix A: Complete Migration Script

See separate file: `/migrations/002_improve_agent_traces.sql`

## Appendix B: Performance Testing Queries

See separate file: `/docs/database-performance-testing.md`

## Appendix C: Monitoring Dashboard Setup

See separate file: `/docs/database-monitoring-setup.md`

---

**Document Version**: 1.0
**Last Updated**: 2026-03-20
**Next Review**: After implementing critical items (estimated 2026-03-27)
