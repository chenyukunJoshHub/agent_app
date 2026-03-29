"""
Chat API with SSE streaming support.

P0: POST /chat endpoint with Server-Sent Events streaming.
"""
import asyncio
import json
import traceback
from collections.abc import AsyncIterator
from functools import lru_cache
from inspect import isawaitable
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Command
from loguru import logger
from pydantic import BaseModel, Field

from app.agent.context import AgentContext
from app.agent.langchain_engine import (
    create_react_agent,
    get_session_granted_tools,
    grant_session_tool_access,
    revoke_session_tool_access,
)
from app.config import settings
from app.db.postgres import get_store
from app.logger import ApiLogger, SseLogger, ToolsLogger
from app.observability.trace_events import emit_trace_event
from app.observability.interrupt_store import get_interrupt_store
from app.planner.orchestrator import TaskPlanner, TaskRuntimeStore
from app.skills.manager import SkillManager
from app.tools.idempotency import IdempotencyStore
from app.tools.registry import build_tool_registry
from app.utils.token import count_tokens


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for /chat endpoint."""

    message: str = Field(..., description="User message")
    session_id: str = Field(..., description="Session identifier (maps to thread_id)")
    user_id: str = Field(default="dev_user", description="User identifier (P0: no auth)")


class ChatResumeRequest(BaseModel):
    """Request model for /chat/resume endpoint (P1: HIL resume)."""

    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(default="dev_user", description="User identifier")
    interrupt_id: str = Field(..., description="Interrupt identifier to resume")
    approved: bool = Field(..., description="Whether user approved the action")
    grant_session: bool = Field(
        default=False,
        description="Whether to allow this tool for the rest of the current session",
    )


class SessionGrantRequest(BaseModel):
    """Request model for session-scoped tool grants."""

    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(default="dev_user", description="User identifier")
    tool_name: str = Field(..., description="Tool name")


# SSE Event Queue
class SSEEventQueue:
    """Async queue for SSE events."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    async def put(self, event: tuple[str, dict[str, Any]]) -> None:
        """Put an event into queue."""
        await self._queue.put(event)

    async def get(self) -> tuple[str, dict[str, Any]]:
        """Get an event from queue."""
        return await self._queue.get()

    def get_nowait(self) -> tuple[str, dict[str, Any]]:
        """Get an event without waiting."""
        return self._queue.get_nowait()

    def empty(self) -> bool:
        """Check whether queue is empty."""
        return self._queue.empty()

    def task_done(self) -> None:
        """Mark a task as done."""
        self._queue.task_done()


# Router
router = APIRouter(prefix="/chat", tags=["chat"])

_RESUME_IDEMPOTENCY_STORE = IdempotencyStore()
_TASK_PLANNER = TaskPlanner()
_TASK_RUNTIME: TaskRuntimeStore | None = None
_TASK_RUNTIME_LOCK = asyncio.Lock()


@lru_cache(maxsize=1)
def _get_resume_tool_manager() -> Any:
    """Get cached ToolManager for resume-time idempotency key lookup."""
    _, tool_manager, _ = build_tool_registry(enable_hil=True)
    return tool_manager


def _build_resume_idempotency_key(
    session_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    """
    Build idempotency key for /chat/resume tool execution.

    Priority:
    1) ToolMeta.idempotency_key_fn(args)
    2) Stable JSON serialization fallback
    """
    key_seed: str | None = None

    try:
        tool_manager = _get_resume_tool_manager()
        meta = tool_manager.get_meta(tool_name)
        if meta and meta.idempotency_key_fn:
            generated = meta.idempotency_key_fn(tool_args)
            if generated is not None:
                key_seed = str(generated)
    except Exception as err:
        logger.warning(f"Failed to generate tool meta idempotency key for {tool_name}: {err}")

    if not key_seed:
        try:
            key_seed = f"{tool_name}:{json.dumps(tool_args, ensure_ascii=False, sort_keys=True)}"
        except TypeError:
            key_seed = f"{tool_name}:{str(tool_args)}"

    # Scope to session to avoid cross-session collisions.
    return f"resume:{session_id}:{key_seed}"


def _check_and_mark_resume_idempotency(
    session_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
) -> tuple[bool, str]:
    """Return (already_executed, key) for resume tool invocation."""
    key = _build_resume_idempotency_key(session_id, tool_name, tool_args)
    already_executed = _RESUME_IDEMPOTENCY_STORE.check_and_mark(key)
    return already_executed, key


def _build_hil_resume_command(
    interrupt_id: str,
    approved: bool,
    tool_name: str,
    decision_count: int = 1,
) -> Command:
    """Build LangGraph Command payload for HITL resume decision."""
    effective_count = max(1, decision_count)
    decisions: list[dict[str, Any]]
    if approved:
        decisions = [{"type": "approve"} for _ in range(effective_count)]
    else:
        decisions = [
            {
                "type": "reject",
                "message": f"用户拒绝执行 {tool_name} 操作",
            }
            for _ in range(effective_count)
        ]
    # Use interrupt-id keyed mapping to be explicit and future-proof for multi-interrupt scenarios.
    return Command(resume={interrupt_id: {"decisions": decisions}})


def _infer_hil_risk_level(tool_name: str) -> str:
    """Map tool meta to coarse UI risk levels."""
    try:
        tool_manager = _get_resume_tool_manager()
        meta = tool_manager.get_meta(tool_name)
        if meta is None:
            return "medium"
        if meta.effect_class in {"external_write", "destructive"}:
            return "high"
        if meta.effect_class == "write":
            return "medium"
    except Exception:
        return "medium"
    return "low"


def _infer_hil_risk_level_for_actions(action_requests: list[dict[str, Any]]) -> str:
    """Use the highest risk level across all interrupted actions."""
    if not action_requests:
        return "medium"
    priorities = {"low": 0, "medium": 1, "high": 2}
    current = "low"
    for action in action_requests:
        level = _infer_hil_risk_level(str(action.get("name", "unknown")))
        if priorities[level] > priorities[current]:
            current = level
    return current


def _build_hil_message(action_requests: list[dict[str, Any]]) -> str:
    """Prefer the action description for single-action interrupts, summarize batches."""
    if not action_requests:
        return "Tool execution requires approval"
    if len(action_requests) == 1:
        return str(action_requests[0].get("description") or "Tool execution requires approval")
    return f"Agent 准备执行 {len(action_requests)} 个需审批操作，请确认"


def _get_grantable_tool_name(interrupt_data: dict[str, Any]) -> str | None:
    """
    Session grant is only well-defined when all interrupted actions target the same tool.
    """
    action_requests = interrupt_data.get("action_requests", []) or []
    tool_names = {
        str(action.get("name"))
        for action in action_requests
        if isinstance(action, dict) and action.get("name")
    }
    if tool_names:
        return next(iter(tool_names)) if len(tool_names) == 1 else None

    tool_name = interrupt_data.get("tool_name")
    if isinstance(tool_name, str) and tool_name:
        return tool_name
    return None


def _extract_hil_interrupt_payload(interrupts: tuple[Any, ...]) -> dict[str, Any]:
    """Normalize LangGraph interrupt payload for SSE/UI and persistence."""
    interrupt = interrupts[0] if interrupts else None
    if interrupt is None:
        return {
            "interrupt_id": "unknown",
            "tool_name": "unknown",
            "tool_args": {},
            "risk_level": "medium",
            "message": "Tool execution requires approval",
            "allowed_decisions": [],
            "action_requests": [],
            "review_configs": [],
            "grant_session_supported": False,
        }

    raw_value = getattr(interrupt, "value", {}) or {}
    action_requests = raw_value.get("action_requests", []) if isinstance(raw_value, dict) else []
    review_configs = raw_value.get("review_configs", []) if isinstance(raw_value, dict) else []
    first_action = action_requests[0] if action_requests else {}
    first_review = review_configs[0] if review_configs else {}

    return {
        "interrupt_id": getattr(interrupt, "id", "unknown"),
        "tool_name": first_action.get("name", "unknown"),
        "tool_args": first_action.get("args", {}),
        "risk_level": _infer_hil_risk_level_for_actions(action_requests),
        "message": _build_hil_message(action_requests),
        "allowed_decisions": first_review.get("allowed_decisions", []),
        "action_requests": action_requests,
        "review_configs": review_configs,
        "grant_session_supported": _get_grantable_tool_name(
            {"tool_name": first_action.get("name"), "action_requests": action_requests}
        )
        is not None,
    }


async def _persist_hil_interrupt(
    session_id: str | None,
    interrupt_payload: dict[str, Any],
) -> None:
    """Persist LangGraph interrupt metadata for /chat/resume lookup."""
    if not session_id:
        return

    interrupt_store = await get_interrupt_store()
    await interrupt_store.save_interrupt(
        session_id=session_id,
        tool_name=interrupt_payload.get("tool_name", "unknown"),
        tool_args=interrupt_payload.get("tool_args", {}),
        interrupt_id=interrupt_payload.get("interrupt_id"),
        allowed_decisions=interrupt_payload.get("allowed_decisions", []),
        action_requests=interrupt_payload.get("action_requests", []),
        review_configs=interrupt_payload.get("review_configs", []),
    )


async def _resolve_hil_resume_decision(
    interrupt_id: str,
    approved: bool,
    tool_name: str,
    tool_args: dict[str, Any],
    event_queue: Any,
) -> dict[str, Any]:
    """Update persisted interrupt state and build the user-facing resolution payload."""
    if approved:
        logger.info(f"User approved interrupt {interrupt_id} for tool {tool_name}")
        await emit_trace_event(
            event_queue,
            stage="hil",
            step="resume_approved",
            payload={"interrupt_id": interrupt_id, "tool_name": tool_name},
        )
        return {
            "success": True,
            "message": f"已批准执行 {tool_name} 操作",
            "tool_name": tool_name,
            "tool_args": tool_args,
        }

    logger.info(f"User rejected interrupt {interrupt_id} for tool {tool_name}")
    await emit_trace_event(
        event_queue,
        stage="hil",
        step="resume_rejected",
        payload={"interrupt_id": interrupt_id, "tool_name": tool_name},
    )
    return {
        "success": True,
        "message": f"已取消 {tool_name} 操作",
        "tool_name": tool_name,
    }


def _plan_to_payload(plan: Any) -> dict[str, Any]:
    """将 PlanState 转换为可序列化 payload（供 trace_event 使用）。"""
    return {
        "plan_id": getattr(plan, "plan_id", ""),
        "complexity": getattr(plan, "complexity", "simple"),
        "step_count": len(getattr(plan, "steps", [])),
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "status": getattr(step.status, "value", str(step.status)),
            }
            for step in getattr(plan, "steps", [])
        ],
        "retrieval_hits": list(getattr(plan, "retrieval_hits", []) or []),
    }


async def _get_task_runtime_store() -> TaskRuntimeStore:
    """Get or create TaskRuntimeStore (with persistent store when available)."""
    global _TASK_RUNTIME

    if _TASK_RUNTIME is not None:
        return _TASK_RUNTIME

    async with _TASK_RUNTIME_LOCK:
        if _TASK_RUNTIME is None:
            store = None
            try:
                store = await get_store()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"TaskRuntimeStore fallback to memory-only mode: {exc}")
            _TASK_RUNTIME = TaskRuntimeStore(max_replans=1, store=store)
    return _TASK_RUNTIME


async def _call_runtime_method(
    runtime: Any,
    async_method: str,
    sync_method: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Call planner runtime method with async/sync compatibility.

    优先调用 async 方法（如 amark_xxx），不存在则回退 sync 方法（mark_xxx）。
    """
    method = getattr(runtime, async_method, None)
    if method is None:
        method = getattr(runtime, sync_method, None)
    if method is None:
        return None
    result = method(*args, **kwargs)
    if isawaitable(result):
        return await result
    return result


async def _format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """
    Format data as SSE event.

    Args:
        event_type: Event type (trace_event, thought, context_window, slot_details, done, error)
        data: Event payload

    Returns:
        str: Formatted SSE event string
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _apply_skill_hint(message: str, skill_id: str | None, mode: str | None) -> str:
    """
    Hint 模式：在消息头部追加 [Skill: X] 软提示，引导 LLM 优先激活指定 skill。

    force 模式当前未实现，静默降级为 hint 行为。
    skill_id 为 None 或空字符串时，直接返回原始消息。
    """
    if not skill_id:
        return message
    effective_mode = mode or settings.skill_invocation_mode
    # force 模式暂未实现，降级为 hint
    if effective_mode in ("hint", "force"):
        return f"[Skill: {skill_id}]\n{message}"
    return message


def _get_skill_description(skill_id: str) -> str | None:
    """从 SkillManager 单例查询 skill 的 description；不存在时返回 None 并 log warning。"""
    try:
        manager = SkillManager.get_instance()
        definitions = manager.scan()  # 使用公开 scan() 方法，返回 SkillDefinition 列表
        for defn in definitions:
            if defn.id == skill_id or defn.name == skill_id:
                return defn.metadata.description
    except Exception:
        pass
    logger.warning(f"⚠️ [Skill] skill_id='{skill_id}' 不在 active 列表中，hint 已注入但 skill 可能无法匹配")
    return None


async def _run_agent_stream(
    message: str,
    session_id: str,
    user_id: str,
    api_logger: "ApiLogger",
    tools_logger: "ToolsLogger",
    sse_logger: "SseLogger",
    skill_id: str | None = None,
    invocation_mode: str | None = None,
) -> AsyncIterator[str]:
    """
    Run agent and yield SSE events.

    Args:
        message: User message
        session_id: Session identifier (thread_id)
        user_id: User identifier
        api_logger: ApiLogger for API logging
        tools_logger: ToolsLogger for tools logging
        sse_logger: SseLogger for SSE event logging

    Yields:
        str: SSE-formatted event strings
    """
    # Create SSE queue
    start_time = asyncio.get_event_loop().time()
    logger.info(f"📥 [API] 收到用户消息，会话ID={session_id}，用户={user_id}，消息长度={len(message)} 字符")
    logger.info(f"⏱️ [超时配置] HTTP超时={settings.http_timeout}s, Keep-alive={settings.keep_alive_timeout}s")
    if skill_id:
        logger.info(f"🎯 [Skill] Skill激活: skill_id={skill_id}, mode={invocation_mode or settings.skill_invocation_mode}")
    event_queue = SSEEventQueue()
    await emit_trace_event(
        event_queue,
        stage="stream",
        step="request_received",
        payload={
            "session_id": session_id,
            "user_id": user_id,
            "message_chars": len(message),
        },
    )

    # Log request received
    api_logger.api_request_received(
        endpoint="/chat",
        method="GET",
        message_length=len(message),
    )

    # config: thread_id identifies the checkpoint; user_id is in AgentContext
    config = {"configurable": {"thread_id": session_id}}

    # Create agent with SSE queue (await function)
    logger.info("🔨 [API] 开始创建 ReAct Agent （create_agent）...")
    agent = await create_react_agent(sse_queue=event_queue, config=config)
    logger.info("✅ [API] ReAct Agent （create_agent） 创建完成，准备执行")

    # Task Orchestration：在真正执行前创建结构化计划，并做轻量历史检索。
    history_texts: list[str] = []
    try:
        prev_state = await agent.aget_state(config)
        prev_messages = prev_state.values.get("messages", []) if prev_state else []
        for msg in prev_messages[-30:]:
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                history_texts.append(content.strip())
    except Exception as hist_err:  # noqa: BLE001
        logger.debug(f"planner history load skipped: {hist_err}")

    plan = _TASK_PLANNER.create_plan(
        session_id=session_id,
        user_goal=message,
        history=history_texts,
    )
    task_runtime = await _get_task_runtime_store()
    await task_runtime.aset_plan(session_id, plan)

    await emit_trace_event(
        event_queue,
        stage="planner",
        step="plan_created",
        payload=_plan_to_payload(plan),
    )
    if plan.retrieval_hits:
        await emit_trace_event(
            event_queue,
            stage="retrieval",
            step="context_retrieved",
            payload={
                "plan_id": plan.plan_id,
                "hits": len(plan.retrieval_hits),
                "items": plan.retrieval_hits,
            },
        )

    await emit_trace_event(
        event_queue,
        stage="stream",
        step="agent_created",
        payload={"session_id": session_id},
    )

    await emit_trace_event(
        event_queue,
        stage="stream",
        step="stream_started",
         payload={"session_id": session_id},
     )

    # Emit skill_invoked event so frontend can update slot data
    if skill_id:
        skill_description = _get_skill_description(skill_id)
        await event_queue.put(("skill_invoked", {
            "skill_id": skill_id,
            "description": skill_description or "",
            "mode": invocation_mode or settings.skill_invocation_mode,
        }))
        # 注意：不要再 yield，主循环会从 queue 取出并 yield

    # Run agent in background; cancelled in finally if SSE exits early
    logger.info(f"🚀 [API] asyncio.create_task(_execute_agent(...)) - agent.astream，会话ID={session_id}")
    agent_task = asyncio.create_task(
        _execute_agent(
            agent,
            message,
            config,
            event_queue,
            user_id,
            tools_logger,
            sse_logger,
            planner_runtime=task_runtime,
            session_id=session_id,
        )
    )

    # Timeout monitoring task
    timeout_seconds = settings.http_timeout
    logger.info(f"⏱️ [超时监控] 启动超时监控任务，超时阈值={timeout_seconds}s")

    async def timeout_monitor():
        try:
            await asyncio.wait_for(agent_task, timeout=timeout_seconds)
        except TimeoutError:
            logger.error(f"⏰ [超时] Agent执行超时！阈值={timeout_seconds}s，会话ID={session_id}")
            await event_queue.put((
                "error",
                {"message": f"请求超时（{timeout_seconds}s），请稍后重试或检查后端日志"}
            ))
            if not agent_task.done():
                agent_task.cancel()
                logger.warning("⚠️ [超时] 已取消超时的agent_task")

    # Start timeout monitor in background
    timeout_task = asyncio.create_task(timeout_monitor())

    # Stream events
    logger.info("📡 [SSE] 开始推送 SSE 事件流给前端...")
    _thought_logged = False
    try:
        while True:
            event_type, data = await event_queue.get()

            if event_type == "thought" and not _thought_logged:
                _thought_logged = True

            # Yield SSE event
            yield await _format_sse_event(event_type, data)

            # Log event pushed
            api_logger.api_sse_event_sent(
                event_type=event_type,
                data_length=len(str(data)),
            )

            # Check if agent is done
            if event_type == "done":
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"🏁 [SSE] 收到 done 事件，流式响应结束，耗时={elapsed:.2f}s")
                api_logger.api_sse_stream_end(
                    session_id=session_id,
                    total_events=data.get("total_tokens", 0),
                    total_bytes=len(str(data)),
                )
                break

            # Error event — log and stop streaming (agent task has already exited)
            if event_type == "error":
                logger.warning(f"⚠️ [SSE] 收到错误事件: {data.get('message', '')}")
                api_logger.api_request_error(
                    session_id=session_id,
                    error_type="sse_error",
                    error_message=data.get("message", ""),
                    stack_trace=None,
                )
                break  # Fix A: error must exit the loop, not hang

    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.error(f"❌ [SSE] SSE 流发生异常: {e}，耗时={elapsed:.2f}s")
        yield await _format_sse_event("error", {"message": str(e)})
        api_logger.api_request_error(
            session_id=session_id,
            error_type="sse_exception",
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
    finally:
        # Fix E: cancel background task if SSE exits before agent finishes
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"🧹 [SSE] finally块执行，总耗时={elapsed:.2f}s，agent_task.done={agent_task.done()}")

        if not agent_task.done():
            logger.warning("⚠️ [SSE] SSE提前退出，取消agent_task")
            agent_task.cancel()

        if not timeout_task.done():
            logger.debug("🧹 [SSE] 取消timeout_task")
            timeout_task.cancel()


async def _execute_agent(
    agent: Any,
    message: str,
    config: dict[str, Any],
    event_queue: SSEEventQueue,
    user_id: str,
    tools_logger: "ToolsLogger",
    sse_logger: "SseLogger",
    agent_input: Any | None = None,
    planner_runtime: TaskRuntimeStore | None = None,
    session_id: str | None = None,
) -> None:
    """
    Execute agent and push events to queue.

    Args:
        agent: Agent executor
        message: User message
        config: LangGraph config with thread_id
        event_queue: SSEEventQueue
        tools_logger: ToolsLogger for tools logging
        planner_runtime: 任务运行时状态机（可选）
        session_id: 会话 ID（可选，默认从 config 读取）
        sse_logger: SseLogger for SSE event logging
    """
    # Prepare input
    execution_start = asyncio.get_event_loop().time()
    logger.info(f"🤔 [Agent] _execute_agent 开始执行，用户消息: '{message[:50]}{'...' if len(message) > 50 else ''}'")
    if agent_input is None:
        messages_input = [HumanMessage(content=message)]
        stream_input: Any = {"messages": messages_input}
    else:
        stream_input = agent_input

    seq = 0  # Event sequence counter
    final_answer = ""  # Accumulate streaming text for done payload
    llm_call_start = None  # Track LLM call timing
    active_session_id = session_id
    if not active_session_id:
        configurable = config.get("configurable", {})
        if isinstance(configurable, dict):
            value = configurable.get("thread_id")
            if isinstance(value, str):
                active_session_id = value

    attempt = 0
    max_attempts = 2 if (planner_runtime is not None and active_session_id) else 1

    while True:
        interrupted = False
        try:
            logger.info(
                "🔄 [Agent] _execute_agent - agent.astream 循环，等待 LLM 响应..."
                f" (attempt={attempt + 1}/{max_attempts})"
            )
            async for chunk in agent.astream(
                stream_input,
                config=config,
                context=AgentContext(sse_queue=event_queue, user_id=user_id),
                stream_mode=["messages", "updates"],
            ):
                elapsed_since_start = asyncio.get_event_loop().time() - execution_start
                mode = chunk[0]
                data = chunk[1]

                # 超时警告：如果执行时间超过配置超时的50%
                if elapsed_since_start > settings.http_timeout * 0.5 and seq == 0:
                    logger.warning(
                        f"⏱️ [超时警告] 执行时间已过半 ({elapsed_since_start:.1f}s / {settings.http_timeout}s)，但尚未收到任何事件"
                    )
                if mode == "messages":  # messages mode
                    # Process AIMessageChunk
                    token, metadata = data
                    _ = metadata

                    if isinstance(token, AIMessageChunk):
                        if token.text:
                            # 第一次收到文本时，记录 LLM 响应延迟
                            if llm_call_start is None:
                                llm_call_start = asyncio.get_event_loop().time()
                                llm_latency = llm_call_start - execution_start
                                logger.info(f"🤖 [Agent] LLM首次响应，延迟={llm_latency:.2f}s")

                            seq += 1
                            final_answer += token.text
                            # debug 级别避免刷屏
                            # Log thought event
                            sse_logger.sse_event_thought(
                                token_text=token.text,
                                cumulative_tokens=seq,
                            )
                            # Push thought event
                            await event_queue.put(
                                (
                                    "thought",
                                    {
                                        "content": token.text,
                                        "seq": seq,
                                    },
                                )
                            )

                        if token.tool_call_chunks:
                            # Fix D: tool_call_chunks are streaming fragments.
                            # Only emit tool_start on the first chunk that carries the name.
                            tool_call_start_time = asyncio.get_event_loop().time()
                            for tool_call_chunk in token.tool_call_chunks:
                                tool_name = tool_call_chunk.get("name", "")
                                if not tool_name:
                                    # Subsequent chunks carry partial args only — skip
                                    continue
                                seq += 1
                                args = tool_call_chunk.get("args", {})

                                logger.info(
                                    f"🔧 [Agent] LLM 决定调用工具: {tool_name}，参数: {str(args)[:80]}，执行时间={tool_call_start_time - execution_start:.2f}s"
                                )
                                tools_logger.toolnode_execute_tool_start(
                                    tool_name=tool_name,
                                    args=args,
                                )

                                sse_logger.sse_event_tool_start(
                                    tool_name=tool_name,
                                    args=args,
                                )

                                # Push tool_start event
                                await event_queue.put(
                                    (
                                        "tool_start",
                                        {
                                            "tool_name": tool_name,
                                            "args": args,
                                        },
                                    )
                                )
                                if planner_runtime is not None and active_session_id:
                                    step = await _call_runtime_method(
                                        planner_runtime,
                                        "amark_next_step_running",
                                        "mark_next_step_running",
                                        active_session_id,
                                        tool_name=tool_name,
                                    )
                                    if step is not None:
                                        await emit_trace_event(
                                            event_queue,
                                            stage="planner",
                                            step="step_running",
                                            payload={
                                                "session_id": active_session_id,
                                                "step_id": step.id,
                                                "title": step.title,
                                                "tool_name": tool_name,
                                            },
                                        )

                elif mode == "updates":  # updates mode
                    for source, update in data.items():
                        seq += 1

                        # Log tool_result
                        if source == "tools":
                            # Fix C: guard against empty messages list
                            tool_messages = update.get("messages", [])
                            if tool_messages:
                                tool_message = tool_messages[-1]
                                if isinstance(tool_message, (ToolMessage, AIMessage)):
                                    tool_name = getattr(tool_message, "name", None) or "unknown"
                                    result_preview = str(tool_message.content)[:100]
                                    tool_elapsed = asyncio.get_event_loop().time() - execution_start
                                    logger.info(
                                        f"📦 [Agent] 工具执行完成，工具={tool_name}，结果长度={len(str(tool_message.content))} 字符，总耗时={tool_elapsed:.2f}s，预览: '{result_preview}...'"
                                    )
                                    tools_logger.toolnode_execute_tool_end(
                                        tool_name=tool_name,
                                        result_length=len(str(tool_message.content)),
                                        latency_ms=0,
                                        error=None,
                                    )

                                    sse_logger.sse_event_tool_result(
                                        tool_name=tool_name,
                                        result_length=len(str(tool_message.content)),
                                    )

                                    # Push tool_result event
                                    await event_queue.put(
                                        (
                                            "tool_result",
                                            {
                                                "tool_name": tool_name,
                                                "result": tool_message.content,
                                            },
                                        )
                                    )
                                    if planner_runtime is not None and active_session_id:
                                        try:
                                            step = await _call_runtime_method(
                                                planner_runtime,
                                                "amark_running_step_succeeded",
                                                "mark_running_step_succeeded",
                                                active_session_id,
                                            )
                                        except ValueError:
                                            step = None
                                        if step is not None:
                                            await emit_trace_event(
                                                event_queue,
                                                stage="planner",
                                                step="step_succeeded",
                                                payload={
                                                    "session_id": active_session_id,
                                                    "step_id": step.id,
                                                    "title": step.title,
                                                    "tool_name": tool_name,
                                                },
                                            )

                        # Log hil_interrupt
                        elif source == "__interrupt__":
                            interrupted = True
                            # Fix B: update is tuple[Interrupt], not a dict
                            # Interrupt.id is the stable identifier (LangGraph >= 0.6)
                            interrupts = update  # tuple[Interrupt, ...]
                            interrupt_payload = _extract_hil_interrupt_payload(interrupts)
                            interrupt_id = interrupt_payload["interrupt_id"]
                            await _persist_hil_interrupt(active_session_id, interrupt_payload)

                            logger.warning(
                                f"⏸️ [Agent] HIL 中断触发，等待用户确认，interrupt_id={interrupt_id}"
                            )
                            sse_logger.sse_event_hil_interrupt(
                                interrupt_id=interrupt_id,
                                tool_name=interrupt_payload["tool_name"],
                                tool_args=interrupt_payload["tool_args"],
                            )

                            # Push hil_interrupt event
                            await event_queue.put(
                                (
                                    "hil_interrupt",
                                    {
                                        "interrupt_id": interrupt_id,
                                        "tool_name": interrupt_payload["tool_name"],
                                        "tool_args": interrupt_payload["tool_args"],
                                        "risk_level": interrupt_payload["risk_level"],
                                        "message": interrupt_payload["message"],
                                        "allowed_decisions": interrupt_payload["allowed_decisions"],
                                        "action_requests": interrupt_payload["action_requests"],
                                        "grant_session_supported": interrupt_payload["grant_session_supported"],
                                    },
                                )
                            )

            # After astream loop completes — emit done unless interrupted
            # NOTE: LangGraph updates mode uses node names ("agent", "tools") as sources,
            # never "end". Done must be emitted here after the stream exhausts.
            total_elapsed = asyncio.get_event_loop().time() - execution_start
            logger.info(
                f"✅ [Agent] astream 循环结束，interrupted={interrupted}，最终回答长度={len(final_answer)} 字符，总耗时={total_elapsed:.2f}s"
            )
            if not interrupted:
                # Fetch final state messages to populate UI metadata panel
                state_messages: list[dict[str, Any]] = []
                try:
                    final_state = await agent.aget_state(config)
                    raw_msgs = final_state.values.get("messages", [])
                    for m in raw_msgs:
                        if isinstance(m, HumanMessage):
                            content = m.content if isinstance(m.content, str) else ""
                            state_messages.append({"role": "user", "content": content})
                        elif isinstance(m, AIMessage):
                            content = m.content if isinstance(m.content, str) else ""
                            state_messages.append({"role": "assistant", "content": content})
                        elif isinstance(m, ToolMessage):
                            state_messages.append({"role": "tool", "content": str(m.content)})
                except Exception as state_err:
                    logger.warning(f"Could not fetch final agent state: {state_err}")

                # Emit history slot update with actual token count so the UI reflects real usage
                if state_messages:
                    history_content = "\n".join(
                        m["content"] for m in state_messages if m.get("content")
                    )
                    history_tokens = count_tokens(history_content) if history_content else 0
                    await event_queue.put(
                        (
                            "slot_update",
                            {
                                "name": "history",
                                "display_name": "会话历史",
                                "tokens": history_tokens,
                                "enabled": True,
                            },
                        )
                    )

                if planner_runtime is not None and active_session_id:
                    completed_plan = await _call_runtime_method(
                        planner_runtime,
                        "amark_plan_completed",
                        "mark_plan_completed",
                        active_session_id,
                    )
                    if completed_plan is not None:
                        await emit_trace_event(
                            event_queue,
                            stage="planner",
                            step="plan_completed",
                            payload={
                                "plan_id": completed_plan.plan_id,
                                "step_count": len(completed_plan.steps),
                                "replan_count": completed_plan.replan_count,
                            },
                        )

                sse_logger.sse_event_done(
                    final_answer_length=len(final_answer),
                    total_tokens=seq,
                )

                await event_queue.put(
                    (
                        "done",
                        {
                            "answer": final_answer,
                            "total_tokens": seq,
                            "messages": state_messages,
                        },
                    )
                )
            return

        except Exception as e:
            error_elapsed = asyncio.get_event_loop().time() - execution_start
            logger.error(f"❌ [Agent] 执行过程中发生异常: {e}，耗时={error_elapsed:.2f}s")

            can_replan = (
                planner_runtime is not None
                and active_session_id is not None
                and attempt < (max_attempts - 1)
                and bool(
                    await _call_runtime_method(
                        planner_runtime,
                        "ashould_replan",
                        "should_replan",
                        active_session_id,
                        str(e),
                    )
                )
            )
            if can_replan and active_session_id is not None and planner_runtime is not None:
                await emit_trace_event(
                    event_queue,
                    stage="replanner",
                    step="triggered",
                    status="start",
                    payload={
                        "session_id": active_session_id,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )
                summary = await _call_runtime_method(
                    planner_runtime,
                    "aapply_replan",
                    "apply_replan",
                    active_session_id,
                    str(e),
                ) or {}
                await emit_trace_event(
                    event_queue,
                    stage="replanner",
                    step="plan_updated",
                    payload=summary,
                )
                final_answer = ""
                llm_call_start = None
                attempt += 1
                continue

            # Push terminal error event
            await event_queue.put(
                (
                    "error",
                    {"message": str(e)},
                )
            )
            return


@router.get("")
async def chat(
    message: str,
    session_id: str,
    user_id: str = "dev_user",
    skill_id: str | None = None,
    invocation_mode: str | None = None,
) -> StreamingResponse:
    """
    Chat endpoint with SSE streaming.

    P0: Streams trace_event, thought, slot_details, context_window, done events.

    Note: Uses GET method for SSE compatibility (EventSource only supports GET).
    Sensitive data should be avoided in query params for production.

    Args:
        message: User message
        session_id: Session identifier (maps to thread_id)
        user_id: User identifier (P0: no auth)

    Returns:
        StreamingResponse: SSE event stream
    """
    # Create loggers
    api_logger = ApiLogger(
        session_id=session_id,
        user_id=user_id,
    )

    tools_logger = ToolsLogger(
        session_id=session_id,
        user_id=user_id,
        thread_id=session_id,
    )

    sse_logger = SseLogger(
        session_id=session_id,
        user_id=user_id,
    )

    # Skill hint injection
    effective_message = _apply_skill_hint(message, skill_id, invocation_mode)
    if skill_id and effective_message != message:
        logger.info(f"💡 [Skill] Hint 注入: skill_id={skill_id}, mode={invocation_mode or settings.skill_invocation_mode}")

    # Log request received
    api_logger.api_request_received(
        endpoint="/chat",
        method="GET",
        message_length=len(effective_message),
    )

    return StreamingResponse(
        _run_agent_stream(
            message=effective_message,
            session_id=session_id,
            user_id=user_id,
            skill_id=skill_id,
            invocation_mode=invocation_mode,
            api_logger=api_logger,
            tools_logger=tools_logger,
            sse_logger=sse_logger,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/session-grants")
async def chat_session_grants(session_id: str) -> dict[str, Any]:
    """Return the currently granted tools for a session."""
    return {
        "session_id": session_id,
        "granted_tools": await get_session_granted_tools(session_id),
    }


@router.post("/session-grants/revoke")
async def revoke_chat_session_grant(request: SessionGrantRequest) -> dict[str, Any]:
    """Revoke a previously granted tool permission for the current session."""
    granted_tools = await revoke_session_tool_access(request.session_id, request.tool_name)
    return {
        "success": True,
        "session_id": request.session_id,
        "revoked_tool": request.tool_name,
        "granted_tools": granted_tools,
    }


@router.post("/resume")
async def chat_resume(request: ChatResumeRequest) -> StreamingResponse:
    """
    Resume interrupted chat (HIL).

    P1: Handles user's decision to approve or reject interrupted tool execution.

    Args:
        request: Resume request with interrupt_id and approval decision

    Returns:
        StreamingResponse: SSE event stream of resumed execution
    """
    logger.info(
        f"Resume request: interrupt={request.interrupt_id}, approved={request.approved}"
    )

    # Keep runtime lookup local so tests and alternate store implementations can patch
    # app.observability.interrupt_store.get_interrupt_store directly.
    from app.observability.interrupt_store import get_interrupt_store as get_interrupt_store_for_resume

    # Get interrupt store
    interrupt_store = await get_interrupt_store_for_resume()

    # Get interrupt data
    interrupt_data = await interrupt_store.get_interrupt(request.interrupt_id)

    if interrupt_data is None:
        # Interrupt not found or expired
        async def error_stream() -> AsyncIterator[str]:
            yield await _format_sse_event(
                "error",
                {"message": f"中断 {request.interrupt_id} 不存在或已过期"},
            )

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Check if already processed
    if interrupt_data.get("status") != "pending":
        async def already_processed_stream() -> AsyncIterator[str]:
            yield await _format_sse_event(
                "error",
                {"message": f"中断已被处理: {interrupt_data.get('status')}"},
            )

        return StreamingResponse(
            already_processed_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    event_queue = SSEEventQueue()
    config = {"configurable": {"thread_id": request.session_id}}
    tool_name = interrupt_data.get("tool_name", "")
    tool_args = interrupt_data.get("tool_args", {})
    result = await _resolve_hil_resume_decision(
        interrupt_id=request.interrupt_id,
        approved=request.approved,
        tool_name=tool_name,
        tool_args=tool_args,
        event_queue=event_queue,
    )

    agent = None
    if request.approved and request.grant_session:
        grantable_tool_name = _get_grantable_tool_name(interrupt_data)
        if grantable_tool_name:
            agent = await create_react_agent(sse_queue=event_queue, config=config)
            result["granted_tools"] = await grant_session_tool_access(
                request.session_id,
                grantable_tool_name,
            )
        else:
            logger.warning(
                f"Skip session grant for interrupt {request.interrupt_id}: multiple tool names"
            )

    await interrupt_store.update_interrupt_status(request.interrupt_id, "processing")

    # Native resume path: recover from checkpoint and continue agent execution
    async def resume_stream() -> AsyncIterator[str]:
        terminal_status = "confirmed" if request.approved else "rejected"
        terminal_marked = False
        saw_error = False

        # Always emit resolution event first
        yield await _format_sse_event("hil_resolved", result)
        while not event_queue.empty():
            event_type, event_data = event_queue.get_nowait()
            yield await _format_sse_event(event_type, event_data)

        # Keep write-side-effect dedupe guard for send_email resume replay.
        idempotency_key: str | None = None
        if request.approved and tool_name == "send_email":
            already_executed, idempotency_key = _check_and_mark_resume_idempotency(
                request.session_id,
                tool_name,
                tool_args,
            )
            if already_executed:
                logger.warning(
                    "Skip duplicated resume side-effect execution: "
                    f"session={request.session_id}, key={idempotency_key}"
                )
                yield await _format_sse_event(
                    "tool_result",
                    {
                        "tool_name": tool_name,
                        "result": json.dumps(
                            {
                                "success": True,
                                "skipped": True,
                                "reason": "idempotent_replay",
                                "idempotency_key": idempotency_key,
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
                yield await _format_sse_event(
                    "done",
                    {
                        "answer": f"{tool_name} 操作已完成（去重跳过）",
                        "finish_reason": "approved",
                    },
                )
                await interrupt_store.update_interrupt_status(
                    request.interrupt_id,
                    terminal_status,
                )
                return

        # Build native LangGraph resume command.
        resume_command = _build_hil_resume_command(
            interrupt_id=request.interrupt_id,
            approved=request.approved,
            tool_name=tool_name,
            decision_count=len(interrupt_data.get("action_requests", []) or []),
        )

        tools_logger = ToolsLogger(
            session_id=request.session_id,
            user_id=request.user_id,
            thread_id=request.session_id,
        )
        sse_logger = SseLogger(session_id=request.session_id, user_id=request.user_id)
        runtime_agent = agent or await create_react_agent(sse_queue=event_queue, config=config)

        agent_task = asyncio.create_task(
            _execute_agent(
                agent=runtime_agent,
                message=f"[HIL_RESUME] {tool_name}",
                config=config,
                event_queue=event_queue,
                user_id=request.user_id,
                tools_logger=tools_logger,
                sse_logger=sse_logger,
                agent_input=resume_command,
            )
        )

        try:
            while True:
                event_type, event_data = await event_queue.get()

                # If resume execution failed after optimistic mark, rollback idempotency.
                if event_type == "error" and idempotency_key:
                    _RESUME_IDEMPOTENCY_STORE.discard(idempotency_key)
                if event_type == "error":
                    saw_error = True
                    await interrupt_store.update_interrupt_status(request.interrupt_id, "pending")
                elif event_type in ("done", "hil_interrupt") and not terminal_marked:
                    await interrupt_store.update_interrupt_status(
                        request.interrupt_id,
                        terminal_status,
                    )
                    terminal_marked = True

                yield await _format_sse_event(event_type, event_data)

                if event_type in ("done", "error"):
                    break
            if (
                not saw_error
                and not terminal_marked
                and agent_task.done()
                and not agent_task.cancelled()
            ):
                await interrupt_store.update_interrupt_status(request.interrupt_id, terminal_status)
        finally:
            if not agent_task.done():
                agent_task.cancel()

    return StreamingResponse(
        resume_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
