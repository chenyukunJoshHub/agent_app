from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, TypedDict


class BackoffConfig(TypedDict):
    strategy: Literal["fixed", "exponential"]
    base_seconds: float


@dataclass
class ToolMeta:
    effect_class: str
    requires_hil: bool = False
    allowed_decisions: list[str] = field(default_factory=list)
    idempotent: bool = True
    idempotency_key_fn: Callable[[dict[str, Any]], str | None] | None = None
    max_retries: int = 0
    timeout_seconds: int = 30
    backoff: BackoffConfig | None = None
    can_parallelize: bool = True
    concurrency_group: str | None = None
    permission_key: str = ""
    audit_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.idempotent:
            self.max_retries = 0


__all__ = ["BackoffConfig", "ToolMeta"]
