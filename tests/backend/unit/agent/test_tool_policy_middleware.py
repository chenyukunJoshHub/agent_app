"""
Unit tests for policy-driven tool gating middleware.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.tools.base import ToolMeta
from app.tools.manager import ToolManager
from app.tools.policy import PolicyEngine


def _build_middleware():
    from app.agent.middleware.tool_policy import PolicyHITLMiddleware

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
            "delete_file": ToolMeta(
                effect_class="destructive",
                allowed_decisions=["deny"],
                idempotent=False,
            ),
        }
    )
    return PolicyHITLMiddleware(
        tool_manager=tool_manager,
        policy_engine=PolicyEngine(),
    )


class TestPolicyHITLMiddleware:
    @pytest.mark.asyncio
    async def test_allow_tool_call_passes_through(self) -> None:
        middleware = _build_middleware()
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "test"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(context=SimpleNamespace(sse_queue=None))

        result = await middleware.aafter_model(state, runtime)

        assert result is not None
        returned_ai = result["messages"][0]
        assert returned_ai.tool_calls == ai_message.tool_calls
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_deny_tool_call_is_replaced_with_error_tool_message(self) -> None:
        middleware = _build_middleware()
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "delete_file",
                    "args": {"path": "/tmp/test.txt"},
                    "id": "call-deny",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(context=SimpleNamespace(sse_queue=None))

        result = await middleware.aafter_model(state, runtime)

        assert result is not None
        returned_ai = result["messages"][0]
        assert returned_ai is not ai_message
        assert ai_message.tool_calls == [
            {
                "name": "delete_file",
                "args": {"path": "/tmp/test.txt"},
                "id": "call-deny",
                "type": "tool_call",
            }
        ]
        error_message = result["messages"][1]
        assert returned_ai.tool_calls == []
        assert isinstance(error_message, ToolMessage)
        assert error_message.tool_call_id == "call-deny"
        assert error_message.name == "delete_file"
        assert error_message.status == "error"
        assert "denied" in str(error_message.content).lower()

    @pytest.mark.asyncio
    async def test_ask_tool_call_uses_interrupt_and_approve_preserves_tool_call(self) -> None:
        middleware = _build_middleware()
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "send_email",
                    "args": {"to": "a@example.com", "subject": "x", "body": "y"},
                    "id": "call-ask",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(context=SimpleNamespace(sse_queue=None))

        with patch(
            "app.agent.middleware.tool_policy.interrupt",
            return_value={"decisions": [{"type": "approve"}]},
        ) as mock_interrupt:
            result = await middleware.aafter_model(state, runtime)

        assert mock_interrupt.called
        hitl_request = mock_interrupt.call_args[0][0]
        assert hitl_request["action_requests"][0]["name"] == "send_email"
        assert hitl_request["action_requests"][0]["args"]["to"] == "a@example.com"
        assert hitl_request["review_configs"][0]["allowed_decisions"] == ["approve", "reject"]
        returned_ai = result["messages"][0]
        assert returned_ai.tool_calls[0]["name"] == "send_email"

    @pytest.mark.asyncio
    async def test_reject_decision_injects_error_and_removes_tool_call(self) -> None:
        middleware = _build_middleware()
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "send_email",
                    "args": {"to": "a@example.com", "subject": "x", "body": "y"},
                    "id": "call-reject",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(context=SimpleNamespace(sse_queue=None))

        with patch(
            "app.agent.middleware.tool_policy.interrupt",
            return_value={"decisions": [{"type": "reject", "message": "nope"}]},
        ):
            result = await middleware.aafter_model(state, runtime)

        assert result is not None
        returned_ai = result["messages"][0]
        rejection = result["messages"][1]
        assert returned_ai.tool_calls == []
        assert isinstance(rejection, ToolMessage)
        assert rejection.status == "error"
        assert rejection.tool_call_id == "call-reject"
        assert rejection.content == "nope"

    @pytest.mark.asyncio
    async def test_mixed_allow_and_ask_keeps_allow_after_resume(self) -> None:
        middleware = _build_middleware()
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "langchain"},
                    "id": "call-allow",
                    "type": "tool_call",
                },
                {
                    "name": "send_email",
                    "args": {"to": "a@example.com", "subject": "x", "body": "y"},
                    "id": "call-ask",
                    "type": "tool_call",
                },
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(context=SimpleNamespace(sse_queue=None))

        with patch(
            "app.agent.middleware.tool_policy.interrupt",
            return_value={"decisions": [{"type": "approve"}]},
        ):
            result = await middleware.aafter_model(state, runtime)

        returned_ai = result["messages"][0]
        assert [tool_call["name"] for tool_call in returned_ai.tool_calls] == [
            "web_search",
            "send_email",
        ]

    @pytest.mark.asyncio
    async def test_revoked_session_grant_restores_ask_decision(self) -> None:
        middleware = _build_middleware()
        middleware.policy_engine.grant_session("send_email", session_id="thread-1")
        middleware.policy_engine.revoke_session("send_email", session_id="thread-1")
        ai_message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "send_email",
                    "args": {"to": "a@example.com", "subject": "x", "body": "y"},
                    "id": "call-revoked",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [ai_message]}
        runtime = SimpleNamespace(
            context=SimpleNamespace(sse_queue=None),
            config={"configurable": {"thread_id": "thread-1"}},
        )

        with patch(
            "app.agent.middleware.tool_policy.interrupt",
            return_value={"decisions": [{"type": "approve"}]},
        ) as mock_interrupt:
            result = await middleware.aafter_model(state, runtime)

        assert mock_interrupt.called
        returned_ai = result["messages"][0]
        assert returned_ai.tool_calls[0]["name"] == "send_email"
