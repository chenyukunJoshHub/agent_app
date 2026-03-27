"""
Integration tests for native HIL resume recovery with real Postgres checkpointer.

Goal:
- Verify Command(resume=...) continues from checkpoint (not from scratch).
- Verify approve/reject decisions produce correct side-effect behavior.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.types import Command
from pydantic import Field

from app.db.postgres import close_db, get_checkpointer


class ScriptedModel(BaseChatModel):
    """Deterministic model that emits scripted tool-calls/content."""

    script: list[Any] = Field(default_factory=list)
    step: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(
        self,
        tools: list[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ScriptedModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.step >= len(self.script):
            message = AIMessage(content="done")
        else:
            action = self.script[self.step]
            self.step += 1
            message = AIMessage(
                content=action.get("content", ""),
                tool_calls=action.get("tool_calls", []),
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


class TestHILResumeCheckpointRecovery:
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_db
    async def test_approve_resume_restores_checkpoint_without_replaying_prefetch(self) -> None:
        calls: dict[str, int] = {"prefetch": 0, "send_email": 0}

        @tool
        def prefetch(payload: str) -> str:
            """Read-only prefetch tool executed before HIL interrupt."""
            calls["prefetch"] += 1
            return f"prefetch:{payload}"

        @tool
        def send_email(to: str, subject: str, body: str) -> str:
            """Write tool guarded by HIL."""
            calls["send_email"] += 1
            return "sent"

        model = ScriptedModel(
            script=[
                {
                    "content": "",
                    "tool_calls": [
                        {"id": "prefetch-1", "name": "prefetch", "args": {"payload": "x"}},
                    ],
                },
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "email-1",
                            "name": "send_email",
                            "args": {"to": "a@b.com", "subject": "s", "body": "b"},
                        },
                    ],
                },
                {"content": "final answer"},
            ]
        )

        # Ensure a fresh saver connection (other integration tests may close DB in lifespan).
        await close_db()
        checkpointer = await get_checkpointer()
        agent = create_agent(
            model=model,
            tools=[prefetch, send_email],
            middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": True})],
            checkpointer=checkpointer,
        )

        thread_id = f"phase21-approve-{uuid.uuid4().hex}"
        config = {"configurable": {"thread_id": thread_id}}

        first = await agent.ainvoke(
            {"messages": [HumanMessage(content="go")]},
            config=config,
        )
        assert "__interrupt__" in first
        assert calls["prefetch"] == 1
        assert calls["send_email"] == 0

        interrupt_id = first["__interrupt__"][0].id
        resumed = await agent.ainvoke(
            Command(resume={interrupt_id: {"decisions": [{"type": "approve"}]}}),
            config=config,
        )

        # Checkpoint resume should continue from interrupt step:
        # prefetch should not replay, send_email should execute once.
        assert calls["prefetch"] == 1
        assert calls["send_email"] == 1

        tool_messages = [m for m in resumed["messages"] if isinstance(m, ToolMessage)]
        assert sum(str(m.content).startswith("prefetch:") for m in tool_messages) == 1
        assert sum(str(m.content) == "sent" for m in tool_messages) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.requires_db
    async def test_reject_resume_skips_send_email_side_effect(self) -> None:
        calls = {"send_email": 0}

        @tool
        def send_email(to: str, subject: str, body: str) -> str:
            """Write tool guarded by HIL."""
            calls["send_email"] += 1
            return "sent"

        model = ScriptedModel(
            script=[
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "email-1",
                            "name": "send_email",
                            "args": {"to": "reject@b.com", "subject": "s", "body": "b"},
                        },
                    ],
                },
                {"content": "final after reject"},
            ]
        )

        # Ensure a fresh saver connection (other integration tests may close DB in lifespan).
        await close_db()
        checkpointer = await get_checkpointer()
        agent = create_agent(
            model=model,
            tools=[send_email],
            middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": True})],
            checkpointer=checkpointer,
        )

        thread_id = f"phase21-reject-{uuid.uuid4().hex}"
        config = {"configurable": {"thread_id": thread_id}}

        first = await agent.ainvoke(
            {"messages": [HumanMessage(content="go")]},
            config=config,
        )
        assert "__interrupt__" in first
        assert calls["send_email"] == 0

        interrupt_id = first["__interrupt__"][0].id
        resumed = await agent.ainvoke(
            Command(resume={interrupt_id: {"decisions": [{"type": "reject"}]}}),
            config=config,
        )

        # Reject decision should not execute write side-effect.
        assert calls["send_email"] == 0
        tool_messages = [m for m in resumed["messages"] if isinstance(m, ToolMessage)]
        assert any("User rejected the tool call" in str(m.content) for m in tool_messages)
