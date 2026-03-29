"""
Integration tests for ToolManager + PolicyEngine contract consistency.
"""

from app.tools.registry import build_tool_registry


class TestPolicyEngineToolManagerIntegration:
    def test_decide_does_not_raise_for_all_registered_tools(self) -> None:
        _, tool_manager, policy_engine = build_tool_registry(enable_hil=True)

        for tool_name in tool_manager.list_available():
            meta = tool_manager.get_meta(tool_name)
            assert meta is not None
            decision = policy_engine.decide(
                tool_name,
                meta.effect_class,
                meta.allowed_decisions,
            )
            assert decision in meta.allowed_decisions

    def test_default_decision_matches_effect_class_for_registered_tools(self) -> None:
        _, tool_manager, policy_engine = build_tool_registry(enable_hil=True)

        expected_by_effect = {
            "read": "allow",
            "write": "allow",
            "external_write": "ask",
            "destructive": "deny",
            "orchestration": "allow",
        }

        for tool_name in tool_manager.list_available():
            meta = tool_manager.get_meta(tool_name)
            assert meta is not None
            expected = expected_by_effect.get(meta.effect_class, "ask")
            decision = policy_engine.decide(tool_name, meta.effect_class)
            assert decision == expected
