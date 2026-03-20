"""
数据库 Schema 测试

测试数据库表、约束、索引和 RLS 策略。
"""

import pytest
from uuid import uuid4
from datetime import datetime

from backend.db import (
    get_pool,
    close_pool,
    set_user_context,
)
from backend.db.models import (
    UserCreate,
    SessionCreate,
    TraceCreate,
    TokenUsage,
    FinishReason,
)
from backend.db.queries import (
    UserRepository,
    SessionRepository,
    AgentTraceRepository,


# ============================================================
-- 测试配置
-- ============================================================

@pytest.fixture(scope="module")
async def db_pool():
    """设置数据库连接池"""
    pool = await get_pool()
    yield pool
    await close_pool()


@pytest.fixture
async def db_connection(db_pool):
    """获取数据库连接"""
    async with db_pool.connection() as conn:
        yield conn


@pytest.fixture
async def test_user(db_connection):
    """创建测试用户"""
    user_id = f"test_user_{uuid4().hex[:8]}"
    user_create = UserCreate(
        id=user_id,
        email=f"{user_id}@example.com"
    )
    user = await UserRepository.create(db_connection, user_create)
    yield user
    # 清理
    await UserRepository.delete(db_connection, user_id)


@pytest.fixture
async def test_session(db_connection, test_user):
    """创建测试会话"""
    session_id = f"test_session_{uuid4().hex[:8]}"
    session_create = SessionCreate(
        id=session_id,
        user_id=test_user.id,
        title="Test Session"
    )
    session = await SessionRepository.create(db_connection, session_create)
    yield session
    # 清理
    await SessionRepository.delete(db_connection, session_id)


# ============================================================
-- Schema 测试
-- ============================================================

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

    async def test_sessions_table_exists(self, db_connection):
        """测试 sessions 表是否存在"""
        result = await db_connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'sessions'
            )
        """)
        assert result is True

    async def test_agent_traces_table_exists(self, db_connection):
        """测试 agent_traces 表是否存在"""
        result = await db_connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'agent_traces'
            )
        """)
        assert result is True


# ============================================================
-- 约束测试
-- ============================================================

class TestConstraints:
    """测试数据库约束"""

    async def test_users_email_unique(self, db_connection):
        """测试 users 表邮箱唯一约束"""
        user_id = f"test_unique_{uuid4().hex[:8]}"
        await UserRepository.create(db_connection, UserCreate(
            id=user_id,
            email="unique@example.com"
        ))

        # 尝试创建相同邮箱的用户
        with pytest.raises(Exception):
            await UserRepository.create(db_connection, UserCreate(
                id=f"{user_id}_2",
                email="unique@example.com"
            ))

    async def test_sessions_foreign_key(self, db_connection):
        """测试 sessions 表外键约束"""
        # 尝试创建引用不存在用户的会话
        with pytest.raises(Exception):
            await SessionRepository.create(db_connection, SessionCreate(
                id=f"test_fk_{uuid4().hex[:8]}",
                user_id="nonexistent_user",
                title="Should Fail"
            ))

    async def test_agent_traces_latency_positive(self, db_connection, test_session):
        """测试 agent_traces 表延迟非负约束"""
        # 设置用户上下文
        await set_user_context(db_connection, test_session.user_id)

        # 尝试插入负延迟
        with pytest.raises(Exception):
            await db_connection.execute("""
                INSERT INTO agent_traces
                (session_id, user_id, user_input, thought_chain, tool_calls, token_usage, latency_ms, finish_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, test_session.id, test_session.user_id, "test", "[]", "[]", '{"total_tokens": 100}', -1, "stop")

    async def test_agent_traces_finish_reason_valid(self, db_connection, test_session):
        """测试 agent_traces 表完成原因约束"""
        await set_user_context(db_connection, test_session.user_id)

        # 尝试插入无效的完成原因
        with pytest.raises(Exception):
            await db_connection.execute("""
                INSERT INTO agent_traces
                (session_id, user_id, user_input, thought_chain, tool_calls, token_usage, latency_ms, finish_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, test_session.id, test_session.user_id, "test", "[]", "[]", '{"total_tokens": 100}', 1000, "invalid_reason")


# ============================================================
-- 索引测试
-- ============================================================

class TestIndexes:
    """测试数据库索引"""

    async def test_index_exists(self, db_connection):
        """测试索引是否存在"""
        indexes = [
            'idx_users_email',
            'idx_sessions_user_id',
            'idx_agent_traces_user_session_created',
            'idx_agent_traces_tool_calls',
            'idx_agent_traces_thought_chain',
        ]

        for index_name in indexes:
            result = await db_connection.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = %s
                )
            """, index_name)
            assert result is True, f"Index {index_name} not found"

    async def test_covering_index(self, db_connection):
        """测试覆盖索引"""
        # 检查包含列的索引
        result = await db_connection.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = 'idx_agent_traces_session_created'
            )
        """)
        assert result is True


# ============================================================
-- RLS 测试
-- ============================================================

class TestRowLevelSecurity:
    """测试 Row Level Security"""

    async def test_rls_enabled(self, db_connection):
        """测试 RLS 是否启用"""
        tables = ['users', 'sessions', 'agent_traces']

        for table_name in tables:
            result = await db_connection.fetchval("""
                SELECT relrowsecurity
                FROM pg_class
                WHERE relname = %s
            """, table_name)
            assert result is True, f"RLS not enabled on {table_name}"

    async def test_user_isolation(self, db_connection):
        """测试用户隔离"""
        # 创建用户 1
        user1_id = f"user1_{uuid4().hex[:8]}"
        await UserRepository.create(db_connection, UserCreate(
            id=user1_id,
            email="user1@example.com"
        ))

        # 创建用户 2
        user2_id = f"user2_{uuid4().hex[:8]}"
        await UserRepository.create(db_connection, UserCreate(
            id=user2_id,
            email="user2@example.com"
        ))

        # 用户 1 创建会话
        session1_id = f"session1_{uuid4().hex[:8]}"
        await SessionRepository.create(db_connection, SessionCreate(
            id=session1_id,
            user_id=user1_id,
            title="User 1 Session"
        ))

        # 设置用户 2 上下文
        await set_user_context(db_connection, user2_id)

        # 用户 2 不应该能访问用户 1 的会话
        session = await SessionRepository.get_by_id(db_connection, session1_id)
        assert session is None, "User 2 should not access User 1's session"

    async def test_policies_exist(self, db_connection):
        """测试 RLS 策略是否存在"""
        policies = [
            ('users', 'users_select_own'),
            ('sessions', 'sessions_select_own'),
            ('agent_traces', 'agent_traces_select_own'),
        ]

        for table_name, policy_name in policies:
            result = await db_connection.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_policies
                    WHERE tablename = %s AND policyname = %s
                )
            """, table_name, policy_name)
            assert result is True, f"Policy {policy_name} not found on {table_name}"


# ============================================================
-- CRUD 测试
-- ============================================================

class TestCRUD:
    """测试 CRUD 操作"""

    async def test_create_and_get_user(self, db_connection):
        """测试创建和获取用户"""
        user_id = f"test_crud_{uuid4().hex[:8]}"
        user_create = UserCreate(
            id=user_id,
            email="crud@example.com"
        )

        # 创建用户
        user = await UserRepository.create(db_connection, user_create)
        assert user.id == user_id
        assert user.email == "crud@example.com"

        # 获取用户
        retrieved_user = await UserRepository.get_by_id(db_connection, user_id)
        assert retrieved_user is not None
        assert retrieved_user.id == user_id

        # 清理
        await UserRepository.delete(db_connection, user_id)

    async def test_create_and_get_session(self, db_connection, test_user):
        """测试创建和获取会话"""
        session_id = f"session_crud_{uuid4().hex[:8]}"
        session_create = SessionCreate(
            id=session_id,
            user_id=test_user.id,
            title="CRUD Test Session"
        )

        # 创建会话
        session = await SessionRepository.create(db_connection, session_create)
        assert session.id == session_id
        assert session.title == "CRUD Test Session"

        # 获取会话
        retrieved_session = await SessionRepository.get_by_id(db_connection, session_id)
        assert retrieved_session is not None
        assert retrieved_session.id == session_id

        # 清理
        await SessionRepository.delete(db_connection, session_id)

    async def test_create_and_list_traces(self, db_connection, test_session):
        """测试创建和列出追踪"""
        await set_user_context(db_connection, test_session.user_id)

        # 创建追踪
        trace_create = TraceCreate(
            session_id=test_session.id,
            user_input="Test input",
            thought_chain=[],
            tool_calls=[],
            token_usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            ),
            latency_ms=1000,
            finish_reason=FinishReason.STOP
        )

        trace = await AgentTraceRepository.create(
            db_connection,
            test_session.user_id,
            trace_create
        )

        assert trace.session_id == test_session.id
        assert trace.user_input == "Test input"

        # 列出追踪
        traces = await AgentTraceRepository.list_by_session(
            db_connection,
            test_session.id
        )

        assert len(traces) > 0
        assert traces[0].id == trace.id


# ============================================================
-- 性能测试
-- ============================================================

class TestPerformance:
    """测试数据库性能"""

    async def test_query_performance(self, db_connection, test_session):
        """测试查询性能"""
        import time

        await set_user_context(db_connection, test_session.user_id)

        # 插入 100 条追踪记录
        for i in range(100):
            await AgentTraceRepository.create(
                db_connection,
                test_session.user_id,
                TraceCreate(
                    session_id=test_session.id,
                    user_input=f"Test input {i}",
                    thought_chain=[],
                    tool_calls=[],
                    token_usage=TokenUsage(
                        prompt_tokens=100,
                        completion_tokens=50,
                        total_tokens=150
                    ),
                    latency_ms=1000,
                    finish_reason=FinishReason.STOP
                )
            )

        # 测试查询性能
        start = time.time()
        traces = await AgentTraceRepository.list_by_session(
            db_connection,
            test_session.id,
            limit=20
        )
        elapsed = time.time() - start

        assert len(traces) == 20
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected < 0.1s"
