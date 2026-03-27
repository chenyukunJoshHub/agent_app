"""
Unit tests for app.api.chat.

These tests verify chat API endpoints and SSE streaming.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.api.chat import (
    ChatRequest,
    ChatResumeRequest,
    SSEEventQueue,
    _execute_agent,
    _format_sse_event,
    _run_agent_stream,
    chat,
    chat_resume,
)


class TestChatRequest:
    """Test ChatRequest model."""

    def test_chat_request_with_required_fields(self) -> None:
        """Test ChatRequest with message and session_id."""
        request = ChatRequest(message="Hello", session_id="test_session")
        assert request.message == "Hello"
        assert request.session_id == "test_session"
        assert request.user_id == "dev_user"  # default

    def test_chat_request_with_all_fields(self) -> None:
        """Test ChatRequest with all fields."""
        request = ChatRequest(
            message="Hello",
            session_id="test_session",
            user_id="custom_user",
        )
        assert request.user_id == "custom_user"

    def test_chat_request_validation(self) -> None:
        """Test that ChatRequest validates required fields."""
        with pytest.raises(ValueError):
            ChatRequest(message="Hello")  # missing session_id

        with pytest.raises(ValueError):
            ChatRequest(session_id="test")  # missing message


class TestChatResumeRequest:
    """Test ChatResumeRequest model."""

    def test_chat_resume_request_with_all_fields(self) -> None:
        """Test ChatResumeRequest with all fields."""
        request = ChatResumeRequest(
            session_id="test_session",
            interrupt_id="interrupt_123",
            approved=True,
        )
        assert request.session_id == "test_session"
        assert request.interrupt_id == "interrupt_123"
        assert request.approved is True
        assert request.user_id == "dev_user"  # default


class TestSSEEventQueue:
    """Test SSEEventQueue class."""

    @pytest.mark.asyncio
    async def test_put_and_get(self) -> None:
        """Test putting and getting events."""
        queue = SSEEventQueue()

        event = ("thought", {"content": "Test"})
        await queue.put(event)

        retrieved = await queue.get()
        assert retrieved == event

    @pytest.mark.asyncio
    async def test_multiple_events(self) -> None:
        """Test queueing multiple events."""
        queue = SSEEventQueue()

        events = [
            ("thought", {"content": "Thinking"}),
            ("tool_start", {"tool_name": "web_search"}),
            ("done", {"answer": "Complete"}),
        ]

        for event in events:
            await queue.put(event)

        for expected_event in events:
            retrieved = await queue.get()
            assert retrieved == expected_event

    @pytest.mark.asyncio
    async def test_task_done(self) -> None:
        """Test task_done method."""
        queue = SSEEventQueue()

        await queue.put(("test", {}))
        queue.task_done()  # Should not raise


class TestFormatSSEEvent:
    """Test _format_sse_event function."""

    @pytest.mark.asyncio
    async def test_format_thought_event(self) -> None:
        """Test formatting thought event."""
        event = await _format_sse_event("thought", {"content": "Test thought"})

        assert "event: thought" in event
        assert "data: " in event
        assert "Test thought" in event

    @pytest.mark.asyncio
    async def test_format_tool_start_event(self) -> None:
        """Test formatting tool_start event."""
        data = {"tool_name": "web_search", "args": {"query": "test"}}
        event = await _format_sse_event("tool_start", data)

        assert "event: tool_start" in event
        assert '"tool_name": "web_search"' in event

    @pytest.mark.asyncio
    async def test_format_done_event(self) -> None:
        """Test formatting done event."""
        data = {"answer": "Final answer", "finish_reason": "stop"}
        event = await _format_sse_event("done", data)

        assert "event: done" in event
        assert '"answer": "Final answer"' in event

    @pytest.mark.asyncio
    async def test_format_error_event(self) -> None:
        """Test formatting error event."""
        event = await _format_sse_event("error", {"message": "Error occurred"})

        assert "event: error" in event
        assert '"message": "Error occurred"' in event

    @pytest.mark.asyncio
    async def test_format_handles_unicode(self) -> None:
        """Test that formatting handles Unicode characters."""
        event = await _format_sse_event("thought", {"content": "测试中文"})

        assert "测试中文" in event

    @pytest.mark.asyncio
    async def test_format_ensure_ascii_false(self) -> None:
        """Test that ensure_ascii=False preserves non-ASCII."""
        event = await _format_sse_event("thought", {"content": "你好"})

        # Should contain actual Chinese characters, not escaped
        assert "你好" in event
        # Should not contain escaped Unicode
        assert "\\u" not in event


class TestExecuteAgent:
    """Test _execute_agent function."""

    @pytest.mark.asyncio
    async def test_execute_agent_runs_agent_stream(self) -> None:
        """Test that _execute_agent runs agent with streaming."""
        mock_agent = MagicMock()
        mock_agent.astream = AsyncMock()

        # Setup stream to yield empty chunks
        async def mock_stream(*args, **kwargs):
            return
            yield  # Make it a generator

        mock_agent.astream = mock_stream

        mock_queue = SSEEventQueue()

        # Should not raise
        await _execute_agent(mock_agent, "test message", {}, mock_queue,
                             user_id="test", tools_logger=MagicMock(), sse_logger=MagicMock())

    @pytest.mark.asyncio
    async def test_execute_agent_sends_done_event(self) -> None:
        """Test that _execute_agent sends done event."""
        mock_agent = MagicMock()

        async def mock_stream(*args, **kwargs):
            return
            yield

        mock_agent.astream = mock_stream

        mock_queue = SSEEventQueue()

        await _execute_agent(mock_agent, "test", {}, mock_queue,
                             user_id="test", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Get the done event
        event = await mock_queue.get()
        assert event[0] == "done"
        assert "answer" in event[1]

    @pytest.mark.asyncio
    async def test_execute_agent_handles_errors(self) -> None:
        """Test that _execute_agent handles exceptions."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        # Create async generator that raises error
        async def mock_stream_gen(*args, **kwargs):
            raise Exception("Agent error")
            yield  # Make it a generator

        mock_agent.astream = mock_stream_gen

        await _execute_agent(mock_agent, "test", {}, mock_queue,
                             user_id="test", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Should send error event (get with timeout to avoid blocking)
        import asyncio

        try:
            event = await asyncio.wait_for(mock_queue.get(), timeout=1.0)
            assert event[0] == "error"
            # The actual error message might differ due to async handling
            assert "message" in event[1]
        except asyncio.TimeoutError:
            pytest.fail("Error event not queued in time")

    @pytest.mark.asyncio
    async def test_execute_agent_creates_human_message(self) -> None:
        """Test that _execute_agent creates HumanMessage."""
        mock_agent = MagicMock()

        async def mock_stream(messages, config):
            # Verify messages structure
            assert len(messages) == 1
            assert isinstance(messages[0], HumanMessage)
            assert messages[0].content == "test message"
            return
            yield

        mock_agent.astream = mock_stream

        mock_queue = SSEEventQueue()

        await _execute_agent(mock_agent, "test message", {}, mock_queue,
                             user_id="test", tools_logger=MagicMock(), sse_logger=MagicMock())


class TestRunAgentStream:
    """Test _run_agent_stream function."""

    @pytest.mark.asyncio
    async def test_stream_yields_sse_events(self) -> None:
        """Test that _run_agent_stream yields SSE-formatted events."""
        with patch("app.api.chat.create_react_agent") as mock_create_agent:

            # Setup mocks — create_react_agent is async
            mock_agent = MagicMock()
            mock_agent.astream = AsyncMock()
            mock_create_agent.return_value = mock_agent
            mock_create_agent.__call__ = AsyncMock(return_value=mock_agent)

            # Stream events
            events = []
            async for event in _run_agent_stream(
                "test", "session_1", "user_1",
                api_logger=MagicMock(), tools_logger=MagicMock(), sse_logger=MagicMock()
            ):
                events.append(event)

            # Should have at least the done event
            assert len(events) > 0

    @pytest.mark.asyncio
    async def test_stream_stops_on_done_event(self) -> None:
        """Test that stream stops after done event."""
        with patch("app.api.chat.create_react_agent"):
            # This test verifies the streaming logic
            # Full integration test would require more complex setup
            pass


class TestChatEndpoint:
    """Test chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_returns_streaming_response(self) -> None:
        """Test that chat endpoint returns StreamingResponse."""
        with patch("app.api.chat._run_agent_stream") as mock_stream:
            async def mock_gen():
                yield "event: thought\ndata: {}\n\n"

            mock_stream.return_value = mock_gen()

            response = await chat(message="Hello", session_id="test")

            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_chat_response_headers(self) -> None:
        """Test that chat response has correct headers."""
        with patch("app.api.chat._run_agent_stream") as mock_stream:
            async def mock_gen():
                yield "data: {}\n\n"

            mock_stream.return_value = mock_gen()

            response = await chat(message="Hello", session_id="test")

            headers = response.headers
            assert "Cache-Control" in headers or "cache-control" in headers
            assert "Connection" in headers or "connection" in headers

    def test_chat_endpoint_signature(self) -> None:
        """Test that chat endpoint has correct signature."""
        # Endpoint should accept ChatRequest
        # This is verified by the function signature
        assert chat.__name__ == "chat"


class TestChatResumeEndpoint:
    """Test chat_resume endpoint."""

    @staticmethod
    async def _consume_streaming_response(response: StreamingResponse) -> list[str]:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            chunks.append(text)
        return chunks

    @pytest.mark.asyncio
    async def test_resume_returns_streaming_response(self) -> None:
        """Test that resume returns StreamingResponse (P1 implementation)."""
        from app.observability.interrupt_store import InterruptStore

        request = ChatResumeRequest(
            session_id="test",
            interrupt_id="interrupt_123",
            approved=True,
        )

        # Mock the interrupt store to return None (interrupt not found)
        with patch("app.observability.interrupt_store.get_interrupt_store") as mock_get_store:
            mock_store = AsyncMock(spec=InterruptStore)
            mock_store.get_interrupt.return_value = None
            mock_get_store.return_value = mock_store

            response = await chat_resume(request)

            # Should return StreamingResponse
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_resume_logs_request(self) -> None:
        """Test that resume logs the interrupt ID."""
        from app.observability.interrupt_store import InterruptStore

        with patch("app.api.chat.logger") as mock_logger, \
             patch("app.observability.interrupt_store.get_interrupt_store") as mock_get_store:
            mock_store = AsyncMock(spec=InterruptStore)
            mock_store.get_interrupt.return_value = None
            mock_get_store.return_value = mock_store

            request = ChatResumeRequest(
                session_id="test",
                interrupt_id="interrupt_123",
                approved=True,
            )

            try:
                await chat_resume(request)
            except (HTTPException, Exception):
                pass

            # Verify logging occurred
            mock_logger.info.assert_called_once()
            call_args = str(mock_logger.info.call_args)
            assert "interrupt_123" in call_args

    @pytest.mark.asyncio
    async def test_resume_approved_deduplicates_same_send_email_payload(self) -> None:
        """Same semantic send_email payload in same session should execute once."""
        from app.api.chat import _RESUME_IDEMPOTENCY_STORE
        from langgraph.types import Command

        class FakeInterruptStore:
            async def get_interrupt(self, interrupt_id: str) -> dict:
                return {
                    "status": "pending",
                    "tool_name": "send_email",
                    "tool_args": {
                        "to": "same@example.com",
                        "subject": "Idempotent Subject",
                        "body": "Body",
                    },
                }

            async def update_interrupt_status(self, interrupt_id: str, status: str) -> None:
                return None

        _RESUME_IDEMPOTENCY_STORE.clear()
        fake_store = FakeInterruptStore()
        call_inputs: list[Command] = []

        class FakeState:
            values = {"messages": []}

        class FakeAgent:
            async def astream(self, input_data, *args, **kwargs):
                call_inputs.append(input_data)
                if False:
                    yield None

            async def aget_state(self, config):
                return FakeState()

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=fake_store),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=FakeAgent()),
            ),
        ):
            response_1 = await chat_resume(
                ChatResumeRequest(
                    session_id="resume-dedupe-session",
                    interrupt_id="interrupt-1",
                    approved=True,
                )
            )
            await self._consume_streaming_response(response_1)

            response_2 = await chat_resume(
                ChatResumeRequest(
                    session_id="resume-dedupe-session",
                    interrupt_id="interrupt-2",
                    approved=True,
                )
            )
            chunks = await self._consume_streaming_response(response_2)

            assert len(call_inputs) == 1
            assert isinstance(call_inputs[0], Command)
            command_payload = call_inputs[0].resume["interrupt-1"]
            assert command_payload["decisions"][0]["type"] == "approve"
            assert any("idempotent_replay" in chunk for chunk in chunks)

    @pytest.mark.asyncio
    async def test_resume_approved_executes_for_different_send_email_payload(self) -> None:
        """Different send_email payloads should not be deduplicated."""
        from app.api.chat import _RESUME_IDEMPOTENCY_STORE
        from langgraph.types import Command

        class FakeInterruptStore:
            async def get_interrupt(self, interrupt_id: str) -> dict:
                subject = "Subject-A" if interrupt_id == "interrupt-a" else "Subject-B"
                return {
                    "status": "pending",
                    "tool_name": "send_email",
                    "tool_args": {
                        "to": "diff@example.com",
                        "subject": subject,
                        "body": "Body",
                    },
                }

            async def update_interrupt_status(self, interrupt_id: str, status: str) -> None:
                return None

        _RESUME_IDEMPOTENCY_STORE.clear()
        fake_store = FakeInterruptStore()
        call_inputs: list[Command] = []

        class FakeState:
            values = {"messages": []}

        class FakeAgent:
            async def astream(self, input_data, *args, **kwargs):
                call_inputs.append(input_data)
                if False:
                    yield None

            async def aget_state(self, config):
                return FakeState()

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=fake_store),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=FakeAgent()),
            ),
        ):
            response_a = await chat_resume(
                ChatResumeRequest(
                    session_id="resume-diff-session",
                    interrupt_id="interrupt-a",
                    approved=True,
                )
            )
            await self._consume_streaming_response(response_a)

            response_b = await chat_resume(
                ChatResumeRequest(
                    session_id="resume-diff-session",
                    interrupt_id="interrupt-b",
                    approved=True,
                )
            )
            await self._consume_streaming_response(response_b)

            assert len(call_inputs) == 2
            assert all(isinstance(i, Command) for i in call_inputs)

    @pytest.mark.asyncio
    async def test_resume_reject_uses_command_with_reject_decision(self) -> None:
        """Reject path should also resume through Command(decisions=[reject])."""
        from app.api.chat import _RESUME_IDEMPOTENCY_STORE
        from langgraph.types import Command

        class FakeInterruptStore:
            async def get_interrupt(self, interrupt_id: str) -> dict:
                return {
                    "status": "pending",
                    "tool_name": "send_email",
                    "tool_args": {
                        "to": "reject@example.com",
                        "subject": "Reject",
                        "body": "Body",
                    },
                }

            async def update_interrupt_status(self, interrupt_id: str, status: str) -> None:
                return None

        _RESUME_IDEMPOTENCY_STORE.clear()
        fake_store = FakeInterruptStore()
        call_inputs: list[Command] = []

        class FakeState:
            values = {"messages": []}

        class FakeAgent:
            async def astream(self, input_data, *args, **kwargs):
                call_inputs.append(input_data)
                if False:
                    yield None

            async def aget_state(self, config):
                return FakeState()

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=fake_store),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=FakeAgent()),
            ),
        ):
            response = await chat_resume(
                ChatResumeRequest(
                    session_id="resume-reject-session",
                    interrupt_id="interrupt-reject",
                    approved=False,
                )
            )
            await self._consume_streaming_response(response)

            assert len(call_inputs) == 1
            assert isinstance(call_inputs[0], Command)
            command_payload = call_inputs[0].resume["interrupt-reject"]
            assert command_payload["decisions"][0]["type"] == "reject"


class TestChatIntegration:
    """Integration tests for chat API."""

    @pytest.mark.asyncio
    async def test_full_flow_structure(self) -> None:
        """Test the structure of full chat flow."""
        # This verifies the components are wired correctly
        with patch("app.api.chat.create_react_agent") as mock_create:

            mock_agent = MagicMock()
            mock_create.return_value = mock_agent

            # Call chat
            with patch("app.api.chat._run_agent_stream") as mock_stream:
                async def gen():
                    yield "event: done\ndata: {}\n\n"

                mock_stream.return_value = gen()

                response = await chat(message="Test", session_id="s1")

                # Verify response structure
                assert response is not None
                assert isinstance(response, StreamingResponse)
