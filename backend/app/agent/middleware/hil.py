"""
Human-in-the-Loop (HIL) Middleware for manual intervention.

Allows users to confirm or reject irreversible operations like sending emails.
Integrates with LangGraph's interrupt mechanism and persists interrupt states.
"""
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from loguru import logger

from app.observability.interrupt_store import InterruptStore
from app.observability.trace_events import emit_trace_event


class HILMiddleware(AgentMiddleware):
    """
    Middleware for Human-in-the-Loop (HIL) manual intervention.

    Intercepts tool calls that require user confirmation before execution.
    Currently supports: send_email (extensible to other irreversible operations).

    Architecture:
    1. Detect tool calls matching interrupt_on in abefore_agent
    2. Save interrupt state to InterruptStore
    3. Push hil_interrupt SSE event to frontend
    4. Wait for user decision via /chat/resume endpoint
    5. Resume or abort execution based on user decision
    """

    def __init__(
        self,
        interrupt_store: InterruptStore,
        sse_queue: Any | None = None,
        interrupt_on: dict[str, bool] | None = None,
    ) -> None:
        """
        Initialize HIL Middleware.

        Args:
            interrupt_store: InterruptStore for persisting interrupt states
            sse_queue: SSE event queue (injected at runtime)
            interrupt_on: Dictionary mapping tool names to interrupt requirement
                         Default: {"send_email": True}
        """
        self.interrupt_store = interrupt_store
        self.sse_queue = sse_queue
        self.interrupt_on = interrupt_on or {"send_email": True}
        # Use dict to support concurrent requests: session_id -> interrupt_id
        self._pending_interrupts: dict[str, str] = {}

        logger.info(
            f"HILMiddleware initialized with interrupt_on={self.interrupt_on}"
        )

    async def _send_sse_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Send an event to the SSE queue.

        Args:
            event_type: Event type (hil_interrupt, error, etc.)
            data: Event payload
        """
        if self.sse_queue is not None:
            try:
                await self.sse_queue.put((event_type, data))
                logger.debug(f"SSE event sent: {event_type}")
            except Exception as e:
                logger.error(f"Failed to send SSE event: {e}")
        else:
            logger.debug(f"No SSE queue, skipping event: {event_type}")

    def _should_interrupt_tool(self, tool_name: str) -> bool:
        """
        Check if a tool requires HIL intervention.

        Args:
            tool_name: Name of the tool being called

        Returns:
            bool: True if tool requires intervention
        """
        return self.interrupt_on.get(tool_name, False)

    def _extract_tool_calls_from_state(self, state: Any) -> list[dict[str, Any]]:
        """
        Extract pending tool calls from agent state.

        Args:
            state: Current agent state

        Returns:
            list: List of tool call dictionaries with name and args
        """
        messages = state.get("messages", [])
        tool_calls = []

        for message in messages:
            if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_calls.append({
                            "name": tool_call.get("name", ""),
                            "args": tool_call.get("args", {}),
                            "id": tool_call.get("id", ""),
                        })

        return tool_calls

    async def abefore_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the start of agent turn.

        Checks if any tool calls require HIL intervention.
        If yes, saves interrupt state and pushes hil_interrupt event.

        Args:
            state: Current agent state
            runtime: Agent runtime information

        Returns:
            dict | None: State updates (None for HIL middleware)
        """
        logger.debug("HILMiddleware: abefore_agent called")

        # Extract tool calls from the last AI message
        tool_calls = self._extract_tool_calls_from_state(state)

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            if self._should_interrupt_tool(tool_name):
                # This tool requires HIL intervention
                session_id = state.get("session_id", "unknown")

                logger.info(
                    f"HIL interrupt triggered for tool {tool_name} in session {session_id}"
                )

                # Save interrupt state to store
                interrupt_id = await self.interrupt_store.save_interrupt(
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )

                # Store pending interrupt ID for this session (concurrent-safe)
                self._pending_interrupts[session_id] = interrupt_id

                # Determine risk level based on tool name
                risk_level = self._get_risk_level(tool_name)

                # Push hil_interrupt event to frontend
                await self._send_sse_event(
                    "hil_interrupt",
                    {
                        "interrupt_id": interrupt_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "risk_level": risk_level,
                        "message": f"Agent 准备执行 {tool_name} 操作，请确认",
                    },
                )
                await emit_trace_event(
                    self.sse_queue,
                    stage="hil",
                    step="interrupt_emitted",
                    payload={
                        "interrupt_id": interrupt_id,
                        "tool_name": tool_name,
                        "risk_level": risk_level,
                    },
                )

                # Only interrupt on first matching tool
                break

        return None

    def _get_risk_level(self, tool_name: str) -> str:
        """
        Get risk level for a given tool.

        Args:
            tool_name: Name of the tool

        Returns:
            str: Risk level ("high" | "medium" | "low")
        """
        # High risk: sending emails, posting to social media, etc.
        high_risk_tools = {"send_email", "post_to_social_media", "delete_file"}

        # Medium risk: placing orders, executing trades
        medium_risk_tools = {"place_order", "execute_trade"}

        if tool_name in high_risk_tools:
            return "high"
        elif tool_name in medium_risk_tools:
            return "medium"
        else:
            return "low"

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the end of agent turn.

        Cleans up pending interrupt if execution completed.

        Args:
            state: Final agent state after execution
            runtime: Agent runtime information

        Returns:
            dict | None: State updates (None for HIL middleware)
        """
        logger.debug("HILMiddleware: aafter_agent called")

        # Check if agent was interrupted
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]

            # If last message is not AIMessage or has content, execution completed
            if isinstance(last_message, AIMessage):
                # Clear pending interrupt for this session if execution completed normally
                session_id = state.get("session_id", "unknown")
                pending_interrupt_id = self._pending_interrupts.get(session_id)

                if pending_interrupt_id and last_message.content:
                    logger.debug(
                        f"Agent execution completed, clearing pending interrupt {pending_interrupt_id} for session {session_id}"
                    )
                    # Note: Don't delete from store here, let /chat/resume handle cleanup
                    del self._pending_interrupts[session_id]

        return None

    async def handle_resume_decision(
        self, interrupt_id: str, approved: bool
    ) -> dict[str, Any]:
        """
        Handle user's resume decision (approve/reject).

        Called by /chat/resume endpoint.

        Args:
            interrupt_id: Interrupt identifier
            approved: True if user approved, False if rejected

        Returns:
            dict: Result message
        """
        # Get interrupt data
        interrupt_data = await self.interrupt_store.get_interrupt(interrupt_id)

        if interrupt_data is None:
            return {
                "success": False,
                "message": f"Interrupt {interrupt_id} not found or expired",
            }

        # Update status
        status = "confirmed" if approved else "rejected"
        await self.interrupt_store.update_interrupt_status(interrupt_id, status)

        tool_name = interrupt_data.get("tool_name", "")

        if approved:
            logger.info(f"User approved interrupt {interrupt_id} for tool {tool_name}")
            await emit_trace_event(
                self.sse_queue,
                stage="hil",
                step="resume_approved",
                payload={"interrupt_id": interrupt_id, "tool_name": tool_name},
            )
            return {
                "success": True,
                "message": f"已批准执行 {tool_name} 操作",
                "tool_name": tool_name,
                "tool_args": interrupt_data.get("tool_args", {}),
            }
        else:
            logger.info(f"User rejected interrupt {interrupt_id} for tool {tool_name}")
            await emit_trace_event(
                self.sse_queue,
                stage="hil",
                step="resume_rejected",
                payload={"interrupt_id": interrupt_id, "tool_name": tool_name},
            )
            return {
                "success": True,
                "message": f"已取消 {tool_name} 操作",
                "tool_name": tool_name,
            }


__all__ = ["HILMiddleware"]
