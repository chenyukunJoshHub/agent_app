"""SSE Event types for streaming."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ThoughtEvent:
    """Event representing LLM reasoning/thought content."""

    content: str
    seq: int


@dataclass
class ToolStartEvent:
    """Event representing the start of a tool execution."""

    tool_name: str
    args: dict[str, Any]
    seq: int


@dataclass
class ToolResultEvent:
    """Event representing the result of a tool execution."""

    tool_name: str
    result: Any
    seq: int


@dataclass
class TokenUpdateEvent:
    """Event representing real-time token usage update."""

    current: int  # 当前已使用 token 数
    budget: int  # 总预算 token 数
    input_tokens: int  # 输入 token 数
    output_tokens: int  # 输出 token 数
    remaining: int  # 剩余 token 数


@dataclass
class DoneEvent:
    """Event representing completion of the agent turn."""

    answer: str
    finish_reason: str
    token_usage: dict[str, int] | None = None  # 总 token 使用情况


@dataclass
class ErrorEvent:
    """Event representing an error during execution."""

    message: str


__all__ = [
    "ThoughtEvent",
    "ToolStartEvent",
    "ToolResultEvent",
    "TokenUpdateEvent",
    "DoneEvent",
    "ErrorEvent",
]
