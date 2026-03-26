"""
FastAPI Application Entry Point.

Multi-Tool AI Agent Backend API.
"""
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

# 配置 loguru：移除默认处理器，添加 DEBUG 级别的彩色输出
logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",
    format=(
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <7}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

from app.api.chat import router as chat_router
from app.api.context import router as context_router
from app.api.preferences import router as preferences_router
from app.api.skills import router as skills_router
from app.config import settings
from app.db.postgres import close_db, init_db
from pathlib import Path
from app.skills.manager import SkillManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 [启动] Multi-Tool AI Agent 后端启动中...")
    logger.info(f"🔧 [配置] 运行环境: {settings.environment}")
    logger.info(f"🤖 [配置] LLM 提供商: {settings.llm_provider}")

    # Initialize database — failure here is fatal (checkpointer/store are required)
    logger.debug("💾 [数据库] 正在初始化数据库连接...")
    await init_db()
    logger.info("✅ [数据库] 数据库初始化成功")

    # Initialize SkillManager singleton
    logger.debug("📚 [技能] 正在初始化 SkillManager...")
    skills_dir = Path(settings.skills_dir).expanduser().resolve()
    SkillManager.get_instance(skills_dir=str(skills_dir))
    logger.info(f"✅ [技能] SkillManager 初始化完成，目录: {skills_dir}")

    logger.info("✅ [启动] 服务器就绪，开始监听请求")
    yield

    # Shutdown
    logger.info("🛑 [关闭] 正在关闭服务器...")
    try:
        await close_db()
        logger.info("✅ [关闭] 数据库连接已关闭")
    except Exception as e:
        logger.error(f"❌ [关闭] 关闭数据库时出错: {e}")

    logger.info("✅ [关闭] 服务器已完全关闭")


# Create FastAPI app
app = FastAPI(
    title="Multi-Tool AI Agent",
    description="Enterprise-grade AI Agent with multi-tool orchestration",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {"status": "ok", "version": "0.1.0"}


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        dict: API information
    """
    return {
        "message": "Multi-Tool AI Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler.

    Args:
        request: Request that caused the exception
        exc: Exception that was raised

    Returns:
        JSONResponse: Error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred",
        },
    )


# Include routers
app.include_router(chat_router)
app.include_router(skills_router)
app.include_router(preferences_router)
app.include_router(context_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        timeout_keep_alive=settings.keep_alive_timeout,
    )
