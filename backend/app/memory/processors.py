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
from typing import ClassVar

from app.memory.schemas import MemoryContext


class BaseInjectionProcessor(ABC):
    """Unified contract for all ephemeral injection processors.

    Implement this to add a new memory type to the injection pipeline.
    Register the instance in MemoryManager(processors=[...]).
    """

    slot_name: ClassVar[str]      # Must match a slot name in ContextPanel
    display_name: ClassVar[str]   # Human-readable label shown in ContextPanel (required by emit_slot_update)

    @abstractmethod
    def build_prompt(self, ctx: MemoryContext) -> str:
        """Extract memory from ctx and return injection text.

        Returns:
            str: Non-empty injection text, or "" if nothing to inject.
        """
        ...


class EpisodicProcessor(BaseInjectionProcessor):
    """Episodic memory processor: user profile preferences.

    Output format (when content is provided):
        Returns the full user persona content directly.

    Output format (when preferences non-empty but no content):
        \\n\\n[用户画像]\\n  domain: legal-tech\\n  language: zh

    Returns "" when both content and preferences are empty or missing.
    """

    slot_name = "episodic"
    display_name = "用户画像"

    def build_prompt(self, ctx: MemoryContext) -> str:
        # Priority 1: Use full content if provided
        if ctx.episodic.content:
            return ctx.episodic.content

        # Priority 2: Fall back to preferences dict (legacy format)
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)


class ProceduralProcessor(BaseInjectionProcessor):
    """Procedural memory processor: workflow SOPs.

    Output format (when workflows non-empty):

        \\n\\n[程序记忆 - 工作流 SOP]\\n
        \\n### 合同审查流程\\n1. 先搜索...\\n2. 再发邮件...

    Returns "" when workflows is empty or missing.
    """

    slot_name = "procedural"
    display_name = "工作流 SOP"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.procedural.workflows:
            return ""
        lines = [
            f"\n### {name}\n{instruction}"
            for name, instruction in ctx.procedural.workflows.items()
        ]
        return "\n\n[程序记忆 - 工作流 SOP]\n" + "\n".join(lines)
