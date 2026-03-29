"""
Unit tests for app.tools.base — ToolMeta dataclass.

Covers:
- Field defaults
- Security fields (effect_class, requires_hil, allowed_decisions)
- Reliability fields (idempotent, idempotency_key_fn, max_retries, timeout, backoff)
- Scheduling fields (can_parallelize, concurrency_group)
- Governance fields (permission_key, audit_tags)
- Validation logic (idempotent=False forces max_retries=0)
"""
from dataclasses import fields

import pytest

from app.tools.base import BackoffConfig, ToolMeta


# ─── Fixture helpers ─────────────────────────────────────────────────────────


def _make_readonly_meta(**overrides) -> ToolMeta:
    """Create a typical read-only tool meta (web_search-like)."""
    defaults = dict(
        effect_class="read",
        requires_hil=False,
        allowed_decisions=["allow"],
        idempotent=True,
        idempotency_key_fn=None,
        max_retries=3,
        timeout_seconds=30,
        backoff={"strategy": "exponential", "base_seconds": 1},
        can_parallelize=True,
        concurrency_group=None,
        permission_key="web_search",
        audit_tags=["network", "search", "readonly"],
    )
    defaults.update(overrides)
    return ToolMeta(**defaults)


def _make_write_meta(**overrides) -> ToolMeta:
    """Create a typical external-write tool meta (send_email-like)."""
    defaults = dict(
        effect_class="external_write",
        requires_hil=True,
        allowed_decisions=["ask", "deny"],
        idempotent=False,
        idempotency_key_fn=lambda args: f"email:{args['to']}:{args['subject']}",
        max_retries=0,
        timeout_seconds=60,
        backoff=None,
        can_parallelize=False,
        concurrency_group=None,
        permission_key="email.send",
        audit_tags=["network", "email", "external", "write"],
    )
    defaults.update(overrides)
    return ToolMeta(**defaults)


# ─── Security field tests ─────────────────────────────────────────────────────


class TestToolMetaSecurityFields:
    """ToolMeta security-related field tests."""

    def test_effect_class_accepts_valid_values(self) -> None:
        for cls in ("read", "write", "external_write", "destructive", "orchestration"):
            meta = ToolMeta(effect_class=cls)
            assert meta.effect_class == cls

    def test_effect_class_required(self) -> None:
        with pytest.raises(TypeError):
            ToolMeta()

    def test_requires_hil_default_false(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.requires_hil is False

    def test_requires_hil_true_for_external_write(self) -> None:
        meta = _make_write_meta()
        assert meta.requires_hil is True

    def test_allowed_decisions_default_empty(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.allowed_decisions == []

    def test_allowed_decisions_are_independent_across_instances(self) -> None:
        meta_a = ToolMeta(effect_class="read", allowed_decisions=["allow"])
        meta_a.allowed_decisions.append("deny")
        meta_b = ToolMeta(effect_class="read", allowed_decisions=["allow"])
        assert "deny" not in meta_b.allowed_decisions

    def test_readonly_meta_example(self) -> None:
        meta = _make_readonly_meta()
        assert meta.effect_class == "read"
        assert meta.requires_hil is False
        assert meta.allowed_decisions == ["allow"]

    def test_write_meta_example(self) -> None:
        meta = _make_write_meta()
        assert meta.effect_class == "external_write"
        assert meta.requires_hil is True
        assert meta.allowed_decisions == ["ask", "deny"]


# ─── Reliability field tests ──────────────────────────────────────────────────


class TestToolMetaReliabilityFields:
    """ToolMeta reliability-related field tests."""

    def test_idempotent_default_true(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.idempotent is True

    def test_non_idempotent_tool(self) -> None:
        meta = _make_write_meta()
        assert meta.idempotent is False

    def test_idempotency_key_fn_default_none(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.idempotency_key_fn is None

    def test_idempotency_key_fn_callable(self) -> None:
        key_fn = lambda args: f"email:{args['to']}:{args['subject']}"
        meta = ToolMeta(effect_class="write", idempotency_key_fn=key_fn)
        assert meta.idempotency_key_fn is not None
        assert meta.idempotency_key_fn({"to": "a@b.com", "subject": "hi"}) == "email:a@b.com:hi"

    def test_max_retries_default_zero(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.max_retries == 0

    def test_max_retries_positive_for_idempotent(self) -> None:
        meta = _make_readonly_meta(max_retries=3)
        assert meta.max_retries == 3

    def test_non_idempotent_forces_max_retries_zero(self) -> None:
        meta = ToolMeta(effect_class="write", idempotent=False, max_retries=5)
        assert meta.max_retries == 0

    def test_timeout_seconds_default(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.timeout_seconds == 30

    def test_timeout_seconds_custom(self) -> None:
        meta = ToolMeta(effect_class="read", timeout_seconds=120)
        assert meta.timeout_seconds == 120

    def test_backoff_default_none(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.backoff is None

    def test_backoff_dict(self) -> None:
        backoff: BackoffConfig = {
            "strategy": "exponential",
            "base_seconds": 1,
        }
        meta = ToolMeta(effect_class="read", backoff=backoff)
        assert meta.backoff["strategy"] == "exponential"
        assert meta.backoff["base_seconds"] == 1

    def test_backoff_config_type_is_exported(self) -> None:
        backoff: BackoffConfig = {"strategy": "fixed", "base_seconds": 2}
        meta = ToolMeta(effect_class="read", backoff=backoff)
        assert meta.backoff == backoff

    def test_backoff_none_for_non_idempotent(self) -> None:
        meta = _make_write_meta()
        assert meta.backoff is None


# ─── Scheduling field tests ───────────────────────────────────────────────────


class TestToolMetaSchedulingFields:
    """ToolMeta scheduling-related field tests."""

    def test_can_parallelize_default_true(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.can_parallelize is True

    def test_cannot_parallelize_for_write(self) -> None:
        meta = _make_write_meta()
        assert meta.can_parallelize is False

    def test_concurrency_group_default_none(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.concurrency_group is None

    def test_concurrency_group_custom(self) -> None:
        meta = ToolMeta(effect_class="read", concurrency_group="io_heavy")
        assert meta.concurrency_group == "io_heavy"


# ─── Governance field tests ───────────────────────────────────────────────────


class TestToolMetaGovernanceFields:
    """ToolMeta governance-related field tests."""

    def test_permission_key_default_empty(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.permission_key == ""

    def test_permission_key_custom(self) -> None:
        meta = ToolMeta(effect_class="write", permission_key="email.send")
        assert meta.permission_key == "email.send"

    def test_audit_tags_default_empty(self) -> None:
        meta = ToolMeta(effect_class="read")
        assert meta.audit_tags == []

    def test_audit_tags_are_independent_across_instances(self) -> None:
        meta_a = ToolMeta(effect_class="read", audit_tags=["network"])
        meta_a.audit_tags.append("search")
        meta_b = ToolMeta(effect_class="read", audit_tags=["network"])
        assert "search" not in meta_b.audit_tags

    def test_audit_tags_custom(self) -> None:
        tags = ["network", "search", "readonly"]
        meta = ToolMeta(effect_class="read", audit_tags=tags)
        assert meta.audit_tags == tags


# ─── Dataclass structure tests ────────────────────────────────────────────────


class TestToolMetaStructure:
    """ToolMeta dataclass structural tests."""

    def test_is_dataclass(self) -> None:
        from dataclasses import is_dataclass
        assert is_dataclass(ToolMeta)

    def test_has_all_required_fields(self) -> None:
        field_names = {f.name for f in fields(ToolMeta)}
        expected = {
            "effect_class",
            "requires_hil",
            "allowed_decisions",
            "idempotent",
            "idempotency_key_fn",
            "max_retries",
            "timeout_seconds",
            "backoff",
            "can_parallelize",
            "concurrency_group",
            "permission_key",
            "audit_tags",
        }
        assert field_names == expected

    def test_mutable_defaults_are_safe(self) -> None:
        """Verify that list fields use factory defaults (no shared mutable state)."""
        meta1 = ToolMeta(effect_class="read")
        meta2 = ToolMeta(effect_class="read")
        meta1.allowed_decisions.append("deny")
        meta1.audit_tags.append("custom")
        assert meta2.allowed_decisions == []
        assert meta2.audit_tags == []
