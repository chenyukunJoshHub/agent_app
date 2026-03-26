"""
Trace Middleware for SSE streaming of agent execution.

P0: Implements after_model hook to push thought events via SSE.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from app.agent.context import AgentContext
from app.observability.trace_block import TraceBlockBuilder, emit_trace_block
from app.observability.trace_events import build_trace_event, emit_trace_event


class TraceMiddleware(AgentMiddleware):
    """
    Middleware for observability and SSE streaming.

    P0: Pushes events to SSE queue after_model hook.
    """

    def __init__(self) -> None:
        """Initialize TraceMiddleware.

        SSE queue is injected per-request via runtime.context (AgentContext).
        """
        self._block_builder = TraceBlockBuilder()
        logger.info("✅ [TraceMiddleware] 初始化完成，负责 SSE 流式推送和 Token 追踪")

    @staticmethod
    def _get_sse_queue(runtime_or_request: Any) -> Any:
        """Extract sse_queue from runtime.context or request.runtime.context."""
        # abefore_agent / aafter_agent pass `runtime` directly
        ctx: AgentContext | None = getattr(runtime_or_request, "context", None)
        if ctx is None:
            # wrap_model_call passes `request`; runtime is request.runtime
            rt = getattr(runtime_or_request, "runtime", None)
            ctx = getattr(rt, "context", None)
        return ctx.sse_queue if ctx else None

    async def _send_sse_event(self, sse_queue: Any, event_type: str, data: dict[str, Any]) -> None:
        """Send an event to the SSE queue."""
        if sse_queue is not None:
            try:
                await sse_queue.put((event_type, data))
                logger.debug(f"SSE event sent: {event_type}")
            except Exception as e:
                logger.error(f"Failed to send SSE event: {e}")
        else:
            logger.debug(f"No SSE queue, skipping event: {event_type}")

    async def _feed_block_builder(
        self,
        sse_queue: Any,
        *,
        stage: str,
        step: str,
        status: str = "ok",
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Feed a trace event to the block builder and emit any resulting blocks."""
        event_dict = build_trace_event(stage=stage, step=step, status=status, payload=payload)
        blocks = self._block_builder.on_trace_event(event_dict)
        for block in blocks:
            await emit_trace_block(sse_queue, block)

    async def abefore_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """Hook called at the start of agent turn."""
        sse_queue = self._get_sse_queue(runtime)
        msg_count = len(state.get("messages", []))
        logger.info(f"▶️ [Middleware] abefore_agent — 开始新一轮 Agent 推理，当前消息历史={msg_count} 条")
        await self._send_sse_event(sse_queue, "agent_start", {"session_id": state.get("session_id")})
        await emit_trace_event(
            sse_queue,
            stage="react",
            step="turn_start",
            payload={"messages": msg_count},
        )
        await self._feed_block_builder(
            sse_queue,
            stage="react",
            step="turn_start",
            payload={"messages": msg_count},
        )
        return None

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        """Hook called before each LLM invocation (sync version)."""
        logger.debug("TraceMiddleware: wrap_model_call called")
        sse_queue = self._get_sse_queue(request)
        if sse_queue is not None:
            try:
                import asyncio

                msg_count = len(getattr(request, "messages", []) or [])

                async def _emit_and_feed() -> None:
                    await emit_trace_event(
                        sse_queue, stage="react", step="model_call_start", status="start",
                        payload={"messages": msg_count},
                    )
                    await self._feed_block_builder(
                        sse_queue, stage="react", step="model_call_start", status="start",
                        payload={"messages": msg_count},
                    )

                asyncio.create_task(_emit_and_feed())
            except RuntimeError:
                pass
        return handler(request)

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        """Hook called before each LLM invocation (async version)."""
        sse_queue = self._get_sse_queue(request)
        msg_count = len(getattr(request, "messages", []) or [])
        logger.info(f"📨 [Middleware] awrap_model_call — 即将调用 LLM，输入消息数={msg_count} 条")
        await emit_trace_event(
            sse_queue, stage="react", step="model_call_start", status="start",
            payload={"messages": msg_count},
        )
        await self._feed_block_builder(
            sse_queue, stage="react", step="model_call_start", status="start",
            payload={"messages": msg_count},
        )
        result = handler(request)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def aafter_model(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called after each LLM invocation.

        P0: Extracts and streams reasoning/thought content + token usage.

        Args:
            state: Current agent state (contains messages)
            runtime: Agent runtime information

        Returns:
            dict | None: State updates (None for trace middleware)
        """
        sse_queue = self._get_sse_queue(runtime)
        logger.info(f"🧠 [Middleware] aafter_model — LLM 响应完成，分析输出内容...")
        await emit_trace_event(
            sse_queue,
            stage="react",
            step="model_call_end",
            payload={"messages": len(state.get("messages", []))},
        )
        await self._feed_block_builder(
            sse_queue,
            stage="react",
            step="model_call_end",
            payload={"messages": len(state.get("messages", []))},
        )

        # Extract latest AI message for thought content
        messages = state.get("messages", [])
        if messages:
            latest_message = messages[-1]

            if isinstance(latest_message, AIMessage):
                has_tool_calls = bool(getattr(latest_message, "tool_calls", None))
                content_len = len(str(latest_message.content or ""))
                if has_tool_calls:
                    tool_names = [tc.get("name", "?") for tc in latest_message.tool_calls]
                    logger.info(f"🔀 [Middleware] LLM 决定调用工具: {tool_names}（内容长度={content_len}）")
                else:
                    logger.info(f"💡 [Middleware] LLM 生成了直接回答，内容长度={content_len} 字符")

                # Stream reasoning if present
                if hasattr(latest_message, "reasoning") and latest_message.reasoning:
                    await self._send_sse_event(
                        sse_queue,
                        "thought",
                        {"content": latest_message.reasoning},
                    )

                # Note: thought events are streamed token-by-token via _execute_agent
                # (stream_mode="messages"). We only emit a trace event here for observability,
                # NOT a thought SSE event, to avoid duplicating the already-streamed content.
                if latest_message.content:
                    await emit_trace_event(
                        sse_queue,
                        stage="react",
                        step="thought_emitted",
                        payload={"chars": len(str(latest_message.content))},
                    )
                    await self._feed_block_builder(
                        sse_queue,
                        stage="react",
                        step="thought_emitted",
                        payload={"chars": len(str(latest_message.content))},
                    )

                # Emit stage="tools" events for planned tool calls
                if hasattr(latest_message, "tool_calls") and latest_message.tool_calls:
                    for tc in latest_message.tool_calls:
                        await emit_trace_event(
                            sse_queue,
                            stage="tools",
                            step="tool_call_planned",
                            status="start",
                            payload={
                                "tool_name": tc.get("name", ""),
                                "tool_call_id": tc.get("id", ""),
                                "args": tc.get("args", {}),
                            },
                        )
                        await self._feed_block_builder(
                            sse_queue,
                            stage="tools",
                            step="tool_call_planned",
                            status="start",
                            payload={
                                "tool_name": tc.get("name", ""),
                                "tool_call_id": tc.get("id", ""),
                                "args": tc.get("args", {}),
                            },
                        )

                # Send token_update event
                response_metadata = getattr(latest_message, "response_metadata", {})
                token_usage = response_metadata.get("token_usage", {})

                if token_usage:
                    # Extract token counts
                    input_tokens = token_usage.get("prompt_tokens", 0)
                    output_tokens = token_usage.get("completion_tokens", 0)
                    total_tokens = token_usage.get("total_tokens", input_tokens + output_tokens)
                    logger.info(f"📊 [Middleware] Token 用量 — 输入={input_tokens}，输出={output_tokens}，合计={total_tokens}")

                    # Get current accumulated usage from state
                    current_usage = state.get("_token_usage", 0)
                    current_usage += total_tokens

                    # Update state with new total
                    state["_token_usage"] = current_usage

                    # Token budget (32K working budget)
                    budget = 32000
                    remaining = budget - current_usage

                    await self._send_sse_event(
                        sse_queue,
                        "token_update",
                        {
                            "current": current_usage,
                            "budget": budget,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "remaining": remaining,
                        },
                    )
                    await emit_trace_event(
                        sse_queue,
                        stage="context",
                        step="token_update",
                        payload={
                            "current": current_usage,
                            "budget": budget,
                            "remaining": remaining,
                        },
                    )
                    await self._feed_block_builder(
                        sse_queue,
                        stage="context",
                        step="token_update",
                        payload={
                            "current": current_usage,
                            "budget": budget,
                            "remaining": remaining,
                        },
                    )

        return None

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """Hook called at the end of agent turn."""
        sse_queue = self._get_sse_queue(runtime)
        msg_count = len(state.get("messages", []))
        logger.info(f"⏹️ [Middleware] aafter_agent — Agent 轮次结束，最终消息历史={msg_count} 条")

        # Extract tool results and emit stage="tools" result events
        messages = state.get("messages", [])
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content_str = str(msg.content)
                await emit_trace_event(
                    sse_queue,
                    stage="tools",
                    step="tool_call_result",
                    status="ok",
                    payload={
                        "tool_call_id": getattr(msg, "tool_call_id", ""),
                        "content_preview": content_str[:200],
                        "content_length": len(content_str),
                    },
                )
                await self._feed_block_builder(
                    sse_queue,
                    stage="tools",
                    step="tool_call_result",
                    status="ok",
                    payload={
                        "tool_call_id": getattr(msg, "tool_call_id", ""),
                        "content_preview": content_str[:200],
                        "content_length": len(content_str),
                    },
                )

        # Extract final answer
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                # 序列化完整 messages 列表供前端同步
                def _serialize_message(msg: Any) -> dict:
                    role_map = {
                        "HumanMessage": "user",
                        "AIMessage": "assistant",
                        "ToolMessage": "tool",
                        "SystemMessage": "system",
                    }
                    role = role_map.get(type(msg).__name__, "assistant")
                    serialized: dict = {"role": role, "content": str(msg.content or "")}
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        serialized["tool_calls"] = [
                            {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": tc.get("name", ""),
                                    "arguments": str(tc.get("args", {})),
                                },
                            }
                            for tc in msg.tool_calls
                        ]
                    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                        serialized["tool_call_id"] = msg.tool_call_id
                    return serialized

                _all_messages = [_serialize_message(m) for m in messages]
                # 仅保留前端 StateMessage 支持的 role（user/assistant/tool），过滤掉 system
                serialized_messages = [m for m in _all_messages if m["role"] in ("user", "assistant", "tool")]

                await self._send_sse_event(
                    sse_queue,
                    "done",
                    {
                        "answer": last_message.content,
                        "finish_reason": getattr(last_message, "response_metadata", {}).get(
                            "finish_reason", "unknown"
                        ),
                        "messages": serialized_messages,
                    },
                )
                await emit_trace_event(
                    sse_queue,
                    stage="react",
                    step="turn_done",
                    payload={"answer_chars": len(str(last_message.content))},
                )
                await self._feed_block_builder(
                    sse_queue,
                    stage="react",
                    step="turn_done",
                    payload={"answer_chars": len(str(last_message.content))},
                )

        return None


__all__ = ["TraceMiddleware"]
