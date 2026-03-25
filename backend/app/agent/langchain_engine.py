"""
LangChain Agent Engine - creates and configures the ReAct agent.

P0: Basic create_agent with web_search tool and middleware.
P1: HIL middleware for manual intervention.
P1: Skills system integration (SkillManager + read_file tool).
"""
from typing import Any
from inspect import isawaitable

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from app.agent.middleware.hil import HILMiddleware
from app.agent.middleware.memory import MemoryMiddleware
from app.agent.middleware.summarization import create_summarization_middleware
from app.agent.middleware.trace import TraceMiddleware
from app.config import settings
from app.db.postgres import get_store
from app.llm.factory import llm_factory
from app.memory.manager import MemoryManager
from app.observability.interrupt_store import get_interrupt_store
from app.observability.trace_events import emit_trace_event
from app.prompt.builder import build_system_prompt
from app.prompt.budget import DEFAULT_BUDGET
from app.skills.manager import SkillManager
from app.tools.file import read_file
from app.tools.registry import build_tool_registry
from app.tools.search import web_search

SLOT_META: dict[str, dict[str, str | int]] = {
    "system": {
        "display_name": "系统提示词",
        "allocated": DEFAULT_BUDGET.SLOT_SYSTEM,
        "color": "#5E6AD2",
    },
    "active_skill": {
        "display_name": "活跃技能",
        "allocated": DEFAULT_BUDGET.SLOT_ACTIVE_SKILL,
        "color": "#8B5CF6",
    },
    "few_shot": {
        "display_name": "动态示例",
        "allocated": DEFAULT_BUDGET.SLOT_FEW_SHOT,
        "color": "#06B6D4",
    },
    "rag": {
        "display_name": "背景知识",
        "allocated": DEFAULT_BUDGET.SLOT_RAG,
        "color": "#10B981",
    },
    "episodic": {
        "display_name": "用户画像",
        "allocated": DEFAULT_BUDGET.SLOT_EPISODIC,
        "color": "#F59E0B",
    },
    "procedural": {
        "display_name": "程序记忆",
        "allocated": DEFAULT_BUDGET.SLOT_PROCEDURAL,
        "color": "#EF4444",
    },
    "tools": {
        "display_name": "工具定义",
        "allocated": DEFAULT_BUDGET.SLOT_TOOLS,
        "color": "#3B82F6",
    },
    "history": {
        "display_name": "会话历史",
        "allocated": DEFAULT_BUDGET.slot_history,
        "color": "#6366F1",
    },
}

AUTO_COMPACT_BUFFER_RATIO = 0.165

# Raw slot names -> canonical context bucket
SLOT_CANONICAL_MAP: dict[str, str] = {
    "system": "system",
    "skill_registry": "system",
    "skill_protocol": "system",
    "output_format": "system",
    "active_skill": "active_skill",
    "few_shot": "few_shot",
    "rag": "rag",
    "episodic": "episodic",
    "procedural": "procedural",
    "tools": "tools",
    "history": "history",
    "user_input": "history",
}


def _build_slot_usage(slot_snapshot: Any) -> list[dict[str, Any]]:
    """
    Normalize raw slot tracker names to the canonical Context Window slots for UI.
    """
    used_by_slot: dict[str, int] = {key: 0 for key in SLOT_META}

    for slot in slot_snapshot.slots.values():
        if not slot.enabled:
            continue
        canonical = SLOT_CANONICAL_MAP.get(slot.name)
        if canonical is None:
            continue
        used_by_slot[canonical] += slot.tokens

    return [
        {
            "name": name,
            "displayName": str(meta["display_name"]),
            "allocated": int(meta["allocated"]),
            "used": used_by_slot[name],
            "color": str(meta["color"]),
        }
        for name, meta in SLOT_META.items()
    ]


async def _queue_put(queue: Any, event: tuple[str, dict[str, Any]]) -> None:
    """Put queue event, supporting both async and sync queue mocks."""
    result = queue.put(event)
    if isawaitable(result):
        await result


async def create_react_agent(
    llm: BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    sse_queue: Any | None = None,
    skills_dir: str | None = None,
) -> CompiledStateGraph:
    """
    Create a LangChain ReAct agent with middleware.

    P0: Single provider, no fallback, basic middleware stack.
    P1: HIL middleware for manual intervention on irreversible operations.
    P1: Skills system integration (SkillManager + read_file tool).

    Args:
        llm: Language model (uses llm_factory() if None)
        tools: List of tools (uses [web_search, send_email, read_file] if None)
        sse_queue: Queue for SSE events (passed to TraceMiddleware)
        skills_dir: Skills directory path (uses settings.skills_dir if None)

    Returns:
        CompiledStateGraph: Configured agent graph (LangGraph 1.0+)

    Raises:
        Exception: If agent creation fails
    """
    await emit_trace_event(
        sse_queue,
        stage="agent_init",
        step="create_react_agent",
        status="start",
        payload={"skills_dir": skills_dir},
    )

    # Initialize LLM
    if llm is None:
        llm = llm_factory()
    await emit_trace_event(
        sse_queue,
        stage="agent_init",
        step="llm_ready",
        payload={"provider": settings.llm_provider},
    )

    # Import send_email tool
    from app.tools.send_email import send_email

    # Initialize tools via build_tool_registry (unique assembly point)
    if tools is None:
        tools, tool_manager, policy_engine = build_tool_registry(enable_hil=True)
    else:
        from app.tools.base import ToolMeta
        from app.tools.manager import ToolManager
        from app.tools.policy import PolicyEngine
        # External tools use restrictive policy by default
        tool_metas = {
            t.name: ToolMeta(effect_class="external_write", allowed_decisions=["ask", "deny"])
            for t in tools
        }
        tool_manager = ToolManager(tool_metas)
        policy_engine = PolicyEngine()

    # Ensure read_file is in tools
    if read_file not in tools:
        tools = list(tools) + [read_file]

    logger.info(f"Creating ReAct agent with {len(tools)} tool(s)")
    tool_names = [tool.name for tool in tools]
    await emit_trace_event(
        sse_queue,
        stage="agent_init",
        step="tools_ready",
        payload={"tools": tool_names},
    )

    # Initialize SkillManager and build snapshot
    if skills_dir is None:
        skills_dir = settings.skills_dir
    skill_manager = SkillManager.get_instance(skills_dir=skills_dir)
    skill_snapshot = skill_manager.build_snapshot()
    logger.info(f"Built SkillSnapshot: {len(skill_snapshot.skills)} skills, version {skill_snapshot.version}")
    await emit_trace_event(
        sse_queue,
        stage="skills",
        step="snapshot_built",
        payload={
            "count": len(skill_snapshot.skills),
            "version": skill_snapshot.version,
            "skills": [s.name for s in skill_snapshot.skills],
        },
    )

    # Build system prompt using build_system_prompt
    prompt_result = build_system_prompt(
        skill_snapshot=skill_snapshot,
        available_tools=tool_names,
        track_slots=True,
    )
    system_prompt, slot_snapshot = prompt_result
    logger.debug(f"System prompt length: {len(system_prompt)} characters")
    await emit_trace_event(
        sse_queue,
        stage="context",
        step="system_prompt_built",
        payload={
            "prompt_chars": len(system_prompt),
            "slot_total_tokens": slot_snapshot.total_tokens,
            "slot_count": len(slot_snapshot.slots),
        },
    )

    if sse_queue is not None:
        # Slot details (raw content + token counts)
        await _queue_put(sse_queue, ("slot_details", slot_snapshot.to_dict()))

        # Context window summary for UI panel
        slot_usage = _build_slot_usage(slot_snapshot)
        await _queue_put(
            sse_queue,
            (
                "context_window",
                {
                    "budget": {
                        "model_context_window": DEFAULT_BUDGET.MODEL_CONTEXT_WINDOW,
                        "working_budget": DEFAULT_BUDGET.WORKING_BUDGET,
                        "slots": {
                            "system": DEFAULT_BUDGET.SLOT_SYSTEM,
                            "active_skill": DEFAULT_BUDGET.SLOT_ACTIVE_SKILL,
                            "few_shot": DEFAULT_BUDGET.SLOT_FEW_SHOT,
                            "rag": DEFAULT_BUDGET.SLOT_RAG,
                            "episodic": DEFAULT_BUDGET.SLOT_EPISODIC,
                            "procedural": DEFAULT_BUDGET.SLOT_PROCEDURAL,
                            "tools": DEFAULT_BUDGET.SLOT_TOOLS,
                            "history": DEFAULT_BUDGET.slot_history,
                        },
                        "usage": {
                            "total_used": slot_snapshot.total_tokens,
                            "total_remaining": max(
                                0, DEFAULT_BUDGET.WORKING_BUDGET - slot_snapshot.total_tokens
                            ),
                            "input_budget": DEFAULT_BUDGET.input_budget,
                            "output_reserve": DEFAULT_BUDGET.SLOT_OUTPUT,
                            "autocompact_buffer": max(
                                0,
                                int(DEFAULT_BUDGET.WORKING_BUDGET * AUTO_COMPACT_BUFFER_RATIO),
                            ),
                        },
                    },
                    "slotUsage": slot_usage,
                    "slotDetails": slot_snapshot.to_dict()["slots"],
                    "compressionEvents": [],
                },
            ),
        )

        # Session metadata for UI panel header (module 1)
        from datetime import datetime, timezone
        _provider = str(settings.llm_provider)
        if _provider == "anthropic":
            _model_name = settings.anthropic_model
        elif _provider == "ollama":
            _model_name = settings.ollama_model
        else:
            _model_name = _provider
        await _queue_put(
            sse_queue,
            (
                "session_metadata",
                {
                    "session_name": "Session",
                    "model": _model_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            ),
        )

        await emit_trace_event(
            sse_queue,
            stage="context",
            step="slot_snapshot_emitted",
            payload={
                "slot_total_tokens": slot_snapshot.total_tokens,
                "slots": [
                    {"name": slot.name, "tokens": slot.tokens}
                    for slot in slot_snapshot.slots.values()
                    if slot.enabled
                ],
            },
        )

    # Create middleware stack
    # Get interrupt store for HIL middleware
    interrupt_store = await get_interrupt_store()

    # Get store for MemoryMiddleware (Long Memory)
    store = await get_store()
    memory_manager = MemoryManager(store=store)

    # Create middleware stack per architecture doc §2.7
    # Order matters: Memory → Summarization → Trace → HIL
    middleware = [
        MemoryMiddleware(
            memory_manager=memory_manager,
            sse_queue=sse_queue,
        ),  # P0: load + inject profile
        create_summarization_middleware(model=llm),  # P0: compress history when token limit exceeded (uses same LLM)
        TraceMiddleware(sse_queue=sse_queue),  # P0: SSE streaming
        HILMiddleware(interrupt_store=interrupt_store, sse_queue=sse_queue),  # P1: HIL intervention
    ]
    await emit_trace_event(
        sse_queue,
        stage="agent_init",
        step="middleware_ready",
        payload={"middleware": [type(m).__name__ for m in middleware]},
    )

    try:
        # Create agent with create_agent (LangChain 1.0+ API)
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,  # type: ignore
        )

        logger.info("Agent created successfully with HIL middleware")
        await emit_trace_event(
            sse_queue,
            stage="agent_init",
            step="agent_ready",
            payload={"tool_count": len(tool_names)},
        )
        return agent

    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        await emit_trace_event(
            sse_queue,
            stage="agent_init",
            step="agent_create_failed",
            status="error",
            payload={"error": str(e)},
        )
        raise


def get_default_tools() -> list[BaseTool]:
    """Get default tools for the agent via build_tool_registry."""
    tools, _, _ = build_tool_registry(enable_hil=True)
    return tools


__all__ = ["create_react_agent", "get_default_tools"]
