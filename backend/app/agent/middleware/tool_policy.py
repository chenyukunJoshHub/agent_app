from __future__ import annotations

import copy
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.human_in_the_loop import (
    ActionRequest,
    HITLRequest,
    ReviewConfig,
)
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langgraph.types import interrupt

from app.tools.base import ToolMeta
from app.tools.manager import ToolManager
from app.tools.policy import PolicyEngine


class PolicyHITLMiddleware(AgentMiddleware):
    """Apply ToolMeta/PolicyEngine decisions before the official ToolNode runs."""

    def __init__(
        self,
        tool_manager: ToolManager,
        policy_engine: PolicyEngine,
        description_prefix: str = "Tool execution requires approval",
    ) -> None:
        self.tool_manager = tool_manager
        self.policy_engine = policy_engine
        self.description_prefix = description_prefix

    def _fallback_meta(self) -> ToolMeta:
        return ToolMeta(
            effect_class="external_write",
            allowed_decisions=["ask", "deny"],
            idempotent=False,
        )

    def _decision_to_review_config(self, tool_name: str) -> ReviewConfig:
        return ReviewConfig(
            action_name=tool_name,
            allowed_decisions=["approve", "reject"],
        )

    def _action_request(self, tool_call: ToolCall) -> ActionRequest:
        return ActionRequest(
            name=tool_call["name"],
            args=tool_call["args"],
            description=(
                f"{self.description_prefix}\n\n"
                f"Tool: {tool_call['name']}\n"
                f"Args: {tool_call['args']}"
            ),
        )

    @staticmethod
    def _extract_session_id(runtime: Any) -> str | None:
        configurable = getattr(runtime, "config", {}) or {}
        if isinstance(configurable, dict):
            configurable = configurable.get("configurable", {})
        if isinstance(configurable, dict):
            value = configurable.get("thread_id")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _rejection_message(tool_call: ToolCall, decision: dict[str, Any]) -> ToolMessage:
        content = decision.get("message") or (
            f"User rejected the tool call for `{tool_call['name']}` with id {tool_call['id']}"
        )
        return ToolMessage(
            content=content,
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
            status="error",
        )

    @staticmethod
    def _denial_message(tool_call: ToolCall) -> ToolMessage:
        return ToolMessage(
            content=f"Policy denied tool call `{tool_call['name']}`.",
            name=tool_call["name"],
            tool_call_id=tool_call["id"],
            status="error",
        )

    def _process_with_decisions(
        self,
        tool_calls: list[ToolCall],
        interrupt_indices: list[int],
        decisions: list[dict[str, Any]],
    ) -> tuple[list[ToolCall], list[ToolMessage]]:
        revised_tool_calls: list[ToolCall] = []
        artificial_tool_messages: list[ToolMessage] = []
        decision_idx = 0

        for idx, tool_call in enumerate(tool_calls):
            if idx not in interrupt_indices:
                revised_tool_calls.append(tool_call)
                continue

            decision = decisions[decision_idx]
            decision_idx += 1
            if decision["type"] == "approve":
                revised_tool_calls.append(tool_call)
                continue
            if decision["type"] == "reject":
                artificial_tool_messages.append(self._rejection_message(tool_call, decision))
                continue
            raise ValueError(f"Unsupported HITL decision: {decision}")

        return revised_tool_calls, artificial_tool_messages

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_ai_msg = next((msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None)
        if not last_ai_msg or not last_ai_msg.tool_calls:
            return None

        session_id = self._extract_session_id(runtime)
        revised_tool_calls: list[ToolCall] = []
        artificial_tool_messages: list[ToolMessage] = []
        action_requests: list[ActionRequest] = []
        review_configs: list[ReviewConfig] = []
        interrupt_indices: list[int] = []

        for idx, tool_call in enumerate(last_ai_msg.tool_calls):
            meta = self.tool_manager.get_meta(tool_call["name"]) or self._fallback_meta()
            decision = self.policy_engine.decide(
                tool_call["name"],
                meta.effect_class,
                meta.allowed_decisions,
                session_id=session_id,
            )
            if decision == "allow":
                revised_tool_calls.append(tool_call)
            elif decision == "deny":
                artificial_tool_messages.append(self._denial_message(tool_call))
            elif decision == "ask":
                revised_tool_calls.append(tool_call)
                action_requests.append(self._action_request(tool_call))
                review_configs.append(self._decision_to_review_config(tool_call["name"]))
                interrupt_indices.append(idx)
            else:
                raise ValueError(f"Unsupported policy decision: {decision}")

        if action_requests:
            hitl_request = HITLRequest(
                action_requests=action_requests,
                review_configs=review_configs,
            )
            decisions = interrupt(hitl_request)["decisions"]
            # Rebuild from original order after human review so allow + ask batches
            # preserve the original tool ordering.
            revised_tool_calls, decision_messages = self._process_with_decisions(
                list(last_ai_msg.tool_calls),
                interrupt_indices,
                decisions,
            )
            # Denied calls were already removed before interrupt. Keep those rejections too.
            artificial_tool_messages.extend(
                [msg for msg in decision_messages if isinstance(msg, ToolMessage)]
            )
            denied_call_ids = {msg.tool_call_id for msg in artificial_tool_messages}
            revised_tool_calls = [
                tc for tc in revised_tool_calls if tc["id"] not in denied_call_ids
            ]

        revised_ai_msg = copy.deepcopy(last_ai_msg)
        revised_ai_msg.tool_calls = revised_tool_calls
        return {"messages": [revised_ai_msg, *artificial_tool_messages]}
