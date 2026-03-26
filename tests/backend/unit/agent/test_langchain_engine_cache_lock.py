"""Regression tests for create_react_agent cache initialization locking."""

import asyncio

import pytest

import app.agent.langchain_engine as engine


@pytest.fixture(autouse=True)
def reset_agent_cache() -> None:
    """Reset cache around each test."""
    engine._agent_cache = None
    yield
    engine._agent_cache = None


@pytest.mark.asyncio
async def test_create_react_agent_builds_once_under_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent first calls should compile the cached agent exactly once."""
    build_calls = 0
    graph = object()

    async def fake_build(_llm, _tools, _skills_dir):
        nonlocal build_calls
        build_calls += 1
        await asyncio.sleep(0.02)
        return engine._CachedAgent(
            graph=graph,  # type: ignore[arg-type]
            slot_snapshot_dict={},
            slot_usage=[],
            tool_names=[],
            skill_names=[],
            skill_version=1,
            model_name="test-model",
        )

    async def fake_emit(_sse_queue, _cached, _config=None):
        return None

    monkeypatch.setattr(engine, "_build_agent_internal", fake_build)
    monkeypatch.setattr(engine, "emit_setup_events", fake_emit)

    results = await asyncio.gather(*[engine.create_react_agent() for _ in range(8)])

    assert build_calls == 1
    assert all(r is graph for r in results)
