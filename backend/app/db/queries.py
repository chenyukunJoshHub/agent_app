"""
Database query helpers
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentState,
    MemoryStore,
    Message,
    Session,
    ToolExecution,
    User,
)


# ============================================
# User Queries
# ============================================
async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Get user by ID"""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Get user by email"""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ============================================
# Session Queries
# ============================================
async def create_session(
    session: AsyncSession,
    user_id: UUID,
    title: str | None = None,
) -> Session:
    """Create a new session"""
    db_session = Session(user_id=user_id, title=title)
    session.add(db_session)
    await session.flush()
    return db_session


async def get_session(session: AsyncSession, session_id: UUID) -> Session | None:
    """Get session by ID"""
    result = await session.execute(
        select(Session).where(Session.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_user_sessions(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Session]:
    """List all sessions for a user"""
    result = await session.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_session_title(
    session: AsyncSession,
    session_id: UUID,
    title: str,
) -> Session | None:
    """Update session title"""
    result = await session.execute(
        select(Session).where(Session.id == session_id)
    )
    db_session = result.scalar_one_or_none()
    if db_session:
        db_session.title = title
        await session.flush()
    return db_session


async def delete_session(session: AsyncSession, session_id: UUID) -> bool:
    """Delete a session"""
    result = await session.execute(
        delete(Session).where(Session.id == session_id)
    )
    return result.rowcount > 0


# ============================================
# Message Queries
# ============================================
async def create_message(
    session: AsyncSession,
    session_id: UUID,
    role: str,
    content: str,
    tool_calls: dict | None = None,
    tokens_used: int = 0,
) -> Message:
    """Create a new message"""
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tokens_used=tokens_used,
    )
    session.add(message)
    await session.flush()
    return message


async def list_session_messages(
    session: AsyncSession,
    session_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Message]:
    """List all messages in a session"""
    result = await session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ============================================
# Memory Store Queries
# ============================================
async def set_memory(
    session: AsyncSession,
    user_id: UUID,
    namespace: str,
    key: str,
    value: dict,
) -> None:
    """Set a value in memory store"""
    # Check if exists
    result = await session.execute(
        select(MemoryStore).where(
            MemoryStore.user_id == user_id,
            MemoryStore.namespace == namespace,
            MemoryStore.key == key,
        )
    )
    memory = result.scalar_one_or_none()

    if memory:
        memory.value = value
    else:
        memory = MemoryStore(
            user_id=user_id, namespace=namespace, key=key, value=value
        )
        session.add(memory)

    await session.flush()


async def get_memory(
    session: AsyncSession,
    user_id: UUID,
    namespace: str,
    key: str,
) -> dict | None:
    """Get a value from memory store"""
    result = await session.execute(
        select(MemoryStore).where(
            MemoryStore.user_id == user_id,
            MemoryStore.namespace == namespace,
            MemoryStore.key == key,
        )
    )
    memory = result.scalar_one_or_none()
    return memory.value if memory else None


async def list_namespace_memories(
    session: AsyncSession,
    user_id: UUID,
    namespace: str,
) -> dict[str, dict]:
    """Get all memories in a namespace"""
    result = await session.execute(
        select(MemoryStore).where(
            MemoryStore.user_id == user_id,
            MemoryStore.namespace == namespace,
        )
    )
    memories = result.scalars().all()
    return {m.key: m.value for m in memories}


async def delete_memory(
    session: AsyncSession,
    user_id: UUID,
    namespace: str,
    key: str,
) -> bool:
    """Delete a memory"""
    result = await session.execute(
        delete(MemoryStore).where(
            MemoryStore.user_id == user_id,
            MemoryStore.namespace == namespace,
            MemoryStore.key == key,
        )
    )
    return result.rowcount > 0


# ============================================
# Agent State Queries
# ============================================
async def save_checkpoint(
    session: AsyncSession,
    session_id: UUID,
    thread_id: str,
    checkpoint_data: dict,
) -> AgentState:
    """Save agent checkpoint"""
    result = await session.execute(
        select(AgentState).where(
            AgentState.session_id == session_id,
            AgentState.thread_id == thread_id,
        )
    )
    state = result.scalar_one_or_none()

    if state:
        state.checkpoint_data = checkpoint_data
    else:
        state = AgentState(
            session_id=session_id,
            thread_id=thread_id,
            checkpoint_data=checkpoint_data,
        )
        session.add(state)

    await session.flush()
    return state


async def load_checkpoint(
    session: AsyncSession,
    session_id: UUID,
    thread_id: str,
) -> dict | None:
    """Load agent checkpoint"""
    result = await session.execute(
        select(AgentState).where(
            AgentState.session_id == session_id,
            AgentState.thread_id == thread_id,
        )
    )
    state = result.scalar_one_or_none()
    return state.checkpoint_data if state else None


# ============================================
# Tool Execution Queries
# ============================================
async def log_tool_execution(
    session: AsyncSession,
    session_id: UUID,
    tool_name: str,
    parameters: dict | None,
    result: dict | None,
    error_message: str | None,
    duration_ms: int | None,
    requires_confirmation: bool,
    confirmed_by_user: bool | None,
) -> ToolExecution:
    """Log a tool execution"""
    execution = ToolExecution(
        session_id=session_id,
        tool_name=tool_name,
        parameters=parameters,
        result=result,
        error_message=error_message,
        duration_ms=duration_ms,
        requires_confirmation=requires_confirmation,
        confirmed_by_user=confirmed_by_user,
    )
    session.add(execution)
    await session.flush()
    return execution


async def list_tool_executions(
    session: AsyncSession,
    session_id: UUID,
    limit: int = 50,
) -> list[ToolExecution]:
    """List tool executions for a session"""
    result = await session.execute(
        select(ToolExecution)
        .where(ToolExecution.session_id == session_id)
        .order_by(ToolExecution.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
