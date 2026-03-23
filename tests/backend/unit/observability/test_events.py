"""
Unit tests for SSE event types.

These tests verify event dataclasses and serialization.
"""
import json


from app.observability.events import (
    DoneEvent,
    ErrorEvent,
    ThoughtEvent,
    ToolResultEvent,
    ToolStartEvent,
)


class TestThoughtEvent:
    """Test ThoughtEvent dataclass."""

    def test_thought_event_creation(self) -> None:
        """Test creating ThoughtEvent."""
        event = ThoughtEvent(content="Thinking about the answer", seq=1)
        assert event.content == "Thinking about the answer"
        assert event.seq == 1

    def test_thought_event_with_unicode(self) -> None:
        """Test ThoughtEvent with Unicode content."""
        event = ThoughtEvent(content="思考中", seq=1)
        assert event.content == "思考中"

    def test_thought_event_serialization(self) -> None:
        """Test serializing ThoughtEvent to dict."""
        event = ThoughtEvent(content="Test thought", seq=1)
        data = {
            "content": event.content,
            "seq": event.seq,
        }
        assert data["content"] == "Test thought"
        assert data["seq"] == 1


class TestToolStartEvent:
    """Test ToolStartEvent dataclass."""

    def test_tool_start_event_creation(self) -> None:
        """Test creating ToolStartEvent."""
        event = ToolStartEvent(
            tool_name="web_search",
            args={"query": "test"},
            seq=1,
        )
        assert event.tool_name == "web_search"
        assert event.args == {"query": "test"}
        assert event.seq == 1

    def test_tool_start_event_with_complex_args(self) -> None:
        """Test ToolStartEvent with complex arguments."""
        event = ToolStartEvent(
            tool_name="search",
            args={
                "query": "test",
                "limit": 10,
                "filters": {"date": "2024-01-01"},
            },
            seq=2,
        )
        assert event.args["limit"] == 10
        assert event.args["filters"]["date"] == "2024-01-01"


class TestToolResultEvent:
    """Test ToolResultEvent dataclass."""

    def test_tool_result_event_creation(self) -> None:
        """Test creating ToolResultEvent."""
        event = ToolResultEvent(
            tool_name="web_search",
            result="Search results",
            seq=2,
        )
        assert event.tool_name == "web_search"
        assert event.result == "Search results"
        assert event.seq == 2

    def test_tool_result_event_with_dict_result(self) -> None:
        """Test ToolResultEvent with dict result."""
        result = {"status": "success", "data": [1, 2, 3]}
        event = ToolResultEvent(
            tool_name="search",
            result=result,
            seq=2,
        )
        assert event.result == result


class TestDoneEvent:
    """Test DoneEvent dataclass."""

    def test_done_event_creation(self) -> None:
        """Test creating DoneEvent."""
        event = DoneEvent(
            answer="Final answer here",
            finish_reason="stop",
        )
        assert event.answer == "Final answer here"
        assert event.finish_reason == "stop"

    def test_done_event_with_different_finish_reasons(self) -> None:
        """Test DoneEvent with various finish reasons."""
        event1 = DoneEvent(answer="Answer", finish_reason="stop")
        event2 = DoneEvent(answer="Answer", finish_reason="length")
        event3 = DoneEvent(answer="Answer", finish_reason="tool_calls")

        assert event1.finish_reason == "stop"
        assert event2.finish_reason == "length"
        assert event3.finish_reason == "tool_calls"


class TestErrorEvent:
    """Test ErrorEvent dataclass."""

    def test_error_event_creation(self) -> None:
        """Test creating ErrorEvent."""
        event = ErrorEvent(message="Something went wrong")
        assert event.message == "Something went wrong"

    def test_error_event_with_detailed_message(self) -> None:
        """Test ErrorEvent with detailed error message."""
        message = "Error: tool 'web_search' failed with timeout"
        event = ErrorEvent(message=message)
        assert "timeout" in event.message


class TestEventSerialization:
    """Test event serialization for SSE."""

    def test_thought_event_to_sse_dict(self) -> None:
        """Test converting ThoughtEvent to SSE dict format."""
        event = ThoughtEvent(content="Test", seq=1)
        sse_dict = {
            "content": event.content,
            "seq": event.seq,
        }
        json_str = json.dumps(sse_dict, ensure_ascii=False)
        assert "Test" in json_str

    def test_tool_start_event_to_sse_dict(self) -> None:
        """Test converting ToolStartEvent to SSE dict format."""
        event = ToolStartEvent(
            tool_name="web_search",
            args={"query": "test"},
            seq=1,
        )
        sse_dict = {
            "tool_name": event.tool_name,
            "args": event.args,
            "seq": event.seq,
        }
        json_str = json.dumps(sse_dict, ensure_ascii=False)
        assert "web_search" in json_str

    def test_tool_result_event_to_sse_dict(self) -> None:
        """Test converting ToolResultEvent to SSE dict format."""
        event = ToolResultEvent(
            tool_name="web_search",
            result="Results",
            seq=2,
        )
        sse_dict = {
            "tool_name": event.tool_name,
            "result": event.result,
            "seq": event.seq,
        }
        json_str = json.dumps(sse_dict, ensure_ascii=False)
        assert "Results" in json_str

    def test_done_event_to_sse_dict(self) -> None:
        """Test converting DoneEvent to SSE dict format."""
        event = DoneEvent(answer="Final", finish_reason="stop")
        sse_dict = {
            "answer": event.answer,
            "finish_reason": event.finish_reason,
        }
        json_str = json.dumps(sse_dict, ensure_ascii=False)
        assert "Final" in json_str
        assert "stop" in json_str

    def test_error_event_to_sse_dict(self) -> None:
        """Test converting ErrorEvent to SSE dict format."""
        event = ErrorEvent(message="Error occurred")
        sse_dict = {
            "message": event.message,
        }
        json_str = json.dumps(sse_dict, ensure_ascii=False)
        assert "Error occurred" in json_str


class TestEventSequence:
    """Test event sequence numbering."""

    def test_sequence_increments(self) -> None:
        """Test that seq numbers increment properly."""
        event1 = ThoughtEvent(content="First", seq=1)
        event2 = ThoughtEvent(content="Second", seq=2)
        event3 = ToolStartEvent(tool_name="test", args={}, seq=3)

        assert event1.seq == 1
        assert event2.seq == 2
        assert event3.seq == 3
