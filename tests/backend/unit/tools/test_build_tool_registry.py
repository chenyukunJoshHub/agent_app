"""
Unit tests for build_tool_registry.
"""

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
