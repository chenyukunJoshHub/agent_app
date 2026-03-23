"""
PostgreSQL connection setup for LangGraph.

This module initializes:
1. AsyncPostgresSaver - for Short Memory (checkpoints/conversation history)
2. AsyncPostgresStore - for Long Memory (user profiles/episodic data)

IMPORTANT: Uses psycopg3, NOT asyncpg or psycopg2.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from loguru import logger
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.config import settings

# Global instances
# Note: from_conn_string returns an async context manager
_checkpointer_cm: Any = None
_checkpointer: AsyncPostgresSaver | None = None
_store_cm: Any = None
_store: AsyncPostgresStore | None = None
_pool: AsyncConnectionPool | None = None


def get_database_url() -> str:
    """Get the database URL from settings."""
    return settings.database_url


async def get_pool() -> AsyncConnectionPool:
    """
    Get or create the connection pool.

    Returns:
        AsyncConnectionPool: psycopg3 async connection pool

    Raises:
        RuntimeError: If PostgreSQL is not reachable
    """
    global _pool

    if _pool is None:
        logger.info(f"Creating PostgreSQL connection pool: {settings.database_url}")

        _pool = AsyncConnectionPool(
            conninfo=get_database_url(),
            min_size=2,
            max_size=10,
            open=False,
        )

        try:
            await _pool.open()
            logger.info("PostgreSQL connection pool opened")

            # Validate connection by getting a connection and running a simple query
            async with _pool.connection() as conn:
                await conn.execute("SELECT 1")
            logger.info("PostgreSQL connection validated successfully")

        except Exception as e:
            # Clean up the failed pool
            _pool = None
            raise RuntimeError(
                f"Failed to connect to PostgreSQL at {settings.database_url}: {e}"
            ) from e

    return _pool


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get or create the AsyncPostgresSaver (Short Memory).

    This handles conversation history/checkpoints for multi-turn dialogue.

    Returns:
        AsyncPostgresSaver: LangGraph checkpointer for conversation state
    """
    global _checkpointer_cm, _checkpointer

    if _checkpointer is None:
        logger.info("Initializing AsyncPostgresSaver...")

        # from_conn_string returns an async context manager that we need to keep alive
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(get_database_url())
        _checkpointer = await _checkpointer_cm.__aenter__()

        # Create checkpoint tables if they don't exist
        await _checkpointer.setup()
        logger.info("AsyncPostgresSaver initialized (checkpoint tables ready)")

    return _checkpointer


async def get_store() -> AsyncPostgresStore:
    """
    Get or create the AsyncPostgresStore (Long Memory).

    This handles user profiles, episodic memory, and other long-term data.

    Returns:
        AsyncPostgresStore: LangGraph store for long-term memory
    """
    global _store_cm, _store

    if _store is None:
        logger.info("Initializing AsyncPostgresStore...")

        # from_conn_string returns an async context manager that we need to keep alive
        _store_cm = AsyncPostgresStore.from_conn_string(get_database_url())
        _store = await _store_cm.__aenter__()

        # Create store tables if they don't exist
        await _store.setup()
        logger.info("AsyncPostgresStore initialized (store tables ready)")

    return _store


async def init_db() -> None:
    """
    Initialize database components.

    This should be called on application startup.
    """
    logger.info("Initializing database...")

    # Initialize connection pool
    pool = await get_pool()
    logger.info(f"Connection pool ready: {pool}")

    # Initialize checkpointer (Short Memory)
    checkpointer = await get_checkpointer()
    logger.info(f"Checkpointer ready: {checkpointer}")

    # Initialize store (Long Memory)
    store = await get_store()
    logger.info(f"Store ready: {store}")

    logger.info("Database initialization complete")


async def close_db() -> None:
    """Close database connections. Call on application shutdown."""
    global _pool, _checkpointer_cm, _checkpointer, _store_cm, _store

    logger.info("Closing database connections...")

    if _checkpointer_cm is not None and _checkpointer is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _checkpointer = None
        logger.info("AsyncPostgresSaver closed")

    if _store_cm is not None and _store is not None:
        await _store_cm.__aexit__(None, None, None)
        _store_cm = None
        _store = None
        logger.info("AsyncPostgresStore closed")

    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed")

    logger.info("Database connections closed")


@asynccontextmanager
async def get_connection(user_id: str | None = None) -> AsyncIterator[AsyncConnection]:
    """
    Get a database connection from the pool.

    Args:
        user_id: Optional user_id to set for RLS policies. If provided,
                 sets the app.user_id configuration parameter for Row Level
                 Security.

    Yields:
        AsyncConnection: A psycopg3 async connection with user_id context set

    Example:
        async with get_connection(user_id="alice") as conn:
            await conn.execute("SELECT * FROM agent_traces")
            # RLS will automatically filter to only show alice's data
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        # Set user_id context for RLS if provided
        if user_id is not None:
            await set_user_context(conn, user_id)

        yield conn


async def set_user_context(conn: AsyncConnection, user_id: str) -> None:
    """
    Set the user_id context for Row Level Security (RLS).

    This function sets the app.user_id configuration parameter which is used
    by RLS policies to restrict data access to the current user.

    The RLS policies (in migration 005_enable_rls.sql) use:
        current_setting('app.user_id', true)

    Args:
        conn: Database connection
        user_id: User ID to set for RLS policies

    Example:
        await set_user_context(conn, "alice")
        # Now all queries on this connection will be filtered by RLS
        # to only show data where user_id = 'alice'
    """
    await conn.execute(
        "SELECT set_config('app.user_id', $1, false)",
        user_id
    )
