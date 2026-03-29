"""
Unit tests for app.tools.manager — ToolManager.
"""

from app.tools.base import ToolMeta
from app.tools.manager import ToolManager


def _build_metas(**overrides) -> dict[str, ToolMeta]:
    defaults = {
        "web_search": ToolMeta(effect_class="read", allowed_decisions=["allow"], idempotent=True, max_retries=2),
        "send_email": ToolMeta(effect_class="external_write", requires_hil=True, allowed_decisions=["ask", "deny"], idempotent=False),
        "read_file": ToolMeta(effect_class="read", allowed_decisions=["allow"], idempotent=True, max_retries=1),
    }
    defaults.update(overrides)
    return defaults


class TestToolManagerListAvailable:
    def test_lists_all_registered_tool_names(self) -> None:
        tm = ToolManager(_build_metas())
        names = tm.list_available()
        assert set(names) == {"web_search", "send_email", "read_file"}

    def test_empty_manager(self) -> None:
        tm = ToolManager({})
        assert tm.list_available() == []


class TestToolManagerGetMeta:
    def test_existing_tool_returns_meta(self) -> None:
        tm = ToolManager(_build_metas())
        meta = tm.get_meta("web_search")
        assert meta is not None
        assert meta.effect_class == "read"

    def test_missing_tool_returns_none(self) -> None:
        tm = ToolManager(_build_metas())
        assert tm.get_meta("nonexistent") is None

    def test_get_meta_returns_copy_not_internal_reference(self) -> None:
        tm = ToolManager(_build_metas())

        meta_1 = tm.get_meta("web_search")
        meta_2 = tm.get_meta("web_search")

        assert meta_1 is not None
        assert meta_2 is not None
        assert meta_1 == meta_2
        assert meta_1 is not meta_2

    def test_mutating_returned_meta_does_not_affect_internal_storage(self) -> None:
        tm = ToolManager(_build_metas())

        original = tm.get_meta("web_search")
        assert original is not None

        mutated = tm.get_meta("web_search")
        assert mutated is not None
        mutated.max_retries = 999
        mutated.allowed_decisions.append("deny")

        fresh = tm.get_meta("web_search")
        assert fresh is not None
        assert fresh.max_retries == original.max_retries
        assert fresh.allowed_decisions == original.allowed_decisions


class TestToolManagerCanRetry:
    def test_idempotent_with_retries(self) -> None:
        tm = ToolManager(_build_metas())
        assert tm.can_retry("web_search") is True

    def test_non_idempotent_cannot_retry(self) -> None:
        tm = ToolManager(_build_metas())
        assert tm.can_retry("send_email") is False

    def test_idempotent_zero_retries(self) -> None:
        metas = _build_metas()
        metas["read_file"] = ToolMeta(effect_class="read", allowed_decisions=["allow"], idempotent=True, max_retries=0)
        tm = ToolManager(metas)
        assert tm.can_retry("read_file") is False

    def test_unknown_tool_cannot_retry(self) -> None:
        tm = ToolManager(_build_metas())
        assert tm.can_retry("nonexistent") is False
