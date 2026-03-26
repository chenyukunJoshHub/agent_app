"""Unit tests for app.api.preferences."""

from dataclasses import dataclass

import pytest

import app.api.preferences as preferences_api


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
async def test_set_preferences_persists_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()

    async def fake_get_store():
        return store

    monkeypatch.setattr(preferences_api, "get_store", fake_get_store)

    req = preferences_api.PreferencesRequest(user_id="u1", preferences={"language": "zh"})
    resp = await preferences_api.set_preferences(req)
    assert resp["status"] == "ok"

    read_back = await preferences_api.get_preferences(user_id="u1")
    assert read_back["preferences"] == {"language": "zh"}


@pytest.mark.asyncio
async def test_set_procedural_merges_workflows(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()
    await store.aput(
        namespace=("profile", "u1"),
        key="procedural",
        value={"workflows": {"wf_a": "old", "wf_b": "keep"}},
    )

    async def fake_get_store():
        return store

    monkeypatch.setattr(preferences_api, "get_store", fake_get_store)

    req = preferences_api.ProceduralRequest(user_id="u1", workflows={"wf_a": "new"})
    resp = await preferences_api.set_procedural(req)

    assert resp["status"] == "ok"
    assert resp["workflows"] == {"wf_a": "new", "wf_b": "keep"}
