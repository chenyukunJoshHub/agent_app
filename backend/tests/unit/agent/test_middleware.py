"""
Unit tests for agent middleware components.

These tests verify MemoryMiddleware and TraceMiddleware behavior.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.middleware.memory import MemoryMiddleware
from app.agent.middleware.trace import TraceMiddleware


class TestMemoryMiddleware:
    """Test MemoryMiddleware (P0: structure only)."""

    @pytest.fixture
    def memory_middleware(self) -> MemoryMiddleware:
        """Create MemoryMiddleware instance."""
        return MemoryMiddleware()

    @pytest.mark.asyncio
    async def test_abefore_agent_returns_none(self, memory_middleware: MemoryMiddleware) -> None:
        """Test that abefore_agent returns None (P0 behavior)."""
        state = {"messages": []}
        runtime = MagicMock()

        result = await memory_middleware.abefore_agent(state, runtime)
        assert result is None

    @pytest.mark.asyncio
    async def test_wrap_model_call_pass_through(
        self,
        memory_middleware: MemoryMiddleware,
    ) -> None:
        """Test that wrap_model_call passes through request (P0 behavior)."""
        request = MagicMock()
        handler = MagicMock(return_value="response")

        result = memory_middleware.wrap_model_call(request, handler)
        assert result == "response"
        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_aafter_agent_returns_none(self, memory_middleware: MemoryMiddleware) -> None:
        """Test that aafter_agent returns None (P0 behavior)."""
        state = {"messages": []}
        runtime = MagicMock()

        result = await memory_middleware.aafter_agent(state, runtime)
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_middleware_initialization(self) -> None:
        """Test MemoryMiddleware initialization."""
        middleware = MemoryMiddleware()
        assert middleware is not None


class TestTraceMiddleware:
    """Test TraceMiddleware."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock SSE queue."""
        import asyncio

        queue = asyncio.Queue()
        return queue

    @pytest.fixture
    def trace_middleware(self, mock_queue) -> TraceMiddleware:
        """Create TraceMiddleware with mock queue."""
        return TraceMiddleware(sse_queue=mock_queue)

    @pytest.mark.asyncio
    async def test_abefore_agent_sends_agent_start_event(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that abefore_agent sends agent_start event."""
        state = {"session_id": "test_session"}
        runtime = MagicMock()

        await trace_middleware.abefore_agent(state, runtime)

        # Check event was sent
        assert not mock_queue.empty()
        event_type, data = await mock_queue.get()
        assert event_type == "agent_start"
        assert data["session_id"] == "test_session"

    @pytest.mark.asyncio
    async def test_wrap_model_call_pass_through(
        self,
        trace_middleware: TraceMiddleware,
    ) -> None:
        """Test that wrap_model_call passes through."""
        request = MagicMock()
        handler = MagicMock(return_value="response")

        result = trace_middleware.wrap_model_call(request, handler)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_aafter_model_sends_thought_event(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that aafter_model sends thought event."""
        from langchain_core.messages import AIMessage

        state = {
            "messages": [
                AIMessage(
                    content="Response content",
                    reasoning="My reasoning process",
                )
            ]
        }
        runtime = MagicMock()

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_model(state, runtime)

        # Check thought events were sent
        events_sent = []
        while not mock_queue.empty():
            event_type, data = mock_queue.get_nowait()
            events_sent.append((event_type, data))

        # Should have sent thought events
        thought_events = [e for e in events_sent if e[0] == "thought"]
        assert len(thought_events) > 0

    @pytest.mark.asyncio
    async def test_aafter_agent_sends_done_event(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that aafter_agent sends done event."""
        from langchain_core.messages import AIMessage

        state = {
            "messages": [
                AIMessage(
                    content="Final answer",
                    response_metadata={"finish_reason": "stop"},
                )
            ]
        }
        runtime = MagicMock()

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_agent(state, runtime)

        # Check done event was sent
        assert not mock_queue.empty()
        event_type, data = await mock_queue.get()
        assert event_type == "done"
        assert "answer" in data
        assert data["answer"] == "Final answer"

    @pytest.mark.asyncio
    async def test_send_sse_event_with_queue(self, mock_queue) -> None:
        """Test _send_sse_event puts event in queue."""
        middleware = TraceMiddleware(sse_queue=mock_queue)

        middleware._send_sse_event("test_event", {"key": "value"})

        assert not mock_queue.empty()
        event_type, data = await mock_queue.get()
        assert event_type == "test_event"
        assert data["key"] == "value"

    @pytest.mark.asyncio
    async def test_send_sse_event_without_queue(self) -> None:
        """Test _send_sse_event handles None queue gracefully."""
        middleware = TraceMiddleware(sse_queue=None)

        # Should not raise error
        middleware._send_sse_event("test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_trace_middleware_with_empty_messages(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test TraceMiddleware with empty messages list."""
        state = {"messages": []}
        runtime = MagicMock()

        # Should not raise error
        await trace_middleware.aafter_model(state, runtime)

        # Should not send thought events (no messages)
        thought_events = []
        while not mock_queue.empty():
            event_type, _ = mock_queue.get_nowait()
            if event_type == "thought":
                thought_events.append(event_type)

        assert len(thought_events) == 0


class TestMiddlewareIntegration:
    """Test middleware interaction with agent."""

    @pytest.mark.asyncio
    async def test_middleware_chain_execution(self) -> None:
        """Test that middleware chain executes in correct order."""
        import asyncio

        # Create mock queue
        queue = asyncio.Queue()

        # Create middleware instances
        memory = MemoryMiddleware()
        trace = TraceMiddleware(sse_queue=queue)

        # Simulate agent turn
        state = {"messages": [], "session_id": "test"}
        runtime = MagicMock()

        # Execute middleware hooks in order
        result1 = await memory.abefore_agent(state, runtime)
        result2 = await trace.abefore_agent(state, runtime)

        # MemoryMiddleware should return None (P0)
        assert result1 is None

        # TraceMiddleware should send agent_start
        assert not queue.empty()

    @pytest.mark.asyncio
    async def test_both_middleware_aafter_agent(
        self,
    ) -> None:
        """Test both middleware aafter_agent hooks."""
        import asyncio

        queue = asyncio.Queue()

        memory = MemoryMiddleware()
        trace = TraceMiddleware(sse_queue=queue)

        state = {"messages": []}
        runtime = MagicMock()

        # Execute both aafter_agent hooks
        result1 = await memory.aafter_agent(state, runtime)
        result2 = await trace.aafter_agent(state, runtime)

        # Both should return None
        assert result1 is None
        assert result2 is None
