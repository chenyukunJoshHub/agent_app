"""Unit tests for summarization middleware compression observability."""
import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from app.agent.context import AgentContext
from app.agent.middleware.summarization import create_summarization_middleware
from app.api.chat import SSEEventQueue


def _build_messages(n_pairs: int) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for idx in range(n_pairs):
        messages.append(HumanMessage(content=f"user-{idx}: 合同风险分析进展"))
        messages.append(AIMessage(content=f"assistant-{idx}: 已记录"))
    return messages


@pytest.mark.asyncio
async def test_abefore_model_emits_compression_event_when_triggered() -> None:
    """When compression runs, middleware should emit a compression SSE event."""
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content="压缩摘要：保留关键目标与待办")],
        profile={"max_input_tokens": 2_000},
    )
    middleware = create_summarization_middleware(
        model=model,
        trigger=("messages", 6),
        keep=("messages", 2),
    )
    queue = SSEEventQueue()
    runtime = SimpleNamespace(context=AgentContext(sse_queue=queue, user_id="u1"))
    state = {"messages": _build_messages(3)}

    update = await middleware.abefore_model(state, runtime)

    assert update is not None
    rewritten_messages = update["messages"]
    assert isinstance(rewritten_messages[0], RemoveMessage)
    assert isinstance(rewritten_messages[1], HumanMessage)
    assert rewritten_messages[1].additional_kwargs.get("lc_source") == "summarization"
    assert "Here is a summary of the conversation to date:" in str(rewritten_messages[1].content)

    event_type, payload = await asyncio.wait_for(queue.get(), timeout=0.1)
    assert event_type == "compression"
    assert payload["method"] == "summarization"
    assert payload["affected_slots"] == ["history"]
    assert payload["before_tokens"] > payload["after_tokens"]
    assert "压缩摘要" in payload["summary_text"]


@pytest.mark.asyncio
async def test_abefore_model_no_event_when_not_triggered() -> None:
    """No compression event should be emitted when trigger condition is not met."""
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content="unused")],
        profile={"max_input_tokens": 2_000},
    )
    middleware = create_summarization_middleware(
        model=model,
        trigger=("messages", 20),
        keep=("messages", 2),
    )
    queue = SSEEventQueue()
    runtime = SimpleNamespace(context=AgentContext(sse_queue=queue, user_id="u1"))
    state = {"messages": _build_messages(3)}

    update = await middleware.abefore_model(state, runtime)

    assert update is None
    assert queue._queue.empty()
