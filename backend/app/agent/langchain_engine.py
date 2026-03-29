"""
LangChain Agent Engine - creates and configures the ReAct agent.

P0: Basic create_agent with web_search tool and middleware.
P1: HIL middleware for manual intervention.
P1: Skills system integration (SkillManager + read_file tool).
"""
import asyncio
from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from app.agent.context import AgentContext
from app.agent.middleware.memory import MemoryMiddleware
from app.agent.middleware.summarization import create_summarization_middleware
from app.agent.middleware.tool_execution import ToolExecutionMiddleware
from app.agent.middleware.tool_policy import PolicyHITLMiddleware
from app.agent.middleware.trace import TraceMiddleware
from app.config import settings
from app.db.postgres import get_checkpointer, get_store
from app.llm.factory import llm_factory
from app.memory.manager import MemoryManager
from app.observability.trace_events import emit_trace_event
from app.prompt.builder import build_system_prompt
from app.prompt.budget import DEFAULT_BUDGET
from app.skills.manager import SkillManager
from app.tools.base import ToolMeta
from app.tools.file import read_file
from app.tools.idempotency import IdempotencyStore
from app.tools.manager import ToolManager
from app.tools.policy import PolicyEngine
from app.tools.registry import build_tool_registry
from app.tools.search import web_search
from app.utils.token import count_tokens

SLOT_META: dict[str, dict[str, str | int]] = {
    "system": {
        "display_name": "系统提示词",
        "allocated": DEFAULT_BUDGET.SLOT_SYSTEM,
        "color": "#5E6AD2",
    },
    "skill_registry": {
        "display_name": "技能注册表",
        "allocated": 0,
        "color": "#0EA5E9",
    },
    "skill_protocol": {
        "display_name": "技能协议",
        "allocated": 0,
        "color": "#7C3AED",
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
    "output_format": {
        "display_name": "输出格式",
        "allocated": 0,
        "color": "#EC4899",
    },
}

AUTO_COMPACT_BUFFER_RATIO = 0.165


@dataclass
class _CachedAgent:
    """Holds the compiled agent graph and static setup data for SSE re-emission."""
    graph: CompiledStateGraph
    slot_snapshot_dict: dict[str, Any]
    slot_usage: list[dict[str, Any]]
    tool_names: list[str]
    tool_manager: ToolManager
    policy_engine: PolicyEngine
    skill_names: list[str]
    skill_version: int
    model_name: str


_agent_cache: _CachedAgent | None = None
_agent_cache_lock = asyncio.Lock()

# Raw slot names -> canonical context bucket
SLOT_CANONICAL_MAP: dict[str, str] = {
    "system": "system",
    "skill_registry": "skill_registry",
    "skill_protocol": "skill_protocol",
    "output_format": "output_format",
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


async def _build_agent_internal(
    llm: BaseChatModel | None,
    tools: list[BaseTool] | None,
    skills_dir: str | None,
) -> _CachedAgent:
    """
    Build the agent graph once. Called only on first request (or after invalidation).
    No SSE emission here — setup events are emitted per-request via emit_setup_events().
    """
    logger.info("═══════════════════════════════════════")
    logger.info("🏗️ [初始化] 构建 ReAct Agent（首次，结果将被缓存）")
    logger.info("═══════════════════════════════════════")

    # Initialize LLM
    if llm is None:
        logger.info(f"🤖 [初始化] 正在初始化 LLM（提供商: {settings.llm_provider}）...")
        llm = llm_factory()
        logger.info("✅ [初始化] LLM 初始化完成")

    # Initialize tools
    logger.info("🔧 [初始化] 正在注册工具集...")
    if tools is None:
        tools, tool_manager, policy_engine = build_tool_registry(enable_hil=True)
    else:
        tools = list(tools)
        tool_metas = {
            t.name: ToolMeta(effect_class="external_write", allowed_decisions=["ask", "deny"])
            for t in tools
        }
        if read_file not in tools:
            tools.append(read_file)
            tool_metas[read_file.name] = ToolMeta(
                effect_class="read",
                allowed_decisions=["allow"],
                idempotent=True,
                max_retries=1,
                timeout_seconds=10,
                backoff=None,
                can_parallelize=True,
                audit_tags=["file", "readonly"],
            )
        tool_manager = ToolManager(tool_metas)
        policy_engine = PolicyEngine()

    tool_names = [t.name for t in tools]
    logger.info(f"✅ [初始化] 工具注册完成，共 {len(tools)} 个: {tool_names}")

    # Initialize SkillManager
    if skills_dir is None:
        skills_dir = settings.skills_dir
    resolved_skills_dir = str(Path(skills_dir).expanduser().resolve())
    logger.info(f"📚 [初始化] 正在初始化 SkillManager，路径: {resolved_skills_dir}")
    skill_manager = SkillManager.get_instance(skills_dir=resolved_skills_dir)
    skill_snapshot = skill_manager.build_snapshot()
    skill_names = [s.name for s in skill_snapshot.skills]
    logger.info(f"✅ [初始化] SkillManager 就绪，{len(skill_snapshot.skills)} 个技能: {skill_names}")

    # Build system prompt
    logger.info("📝 [初始化] 正在构建 System Prompt...")
    system_prompt, slot_snapshot = build_system_prompt(
        skill_snapshot=skill_snapshot,
        available_tools=tool_names,
        track_slots=True,
    )
    logger.info(f"✅ [初始化] System Prompt 构建完成，{slot_snapshot.total_tokens} tokens")

    # Resolve model name for session_metadata SSE
    _provider = str(settings.llm_provider)
    if _provider == "anthropic":
        model_name = settings.anthropic_model
    elif _provider == "ollama":
        model_name = settings.ollama_model
    else:
        model_name = _provider

    # Create middleware stack — no sse_queue; injected per-request via AgentContext
    logger.info("🧩 [初始化] 正在构建 Middleware 堆栈...")
    store = await get_store()
    checkpointer = await get_checkpointer()
    memory_manager = MemoryManager(store=store)
    idempotency_store = IdempotencyStore()

    middleware = [
        MemoryMiddleware(memory_manager=memory_manager),
        create_summarization_middleware(model=llm),
        TraceMiddleware(),
        PolicyHITLMiddleware(tool_manager=tool_manager, policy_engine=policy_engine),
        ToolExecutionMiddleware(
            tool_manager=tool_manager,
            idempotency_store=idempotency_store,
        ),
    ]
    middleware_names = [type(m).__name__ for m in middleware]
    logger.info(f"✅ [初始化] Middleware 堆栈就绪: {' → '.join(middleware_names)}")

    # Compile agent graph with context_schema=AgentContext
    logger.info("🔗 [初始化] create_agent（绑定 LLM + 工具 + Middleware + context_schema）...")
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,  # type: ignore
        checkpointer=checkpointer,
        context_schema=AgentContext,
    )
    logger.info("✅ [初始化] Agent 编译完成，已缓存，可跨请求复用")

    return _CachedAgent(
        graph=agent,
        slot_snapshot_dict=slot_snapshot.to_dict(),
        slot_usage=_build_slot_usage(slot_snapshot),
        tool_names=tool_names,
        tool_manager=tool_manager,
        policy_engine=policy_engine,
        skill_names=skill_names,
        skill_version=skill_snapshot.version,
        model_name=model_name,
    )


async def emit_setup_events(sse_queue: Any, cached: _CachedAgent, config: dict | None = None) -> None:
    """
    Emit per-request setup SSE events from cached agent data.

    Called once per request before agent.astream(), so the frontend
    always receives slot_details, context_window, and session_metadata
    even though the agent graph is reused across requests.
    """
    if sse_queue is None:
        return

    from datetime import datetime, timezone

    # Slot details
    await _queue_put(sse_queue, ("slot_details", cached.slot_snapshot_dict))

    # Context window summary
    slots_dict = cached.slot_snapshot_dict
    base_used = sum(s.get("tokens", 0) for s in slots_dict.get("slots", []))

    # Compute history tokens from current checkpoint state and update slotUsage
    history_tokens = 0
    if config is not None:
        try:
            state = await cached.graph.aget_state(config)
            raw_msgs = state.values.get("messages", [])
            if raw_msgs:
                history_content = "\n".join(
                    m.content if isinstance(m.content, str) else ""
                    for m in raw_msgs
                    if hasattr(m, "content")
                )
                history_tokens = count_tokens(history_content) if history_content else 0
        except Exception:
            pass

    total_used = base_used + history_tokens

    # Build updated slotUsage with current history token count
    slot_usage = [dict(s) for s in cached.slot_usage]
    for s in slot_usage:
        if s["name"] == "history":
            s["used"] = history_tokens
            break

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
                        "skill_registry": 0,
                        "skill_protocol": 0,
                        "few_shot": DEFAULT_BUDGET.SLOT_FEW_SHOT,
                        "rag": DEFAULT_BUDGET.SLOT_RAG,
                        "episodic": DEFAULT_BUDGET.SLOT_EPISODIC,
                        "procedural": DEFAULT_BUDGET.SLOT_PROCEDURAL,
                        "tools": DEFAULT_BUDGET.SLOT_TOOLS,
                        "history": DEFAULT_BUDGET.slot_history,
                        "output_format": 0,
                        "user_input": 0,
                    },
                    "usage": {
                        "total_used": total_used,
                        "total_remaining": max(0, DEFAULT_BUDGET.WORKING_BUDGET - total_used),
                        "input_budget": DEFAULT_BUDGET.input_budget,
                        "output_reserve": DEFAULT_BUDGET.SLOT_OUTPUT,
                        "autocompact_buffer": max(
                            0, int(DEFAULT_BUDGET.WORKING_BUDGET * AUTO_COMPACT_BUFFER_RATIO)
                        ),
                    },
                },
                "slotUsage": slot_usage,
                "slotDetails": slots_dict.get("slots", {}),
                "compressionEvents": [],
            },
        ),
    )

    # Session metadata (timestamp is per-request)
    await _queue_put(
        sse_queue,
        (
            "session_metadata",
            {
                "session_name": "Session",
                "model": cached.model_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ),
    )


async def create_react_agent(
    llm: BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    sse_queue: Any | None = None,
    skills_dir: str | None = None,
    config: dict | None = None,
) -> CompiledStateGraph:
    """
    Get (or build) cached ReAct agent, then emit per-request setup SSE events.

    The agent graph is compiled once and reused across requests.
    SSE queue and user_id are injected per-request via AgentContext
    (passed to agent.astream(context=AgentContext(...))).

    Args:
        llm: Override LLM (used only on first call; ignored if agent already cached)
        tools: Override tools (used only on first call)
        sse_queue: Per-request SSE queue — receives setup events immediately
        skills_dir: Skills directory (used only on first call)

    Returns:
        CompiledStateGraph: Cached agent graph ready for astream()
    """
    global _agent_cache
    global _agent_cache_lock
    import time
    start_time = time.time()

    if _agent_cache is None:
        async with _agent_cache_lock:
            if _agent_cache is None:
                try:
                    _agent_cache = await _build_agent_internal(llm, tools, skills_dir)
                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.error(f"❌ [初始化] Agent 创建失败: {e}，耗时={elapsed:.2f}s")
                    if sse_queue is not None:
                        await emit_trace_event(
                            sse_queue, stage="agent_init", step="agent_create_failed",
                            status="error", payload={"error": str(e), "elapsed_seconds": elapsed},
                        )
                    raise
            else:
                logger.info("✅ [初始化] 使用缓存 Agent（跳过重新编译）")
    else:
        logger.info("✅ [初始化] 使用缓存 Agent（跳过重新编译）")

    # Always emit per-request setup events
    setup_start = time.time()
    await emit_setup_events(sse_queue, _agent_cache, config)
    setup_elapsed = time.time() - setup_start
    logger.debug(f"📊 [初始化] emit_setup_events 耗时={setup_elapsed:.3f}s")

    return _agent_cache.graph


def get_default_tools() -> list[BaseTool]:
    """Get default tools for the agent via build_tool_registry."""
    tools, _, _ = build_tool_registry(enable_hil=True)
    return tools


async def grant_session_tool_access(session_id: str, tool_name: str) -> list[str]:
    """Grant allow-once-per-session bypass for a tool on the cached policy engine."""
    global _agent_cache
    if _agent_cache is None:
        await create_react_agent()
    assert _agent_cache is not None

    meta = _agent_cache.tool_manager.get_meta(tool_name)
    if meta is None:
        raise ValueError(f"Unknown tool for session grant: {tool_name}")
    if meta.effect_class == "destructive":
        raise ValueError(f"Destructive tool cannot be session granted: {tool_name}")

    _agent_cache.policy_engine.grant_session(tool_name, session_id=session_id)
    return sorted(_agent_cache.policy_engine.get_granted_tools(session_id))


async def revoke_session_tool_access(session_id: str, tool_name: str) -> list[str]:
    """Remove a previously granted session allow for a tool."""
    if _agent_cache is None:
        return []
    _agent_cache.policy_engine.revoke_session(tool_name, session_id=session_id)
    return sorted(_agent_cache.policy_engine.get_granted_tools(session_id))


async def get_session_granted_tools(session_id: str) -> list[str]:
    """Return the currently granted tools for a session."""
    if _agent_cache is None:
        return []
    return sorted(_agent_cache.policy_engine.get_granted_tools(session_id))


__all__ = [
    "create_react_agent",
    "get_default_tools",
    "grant_session_tool_access",
    "revoke_session_tool_access",
    "get_session_granted_tools",
]
