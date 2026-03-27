"""
Unit tests for agent middleware components.

These tests verify MemoryMiddleware and TraceMiddleware behavior.
"""
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.agent.middleware.memory import MemoryMiddleware
from app.agent.middleware.trace import TraceMiddleware
from app.memory.manager import MemoryManager


class TestMemoryMiddleware:
    """Test MemoryMiddleware (P0: structure only)."""

    @pytest.fixture
    def mock_store(self):
        """Mock AsyncPostgresStore."""
        store = MagicMock()
        store.aput = AsyncMock()
        store.aget = AsyncMock(return_value=None)  # 默认返回 None
        return store

    @pytest.fixture
    def memory_manager(self, mock_store):
        """Create MemoryManager instance."""
        return MemoryManager(store=mock_store)

    @pytest.fixture
    def memory_middleware(self, memory_manager) -> MemoryMiddleware:
        """Create MemoryMiddleware instance."""
        return MemoryMiddleware(memory_manager=memory_manager)

    @pytest.mark.asyncio
    async def test_abefore_agent_returns_memory_ctx(self, memory_middleware: MemoryMiddleware) -> None:
        """Test that abefore_agent returns memory_ctx (P0 behavior)."""
        state = {"messages": []}
        runtime = MagicMock()
        runtime.config = {"configurable": {"user_id": "test-user"}}

        result = await memory_middleware.abefore_agent(state, runtime)
        assert result is not None
        assert "memory_ctx" in result

    @pytest.mark.asyncio
    async def test_wrap_model_call_pass_through(
        self,
        memory_middleware: MemoryMiddleware,
    ) -> None:
        """Test that wrap_model_call passes through request (P0 behavior)."""
        request = MagicMock()
        request.state = {}
        handler = MagicMock(return_value="response")

        result = memory_middleware.wrap_model_call(request, handler)
        assert result == "response"

    @pytest.mark.asyncio
    async def test_aafter_agent_returns_none(self, memory_middleware: MemoryMiddleware) -> None:
        """Test that aafter_agent returns None (P0 behavior)."""
        state = {"messages": []}
        runtime = MagicMock()

        result = await memory_middleware.aafter_agent(state, runtime)
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_middleware_initialization(self, memory_manager) -> None:
        """Test MemoryMiddleware initialization."""
        middleware = MemoryMiddleware(memory_manager=memory_manager)
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
        """Create TraceMiddleware (SSE queue injected per-request via runtime.context)."""
        return TraceMiddleware()

    @pytest.mark.asyncio
    async def test_abefore_agent_sends_agent_start_event(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that abefore_agent sends agent_start event."""
        state = {"session_id": "test_session"}
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

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
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

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
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_agent(state, runtime)

        # Check done event was sent (trace_block/trace_event may appear before done)
        events_sent = []
        while not mock_queue.empty():
            events_sent.append(await mock_queue.get())

        done_events = [payload for event_type, payload in events_sent if event_type == "done"]
        assert len(done_events) == 1
        assert "answer" in done_events[0]
        assert done_events[0]["answer"] == "Final answer"

    @pytest.mark.asyncio
    async def test_aafter_agent_emits_tool_results_for_current_turn_only(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Historical ToolMessage entries should not be replayed as current-turn tool results."""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        state = {
            "messages": [
                HumanMessage(content="上一轮问题"),
                ToolMessage(content="old-result", tool_call_id="call_old"),
                HumanMessage(content="这一轮问题"),
                ToolMessage(content="new-result", tool_call_id="call_new"),
                AIMessage(content="最终回答", response_metadata={"finish_reason": "stop"}),
            ]
        }
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_agent(state, runtime)

        tool_result_ids: list[str] = []
        while not mock_queue.empty():
            event_type, payload = await mock_queue.get()
            if event_type != "trace_event":
                continue
            if payload.get("stage") == "tools" and payload.get("step") == "tool_call_result":
                tool_result_ids.append(str(payload.get("payload", {}).get("tool_call_id", "")))

        assert tool_result_ids == ["call_new"]

    @pytest.mark.asyncio
    async def test_send_sse_event_with_queue(self, mock_queue) -> None:
        """Test _send_sse_event puts event in queue."""
        middleware = TraceMiddleware()

        await middleware._send_sse_event(mock_queue, "test_event", {"key": "value"})

        assert not mock_queue.empty()
        event_type, data = await mock_queue.get()
        assert event_type == "test_event"
        assert data["key"] == "value"

    @pytest.mark.asyncio
    async def test_send_sse_event_without_queue(self) -> None:
        """Test _send_sse_event handles None queue gracefully."""
        middleware = TraceMiddleware()

        # Should not raise error
        await middleware._send_sse_event(None, "test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_trace_middleware_with_empty_messages(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test TraceMiddleware with empty messages list."""
        state = {"messages": []}
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        # Should not raise error
        await trace_middleware.aafter_model(state, runtime)

        # Should not send thought events (no messages)
        thought_events = []
        while not mock_queue.empty():
            event_type, _ = mock_queue.get_nowait()
            if event_type == "thought":
                thought_events.append(event_type)

        assert len(thought_events) == 0

    @pytest.mark.asyncio
    async def test_aafter_model_sends_token_update_event(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that aafter_model sends token_update event when token_usage is present."""
        from langchain_core.messages import AIMessage

        state = {
            "messages": [
                AIMessage(
                    content="Response content",
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                            "total_tokens": 150,
                        }
                    },
                )
            ],
            "_token_usage": 0,  # Initial token usage
        }
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_model(state, runtime)

        # Check events
        events_sent = []
        while not mock_queue.empty():
            event_type, data = mock_queue.get_nowait()
            events_sent.append((event_type, data))

        # Should have sent token_update event
        token_update_events = [e for e in events_sent if e[0] == "token_update"]
        assert len(token_update_events) == 1

        # Verify token_update data
        _, token_data = token_update_events[0]
        assert token_data["current"] == 150  # 0 + 150
        assert token_data["budget"] == 32000
        assert token_data["input_tokens"] == 100
        assert token_data["output_tokens"] == 50
        assert token_data["remaining"] == 32000 - 150

        # Verify state was updated with accumulated usage
        assert state["_token_usage"] == 150

    @pytest.mark.asyncio
    async def test_aafter_model_accumulates_token_usage(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that aafter_model accumulates token usage across multiple calls."""
        from langchain_core.messages import AIMessage

        # First call with 100 tokens
        state = {
            "messages": [
                AIMessage(
                    content="First response",
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": 50,
                            "completion_tokens": 50,
                            "total_tokens": 100,
                        }
                    },
                )
            ],
            "_token_usage": 500,  # Previous usage
        }
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_model(state, runtime)

        # Get all events and find token_update
        token_update_found = False
        while not mock_queue.empty():
            event_type, token_data = mock_queue.get_nowait()
            if event_type == "token_update":
                token_update_found = True
                assert token_data["current"] == 600  # 500 + 100
                assert state["_token_usage"] == 600

        assert token_update_found, "token_update event should be sent"

    @pytest.mark.asyncio
    async def test_aafter_model_handles_missing_token_usage(
        self,
        trace_middleware: TraceMiddleware,
        mock_queue,
    ) -> None:
        """Test that aafter_model handles messages without token_usage gracefully."""
        from langchain_core.messages import AIMessage

        state = {
            "messages": [
                AIMessage(content="Response without token usage"),
            ],
            "_token_usage": 100,
        }
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = mock_queue

        # Clear queue
        while not mock_queue.empty():
            mock_queue.get_nowait()

        await trace_middleware.aafter_model(state, runtime)

        # Should not send token_update event (no token_usage in metadata)
        events_sent = []
        while not mock_queue.empty():
            event_type, data = mock_queue.get_nowait()
            events_sent.append((event_type, data))

        # Should NOT have token_update event
        token_update_events = [e for e in events_sent if e[0] == "token_update"]
        assert len(token_update_events) == 0

        # Token usage should remain unchanged
        assert state["_token_usage"] == 100


class TestTraceBlockBuilderIntegration:
    """Test trace_block emission integration via emit_trace_event."""

    @pytest.fixture
    def trace_middleware(self) -> TraceMiddleware:
        """Create TraceMiddleware with block builder."""
        return TraceMiddleware()

    @pytest.mark.asyncio
    async def test_abefore_agent_emits_trace_block(self, trace_middleware: TraceMiddleware) -> None:
        """abefore_agent should emit both trace_event and trace_block for turn_start."""
        import asyncio

        queue = asyncio.Queue()
        state = {"session_id": "test_session", "messages": []}
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = queue

        await trace_middleware.abefore_agent(state, runtime)

        events_sent = []
        while not queue.empty():
            events_sent.append(await queue.get())

        event_types = [event_type for event_type, _ in events_sent]
        assert "trace_event" in event_types
        assert "trace_block" in event_types
        turn_start_blocks = [
            payload
            for event_type, payload in events_sent
            if event_type == "trace_block" and payload.get("type") == "turn_start"
        ]
        assert len(turn_start_blocks) == 1


class TestMiddlewareIntegration:
    """Test middleware interaction with agent."""

    @pytest.fixture
    def mock_store(self):
        """Mock AsyncPostgresStore."""
        store = MagicMock()
        store.aput = AsyncMock()
        store.aget = AsyncMock(return_value=None)  # 默认返回 None
        return store

    @pytest.fixture
    def memory_manager(self, mock_store):
        """Create MemoryManager instance."""
        return MemoryManager(store=mock_store)

    @pytest.mark.asyncio
    async def test_middleware_chain_execution(self, memory_manager) -> None:
        """Test that middleware chain executes in correct order."""
        import asyncio

        # Create mock queue
        queue = asyncio.Queue()

        # Create middleware instances
        memory = MemoryMiddleware(memory_manager=memory_manager)
        trace = TraceMiddleware()

        # Simulate agent turn
        state = {"messages": [], "session_id": "test"}
        runtime = MagicMock()
        runtime.config = {"configurable": {"user_id": "test"}}
        runtime.context = MagicMock()
        runtime.context.sse_queue = queue

        # Execute middleware hooks in order
        result1 = await memory.abefore_agent(state, runtime)
        result2 = await trace.abefore_agent(state, runtime)

        # MemoryMiddleware should return memory_ctx (P0)
        assert result1 is not None
        assert "memory_ctx" in result1

        # TraceMiddleware should send agent_start
        assert not queue.empty()

    @pytest.mark.asyncio
    async def test_both_middleware_aafter_agent(
        self, memory_manager
    ) -> None:
        """Test both middleware aafter_agent hooks."""
        import asyncio

        queue = asyncio.Queue()

        memory = MemoryMiddleware(memory_manager=memory_manager)
        trace = TraceMiddleware()

        state = {"messages": []}
        runtime = MagicMock()
        runtime.context = MagicMock()
        runtime.context.sse_queue = queue

        # Execute both aafter_agent hooks
        result1 = await memory.aafter_agent(state, runtime)
        result2 = await trace.aafter_agent(state, runtime)

        # Both should return None (P0)
        assert result1 is None
        assert result2 is None
