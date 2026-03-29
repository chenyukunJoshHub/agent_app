"""
Trace Middleware for SSE streaming of agent execution.

P0: Implements after_model hook to push thought events via SSE.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from loguru import logger

from app.agent.context import AgentContext
from app.observability.trace_events import emit_trace_event
from app.prompt.budget import DEFAULT_BUDGET


class TraceMiddleware(AgentMiddleware):
    """
    Middleware for observability and SSE streaming.

    P0: Pushes events to SSE queue after_model hook.
    """

    _EMAIL_ARG_KEYS = {"to", "cc", "bcc", "from", "email", "recipient"}
    _SENSITIVE_ARG_KEYS = {
        "body",
        "content",
        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "access_token",
        "refresh_token",
        "cookie",
    }

    def __init__(self) -> None:
        """Initialize TraceMiddleware."""
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

    @staticmethod
    def _iter_current_turn_tool_messages(messages: list[Any]) -> list[ToolMessage]:
        """Return ToolMessage objects for the latest turn only.

        State messages can contain the full session history. For trace fidelity, tool
        result events should map to the current turn (messages after the last user input).
        """
        last_human_index: int | None = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_index = i
                break

        start_index = last_human_index if last_human_index is not None else 0
        current_turn = messages[start_index:]

        seen_tool_call_ids: set[str] = set()
        tool_messages: list[ToolMessage] = []
        for msg in current_turn:
            if not isinstance(msg, ToolMessage):
                continue
            tool_call_id = str(getattr(msg, "tool_call_id", "") or "")
            if tool_call_id and tool_call_id in seen_tool_call_ids:
                continue
            if tool_call_id:
                seen_tool_call_ids.add(tool_call_id)
            tool_messages.append(msg)
        return tool_messages

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

    @staticmethod
    def _mask_email(value: str) -> str:
        if "@" not in value:
            return "***"
        local, _, domain = value.partition("@")
        if not local:
            return f"***@{domain}"
        return f"{local[0]}***@{domain}"

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        lowered = key.lower()
        if lowered in cls._SENSITIVE_ARG_KEYS:
            return True
        return lowered.endswith(("_token", "_secret", "_key"))

    @classmethod
    def _sanitize_tool_args(cls, payload: Any, parent_key: str | None = None) -> Any:
        key = (parent_key or "").lower()

        if isinstance(payload, dict):
            return {
                k: cls._sanitize_tool_args(v, parent_key=k)
                for k, v in payload.items()
            }

        if isinstance(payload, list):
            return [cls._sanitize_tool_args(item, parent_key=parent_key) for item in payload]

        if key in cls._EMAIL_ARG_KEYS and isinstance(payload, str):
            return cls._mask_email(payload)

        if cls._is_sensitive_key(key):
            return "[REDACTED]"

        return payload

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
            dict | None: State updates for token usage accumulation
        """
        sse_queue = self._get_sse_queue(runtime)
        logger.info(f"🧠 [Middleware] aafter_model — LLM 响应完成，分析输出内容...")
        state_patch: dict[str, Any] = {}

        # Extract latest AI message for thought content
        messages = state.get("messages", [])
        if messages:
            latest_message = messages[-1]

            if isinstance(latest_message, AIMessage):
                has_tool_calls = bool(getattr(latest_message, "tool_calls", None))
                content_len = len(str(latest_message.content or ""))
                tool_count = len(latest_message.tool_calls) if has_tool_calls else 0
                content_preview = str(latest_message.content or "")[:200]
                await emit_trace_event(
                    sse_queue,
                    stage="react",
                    step="model_call_end",
                    payload={
                        "messages": len(state.get("messages", [])),
                        "tool_count": tool_count,
                        "content_preview": content_preview,
                    },
                )
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
                        payload={
                            "chars": len(str(latest_message.content)),
                            "content_preview": content_preview,
                            "tool_count": tool_count,
                        },
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
                                "args": self._sanitize_tool_args(tc.get("args", {})),
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

                    # Return a state patch instead of mutating input state in-place.
                    state_patch["_token_usage"] = current_usage

                    # Token budget from global prompt configuration.
                    budget = DEFAULT_BUDGET.WORKING_BUDGET
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
            else:
                await emit_trace_event(
                    sse_queue,
                    stage="react",
                    step="model_call_end",
                    payload={"messages": len(state.get("messages", []))},
                )
        else:
            await emit_trace_event(
                sse_queue,
                stage="react",
                step="model_call_end",
                payload={"messages": 0},
            )

        return state_patch or None

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """Hook called at the end of agent turn."""
        sse_queue = self._get_sse_queue(runtime)
        msg_count = len(state.get("messages", []))
        logger.info(f"⏹️ [Middleware] aafter_agent — Agent 轮次结束，最终消息历史={msg_count} 条")

        # Extract tool results for current turn only and emit stage="tools" result events
        messages = state.get("messages", [])
        for msg in self._iter_current_turn_tool_messages(messages):
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

                # Emit answer block before turn_summary
                answer_text = str(last_message.content or "")
                answer_preview = answer_text[:200]
                await emit_trace_event(
                    sse_queue,
                    stage="react",
                    step="answer_emitted",
                    payload={"chars": len(answer_text), "content_preview": answer_preview},
                )
                finish_reason = getattr(last_message, "response_metadata", {}).get(
                    "finish_reason", "stop"
                )

                await self._send_sse_event(
                    sse_queue,
                    "done",
                    {
                        "answer": last_message.content,
                        "finish_reason": finish_reason,
                        "messages": serialized_messages,
                    },
                )
                await emit_trace_event(
                    sse_queue,
                    stage="react",
                    step="turn_done",
                    payload={
                        "answer_chars": len(str(last_message.content)),
                        "finish_reason": finish_reason,
                    },
                )

        return None


__all__ = ["TraceMiddleware"]
