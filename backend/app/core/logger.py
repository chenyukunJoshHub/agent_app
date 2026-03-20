"""
Application logger configuration
"""

import logging
import sys
from pathlib import Path

from loguru import logger as loguru_logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and redirect to Loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger() -> None:
    """Configure Loguru logger with file and console handlers"""

    # Remove default handler
    loguru_logger.remove()

    # Console handler with colors
    loguru_logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    # File handler for general logs
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    loguru_logger.add(
        log_path / "agent_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
    )

    # File handler for errors only
    loguru_logger.add(
        log_path / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
    )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# Setup logger on import
setup_logger()

# Export logger
__all__ = ["loguru_logger", "setup_logger"]
