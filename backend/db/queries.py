"""
数据库查询

提供对数据库表的 CRUD 操作。
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from .models import (
    User,
    UserCreate,
    UserUpdate,
    Session,
    SessionCreate,
    SessionUpdate,
    AgentTrace,
    TraceCreate,
    TraceUpdate,
    PaginatedTraces,
    PaginatedSessions,
)


# ============================================================
-- Users Repository
-- ============================================================

class UserRepository:
    """用户数据访问层"""

    @staticmethod
    async def create(
        conn: AsyncConnection,
        user: UserCreate
    ) -> User:
        """创建用户"""
        query = """
            INSERT INTO users (id, email)
            VALUES (%s, %s)
            RETURNING *
        """
        cursor = await conn.execute(query, user.id, user.email)
        row = await cursor.fetchone()
        return User(**row)

    @staticmethod
    async def get_by_id(
        conn: AsyncConnection,
        user_id: str
    ) -> Optional[User]:
        """根据 ID 获取用户"""
        query = """
            SELECT * FROM users
            WHERE id = %s
        """
        cursor = await conn.execute(query, user_id)
        row = await cursor.fetchone()
        return User(**row) if row else None

    @staticmethod
    async def get_by_email(
        conn: AsyncConnection,
        email: str
    ) -> Optional[User]:
        """根据邮箱获取用户"""
        query = """
            SELECT * FROM users
            WHERE email = %s
        """
        cursor = await conn.execute(query, email)
        row = await cursor.fetchone()
        return User(**row) if row else None

    @staticmethod
    async def update(
        conn: AsyncConnection,
        user_id: str,
        user_update: UserUpdate
    ) -> Optional[User]:
        """更新用户"""
        set_clauses = []
        params = []

        if user_update.email is not None:
            set_clauses.append("email = %s")
            params.append(user_update.email)

        if not set_clauses:
            return await UserRepository.get_by_id(conn, user_id)

        set_clauses.append("updated_at = NOW()")
        params.append(user_id)

        query = f"""
            UPDATE users
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING *
        """

        cursor = await conn.execute(query, *params)
        row = await cursor.fetchone()
        return User(**row) if row else None

    @staticmethod
    async def delete(
        conn: AsyncConnection,
        user_id: str
    ) -> bool:
        """删除用户"""
        query = """
            DELETE FROM users
            WHERE id = %s
            RETURNING id
        """
        cursor = await conn.execute(query, user_id)
        row = await cursor.fetchone()
        return row is not None


# ============================================================
-- Sessions Repository
-- ============================================================

class SessionRepository:
    """会话数据访问层"""

    @staticmethod
    async def create(
        conn: AsyncConnection,
        session: SessionCreate
    ) -> Session:
        """创建会话"""
        query = """
            INSERT INTO sessions (id, user_id, title)
            VALUES (%s, %s, %s)
            RETURNING *
        """
        cursor = await conn.execute(
            query,
            session.id,
            session.user_id,
            session.title
        )
        row = await cursor.fetchone()
        return Session(**row)

    @staticmethod
    async def get_by_id(
        conn: AsyncConnection,
        session_id: str
    ) -> Optional[Session]:
        """根据 ID 获取会话"""
        query = """
            SELECT * FROM sessions
            WHERE id = %s
        """
        cursor = await conn.execute(query, session_id)
        row = await cursor.fetchone()
        return Session(**row) if row else None

    @staticmethod
    async def list_by_user(
        conn: AsyncConnection,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Session]:
        """获取用户的会话列表"""
        query = """
            SELECT * FROM sessions
            WHERE user_id = %s
            ORDER BY last_message_at DESC NULLS LAST, created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor = await conn.execute(query, user_id, limit, offset)
        rows = await cursor.fetchall()
        return [Session(**row) for row in rows]

    @staticmethod
    async def count_by_user(
        conn: AsyncConnection,
        user_id: str
    ) -> int:
        """统计用户的会话数量"""
        query = """
            SELECT COUNT(*) FROM sessions
            WHERE user_id = %s
        """
        cursor = await conn.execute(query, user_id)
        row = await cursor.fetchone()
        return row["count"] if row else 0

    @staticmethod
    async def update(
        conn: AsyncConnection,
        session_id: str,
        session_update: SessionUpdate
    ) -> Optional[Session]:
        """更新会话"""
        set_clauses = []
        params = []

        if session_update.title is not None:
            set_clauses.append("title = %s")
            params.append(session_update.title)

        if not set_clauses:
            return await SessionRepository.get_by_id(conn, session_id)

        set_clauses.append("updated_at = NOW()")
        params.append(session_id)

        query = f"""
            UPDATE sessions
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING *
        """

        cursor = await conn.execute(query, *params)
        row = await cursor.fetchone()
        return Session(**row) if row else None

    @staticmethod
    async def update_last_message_at(
        conn: AsyncConnection,
        session_id: str
    ) -> Optional[Session]:
        """更新会话的最后消息时间"""
        query = """
            UPDATE sessions
            SET last_message_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """
        cursor = await conn.execute(query, session_id)
        row = await cursor.fetchone()
        return Session(**row) if row else None

    @staticmethod
    async def delete(
        conn: AsyncConnection,
        session_id: str
    ) -> bool:
        """删除会话"""
        query = """
            DELETE FROM sessions
            WHERE id = %s
            RETURNING id
        """
        cursor = await conn.execute(query, session_id)
        row = await cursor.fetchone()
        return row is not None


# ============================================================
-- Agent Traces Repository
-- ============================================================

class AgentTraceRepository:
    """Agent 追踪数据访问层"""

    @staticmethod
    async def create(
        conn: AsyncConnection,
        user_id: str,
        trace: TraceCreate
    ) -> AgentTrace:
        """创建追踪"""
        query = """
            INSERT INTO agent_traces (
                session_id, user_id, user_input,
                thought_chain, tool_calls, token_usage,
                latency_ms, finish_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        cursor = await conn.execute(
            query,
            trace.session_id,
            user_id,
            trace.user_input,
            trace.thought_chain,
            trace.tool_calls,
            trace.token_usage.dict(),
            trace.latency_ms,
            trace.finish_reason
        )
        row = await cursor.fetchone()
        return AgentTrace(**row)

    @staticmethod
    async def get_by_id(
        conn: AsyncConnection,
        trace_id: UUID
    ) -> Optional[AgentTrace]:
        """根据 ID 获取追踪"""
        query = """
            SELECT * FROM agent_traces
            WHERE id = %s
        """
        cursor = await conn.execute(query, trace_id)
        row = await cursor.fetchone()
        return AgentTrace(**row) if row else None

    @staticmethod
    async def list_by_session(
        conn: AsyncConnection,
        session_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[AgentTrace]:
        """获取会话的追踪列表"""
        query = """
            SELECT * FROM agent_traces
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor = await conn.execute(query, session_id, limit, offset)
        rows = await cursor.fetchall()
        return [AgentTrace(**row) for row in rows]

    @staticmethod
    async def list_by_user(
        conn: AsyncConnection,
        user_id: str,
        days: int = 30,
        limit: int = 20,
        offset: int = 0
    ) -> List[AgentTrace]:
        """获取用户的追踪列表"""
        since = datetime.now() - timedelta(days=days)

        query = """
            SELECT * FROM agent_traces
            WHERE user_id = %s
              AND created_at >= %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor = await conn.execute(query, user_id, since, limit, offset)
        rows = await cursor.fetchall()
        return [AgentTrace(**row) for row in rows]

    @staticmethod
    async def list_errors(
        conn: AsyncConnection,
        user_id: str,
        limit: int = 50
    ) -> List[AgentTrace]:
        """获取用户的错误追踪"""
        query = """
            SELECT * FROM agent_traces
            WHERE user_id = %s
              AND finish_reason IN ('error', 'length', 'content_filter')
            ORDER BY created_at DESC
            LIMIT %s
        """
        cursor = await conn.execute(query, user_id, limit)
        rows = await cursor.fetchall()
        return [AgentTrace(**row) for row in rows]

    @staticmethod
    async def list_high_latency(
        conn: AsyncConnection,
        user_id: str,
        threshold_ms: int = 10000,
        limit: int = 20
    ) -> List[AgentTrace]:
        """获取高延迟追踪"""
        query = """
            SELECT * FROM agent_traces
            WHERE user_id = %s
              AND latency_ms > %s
            ORDER BY latency_ms DESC
            LIMIT %s
        """
        cursor = await conn.execute(query, user_id, threshold_ms, limit)
        rows = await cursor.fetchall()
        return [AgentTrace(**row) for row in rows]

    @staticmethod
    async def count_by_session(
        conn: AsyncConnection,
        session_id: str
    ) -> int:
        """统计会话的追踪数量"""
        query = """
            SELECT COUNT(*) FROM agent_traces
            WHERE session_id = %s
        """
        cursor = await conn.execute(query, session_id)
        row = await cursor.fetchone()
        return row["count"] if row else 0

    @staticmethod
    async def count_by_user(
        conn: AsyncConnection,
        user_id: str,
        days: int = 30
    ) -> int:
        """统计用户的追踪数量"""
        since = datetime.now() - timedelta(days=days)

        query = """
            SELECT COUNT(*) FROM agent_traces
            WHERE user_id = %s
              AND created_at >= %s
        """
        cursor = await conn.execute(query, user_id, since)
        row = await cursor.fetchone()
        return row["count"] if row else 0

    @staticmethod
    async def update_final_answer(
        conn: AsyncConnection,
        trace_id: UUID,
        final_answer: str,
        finish_reason: str
    ) -> Optional[AgentTrace]:
        """更新追踪的最终答案"""
        query = """
            UPDATE agent_traces
            SET final_answer = %s,
                finish_reason = %s
            WHERE id = %s
            RETURNING *
        """
        cursor = await conn.execute(query, final_answer, finish_reason, trace_id)
        row = await cursor.fetchone()
        return AgentTrace(**row) if row else None

    @staticmethod
    async def get_tool_usage_stats(
        conn: AsyncConnection,
        user_id: str,
        days: int = 30
    ) -> List[dict]:
        """获取工具使用统计"""
        since = datetime.now() - timedelta(days=days)

        query = """
            SELECT
                jsonb_array_elements(tool_calls)->>'name' as tool_name,
                COUNT(*) as usage_count,
                AVG(latency_ms) as avg_latency_ms
            FROM agent_traces
            WHERE user_id = %s
              AND created_at >= %s
              AND jsonb_array_length(tool_calls) > 0
            GROUP BY tool_name
            ORDER BY usage_count DESC
        """
        cursor = await conn.execute(query, user_id, since)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
