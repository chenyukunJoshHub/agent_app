"""
Trace Middleware for SSE streaming of agent execution.

P0: Implements after_model hook to push thought events via SSE.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from loguru import logger


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
        return None

    def wrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (sync version).

        P0: Pass-through only.
        """
        logger.debug("TraceMiddleware: wrap_model_call called")
        return handler(request)

    async def awrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (async version).

        P0: Pass-through only.
        """
        logger.debug("TraceMiddleware: awrap_model_call called")
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

        return None

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the end of agent turn.

        P0: Sends completion event.
        """
        logger.debug("TraceMiddleware: aafter_agent called")

        # Extract final answer
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                await self._send_sse_event(
                    "done",
                    {
                        "answer": last_message.content,
                        "finish_reason": getattr(last_message, "response_metadata", {}).get(
                            "finish_reason", "unknown"
                        ),
                    },
                )

        return None


__all__ = ["TraceMiddleware"]
