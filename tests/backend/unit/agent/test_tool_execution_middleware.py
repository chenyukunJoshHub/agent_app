"""
Unit tests for tool execution governance middleware.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import ToolMessage

from app.tools.base import ToolMeta
from app.tools.idempotency import IdempotencyStore
from app.tools.manager import ToolManager


def _build_request(tool_name: str, args: dict, tool_call_id: str, thread_id: str = "session-1"):
    return SimpleNamespace(
        tool_call={
            "name": tool_name,
            "args": args,
            "id": tool_call_id,
            "type": "tool_call",
        },
        runtime=SimpleNamespace(
            config={"configurable": {"thread_id": thread_id}},
            context=SimpleNamespace(user_id="test-user"),
        ),
    )


def _build_execution_middleware():
    from app.agent.middleware.tool_execution import ToolExecutionMiddleware

    tool_manager = ToolManager(
        {
            "web_search": ToolMeta(
                effect_class="read",
                allowed_decisions=["allow"],
                idempotent=True,
                max_retries=2,
            ),
            "send_email": ToolMeta(
                effect_class="external_write",
                requires_hil=True,
                allowed_decisions=["ask", "deny"],
                idempotent=False,
            ),
        }
    )
    return ToolExecutionMiddleware(
        tool_manager=tool_manager,
        idempotency_store=IdempotencyStore(),
    )


class TestToolExecutionMiddleware:
    @pytest.mark.asyncio
    async def test_duplicate_idempotent_call_returns_skipped_tool_message(self) -> None:
        middleware = _build_execution_middleware()
        request = _build_request(
            "web_search",
            {"query": "langchain"},
            "call-1",
        )
        handler = AsyncMock(
            return_value=ToolMessage(
                content="result",
                name="web_search",
                tool_call_id="call-1",
            )
        )

        first = await middleware.awrap_tool_call(request, handler)
        second = await middleware.awrap_tool_call(request, handler)

        assert first.content == "result"
        assert second.tool_call_id == "call-1"
        assert second.name == "web_search"
        assert second.status == "success"
        assert "idempotent_replay" in str(second.content)
        assert handler.await_count == 1

    @pytest.mark.asyncio
    async def test_idempotent_tool_retries_then_succeeds(self) -> None:
        middleware = _build_execution_middleware()
        request = _build_request(
            "web_search",
            {"query": "retry me"},
            "call-2",
        )
        handler = AsyncMock(
            side_effect=[
                RuntimeError("temporary"),
                ToolMessage(
                    content="ok",
                    name="web_search",
                    tool_call_id="call-2",
                ),
            ]
        )

        result = await middleware.awrap_tool_call(request, handler)

        assert result.content == "ok"
        assert handler.await_count == 2

    @pytest.mark.asyncio
    async def test_non_idempotent_tool_does_not_retry(self) -> None:
        middleware = _build_execution_middleware()
        request = _build_request(
            "send_email",
            {"to": "a@example.com", "subject": "x", "body": "y"},
            "call-3",
        )
        handler = AsyncMock(side_effect=RuntimeError("boom"))

        result = await middleware.awrap_tool_call(request, handler)

        assert isinstance(result, ToolMessage)
        assert result.name == "send_email"
        assert result.tool_call_id == "call-3"
        assert result.status == "error"
        assert "boom" in str(result.content)
        assert handler.await_count == 1

    @pytest.mark.asyncio
    async def test_failed_idempotent_call_discards_mark_and_can_retry_later(self) -> None:
        middleware = _build_execution_middleware()
        request = _build_request(
            "web_search",
            {"query": "recover"},
            "call-4",
        )
        failing_handler = AsyncMock(side_effect=RuntimeError("still failing"))

        first = await middleware.awrap_tool_call(request, failing_handler)
        assert first.status == "error"

        succeeding_handler = AsyncMock(
            return_value=ToolMessage(
                content="recovered",
                name="web_search",
                tool_call_id="call-4",
            )
        )
        second = await middleware.awrap_tool_call(request, succeeding_handler)

        assert second.content == "recovered"
        assert succeeding_handler.await_count == 1
