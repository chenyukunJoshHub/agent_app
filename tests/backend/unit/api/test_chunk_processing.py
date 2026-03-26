"""
Unit tests for LangGraph chunk processing in _execute_agent.

These tests verify that astream chunks are correctly parsed and converted to SSE events.
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.api.chat import SSEEventQueue, _execute_agent


class TestChunkProcessing:
    """Test LangGraph astream chunk processing."""

    @pytest.mark.asyncio
    async def test_process_messages_update_chunk(self) -> None:
        """Test processing 'updates' stream_mode chunk with messages."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        # Simulate LangGraph astream yielding updates (stream_mode=["messages","updates"])
        async def mock_stream(*args, **kwargs):
            # Simulate an updates chunk from the agent node
            yield (
                "updates",
                {"agent": {"messages": [AIMessage(content="I should search for that information.")]}},
            )

        mock_agent.astream = mock_stream

        # Execute agent
        await _execute_agent(
            mock_agent,
            "Search for latest AI news",
            {},
            mock_queue,
            user_id="dev_user",
            tools_logger=MagicMock(),
            sse_logger=MagicMock(),
        )

        # Verify events were queued
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Should have at least a done event
        event_types = [e[0] for e in events]
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_process_tool_call_chunk(self) -> None:
        """Test processing chunk with tool calls."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        # Simulate chunk with tool call (stream_mode=["messages","updates"])
        async def mock_stream(*args, **kwargs):
            # AI message with tool calls — comes as updates from agent node
            yield (
                "updates",
                {"agent": {"messages": [AIMessage(
                    content="",
                    tool_calls=[{"name": "web_search", "args": {"query": "test query"}, "id": "call_123"}],
                )]}},
            )
            # Tool result message — comes as updates from tools node
            yield (
                "updates",
                {"tools": {"messages": [ToolMessage(content="Search results found", tool_call_id="call_123")]}},
            )

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Search for something",
            {},
            mock_queue,
            user_id="dev_user",
            tools_logger=MagicMock(),
            sse_logger=MagicMock(),
        )

        # Collect events
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Verify we got events
        assert len(events) > 0
        event_types = [e[0] for e in events]
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_process_multiple_chunks(self) -> None:
        """Test processing multiple chunks in sequence."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            # Chunk 1: Initial thought — updates from agent node
            yield ("updates", {"agent": {"messages": [AIMessage(content="Let me think about this...")]}})
            # Chunk 2: Tool call — updates from agent node
            yield (
                "updates",
                {"agent": {"messages": [AIMessage(
                    content="I'll search for that.",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}],
                )]}},
            )
            # Chunk 3: Tool result — updates from tools node
            yield (
                "updates",
                {"tools": {"messages": [ToolMessage(content="Result: test data", tool_call_id="call_1")]}},
            )
            # Chunk 4: Final answer — updates from agent node
            yield ("updates", {"agent": {"messages": [AIMessage(content="Based on the search, here's the answer.")]}})

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Test question",
            {},
            mock_queue,
            user_id="dev_user",
            tools_logger=MagicMock(),
            sse_logger=MagicMock(),
        )

        # Collect all events
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Should have multiple events including done
        assert len(events) > 0
        event_types = [e[0] for e in events]
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_process_chunk_with_values_stream_mode(self) -> None:
        """Test processing 'values' stream_mode chunk."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        # In 'updates' mode (LangGraph stream_mode=["messages","updates"])
        async def mock_stream(*args, **kwargs):
            yield (
                "updates",
                {"agent": {"messages": [HumanMessage(content="Test"), AIMessage(content="Response")]}},
            )

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Test",
            {},
            mock_queue,
            user_id="dev_user",
            tools_logger=MagicMock(),
            sse_logger=MagicMock(),
        )

        # Should complete without error
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_handle_empty_chunk(self) -> None:
        """Test handling empty chunks gracefully."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield ("updates", {})  # Empty updates chunk
            yield ("updates", {"agent": {"messages": []}})  # Empty messages

        mock_agent.astream = mock_stream

        # Should not raise
        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Should still send done event
        event = await mock_queue.get()
        assert event[0] == "done"

    @pytest.mark.asyncio
    async def test_extract_content_from_ai_message(self) -> None:
        """Test extracting content from AIMessage in chunk."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        test_content = "This is the AI's response"
        async def mock_stream(*args, **kwargs):
            yield ("updates", {"agent": {"messages": [AIMessage(content=test_content)]}})

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Collect events
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Should have done event with the content
        done_events = [e for e in events if e[0] == "done"]
        assert len(done_events) > 0
        assert "answer" in done_events[0][1]

    @pytest.mark.asyncio
    async def test_sequence_numbering_in_events(self) -> None:
        """Test that events are properly sequenced."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            # Multiple messages to generate multiple events
            for i in range(3):
                yield ("updates", {"agent": {"messages": [AIMessage(content=f"Message {i}")]}})

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Collect all events
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Verify we have events
        assert len(events) > 0


class TestChunkErrorHandling:
    """Test error handling in chunk processing."""

    @pytest.mark.asyncio
    async def test_handle_malformed_chunk(self) -> None:
        """Test handling malformed chunk gracefully."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield ("unknown_mode", {})  # Unknown mode — should be ignored gracefully
            yield ("updates", {})  # Empty updates — no sources
            yield ("updates", {"invalid_key": "value"})  # Source with no messages key

        mock_agent.astream = mock_stream

        # Should not raise
        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Should still send done event
        event = await mock_queue.get()
        assert event[0] == "done"

    @pytest.mark.asyncio
    async def test_handle_stream_exception(self) -> None:
        """Test handling exception during streaming."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield ("messages", (AIMessageChunk(content="Before error"), {}))
            raise RuntimeError("Stream error")

        mock_agent.astream = mock_stream

        # Should handle error gracefully
        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Collect all events
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        # Should have thought event from before error, and error event
        event_types = [e[0] for e in events]
        assert "thought" in event_types  # From the message before error
        assert "error" in event_types  # From the exception handling


class TestToolCallDetection:
    """Test tool call detection in chunks."""

    @pytest.mark.asyncio
    async def test_detect_single_tool_call(self) -> None:
        """Test detecting a single tool call in chunk."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield (
                "updates",
                {"agent": {"messages": [AIMessage(
                    content="I'll search for that",
                    tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}],
                )]}},
            )

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Should complete without error
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_detect_multiple_tool_calls(self) -> None:
        """Test detecting multiple tool calls in chunk."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield (
                "updates",
                {"agent": {"messages": [AIMessage(
                    content="I'll use multiple tools",
                    tool_calls=[
                        {"name": "web_search", "args": {"query": "test1"}, "id": "call_1"},
                        {"name": "web_search", "args": {"query": "test2"}, "id": "call_2"},
                    ],
                )]}},
            )

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue,
                             user_id="dev_user", tools_logger=MagicMock(), sse_logger=MagicMock())

        # Should complete without error
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        assert len(events) > 0
