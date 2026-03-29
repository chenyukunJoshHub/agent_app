from __future__ import annotations


class PolicyEngine:
    _DEFAULT_RULES: dict[str, str] = {
        "read": "allow",
        "write": "allow",
        "external_write": "ask",
        "destructive": "deny",
        "orchestration": "allow",
    }

    def __init__(self) -> None:
        self._session_grants: dict[str | None, dict[str, str]] = {}

    def decide(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        grants = self._session_grants.get(session_id, {})
        is_session_granted = tool_name in grants and effect_class != "destructive"
        if is_session_granted:
            return grants[tool_name]

        decision = self._DEFAULT_RULES.get(effect_class, "ask")
        if not allowed_decisions:
            return decision
        if decision in allowed_decisions:
            return decision
        if decision == "allow":
            if "ask" in allowed_decisions:
                return "ask"
            if "deny" in allowed_decisions:
                return "deny"
        elif decision == "ask":
            if "deny" in allowed_decisions:
                return "deny"
        raise ValueError(
            f"PolicyEngine: tool '{tool_name}' decision '{decision}' "
            f"not in allowed_decisions {allowed_decisions}"
        )

    def grant_session(self, tool_name: str, session_id: str | None = None) -> None:
        grants = self._session_grants.setdefault(session_id, {})
        grants[tool_name] = "allow"

    def revoke_session(self, tool_name: str, session_id: str | None = None) -> None:
        grants = self._session_grants.get(session_id, {})
        if tool_name in grants:
            del grants[tool_name]
        if not grants and session_id in self._session_grants:
            del self._session_grants[session_id]

    def get_granted_tools(self, session_id: str | None = None) -> set[str]:
        return set(self._session_grants.get(session_id, {}).keys())

    def hil_required(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
        session_id: str | None = None,
    ) -> bool:
        return self.decide(
            tool_name,
            effect_class,
            allowed_decisions,
            session_id=session_id,
        ) == "ask"


__all__ = ["PolicyEngine"]
