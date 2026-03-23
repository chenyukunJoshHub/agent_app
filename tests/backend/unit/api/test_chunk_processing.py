"""
Unit tests for LangGraph chunk processing in _execute_agent.

These tests verify that astream chunks are correctly parsed and converted to SSE events.
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.api.chat import SSEEventQueue, _execute_agent


class TestChunkProcessing:
    """Test LangGraph astream chunk processing."""

    @pytest.mark.asyncio
    async def test_process_messages_update_chunk(self) -> None:
        """Test processing 'updates' stream_mode chunk with messages."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        # Simulate LangGraph astream yielding updates
        async def mock_stream(*args, **kwargs):
            # Simulate a messages update chunk
            yield {
                "messages": [
                    AIMessage(
                        content="I should search for that information.",
                    )
                ]
            }

        mock_agent.astream = mock_stream

        # Execute agent
        await _execute_agent(
            mock_agent,
            "Search for latest AI news",
            {},
            mock_queue,
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

        # Simulate chunk with tool call
        async def mock_stream(*args, **kwargs):
            # AI message with tool calls
            yield {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "web_search",
                                "args": {"query": "test query"},
                                "id": "call_123",
                            }
                        ],
                    )
                ]
            }
            # Tool result message
            yield {
                "messages": [
                    ToolMessage(
                        content="Search results found",
                        tool_call_id="call_123",
                    )
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Search for something",
            {},
            mock_queue,
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
            # Chunk 1: Initial thought
            yield {
                "messages": [
                    AIMessage(
                        content="Let me think about this...",
                    )
                ]
            }
            # Chunk 2: Tool call
            yield {
                "messages": [
                    AIMessage(
                        content="I'll search for that.",
                        tool_calls=[
                            {
                                "name": "web_search",
                                "args": {"query": "test"},
                                "id": "call_1",
                            }
                        ],
                    )
                ]
            }
            # Chunk 3: Tool result
            yield {
                "messages": [
                    ToolMessage(
                        content="Result: test data",
                        tool_call_id="call_1",
                    )
                ]
            }
            # Chunk 4: Final answer
            yield {
                "messages": [
                    AIMessage(
                        content="Based on the search, here's the answer.",
                    )
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Test question",
            {},
            mock_queue,
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

        # In 'values' mode, chunks contain full state
        async def mock_stream(*args, **kwargs):
            yield {
                "messages": [
                    HumanMessage(content="Test"),
                    AIMessage(content="Response"),
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(
            mock_agent,
            "Test",
            {},
            mock_queue,
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
            yield {}  # Empty chunk
            yield {"messages": []}  # Empty messages

        mock_agent.astream = mock_stream

        # Should not raise
        await _execute_agent(mock_agent, "Test", {}, mock_queue)

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
            yield {
                "messages": [
                    AIMessage(content=test_content),
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue)

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
                yield {
                    "messages": [
                        AIMessage(content=f"Message {i}"),
                    ]
                }

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue)

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
            yield None  # Invalid chunk
            yield "invalid"  # Wrong type
            yield {"invalid_key": "value"}  # Missing messages key

        mock_agent.astream = mock_stream

        # Should not raise
        await _execute_agent(mock_agent, "Test", {}, mock_queue)

        # Should still send done event
        event = await mock_queue.get()
        assert event[0] == "done"

    @pytest.mark.asyncio
    async def test_handle_stream_exception(self) -> None:
        """Test handling exception during streaming."""
        mock_agent = MagicMock()
        mock_queue = SSEEventQueue()

        async def mock_stream(*args, **kwargs):
            yield {"messages": [AIMessage(content="Before error")]}
            raise RuntimeError("Stream error")

        mock_agent.astream = mock_stream

        # Should handle error gracefully
        await _execute_agent(mock_agent, "Test", {}, mock_queue)

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
            yield {
                "messages": [
                    AIMessage(
                        content="I'll search for that",
                        tool_calls=[
                            {
                                "name": "web_search",
                                "args": {"query": "test"},
                                "id": "call_1",
                            }
                        ],
                    )
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue)

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
            yield {
                "messages": [
                    AIMessage(
                        content="I'll use multiple tools",
                        tool_calls=[
                            {
                                "name": "web_search",
                                "args": {"query": "test1"},
                                "id": "call_1",
                            },
                            {
                                "name": "web_search",
                                "args": {"query": "test2"},
                                "id": "call_2",
                            },
                        ],
                    )
                ]
            }

        mock_agent.astream = mock_stream

        await _execute_agent(mock_agent, "Test", {}, mock_queue)

        # Should complete without error
        events = []
        while not mock_queue._queue.empty():
            event = await mock_queue.get()
            events.append(event)
            mock_queue.task_done()

        assert len(events) > 0
