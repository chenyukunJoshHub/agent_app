"""
Unit tests for app.tools.policy — PolicyEngine.
"""

import pytest

from app.tools.policy import PolicyEngine


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


class TestPolicyEngineDecide:
    def test_read_allows(self, engine: PolicyEngine) -> None:
        assert engine.decide("web_search", "read") == "allow"

    def test_write_allows(self, engine: PolicyEngine) -> None:
        assert engine.decide("save_file", "write") == "allow"

    def test_external_write_asks(self, engine: PolicyEngine) -> None:
        assert engine.decide("send_email", "external_write") == "ask"

    def test_destructive_denies(self, engine: PolicyEngine) -> None:
        assert engine.decide("rm_rf", "destructive") == "deny"

    def test_orchestration_allows(self, engine: PolicyEngine) -> None:
        assert engine.decide("task_dispatch", "orchestration") == "allow"

    def test_unknown_effect_asks(self, engine: PolicyEngine) -> None:
        assert engine.decide("mystery", "custom_type") == "ask"


class TestPolicyEngineAllowedDecisions:
    def test_valid_decision_passes(self, engine: PolicyEngine) -> None:
        result = engine.decide("web_search", "read", allowed_decisions=["allow"])
        assert result == "allow"

    def test_invalid_decision_raises(self, engine: PolicyEngine) -> None:
        with pytest.raises(ValueError, match="allowed_decisions"):
            engine.decide("rm_rf", "destructive", allowed_decisions=["allow"])

    def test_no_allowed_decisions_skips_validation(self, engine: PolicyEngine) -> None:
        result = engine.decide("send_email", "external_write", allowed_decisions=None)
        assert result == "ask"

    def test_empty_allowed_decisions_skips_validation(self, engine: PolicyEngine) -> None:
        result = engine.decide("send_email", "external_write", allowed_decisions=[])
        assert result == "ask"


class TestPolicyEngineSessionGrants:
    def test_grant_overrides_default(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("send_email")
        assert engine.decide("send_email", "external_write") == "allow"

    def test_grant_does_not_affect_other_tools(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("send_email")
        assert engine.decide("other_tool", "external_write") == "ask"

    def test_revoke_restores_default(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("send_email")
        engine.revoke_session("send_email")
        assert engine.decide("send_email", "external_write") == "ask"

    def test_revoke_nonexistent_no_error(self) -> None:
        engine = PolicyEngine()
        engine.revoke_session("nonexistent_tool")
        assert engine.decide("nonexistent_tool", "read") == "allow"

    def test_get_granted_tools_returns_set(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("tool_a")
        engine.grant_session("tool_b")
        granted = engine.get_granted_tools()
        assert granted == {"tool_a", "tool_b"}

    def test_get_granted_tools_empty_when_none_granted(self) -> None:
        engine = PolicyEngine()
        granted = engine.get_granted_tools()
        assert granted == set()

    def test_grant_and_revoke_update_granted_tools(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("tool_a")
        engine.grant_session("tool_b")
        assert "tool_a" in engine.get_granted_tools()
        assert "tool_b" in engine.get_granted_tools()

        engine.revoke_session("tool_a")
        assert "tool_a" not in engine.get_granted_tools()
        assert "tool_b" in engine.get_granted_tools()

    def test_destructive_tool_not_affected_by_grant(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("rm_rf")
        assert engine.decide("rm_rf", "destructive") == "deny"

    def test_multiple_grants_same_tool(self) -> None:
        engine = PolicyEngine()
        engine.grant_session("send_email")
        engine.grant_session("send_email")
        granted = engine.get_granted_tools()
        assert granted == {"send_email"}


class TestPolicyEngineHilRequired:
    def test_returns_true_for_ask(self, engine: PolicyEngine) -> None:
        assert engine.hil_required("send_email", "external_write") is True

    def test_returns_false_for_allow(self, engine: PolicyEngine) -> None:
        assert engine.hil_required("web_search", "read") is False

    def test_returns_false_for_deny(self, engine: PolicyEngine) -> None:
        assert engine.hil_required("rm_rf", "destructive") is False
