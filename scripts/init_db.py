#!/usr/bin/env python3
"""
Database initialization script
Run this script to initialize the database with migrations
"""

import asyncio
import sys

from app.db.connection import init_database
from app.core.logger import loguru_logger


async def main() -> int:
    """Main initialization function"""
    try:
        loguru_logger.info("Starting database initialization...")
        await init_database()
        loguru_logger.info("✅ Database initialized successfully")
        return 0
    except Exception as e:
        loguru_logger.error(f"❌ Database initialization failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
