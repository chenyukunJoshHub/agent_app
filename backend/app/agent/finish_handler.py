"""
Finish Reason Handler for agent execution results.

P0: Handles all finish_reason cases with appropriate responses.
"""
from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage
from loguru import logger


class FinishReason(StrEnum):
    """Agent finish reason categories."""

    # Successful completion
    STOP = "stop"  # Agent completed naturally
    TOOL_EXECUTIONS_COMPLETE = "tool_executions_complete"  # All tools executed

    # Length-related stops
    MAX_TOKENS = "max_tokens"  # Token limit reached
    TOKEN_LIMIT = "length"  # Content length limit

    # Tool-related stops
    TOOL_ERROR = "tool_error"  # Tool execution failed
    TOOL_LIMIT = "tool_limit"  # Too many tool calls

    # Interruption
    INTERRUPTED = "interrupted"  # Human-in-the-loop interrupt

    # Errors
    ERROR = "error"  # General error
    TIMEOUT = "timeout"  # Execution timeout

    # Unknown
    UNKNOWN = "unknown"  # Unable to determine


def extract_finish_reason(result: dict[str, Any]) -> FinishReason:
    """
    Extract finish reason from agent result.

    Args:
        result: Agent execution result

    Returns:
        FinishReason: Categorized finish reason
    """
    # Check for explicit finish_reason in metadata
    if "finish_reason" in result:
        return FinishReason(result["finish_reason"])

    # Check response metadata
    if "response_metadata" in result:
        metadata = result["response_metadata"]
        if "finish_reason" in metadata:
            return FinishReason(metadata["finish_reason"])

    # Check for error
    if "error" in result:
        return FinishReason.ERROR

    # Check for interrupt
    if "__interrupt__" in result:
        return FinishReason.INTERRUPTED

    # Default to STOP if we have a valid response
    if "output" in result or "answer" in result:
        return FinishReason.STOP

    return FinishReason.UNKNOWN


def handle_finish_result(
    result: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    """
    Handle agent execution result based on finish reason.

    P0: Returns formatted response for all finish reasons.

    Args:
        result: Agent execution result
        session_id: Session identifier

    Returns:
        dict: Formatted response with finish_reason handling
    """
    finish_reason = extract_finish_reason(result)
    logger.info(f"Agent finished with reason: {finish_reason}")

    # Extract answer/output
    answer = result.get("output") or result.get("answer", "")

    # Handle different finish reasons
    match finish_reason:
        case FinishReason.STOP | FinishReason.TOOL_EXECUTIONS_COMPLETE:
            # Successful completion
            return {
                "finish_reason": finish_reason,
                "status": "success",
                "answer": answer,
                "session_id": session_id,
            }

        case FinishReason.MAX_TOKENS | FinishReason.TOKEN_LIMIT:
            # Token limit - partial response
            logger.warning(f"Token limit reached: {finish_reason}")
            return {
                "finish_reason": finish_reason,
                "status": "partial",
                "answer": f"{answer}\n\n[响应因达到长度限制被截断]",
                "session_id": session_id,
            }

        case FinishReason.TOOL_ERROR:
            # Tool execution failed
            error_msg = result.get("error", "工具执行失败")
            logger.error(f"Tool error: {error_msg}")
            return {
                "finish_reason": finish_reason,
                "status": "error",
                "answer": f"抱歉，执行工具时出错：{error_msg}",
                "session_id": session_id,
            }

        case FinishReason.INTERRUPTED:
            # HIL interrupt
            logger.info("Agent interrupted, waiting for human input")
            return {
                "finish_reason": finish_reason,
                "status": "interrupted",
                "answer": "",
                "interrupt_data": result.get("__interrupt__"),
                "session_id": session_id,
            }

        case FinishReason.ERROR | FinishReason.TIMEOUT:
            # General error
            error_msg = result.get("error", "执行出错")
            logger.error(f"Execution error: {error_msg}")
            return {
                "finish_reason": finish_reason,
                "status": "error",
                "answer": f"抱歉，执行时出错：{error_msg}",
                "session_id": session_id,
            }

        case FinishReason.TOOL_LIMIT:
            # Too many tool calls
            logger.warning("Tool call limit reached")
            return {
                "finish_reason": finish_reason,
                "status": "error",
                "answer": "抱歉，已达到工具调用次数限制，请重新开始对话",
                "session_id": session_id,
            }

        case _:
            # Unknown finish reason
            logger.warning(f"Unknown finish reason: {finish_reason}")
            return {
                "finish_reason": finish_reason,
                "status": "unknown",
                "answer": answer or "执行完成，但无法确定结果",
                "session_id": session_id,
            }


def format_ai_message_finish(message: AIMessage) -> FinishReason:
    """
    Extract finish reason from AIMessage response metadata.

    Args:
        message: AI message from agent

    Returns:
        FinishReason: Categorized finish reason
    """
    if not message.response_metadata:
        return FinishReason.UNKNOWN

    return FinishReason(
        message.response_metadata.get("finish_reason", "unknown")
    )


__all__ = [
    "FinishReason",
    "extract_finish_reason",
    "handle_finish_result",
    "format_ai_message_finish",
]
