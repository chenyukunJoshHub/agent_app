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
        self._session_grants: dict[str, str] = {}

    def decide(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
    ) -> str:
        # Destructive tools cannot be session granted
        if tool_name in self._session_grants and effect_class != "destructive":
            decision = self._session_grants[tool_name]
        else:
            decision = self._DEFAULT_RULES.get(effect_class, "ask")

        if allowed_decisions and decision not in allowed_decisions:
            raise ValueError(
                f"PolicyEngine: tool '{tool_name}' decision '{decision}' "
                f"not in allowed_decisions {allowed_decisions}"
            )
        return decision

    def grant_session(self, tool_name: str) -> None:
        self._session_grants[tool_name] = "allow"

    def revoke_session(self, tool_name: str) -> None:
        if tool_name in self._session_grants:
            del self._session_grants[tool_name]

    def get_granted_tools(self) -> set[str]:
        return set(self._session_grants.keys())

    def hil_required(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
    ) -> bool:
        return self.decide(tool_name, effect_class, allowed_decisions) == "ask"


__all__ = ["PolicyEngine"]
