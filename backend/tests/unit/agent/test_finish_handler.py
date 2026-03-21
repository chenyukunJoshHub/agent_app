"""
Unit tests for app.agent.finish_handler.

These tests verify finish reason handling logic.
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.agent.finish_handler import (
    FinishReason,
    extract_finish_reason,
    format_ai_message_finish,
    handle_finish_result,
)


class TestFinishReason:
    """Test FinishReason enum."""

    def test_finish_reason_values(self) -> None:
        """Test that FinishReason has all expected values."""
        assert FinishReason.STOP == "stop"
        assert FinishReason.TOOL_EXECUTIONS_COMPLETE == "tool_executions_complete"
        assert FinishReason.MAX_TOKENS == "max_tokens"
        assert FinishReason.TOKEN_LIMIT == "length"
        assert FinishReason.TOOL_ERROR == "tool_error"
        assert FinishReason.TOOL_LIMIT == "tool_limit"
        assert FinishReason.INTERRUPTED == "interrupted"
        assert FinishReason.ERROR == "error"
        assert FinishReason.TIMEOUT == "timeout"
        assert FinishReason.UNKNOWN == "unknown"


class TestExtractFinishReason:
    """Test extract_finish_reason function."""

    def test_extract_from_top_level_finish_reason(self) -> None:
        """Test extracting finish_reason from top level."""
        result = {"finish_reason": "stop"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.STOP

    def test_extract_from_response_metadata(self) -> None:
        """Test extracting finish_reason from response_metadata."""
        result = {"response_metadata": {"finish_reason": "max_tokens"}}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.MAX_TOKENS

    def test_extract_from_error(self) -> None:
        """Test extracting ERROR when error field exists."""
        result = {"error": "Something went wrong"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.ERROR

    def test_extract_from_interrupt(self) -> None:
        """Test extracting INTERRUPTED when __interrupt__ exists."""
        result = {"__interrupt__": {"tool_name": "send_email"}}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.INTERRUPTED

    def test_extract_from_output_default_stop(self) -> None:
        """Test default STOP when output exists."""
        result = {"output": "Here is the answer"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.STOP

    def test_extract_from_answer_default_stop(self) -> None:
        """Test default STOP when answer exists."""
        result = {"answer": "Here is the answer"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.STOP

    def test_extract_unknown_when_no_indicators(self) -> None:
        """Test UNKNOWN when no indicators present."""
        result = {"some_other_field": "value"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.UNKNOWN

    def test_extract_precedence_top_level_over_metadata(self) -> None:
        """Test that top-level finish_reason takes precedence."""
        result = {
            "finish_reason": "stop",
            "response_metadata": {"finish_reason": "max_tokens"},
        }
        reason = extract_finish_reason(result)
        assert reason == FinishReason.STOP

    def test_extract_precedence_error_over_output(self) -> None:
        """Test that error takes precedence over output."""
        result = {"error": "Error", "output": "Answer"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.ERROR

    def test_extract_precedence_interrupt_over_output(self) -> None:
        """Test that interrupt takes precedence over output."""
        result = {"__interrupt__": {}, "output": "Answer"}
        reason = extract_finish_reason(result)
        assert reason == FinishReason.INTERRUPTED

    def test_extract_all_finish_reason_types(self) -> None:
        """Test extracting all finish reason types."""
        test_cases = [
            ("stop", FinishReason.STOP),
            ("tool_executions_complete", FinishReason.TOOL_EXECUTIONS_COMPLETE),
            ("max_tokens", FinishReason.MAX_TOKENS),
            ("length", FinishReason.TOKEN_LIMIT),
            ("tool_error", FinishReason.TOOL_ERROR),
            ("tool_limit", FinishReason.TOOL_LIMIT),
            ("interrupted", FinishReason.INTERRUPTED),
            ("error", FinishReason.ERROR),
            ("timeout", FinishReason.TIMEOUT),
        ]

        for reason_str, expected in test_cases:
            result = {"finish_reason": reason_str}
            assert extract_finish_reason(result) == expected


class TestHandleFinishResult:
    """Test handle_finish_result function."""

    def test_handle_stop_success(self) -> None:
        """Test handling STOP finish reason."""
        result = {"finish_reason": "stop", "output": "Answer here"}
        response = handle_finish_result(result, session_id="test_session")

        assert response["finish_reason"] == FinishReason.STOP
        assert response["status"] == "success"
        assert response["answer"] == "Answer here"
        assert response["session_id"] == "test_session"

    def test_handle_tool_executions_complete(self) -> None:
        """Test handling TOOL_EXECUTIONS_COMPLETE."""
        result = {"finish_reason": "tool_executions_complete", "answer": "Done"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.TOOL_EXECUTIONS_COMPLETE
        assert response["status"] == "success"
        assert response["answer"] == "Done"

    def test_handle_max_tokens(self) -> None:
        """Test handling MAX_TOKENS with partial response."""
        result = {"finish_reason": "max_tokens", "output": "Partial answer"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.MAX_TOKENS
        assert response["status"] == "partial"
        assert "被截断" in response["answer"]
        assert "Partial answer" in response["answer"]

    def test_handle_token_limit(self) -> None:
        """Test handling TOKEN_LIMIT (length)."""
        result = {"finish_reason": "length", "output": "Long text..."}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.TOKEN_LIMIT
        assert response["status"] == "partial"
        assert "被截断" in response["answer"]

    def test_handle_tool_error(self) -> None:
        """Test handling TOOL_ERROR."""
        result = {"finish_reason": "tool_error", "error": "Search failed"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.TOOL_ERROR
        assert response["status"] == "error"
        assert "Search failed" in response["answer"]
        assert "执行工具时出错" in response["answer"]

    def test_handle_tool_error_default_message(self) -> None:
        """Test TOOL_ERROR with default message."""
        result = {"finish_reason": "tool_error"}
        response = handle_finish_result(result, session_id="s1")

        assert "工具执行失败" in response["answer"]

    def test_handle_interrupted(self) -> None:
        """Test handling INTERRUPTED."""
        interrupt_data = {"tool_name": "send_email", "args": {"to": "user@example.com"}}
        result = {"finish_reason": "interrupted", "__interrupt__": interrupt_data}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.INTERRUPTED
        assert response["status"] == "interrupted"
        assert response["answer"] == ""
        assert response["interrupt_data"] == interrupt_data

    def test_handle_error(self) -> None:
        """Test handling general ERROR."""
        result = {"finish_reason": "error", "error": "Something failed"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.ERROR
        assert response["status"] == "error"
        assert "Something failed" in response["answer"]
        assert "执行时出错" in response["answer"]

    def test_handle_timeout(self) -> None:
        """Test handling TIMEOUT."""
        result = {"finish_reason": "timeout", "error": "Request timed out"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.TIMEOUT
        assert response["status"] == "error"
        assert "Request timed out" in response["answer"]

    def test_handle_tool_limit(self) -> None:
        """Test handling TOOL_LIMIT."""
        result = {"finish_reason": "tool_limit"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.TOOL_LIMIT
        assert response["status"] == "error"
        assert "达到工具调用次数限制" in response["answer"]

    def test_handle_unknown(self) -> None:
        """Test handling UNKNOWN finish reason."""
        result = {"finish_reason": "unknown", "output": "Some answer"}
        response = handle_finish_result(result, session_id="s1")

        assert response["finish_reason"] == FinishReason.UNKNOWN
        assert response["status"] == "unknown"
        assert response["answer"] == "Some answer"

    def test_handle_unknown_with_empty_answer(self) -> None:
        """Test UNKNOWN with empty answer uses default message."""
        result = {"finish_reason": "unknown"}
        response = handle_finish_result(result, session_id="s1")

        assert response["status"] == "unknown"
        assert "无法确定结果" in response["answer"]

    def test_handle_output_over_answer(self) -> None:
        """Test that output takes precedence over answer."""
        result = {"output": "From output", "answer": "From answer"}
        response = handle_finish_result(result, session_id="s1")

        assert response["answer"] == "From output"

    def test_handle_answer_when_no_output(self) -> None:
        """Test that answer is used when output is missing."""
        result = {"answer": "From answer"}
        response = handle_finish_result(result, session_id="s1")

        assert response["answer"] == "From answer"

    def test_handle_empty_output_and_answer(self) -> None:
        """Test default message when neither output nor answer exists."""
        result = {}
        response = handle_finish_result(result, session_id="s1")

        # When finish_reason is UNKNOWN and no answer, uses default message
        assert response["status"] == "unknown"
        assert "无法确定结果" in response["answer"]


class TestFormatAIMessageFinish:
    """Test format_ai_message_finish function."""

    def test_format_with_finish_reason_in_metadata(self) -> None:
        """Test extracting finish_reason from AIMessage metadata."""
        message = AIMessage(
            content="Response",
            response_metadata={"finish_reason": "stop"},
        )
        reason = format_ai_message_finish(message)
        assert reason == FinishReason.STOP

    def test_format_with_max_tokens_in_metadata(self) -> None:
        """Test extracting max_tokens from metadata."""
        message = AIMessage(
            content="Partial",
            response_metadata={"finish_reason": "max_tokens"},
        )
        reason = format_ai_message_finish(message)
        assert reason == FinishReason.MAX_TOKENS

    def test_format_without_metadata(self) -> None:
        """Test AIMessage without response_metadata."""
        message = AIMessage(content="Response")
        reason = format_ai_message_finish(message)
        assert reason == FinishReason.UNKNOWN

    def test_format_with_empty_metadata(self) -> None:
        """Test AIMessage with empty response_metadata."""
        message = AIMessage(content="Response", response_metadata={})
        reason = format_ai_message_finish(message)
        assert reason == FinishReason.UNKNOWN

    def test_format_with_missing_finish_reason_in_metadata(self) -> None:
        """Test AIMessage with metadata but no finish_reason."""
        message = AIMessage(
            content="Response",
            response_metadata={"tokens_used": 100},
        )
        reason = format_ai_message_finish(message)
        assert reason == FinishReason.UNKNOWN

    def test_format_with_all_finish_reasons(self) -> None:
        """Test formatting all finish reason types from AIMessage."""
        test_cases = [
            "stop",
            "tool_executions_complete",
            "max_tokens",
            "length",
            "tool_error",
            "tool_limit",
            "interrupted",
            "error",
            "timeout",
        ]

        for reason_str in test_cases:
            message = AIMessage(
                content="Test",
                response_metadata={"finish_reason": reason_str},
            )
            reason = format_ai_message_finish(message)
            assert reason.value == reason_str
