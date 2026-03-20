"""
Database connection and session management
"""

import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.core.logger import loguru_logger

# SQLAlchemy Base
Base = declarative_base()

# Async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.debug,
)

# Async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncSession:
    """Get async database session for dependency injection"""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """Initialize database connection and create tables"""
    try:
        # Test connection
        conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
        version = await conn.fetchval("SELECT version()")
        loguru_logger.info(f"Database connected: PostgreSQL {version.split()[1]}")
        await conn.close()

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            loguru_logger.info("Database tables created")

    except Exception as e:
        loguru_logger.error(f"Database initialization failed: {e}")
        raise


async def close_database() -> None:
    """Close database connections"""
    await engine.dispose()
    loguru_logger.info("Database connections closed")
