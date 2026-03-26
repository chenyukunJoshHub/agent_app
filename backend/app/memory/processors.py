"""Memory injection processors.

Each processor extracts one type of memory from MemoryContext and builds
an ephemeral text snippet to inject into the LLM's HumanMessage.

Convention:
- slot_name maps to ContextPanel slot names (episodic, procedural, rag, ...)
- build_prompt returns "" when there is nothing to inject
- build_prompt never raises; it returns "" on any missing data
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.memory.schemas import MemoryContext


class BaseInjectionProcessor(ABC):
    """Unified contract for all ephemeral injection processors.

    Implement this to add a new memory type to the injection pipeline.
    Register the instance in MemoryManager(processors=[...]).
    """

    slot_name: str     # Must match a slot name in ContextPanel
    display_name: str  # Human-readable label shown in ContextPanel (required by emit_slot_update)

    @abstractmethod
    def build_prompt(self, ctx: MemoryContext) -> str:
        """Extract memory from ctx and return injection text.

        Returns:
            str: Non-empty injection text, or "" if nothing to inject.
        """
        ...


class EpisodicProcessor(BaseInjectionProcessor):
    """Episodic memory processor: user profile preferences.

    Output format (when preferences non-empty):

        \\n\\n[用户画像]\\n  domain: legal-tech\\n  language: zh

    Returns "" when preferences is empty or missing.
    """

    slot_name = "episodic"
    display_name = "用户画像"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)
