"""
Chat API with SSE streaming support.

P0: POST /chat endpoint with Server-Sent Events streaming.
"""
import asyncio
import json
import traceback
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.agent.context import AgentContext
from app.agent.langchain_engine import create_react_agent
from app.observability.trace_events import build_trace_event, emit_trace_event
from app.utils.token import count_tokens

from app.config import settings
from app.logger import ApiLogger, ToolsLogger, SseLogger
from app.skills.manager import SkillManager


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
    logger.info(f"📥 [API] 收到用户消息，会话ID={session_id}，用户={user_id}，消息长度={len(message)} 字符")
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
        _execute_agent(agent, message, config, event_queue, user_id, tools_logger, sse_logger)
    )

    # Stream events
    logger.info("📡 [SSE] 开始推送 SSE 事件流给前端...")
    _thought_logged = False
    try:
        while True:
            event_type, data = await event_queue.get()

            if event_type == "thought":
                if not _thought_logged:
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
                logger.info("🏁 [SSE] 收到 done 事件，流式响应结束")
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
        logger.error(f"❌ [SSE] SSE 流发生异常: {e}")
        yield await _format_sse_event("error", {"message": str(e)})
        api_logger.api_request_error(
            session_id=session_id,
            error_type="sse_exception",
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
    finally:
        # Fix E: cancel background task if SSE exits before agent finishes
        if not agent_task.done():
            agent_task.cancel()


async def _execute_agent(
    agent: Any,
    message: str,
    config: dict[str, Any],
    event_queue: SSEEventQueue,
    user_id: str,
    tools_logger: "ToolsLogger",
    sse_logger: "SseLogger",
) -> None:
    """
    Execute agent and push events to queue.

    Args:
        agent: Agent executor
        message: User message
        config: LangGraph config with thread_id
        event_queue: SSEEventQueue
        tools_logger: ToolsLogger for tools logging
        sse_logger: SseLogger for SSE event logging
    """
    # Prepare input
    logger.info(f"🤔 [Agent] _execute_agent 开始执行，用户消息: '{message[:50]}{'...' if len(message) > 50 else ''}'")
    messages_input = [HumanMessage(content=message)]

    seq = 0  # Event sequence counter
    final_answer = ""  # Accumulate streaming text for done payload
    interrupted = False  # Track if HIL interrupt occurred

    try:
        logger.info("🔄 [Agent] _execute_agent - agent.astream 循环，等待 LLM 响应...")
        async for chunk in agent.astream(
            {"messages": messages_input},
            config=config,
            context=AgentContext(sse_queue=event_queue, user_id=user_id),
            stream_mode=["messages", "updates"],
        ):
            mode = chunk[0]
            data = chunk[1]
            if mode == "messages":  # messages mode
                # Process AIMessageChunk
                token, metadata = data

                if isinstance(token, AIMessageChunk):
                    if token.text:
                        seq += 1
                        final_answer += token.text
                         # debug 级别避免刷屏
                        # Log thought event
                        sse_logger.sse_event_thought(
                            token_text=token.text,
                            cumulative_tokens=seq,
                        )
                        # Push thought event
                        await event_queue.put((
                            "thought",
                            {
                                "content": token.text,
                                "seq": seq,
                            },
                        ))

                    if token.tool_call_chunks:
                        # Fix D: tool_call_chunks are streaming fragments.
                        # Only emit tool_start on the first chunk that carries the name.
                        for tool_call_chunk in token.tool_call_chunks:
                            tool_name = tool_call_chunk.get("name", "")
                            if not tool_name:
                                # Subsequent chunks carry partial args only — skip
                                continue
                            seq += 1
                            args = tool_call_chunk.get("args", {})

                            logger.info(f"🔧 [Agent] LLM 决定调用工具: {tool_name}，参数: {str(args)[:80]}")
                            tools_logger.toolnode_execute_tool_start(
                                tool_name=tool_name,
                                args=args,
                            )

                            sse_logger.sse_event_tool_start(
                                tool_name=tool_name,
                                args=args,
                            )

                            # Push tool_start event
                            await event_queue.put((
                                "tool_start",
                                {
                                    "tool_name": tool_name,
                                    "args": args,
                                },
                            ))

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
                                logger.info(f"📦 [Agent] 工具执行完成，结果长度={len(str(tool_message.content))} 字符，预览: '{result_preview}...'")
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
                                await event_queue.put((
                                    "tool_result",
                                    {
                                        "tool_name": tool_name,
                                        "result": tool_message.content,
                                    },
                                ))

                    # Log hil_interrupt
                    elif source == "__interrupt__":
                        interrupted = True
                        # Fix B: update is tuple[Interrupt], not a dict
                        # Interrupt.id is the stable identifier (LangGraph >= 0.6)
                        interrupts = update  # tuple[Interrupt, ...]
                        interrupt_id = interrupts[0].id if interrupts else "unknown"

                        logger.warning(f"⏸️ [Agent] HIL 中断触发，等待用户确认，interrupt_id={interrupt_id}")
                        sse_logger.sse_event_hil_interrupt(
                            interrupt_id=interrupt_id,
                            tool_name="unknown",
                            tool_args={},
                        )

                        # Push hil_interrupt event
                        await event_queue.put((
                            "hil_interrupt",
                            {
                                "interrupt_id": interrupt_id,
                                "tool_name": "unknown",
                                "tool_args": {},
                            },
                        ))

        # After astream loop completes — emit done unless interrupted
        # NOTE: LangGraph updates mode uses node names ("agent", "tools") as sources,
        # never "end". Done must be emitted here after the stream exhausts.
        logger.info(f"✅ [Agent] astream 循环结束，interrupted={interrupted}，最终回答长度={len(final_answer)} 字符")
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
                await event_queue.put((
                    "slot_update",
                    {
                        "name": "history",
                        "display_name": "会话历史",
                        "tokens": history_tokens,
                        "enabled": True,
                    },
                ))

            sse_logger.sse_event_done(
                final_answer_length=len(final_answer),
                total_tokens=seq,
            )

            await event_queue.put((
                "done",
                {
                    "answer": final_answer,
                    "total_tokens": seq,
                    "messages": state_messages,
                },
            ))

    except Exception as e:
        logger.error(f"❌ [Agent] 执行过程中发生异常: {e}")
        # Push error event
        await event_queue.put((
            "error",
            {"message": str(e)},
        ))


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

    # Import here to avoid circular dependency
    from app.agent.middleware.hil import HILMiddleware
    from app.observability.interrupt_store import get_interrupt_store

    # Get interrupt store
    interrupt_store = await get_interrupt_store()

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

    # Create HIL middleware instance to handle resume
    event_queue = SSEEventQueue()
    hil_middleware = HILMiddleware(
        interrupt_store=interrupt_store,
        interrupt_on={interrupt_data.get("tool_name", ""): True},
    )

    # Handle resume decision (sse_queue passed explicitly, not via constructor)
    result = await hil_middleware.handle_resume_decision(
        request.interrupt_id, request.approved, sse_queue=event_queue
    )

    # If rejected, send done event immediately
    if not request.approved:
        async def rejected_stream() -> AsyncIterator[str]:
            yield await _format_sse_event("hil_resolved", result)
            while not event_queue.empty():
                event_type, event_data = event_queue.get_nowait()
                yield await _format_sse_event(event_type, event_data)
            yield await _format_sse_event(
                "done",
                {
                    "answer": result.get("message", "操作已取消"),
                    "finish_reason": "rejected",
                },
            )

        return StreamingResponse(
            rejected_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # If approved, continue agent execution
    # For P1, we'll send a success message and indicate tool was approved
    # In a full implementation, this would resume actual agent execution
    async def approved_stream() -> AsyncIterator[str]:
        # Send approval confirmation
        yield await _format_sse_event("hil_resolved", result)
        while not event_queue.empty():
            event_type, event_data = event_queue.get_nowait()
            yield await _format_sse_event(event_type, event_data)

        # Indicate that tool execution would continue here
        # For P1, we simulate completion
        tool_name = interrupt_data.get("tool_name", "")
        tool_args = interrupt_data.get("tool_args", {})

        # Simulate tool execution result
        if tool_name == "send_email":
            # Import and execute actual tool
            from app.tools.send_email import send_email

            tool_result = send_email.invoke(tool_args)
            yield await _format_sse_event(
                "tool_result",
                {"tool_name": tool_name, "result": tool_result},
            )

        # Send completion
        yield await _format_sse_event(
            "done",
            {
                "answer": f"{tool_name} 操作已完成",
                "finish_reason": "approved",
            },
        )

    return StreamingResponse(
        approved_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
