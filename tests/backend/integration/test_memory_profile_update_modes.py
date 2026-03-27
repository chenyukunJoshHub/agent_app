"""Integration tests for MemoryMiddleware profile update modes."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import HumanMessage

from app.agent.middleware.memory import MemoryMiddleware
from app.memory.manager import MemoryManager


@dataclass
class _Item:
    value: dict


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[tuple[tuple[str, str], str], dict] = {}

    async def aget(self, namespace: tuple[str, str], key: str):
        value = self._data.get((namespace, key))
        if value is None:
            return None
        return _Item(value=value)

    async def aput(self, namespace: tuple[str, str], key: str, value: dict) -> None:
        self._data[(namespace, key)] = value


@pytest.mark.asyncio
async def test_llm_mode_runs_every_10_turns_and_persists_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()
    manager = MemoryManager(store=store)  # type: ignore[arg-type]
    middleware = MemoryMiddleware(memory_manager=manager)

    monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "llm")
    monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_llm_interval", 10)
    monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_opinion_min_confidence", 0.9)

    llm_payload = {
        "preferences": {"tone": "professional"},
        "summary": "用户画像更新",
        "retain": [
            {"type": "W", "text": "用户处理合同场景"},
            {"type": "B", "text": "执行了合同审查流程"},
            {"type": "O", "text": "偏好中文回复", "confidence": 0.95, "preference": {"language": "zh"}},
            {"type": "S", "text": "持续关注流程效率"},
        ],
    }
    mock_extract = AsyncMock(return_value=llm_payload)
    monkeypatch.setattr(middleware, "_extract_profile_with_llm", mock_extract)

    runtime = Mock()
    runtime.context = Mock()
    runtime.context.user_id = "u-int-1"
    runtime.context.sse_queue = None

    for _ in range(10):
        before = await middleware.abefore_agent({}, runtime)
        assert before is not None
        state = {
            "memory_ctx": before["memory_ctx"],
            "memory_ctx_baseline": before["memory_ctx_baseline"],
            "messages": [HumanMessage(content="请继续处理合同签署流程，并用中文回复")],
        }
        await middleware.aafter_agent(state, runtime)

    assert mock_extract.await_count == 1

    final_profile = await manager.load_episodic("u-int-1")
    assert final_profile.interaction_count == 10
    assert final_profile.preferences["domain"] == "legal-tech"
    assert final_profile.preferences["language"] == "zh"
    assert final_profile.preferences["tone"] == "professional"
    assert "W @" in final_profile.summary
    assert "B @" in final_profile.summary
    assert "O(c=0.95)" in final_profile.summary
    assert "S @" in final_profile.summary
