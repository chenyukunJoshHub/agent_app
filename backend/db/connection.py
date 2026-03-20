"""
数据库连接管理

提供连接池配置、连接获取和 RLS 用户上下文设置。
"""

import os
from typing import AsyncGenerator, Optional
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

# 连接池配置
POOL_CONFIG = {
    "development": {
        "min_size": 2,
        "max_size": 10,
        "timeout": 30,
        "max_inactive": 300,
        "kwargs": {
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
            "options": "-c statement_timeout=30000",  # 30s 查询超时
        }
    },
    "production": {
        "min_size": 5,
        "max_size": 20,
        "timeout": 30,
        "max_inactive": 300,
        "kwargs": {
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
            "options": "-c statement_timeout=30000",
        }
    },
    "high_traffic": {
        "min_size": 10,
        "max_size": 50,
        "timeout": 30,
        "max_inactive": 300,
        "kwargs": {
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
            "options": "-c statement_timeout=30000",
        }
    }
}

# 全局连接池
_pool: Optional[AsyncConnectionPool] = None


def get_database_url() -> str:
    """获取数据库连接 URL"""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:54322/agent_db"
    )


def get_pool_config(env: str = "development") -> dict:
    """获取连接池配置"""
    return POOL_CONFIG.get(env, POOL_CONFIG["development"])


async def get_pool() -> AsyncConnectionPool:
    """获取或创建连接池"""
    global _pool

    if _pool is None:
        env = os.getenv("ENV", "development")
        config = get_pool_config(env)
        db_url = get_database_url()

        _pool = AsyncConnectionPool(db_url, **config)
        await _pool.wait()

    return _pool


async def close_pool() -> None:
    """关闭连接池"""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """获取数据库连接（用于依赖注入）"""
    pool = await get_pool()

    async with pool.connection() as conn:
        yield conn


async def set_user_context(conn: AsyncConnection, user_id: str) -> None:
    """
    为数据库连接设置用户上下文（用于 RLS）

    Args:
        conn: 数据库连接
        user_id: 用户 ID
    """
    await conn.execute(
        "SET LOCAL app.user_id = %s",
        (user_id,)
    )


async def get_db_with_user_context(
    user_id: str
) -> AsyncGenerator[AsyncConnection, None]:
    """
    获取带有用户上下文的数据库连接

    Args:
        user_id: 用户 ID

    Yields:
        带有用户上下文的数据库连接
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        await set_user_context(conn, user_id)
        yield conn


async def set_admin_context(conn: AsyncConnection, user_id: str) -> None:
    """
    设置管理员上下文（绕过 RLS 限制）

    Args:
        conn: 数据库连接
        user_id: 管理员用户 ID
    """
    await conn.execute("SELECT app.set_admin_user(%s)", (user_id,))


async def get_db_with_admin_context(
    user_id: str
) -> AsyncGenerator[AsyncConnection, None]:
    """
    获取带有管理员上下文的数据库连接

    Args:
        user_id: 管理员用户 ID

    Yields:
        带有管理员上下文的数据库连接
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        await set_admin_context(conn, user_id)
        yield conn
