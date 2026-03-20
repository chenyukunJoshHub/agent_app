"""
FastAPI application factory
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import loguru_logger, setup_logger
from app.db.connection import close_database, init_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager"""
    # Startup
    loguru_logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    setup_logger()

    # Initialize database
    await init_database()

    yield

    # Shutdown
    loguru_logger.info("Shutting down application...")
    await close_database()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "version": settings.app_version}

    # API routes
    from app.api.routes import chat, sessions, skills

    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(skills.router, prefix="/api/skills", tags=["skills"])

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        loguru_logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


# Application instance
app = create_app()
