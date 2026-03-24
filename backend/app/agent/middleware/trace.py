"""
Trace Middleware for SSE streaming of agent execution.

P0: Implements after_model hook to push thought events via SSE.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from loguru import logger

from app.observability.trace_events import emit_trace_event


class TraceMiddleware(AgentMiddleware):
    """
    Middleware for observability and SSE streaming.

    P0: Pushes events to SSE queue after_model hook.
    """

    def __init__(self, sse_queue: Any | None = None) -> None:
        """
        Initialize TraceMiddleware.

        Args:
            sse_queue: Queue for SSE events (will be injected at runtime)
        """
        self.sse_queue = sse_queue
        logger.info("TraceMiddleware initialized")

    async def _send_sse_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Send an event to the SSE queue.

        Args:
            event_type: Event type (thought, tool_start, tool_result, done, error)
            data: Event payload
        """
        if self.sse_queue is not None:
            try:
                # Queue format: (event_type, data_dict)
                await self.sse_queue.put((event_type, data))
                logger.debug(f"SSE event sent: {event_type}")
            except Exception as e:
                logger.error(f"Failed to send SSE event: {e}")
        else:
            logger.debug(f"No SSE queue, skipping event: {event_type}")

    async def abefore_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the start of agent turn.

        P0: Sends initial state event.
        """
        logger.debug("TraceMiddleware: abefore_agent called")
        await self._send_sse_event("agent_start", {"session_id": state.get("session_id")})
        await emit_trace_event(
            self.sse_queue,
            stage="react",
            step="turn_start",
            payload={"messages": len(state.get("messages", []))},
        )
        return None

    def wrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (sync version).

        P0: Pass-through only.
        """
        logger.debug("TraceMiddleware: wrap_model_call called")
        if self.sse_queue is not None:
            try:
                import asyncio

                asyncio.create_task(
                    emit_trace_event(
                        self.sse_queue,
                        stage="react",
                        step="model_call_start",
                        status="start",
                        payload={"messages": len(getattr(request, "messages", []) or [])},
                    )
                )
            except RuntimeError:
                pass
        return handler(request)

    async def awrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (async version).

        P0: Pass-through only.
        """
        logger.debug("TraceMiddleware: awrap_model_call called")
        await emit_trace_event(
            self.sse_queue,
            stage="react",
            step="model_call_start",
            status="start",
            payload={"messages": len(getattr(request, "messages", []) or [])},
        )
        result = handler(request)
        # Handle both coroutines and direct results
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
        logger.debug("TraceMiddleware: aafter_model called")
        await emit_trace_event(
            self.sse_queue,
            stage="react",
            step="model_call_end",
            payload={"messages": len(state.get("messages", []))},
        )

        # Extract latest AI message for thought content
        messages = state.get("messages", [])
        if messages:
            latest_message = messages[-1]

            if isinstance(latest_message, AIMessage):
                # Stream reasoning if present
                if hasattr(latest_message, "reasoning") and latest_message.reasoning:
                    await self._send_sse_event(
                        "thought",
                        {"content": latest_message.reasoning},
                    )

                # Stream content as thought
                if latest_message.content:
                    await self._send_sse_event(
                        "thought",
                        {"content": latest_message.content},
                    )
                    await emit_trace_event(
                        self.sse_queue,
                        stage="react",
                        step="thought_emitted",
                        payload={"chars": len(str(latest_message.content))},
                    )

                # Emit stage="tools" events for planned tool calls
                if hasattr(latest_message, "tool_calls") and latest_message.tool_calls:
                    for tc in latest_message.tool_calls:
                        await emit_trace_event(
                            self.sse_queue,
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

                    # Get current accumulated usage from state
                    current_usage = state.get("_token_usage", 0)
                    current_usage += total_tokens

                    # Update state with new total
                    state["_token_usage"] = current_usage

                    # Token budget (32K working budget)
                    budget = 32000
                    remaining = budget - current_usage

                    await self._send_sse_event(
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
                        self.sse_queue,
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
        """
        Hook called at the end of agent turn.

        P0: Sends completion event.
        """
        logger.debug("TraceMiddleware: aafter_agent called")

        # Extract tool results and emit stage="tools" result events
        messages = state.get("messages", [])
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content_str = str(msg.content)
                await emit_trace_event(
                    self.sse_queue,
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
                    self.sse_queue,
                    stage="react",
                    step="turn_done",
                    payload={"answer_chars": len(str(last_message.content))},
                )

        return None


__all__ = ["TraceMiddleware"]
