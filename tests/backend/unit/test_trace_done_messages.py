"""
Unit tests for trace.py done event message serialization.

This file tests the _serialize_message function before it is moved to trace.py.
"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage


def _serialize_message(msg):
    """从 trace.py 提取的序列化函数（先在此处实现，再搬到 trace.py）"""
    role_map = {
        "HumanMessage": "user",
        "AIMessage": "assistant",
        "ToolMessage": "tool",
        "SystemMessage": "system",
    }
    role = role_map.get(type(msg).__name__, "assistant")
    serialized = {"role": role, "content": str(msg.content or "")}
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        serialized["tool_calls"] = [
            {"id": tc.get("id", ""), "type": "function",
             "function": {"name": tc.get("name", ""), "arguments": str(tc.get("args", {}))}}
            for tc in msg.tool_calls
        ]
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        serialized["tool_call_id"] = msg.tool_call_id
    return serialized


class TestSerializeMessage:
    def test_human_message_serializes_to_user(self):
        msg = HumanMessage(content="hello")
        result = _serialize_message(msg)
        assert result["role"] == "user"
        assert result["content"] == "hello"

    def test_ai_message_serializes_to_assistant(self):
        msg = AIMessage(content="hi there")
        result = _serialize_message(msg)
        assert result["role"] == "assistant"

    def test_tool_message_serializes_to_tool_with_tool_call_id(self):
        msg = ToolMessage(content="result", tool_call_id="tc1")
        result = _serialize_message(msg)
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "tc1"

    def test_system_message_filtered_out_by_frontend_roles(self):
        """SystemMessage 序列化后 role='system'，前端过滤掉，不在 user/assistant/tool 中"""
        msg = SystemMessage(content="system prompt")
        result = _serialize_message(msg)
        # 确认 role='system'，前端过滤逻辑会排除它
        assert result["role"] == "system"

    def test_filter_keeps_only_frontend_roles(self):
        messages = [
            HumanMessage(content="hi"),
            SystemMessage(content="sys"),
            AIMessage(content="hello"),
            ToolMessage(content="result", tool_call_id="tc1"),
        ]
        serialized = [_serialize_message(m) for m in messages]
        filtered = [m for m in serialized if m["role"] in ("user", "assistant", "tool")]
        assert len(filtered) == 3
        assert filtered[0]["role"] == "user"
        assert filtered[1]["role"] == "assistant"
        assert filtered[2]["role"] == "tool"
