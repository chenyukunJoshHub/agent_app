"""
Integration tests for /chat API endpoint.

These tests verify the SSE streaming chat endpoint.
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from app.main import app


class TestChatEndpoint:
    """Test POST /chat endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient) -> None:
        """Test health check endpoint."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, async_client: AsyncClient) -> None:
        """Test root endpoint."""
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    @pytest.mark.requires_llm
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OLLAMA_BASE_URL"),
        reason="Ollama not configured",
    )
    async def test_chat_endpoint_returns_stream(self, async_client: AsyncClient) -> None:
        """Test that /chat returns SSE stream."""
        response = await async_client.post(
            "/chat/chat",
            json={
                "message": "你好",
                "session_id": "test_session",
                "user_id": "test_user",
            },
        )

        # Should return 200 with streaming response
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_chat_request_validation(self, async_client: AsyncClient) -> None:
        """Test chat request validation."""
        # Missing message
        response = await async_client.post(
            "/chat/chat",
            json={
                "session_id": "test_session",
                "user_id": "test_user",
            },
        )
        assert response.status_code == 422  # Validation error

        # Missing session_id
        response = await async_client.post(
            "/chat/chat",
            json={
                "message": "test",
                "user_id": "test_user",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_default_user_id(self, async_client: AsyncClient) -> None:
        """Test that user_id defaults to 'dev_user'."""
        with patch("app.api.chat.create_react_agent") as mock_create:
            # Mock agent
            mock_agent = AsyncMock()
            mock_agent.astream = AsyncMock(return_value=[])
            mock_create.return_value = mock_agent

            response = await async_client.post(
                "/chat/chat",
                json={
                    "message": "test",
                    "session_id": "test_session",
                    # user_id not provided
                },
            )

            # Should accept request without user_id
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_resume_not_implemented(self, async_client: AsyncClient) -> None:
        """Test that /chat/resume returns 501 in P0."""
        response = await async_client.post(
            "/chat/chat/resume",
            json={
                "session_id": "test_session",
                "user_id": "test_user",
                "interrupt_id": "test_interrupt",
                "approved": True,
            },
        )

        assert response.status_code == 501
        data = response.json()
        assert "not implemented in P0" in data.get("detail", "")


class TestChatSSEStreaming:
    """Test SSE streaming functionality."""

    @pytest.fixture
    def mock_agent_stream(self):
        """Mock agent astream generator."""
        async def stream_generator():
            # Yield chunks that would trigger SSE events
            yield {"messages": [HumanMessage(content="test")]}
            await asyncio.sleep(0.01)
            yield {"messages": [AIMessage(content="response")]}

        return stream_generator()

    @pytest.mark.asyncio
    async def test_sse_content_type(self, async_client: AsyncClient) -> None:
        """Test SSE response has correct content type."""
        with patch("app.api.chat.create_react_agent") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.astream = AsyncMock(return_value=self.mock_agent_stream())
            mock_create.return_value = mock_agent

            response = await async_client.post(
                "/chat/chat",
                json={
                    "message": "test",
                    "session_id": "test_session",
                    "user_id": "test_user",
                },
            )

            assert "text/event-stream" in response.headers.get("content-type", "")
            # Verify no-buffering header
            assert response.headers.get("X-Accel-Buffering") == "no"

    @pytest.mark.asyncio
    async def test_sse_event_format(self, async_client: AsyncClient) -> None:
        """Test SSE events are correctly formatted."""
        with patch("app.api.chat.create_react_agent") as mock_create:
            # Create a mock that yields formatted events
            async def event_stream():
                # Simulate SSE events
                events = [
                    "event: agent_start\ndata: {\"session_id\": \"test\"}\n\n",
                    "event: thought\ndata: {\"content\": \"thinking\"}\n\n",
                    "event: done\ndata: {\"answer\": \"complete\"}\n\n",
                ]
                for event in events:
                    yield event

            mock_agent = MagicMock()
            mock_agent.astream = event_stream
            mock_create.return_value = mock_agent

            response = await async_client.post(
                "/chat/chat",
                json={
                    "message": "test",
                    "session_id": "test_session",
                    "user_id": "test_user",
                },
            )

            # Read response content
            content = response.text
            assert "event: agent_start" in content
            assert "event: thought" in content
            assert "event: done" in content


class TestChatErrorHandling:
    """Test error handling in chat endpoint."""

    @pytest.mark.asyncio
    async def test_agent_error_returns_sse_error(self, async_client: AsyncClient) -> None:
        """Test that agent errors are sent as SSE error events."""
        with patch("app.api.chat.create_react_agent") as mock_create:
            # Mock agent that raises error
            async def error_stream():
                raise Exception("Agent execution failed")

            mock_agent = MagicMock()
            mock_agent.astream = error_stream
            mock_create.return_value = mock_agent

            response = await async_client.post(
                "/chat/chat",
                json={
                    "message": "test",
                    "session_id": "test_session",
                    "user_id": "test_user",
                },
            )

            # Should still return 200 (error sent via SSE)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_json_in_sse(self, async_client: AsyncClient) -> None:
        """Test handling of malformed SSE data."""
        # This would test client resilience to bad SSE
        pass


class TestChatCORS:
    """Test CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers(self, async_client: AsyncClient) -> None:
        """Test that CORS headers are set correctly."""
        response = await async_client.options(
            "/chat/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Verify CORS headers
        assert "access-control-allow-origin" in response.headers


# Import os
import os
