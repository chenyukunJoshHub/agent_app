"""
Unit tests for build_tool_registry.
"""

import builtins
import importlib
import sys

import pytest
from langchain_core.tools import BaseTool

from app.tools.base import ToolMeta
from app.tools.manager import ToolManager
from app.tools.policy import PolicyEngine


class TestBuildToolRegistry:
    def test_returns_tuple_of_three(self) -> None:
        from app.tools.registry import build_tool_registry
        tools, tm, pe = build_tool_registry(enable_hil=False)
        assert isinstance(tools, list)
        assert isinstance(tm, ToolManager)
        assert isinstance(pe, PolicyEngine)

    def test_enable_hil_false_no_send_email(self) -> None:
        from app.tools.registry import build_tool_registry
        tools, _, _ = build_tool_registry(enable_hil=False)
        names = [t.name for t in tools]
        assert "send_email" not in names

    def test_enable_hil_true_has_send_email(self) -> None:
        from app.tools.registry import build_tool_registry
        tools, _, _ = build_tool_registry(enable_hil=True)
        names = [t.name for t in tools]
        assert "send_email" in names

    def test_tools_are_base_tool_instances(self) -> None:
        from app.tools.registry import build_tool_registry

        tools, _, _ = build_tool_registry(enable_hil=True)

        assert tools
        assert all(isinstance(tool, BaseTool) for tool in tools)

    def test_activate_skill_in_tools(self) -> None:
        from app.tools.registry import build_tool_registry
        tools, _, _ = build_tool_registry(enable_hil=False)
        names = [t.name for t in tools]
        assert "activate_skill" in names

    def test_shared_meta_consistency(self) -> None:
        from app.tools.registry import build_tool_registry
        tools, tm, _ = build_tool_registry(enable_hil=True)
        for tool in tools:
            meta = tm.get_meta(tool.name)
            assert meta is not None, f"Tool '{tool.name}' missing from ToolManager"
            assert isinstance(meta, ToolMeta)

    def test_send_email_meta_requires_hil(self) -> None:
        from app.tools.registry import build_tool_registry
        _, tm, _ = build_tool_registry(enable_hil=True)
        meta = tm.get_meta("send_email")
        assert meta is not None
        assert meta.requires_hil is True
        assert meta.idempotent is False

    def test_multiple_calls_are_stable_and_isolated(self) -> None:
        from app.tools.registry import build_tool_registry

        tools_a, tm_a, pe_a = build_tool_registry(enable_hil=True)
        tools_b, tm_b, pe_b = build_tool_registry(enable_hil=True)

        assert [tool.name for tool in tools_a] == [tool.name for tool in tools_b]
        assert tm_a is not tm_b
        assert pe_a is not pe_b

        pe_a.grant_session("send_email", session_id="thread-1")
        assert pe_a.get_granted_tools("thread-1") == {"send_email"}
        assert pe_b.get_granted_tools("thread-1") == set()

        for tool in tools_a:
            meta_a = tm_a.get_meta(tool.name)
            meta_b = tm_b.get_meta(tool.name)
            assert meta_a is not None
            assert meta_b is not None
            assert meta_a.effect_class == meta_b.effect_class
            assert meta_a.allowed_decisions == meta_b.allowed_decisions
            assert meta_a.idempotent == meta_b.idempotent
            assert meta_a.max_retries == meta_b.max_retries
            assert meta_a.timeout_seconds == meta_b.timeout_seconds
            assert meta_a.backoff == meta_b.backoff
            assert meta_a.can_parallelize == meta_b.can_parallelize
            assert meta_a.concurrency_group == meta_b.concurrency_group
            assert meta_a.permission_key == meta_b.permission_key
            assert meta_a.audit_tags == meta_b.audit_tags
            if meta_a.idempotency_key_fn or meta_b.idempotency_key_fn:
                assert meta_a.idempotency_key_fn is not None
                assert meta_b.idempotency_key_fn is not None
                sample_args = {"to": "a@example.com", "subject": "hi"}
                assert meta_a.idempotency_key_fn(sample_args) == meta_b.idempotency_key_fn(
                    sample_args
                )

    def test_web_search_meta_is_readonly(self) -> None:
        from app.tools.registry import build_tool_registry
        _, tm, _ = build_tool_registry(enable_hil=False)
        meta = tm.get_meta("web_search")
        assert meta is not None
        assert meta.effect_class == "read"
        assert meta.idempotent is True

    def test_external_tools_use_restrictive_policy(self) -> None:
        """Test that external tools passed to langchain_engine use restrictive policy."""
        from langchain_core.tools import tool

        @tool
        def external_tool(x: str) -> str:
            """An external tool for testing."""
            return x

        # Simulate what langchain_engine.py does for external tools
        from app.tools.base import ToolMeta
        from app.tools.manager import ToolManager

        tool_metas = {
            t.name: ToolMeta(effect_class="external_write", allowed_decisions=["ask", "deny"])
            for t in [external_tool]
        }
        tool_manager = ToolManager(tool_metas)

        meta = tool_manager.get_meta("external_tool")
        assert meta is not None
        assert meta.effect_class == "external_write"
        assert meta.allowed_decisions == ["ask", "deny"]
        assert meta.idempotent is True  # __post_init__ sets max_retries=0 when idempotent=True

    def test_external_tools_require_hil_by_default(self) -> None:
        """Test that external tools require HIL (ask decision) by default."""
        from langchain_core.tools import tool

        @tool
        def external_tool(x: str) -> str:
            """An external tool for testing."""
            return x

        from app.tools.base import ToolMeta
        from app.tools.policy import PolicyEngine

        # External tools have effect_class="external_write" and allowed_decisions=["ask", "deny"]
        meta = ToolMeta(effect_class="external_write", allowed_decisions=["ask", "deny"])
        engine = PolicyEngine()

        decision = engine.decide("external_tool", meta.effect_class, meta.allowed_decisions)
        # Should require HIL (ask decision)
        assert decision == "ask"

    def test_import_failure_surfaces_for_required_dependency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.tools.registry import build_tool_registry

        original_import = builtins.__import__

        def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "app.tools.search":
                raise ImportError("search import failed")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", failing_import)

        with pytest.raises(ImportError, match="search import failed"):
            build_tool_registry(enable_hil=False)

    def test_tools_package_does_not_export_send_email_by_default(self) -> None:
        sys.modules.pop("app.tools", None)
        sys.modules.pop("app.tools.send_email", None)

        package = importlib.import_module("app.tools")

        assert not hasattr(package, "send_email")
        assert "app.tools.send_email" not in sys.modules
