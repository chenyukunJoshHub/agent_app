"""
Integration tests for Layer4 execution semantics (Path A/B/A+B only).

Scope:
- Path A: parallel tool execution in one step
- Path B: serial multi-step execution with dependency
- Path A+B: parallel first step, serial second step
- HIL + idempotency RED case (known gap, xfail)

Path C (task_dispatch) intentionally excluded.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Sequence
from unittest.mock import AsyncMock, patch

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from pydantic import Field


@dataclass
class EventCapture:
    """Simple in-memory event recorder for deterministic assertions."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event_type: str, **payload: Any) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "ts": time.perf_counter(),
                **payload,
            }
        )

    def first(self, event_type: str, tool_name: str) -> dict[str, Any]:
        for event in self.events:
            if event["event_type"] == event_type and event.get("tool_name") == tool_name:
                return event
        raise AssertionError(f"Event not found: {event_type=} {tool_name=}")


class ScriptedModel(BaseChatModel):
    """
    Deterministic chat model that returns scripted AIMessage responses.

    Each script step can be:
    - dict: {"content": str, "tool_calls": list[dict]}
    - callable: receives messages and returns AIMessage
    """

    script: list[Any] = Field(default_factory=list)
    step: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ScriptedModel":
        # create_agent binds tools into the model. For deterministic tests we don't need
        # special binding behavior, so we return self.
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.step >= len(self.script):
            ai_message = AIMessage(content="done")
        else:
            action = self.script[self.step]
            self.step += 1
            if callable(action):
                ai_message = action(messages)
            else:
                ai_message = AIMessage(
                    content=action.get("content", ""),
                    tool_calls=action.get("tool_calls", []),
                )

        return ChatResult(generations=[ChatGeneration(message=ai_message)])


def _create_timed_unary_tool(
    name: str,
    delay_seconds: float,
    capture: EventCapture,
    result_prefix: str | None = None,
):
    async def _impl(payload: str) -> str:
        capture.record("tool_start", tool_name=name, args={"payload": payload})
        await asyncio.sleep(delay_seconds)
        result = f"{result_prefix or name}:{payload}"
        capture.record("tool_result", tool_name=name, result=result)
        return result

    _impl.__name__ = name
    _impl.__doc__ = f"Timed unary tool {name} for integration tests."
    return tool(_impl)


def _create_timed_merge_tool(name: str, delay_seconds: float, capture: EventCapture):
    async def _impl(left: str, right: str) -> str:
        capture.record("tool_start", tool_name=name, args={"left": left, "right": right})
        await asyncio.sleep(delay_seconds)
        result = f"{name}:{left}|{right}"
        capture.record("tool_result", tool_name=name, result=result)
        return result

    _impl.__name__ = name
    _impl.__doc__ = f"Timed merge tool {name} for integration tests."
    return tool(_impl)


async def _run_agent(
    model: BaseChatModel,
    tools: list[Any],
    capture: EventCapture,
    user_message: str = "run",
) -> dict[str, Any]:
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt="Execution layer integration test.",
    )
    result = await agent.ainvoke({"messages": [HumanMessage(content=user_message)]})
    capture.record("done", message_count=len(result.get("messages", [])))
    return result


async def _consume_streaming_response(response: Any, capture: EventCapture) -> None:
    async for chunk in response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        if text.startswith("event: "):
            event_type = text.splitlines()[0].replace("event: ", "").strip()
            capture.record(event_type)


class TestExecutionLayerABMix:
    @pytest.mark.asyncio
    async def test_path_a_parallel_exec_overlaps_and_is_faster_than_serial_sum(self) -> None:
        capture = EventCapture()
        delay = 0.35
        read_alpha = _create_timed_unary_tool("read_alpha", delay, capture)
        read_beta = _create_timed_unary_tool("read_beta", delay, capture)

        model = ScriptedModel(
            script=[
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_alpha", "name": "read_alpha", "args": {"payload": "A"}},
                        {"id": "call_beta", "name": "read_beta", "args": {"payload": "B"}},
                    ],
                },
                {"content": "parallel complete"},
            ]
        )

        started_at = time.perf_counter()
        result = await _run_agent(model, [read_alpha, read_beta], capture)
        total_elapsed = time.perf_counter() - started_at

        alpha_start = capture.first("tool_start", "read_alpha")["ts"]
        alpha_end = capture.first("tool_result", "read_alpha")["ts"]
        beta_start = capture.first("tool_start", "read_beta")["ts"]
        beta_end = capture.first("tool_result", "read_beta")["ts"]

        # Overlap means both tasks were running at the same time.
        assert alpha_start < beta_end
        assert beta_start < alpha_end

        # Parallel wall-clock time should be significantly lower than serial sum (2 * delay).
        assert total_elapsed < (delay * 2) - 0.05

        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 2

    @pytest.mark.asyncio
    async def test_path_b_serial_exec_waits_for_previous_result(self) -> None:
        capture = EventCapture()
        fetch_primary = _create_timed_unary_tool(
            "fetch_primary",
            delay_seconds=0.20,
            capture=capture,
            result_prefix="fetch_primary",
        )
        derive_secondary = _create_timed_unary_tool(
            "derive_secondary",
            delay_seconds=0.20,
            capture=capture,
            result_prefix="derive_secondary",
        )

        def step_two_with_dependency(messages: list[BaseMessage]) -> AIMessage:
            first_tool_msg = next(
                m for m in reversed(messages) if isinstance(m, ToolMessage)
            )
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_secondary",
                        "name": "derive_secondary",
                        "args": {"payload": str(first_tool_msg.content)},
                    }
                ],
            )

        model = ScriptedModel(
            script=[
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_primary", "name": "fetch_primary", "args": {"payload": "seed"}}
                    ],
                },
                step_two_with_dependency,
                {"content": "serial complete"},
            ]
        )

        result = await _run_agent(model, [fetch_primary, derive_secondary], capture)

        primary_end = capture.first("tool_result", "fetch_primary")["ts"]
        secondary_start_event = capture.first("tool_start", "derive_secondary")

        # Serial path requires second tool to start after first tool finished.
        assert secondary_start_event["ts"] >= primary_end
        assert secondary_start_event["args"]["payload"].startswith("fetch_primary:")

        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 2
        assert str(tool_messages[1].content).startswith("derive_secondary:fetch_primary:")

    @pytest.mark.asyncio
    async def test_path_a_plus_b_mixed_parallel_then_serial(self) -> None:
        capture = EventCapture()
        read_left = _create_timed_unary_tool("read_left", 0.25, capture, result_prefix="left")
        read_right = _create_timed_unary_tool("read_right", 0.25, capture, result_prefix="right")
        merge_summary = _create_timed_merge_tool("merge_summary", 0.15, capture)

        def second_step_merge(messages: list[BaseMessage]) -> AIMessage:
            tool_outputs = [
                str(m.content) for m in messages if isinstance(m, ToolMessage)
            ]
            left_output, right_output = tool_outputs[-2], tool_outputs[-1]
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_merge",
                        "name": "merge_summary",
                        "args": {"left": left_output, "right": right_output},
                    }
                ],
            )

        model = ScriptedModel(
            script=[
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_left", "name": "read_left", "args": {"payload": "L"}},
                        {"id": "call_right", "name": "read_right", "args": {"payload": "R"}},
                    ],
                },
                second_step_merge,
                {"content": "mixed complete"},
            ]
        )

        result = await _run_agent(model, [read_left, read_right, merge_summary], capture)

        left_start = capture.first("tool_start", "read_left")["ts"]
        left_end = capture.first("tool_result", "read_left")["ts"]
        right_start = capture.first("tool_start", "read_right")["ts"]
        right_end = capture.first("tool_result", "read_right")["ts"]
        merge_start = capture.first("tool_start", "merge_summary")["ts"]

        # Step1 parallel overlap.
        assert left_start < right_end
        assert right_start < left_end
        # Step2 serial boundary after both step1 tools.
        assert merge_start >= max(left_end, right_end)

        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 3
        assert str(tool_messages[-1].content).startswith("merge_summary:")

    @pytest.mark.asyncio
    async def test_hil_resume_should_not_repeat_send_email_side_effect_for_same_payload(self) -> None:
        """
        Same effective send_email payload should be deduplicated across resumes.
        """
        from app.api.chat import ChatResumeRequest, chat_resume
        from langgraph.types import Command

        capture = EventCapture()

        class FakeInterruptStore:
            async def get_interrupt(self, interrupt_id: str) -> dict[str, Any]:
                return {
                    "status": "pending",
                    "tool_name": "send_email",
                    "tool_args": {
                        "to": "dup@example.com",
                        "subject": "Same Subject",
                        "body": "Same Body",
                    },
                }

            async def update_interrupt_status(self, interrupt_id: str, status: str) -> None:
                return None

        fake_store = FakeInterruptStore()
        call_inputs: list[Command] = []

        class FakeState:
            values = {"messages": []}

        class FakeAgent:
            async def astream(self, input_data, *args, **kwargs):
                call_inputs.append(input_data)
                if False:
                    yield None

            async def aget_state(self, config):
                return FakeState()

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=fake_store),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=FakeAgent()),
            ),
        ):
            response_1 = await chat_resume(
                ChatResumeRequest(
                    session_id="s-1",
                    interrupt_id="interrupt-1",
                    approved=True,
                )
            )
            await _consume_streaming_response(response_1, capture)

            response_2 = await chat_resume(
                ChatResumeRequest(
                    session_id="s-1",
                    interrupt_id="interrupt-2",
                    approved=True,
                )
            )
            await _consume_streaming_response(response_2, capture)

            assert len(call_inputs) == 1
            assert isinstance(call_inputs[0], Command)
            payload = call_inputs[0].resume["interrupt-1"]
            assert payload["decisions"][0]["type"] == "approve"
