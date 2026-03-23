"""
FastAPI Application Entry Point.

Multi-Tool AI Agent Backend API.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.chat import router as chat_router
from app.api.context import router as context_router
from app.api.skills import router as skills_router
from app.config import settings
from app.db.postgres import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Multi-Tool AI Agent backend...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't fail startup, log and continue
        # (allows running without DB for testing)

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")

    logger.info("Shutdown complete")


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
