"""
Per-request runtime context injected via LangGraph context_schema.

Passed to agent.astream(context=...) and accessible in middleware hooks
via runtime.context (abefore_agent/aafter_agent) and
request.runtime.context (wrap_model_call).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Per-request context for the agent.

    Decouples per-request state (SSE queue, user identity) from
    middleware instances, enabling agent graph caching across requests.

    Fields:
        sse_queue: Per-request SSE event queue (None in tests / non-SSE calls)
        user_id:   Caller identity for Long Memory lookup
    """

    sse_queue: Any = field(default=None)
    user_id: str = field(default="")


__all__ = ["AgentContext"]
