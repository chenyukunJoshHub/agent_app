"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest for all tests.
"""
import asyncio
from collections.abc import AsyncIterator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.main import app


# ────────────────────────────────────────────────────────────────────────────────
# Pytest Hooks
# ────────────────────────────────────────────────────────────────────────────────


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "unit: Unit tests (fast, no external dependencies)",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (database, API)",
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests (full system)",
    )
    config.addinivalue_line(
        "markers",
        "slow: Slow-running tests",
    )
    config.addinivalue_line(
        "markers",
        "requires_db: Tests requiring database connection",
    )
    config.addinivalue_line(
        "markers",
        "requires_llm: Tests requiring LLM API (may incur costs)",
    )
    config.addinivalue_line(
        "markers",
        "requires_api_key: Tests requiring external API keys",
    )


# ────────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for each test case.

    This ensures async tests have a fresh event loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> Settings:
    """
    Mock settings for testing.

    Override with @pytest.mark.parametrize or in individual tests as needed.
    """
    return Settings(
        database_url="postgresql://postgres:postgres@localhost:5432/test_db",
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
        tavily_api_key="test_key",
        environment="testing",
        debug=True,
    )


@pytest.fixture
def mock_llm() -> BaseChatModel:
    """
    Mock LLM for testing.

    Returns a MagicMock that mimics BaseChatModel behavior.
    Override return values in tests as needed.
    """
    llm = MagicMock(spec=BaseChatModel)

    # Mock ainvoke method
    async def mock_ainvoke(
        messages: list[HumanMessage],
        *args: Any,
        **kwargs: Any,
    ) -> AIMessage:
        return AIMessage(
            content="Test response",
            reasoning="Test reasoning",
        )

    llm.ainvoke = mock_ainvoke
    llm.bind = MagicMock(return_value=llm)

    return llm


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """
    Async HTTP client for testing FastAPI endpoints.

    Uses httpx.AsyncClient which is async-compatible.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_user_message() -> HumanMessage:
    """Sample user message for testing."""
    return HumanMessage(content="帮我查一下茅台今天的股价")


@pytest.fixture
def sample_assistant_message() -> AIMessage:
    """Sample assistant message for testing."""
    return AIMessage(
        content="根据搜索结果，茅台今天股价为...",
        reasoning="我需要使用 web_search 工具查询实时股价",
    )


# ────────────────────────────────────────────────────────────────────────────────
# Database Fixtures
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    pool.__aenter__ = AsyncMock(return_value=pool)
    pool.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_checkpointer():
    """Mock AsyncPostgresSaver checkpointer."""
    checkpointer = AsyncMock()
    checkpointer.setup = AsyncMock()
    checkpointer.aput = AsyncMock()
    checkpointer.aget = AsyncMock()
    checkpointer.alist = AsyncMock(return_value=[])
    return checkpointer


@pytest.fixture
def mock_store():
    """Mock AsyncPostgresStore."""
    store = AsyncMock()
    store.setup = AsyncMock()
    store.asearch = AsyncMock(return_value=[])
    store.aput = AsyncMock()
    store.aget = AsyncMock()
    store.adelete = AsyncMock()
    return store


# ────────────────────────────────────────────────────────────────────────────────
# SSE Event Fixtures
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_sse_events():
    """Sample SSE events for testing."""
    return [
        ("agent_start", {"session_id": "test_session_001"}),
        ("thought", {"content": "我需要搜索茅台股价"}),
        ("tool_start", {"tool_name": "web_search", "args": {"query": "茅台股价"}}),
        ("tool_result", {"result": '{"query": "茅台股价", "results": []}'}),
        ("done", {"answer": "茅台今天股价为...", "finish_reason": "stop"}),
    ]


@pytest.fixture
def mock_sse_queue():
    """Mock SSE event queue."""
    queue = asyncio.Queue()

    # Populate with sample events
    async def populate() -> None:
        for event_type, data in [
            ("thought", {"content": "Test thought"}),
            ("done", {"answer": "Test answer"}),
        ]:
            await queue.put((event_type, data))

    asyncio.create_task(populate())
    return queue


# ────────────────────────────────────────────────────────────────────────────────
# Tool Fixtures
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_tavily_response():
    """Mock Tavily API response."""
    return {
        "query": "茅台股价",
        "answer": "根据搜索结果...",
        "results": [
            {
                "title": "贵州茅台股票行情",
                "url": "https://example.com",
                "content": "茅台股价 1680.00 元",
            }
        ],
    }
