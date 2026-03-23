"""
Chat API with SSE streaming support.

P0: POST /chat endpoint with Server-Sent Events streaming.
"""
import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from loguru import logger
from pydantic import BaseModel, Field

from app.agent.langchain_engine import create_react_agent
from app.observability.trace_events import build_trace_event, emit_trace_event


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
        """Put an event into the queue."""
        await self._queue.put(event)

    async def get(self) -> tuple[str, dict[str, Any]]:
        """Get an event from the queue."""
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
        event_type: Event type (thought, tool_start, tool_result, done, error)
        data: Event payload

    Returns:
        str: Formatted SSE event string
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _run_agent_stream(
    message: str,
    session_id: str,
    user_id: str,
) -> AsyncIterator[str]:
    """
    Run agent and yield SSE events.

    Args:
        message: User message
        session_id: Session identifier (thread_id)
        user_id: User identifier

    Yields:
        str: SSE-formatted event strings
    """
    # Create SSE queue
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

    # Create agent with SSE queue (await the async function)
    agent = await create_react_agent(sse_queue=event_queue)
    await emit_trace_event(
        event_queue,
        stage="stream",
        step="agent_created",
        payload={"session_id": session_id},
    )

    # Config for LangGraph (thread_id = session_id)
    config = {
        "configurable": {
            "thread_id": session_id,
        }
    }

    # Run agent in background
    agent_task = asyncio.create_task(
        _execute_agent(agent, message, config, event_queue)
    )
    await emit_trace_event(
        event_queue,
        stage="stream",
        step="stream_started",
        payload={"session_id": session_id},
    )

    # Stream events
    try:
        while True:
            event_type, data = await event_queue.get()

            # Yield SSE event
            yield await _format_sse_event(event_type, data)

            event_queue.task_done()

            # Check if agent is done
            if event_type == "done":
                # Wait for agent task to complete
                await agent_task
                yield await _format_sse_event(
                    "trace_event",
                    build_trace_event(
                        stage="stream",
                        step="stream_done",
                        payload={"session_id": session_id},
                    ),
                )
                break

            if event_type == "error":
                # Agent encountered error
                await agent_task
                yield await _format_sse_event(
                    "trace_event",
                    build_trace_event(
                        stage="stream",
                        step="stream_error",
                        status="error",
                        payload={"session_id": session_id, "error": data.get("message", "")},
                    ),
                )
                break

    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        yield await _format_sse_event("error", {"message": str(e)})


async def _execute_agent(
    agent: Any,
    message: str,
    config: dict[str, Any],
    event_queue: SSEEventQueue,
) -> None:
    """
    Execute agent and push events to queue.

    Args:
        agent: Agent executor
        message: User message
        config: LangGraph config with thread_id
        event_queue: SSE event queue
    """
    seq = 0  # Event sequence counter

    try:
        await emit_trace_event(
            event_queue,
            stage="react",
            step="execution_start",
            status="start",
            payload={"message_chars": len(message)},
        )
        # Prepare input
        messages = [HumanMessage(content=message)]

        # Invoke agent with streaming
        # P0: Use astream for event streaming
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
        ):
            # Process chunk and push events
            # LangGraph chunks can be in different formats depending on stream_mode
            # Default is 'values' mode which contains full state updates

            if not isinstance(chunk, dict):
                logger.debug(f"Skipping non-dict chunk: {type(chunk)}")
                continue

            # Extract messages from chunk
            chunk_messages = chunk.get("messages", [])
            if not chunk_messages:
                logger.debug("Chunk has no messages, skipping")
                continue

            # Process each message in the chunk
            for msg in chunk_messages:
                # Handle AIMessage with tool calls
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        seq += 1
                        tool_name = tool_call.get("name", "unknown")
                        tool_args = tool_call.get("args", {})

                        # Push tool_start event
                        await event_queue.put(
                            (
                                "tool_start",
                                {
                                    "tool_name": tool_name,
                                    "args": tool_args,
                                    "seq": seq,
                                },
                            )
                        )
                        logger.debug(f"Tool start: {tool_name}")
                        await emit_trace_event(
                            event_queue,
                            stage="tools",
                            step="tool_start",
                            payload={"tool_name": tool_name, "args": tool_args},
                        )

                # Handle AIMessage content (thought/response)
                if hasattr(msg, "content") and msg.content:
                    # Stream content as thought
                    seq += 1
                    await event_queue.put(
                        (
                            "thought",
                            {
                                "content": str(msg.content),
                                "seq": seq,
                            },
                        )
                    )
                    logger.debug(f"Thought: {msg.content[:100]}...")

                # Handle ToolMessage (tool result)
                if hasattr(msg, "content") and isinstance(
                    msg, type(msg)
                ) and type(msg).__name__ == "ToolMessage":
                    # Extract tool_call_id to identify which tool
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    if tool_call_id:
                        seq += 1
                        await event_queue.put(
                            (
                                "tool_result",
                                {
                                    "tool_name": "tool",  # Could be enhanced to map tool_call_id to name
                                    "result": str(msg.content),
                                    "seq": seq,
                                },
                            )
                        )
                        logger.debug(f"Tool result: {msg.content[:100]}...")
                        await emit_trace_event(
                            event_queue,
                            stage="tools",
                            step="tool_result",
                            payload={
                                "tool_call_id": tool_call_id,
                                "result_chars": len(str(msg.content)),
                            },
                        )

        # Send final done event if not already sent
        await event_queue.put(("done", {"answer": "执行完成", "finish_reason": "stop"}))
        await emit_trace_event(
            event_queue,
            stage="react",
            step="execution_done",
            payload={"events_emitted": seq},
        )

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        await event_queue.put(("error", {"message": str(e)}))
        await emit_trace_event(
            event_queue,
            stage="react",
            step="execution_failed",
            status="error",
            payload={"error": str(e)},
        )


@router.get("")
async def chat(
    message: str,
    session_id: str,
    user_id: str = "dev_user",
) -> StreamingResponse:
    """
    Chat endpoint with SSE streaming.

    P0: Streams thought, tool_start, tool_result, done events.

    Note: Uses GET method for SSE compatibility (EventSource only supports GET).
    Sensitive data should be avoided in query params for production.

    Args:
        message: User message
        session_id: Session identifier (maps to thread_id)
        user_id: User identifier (P0: no auth)

    Returns:
        StreamingResponse: SSE event stream
    """
    logger.info(f"Chat request: session={session_id}, user={user_id}")

    return StreamingResponse(
        _run_agent_stream(
            message=message,
            session_id=session_id,
            user_id=user_id,
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
        sse_queue=event_queue,
        interrupt_on={interrupt_data.get("tool_name", ""): True},
    )

    # Handle resume decision
    result = await hil_middleware.handle_resume_decision(
        request.interrupt_id, request.approved
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
    # For P1, we'll send a success message and indicate the tool was approved
    # In a full implementation, this would resume the actual agent execution
    async def approved_stream() -> AsyncIterator[str]:
        # Send approval confirmation
        yield await _format_sse_event("hil_resolved", result)
        while not event_queue.empty():
            event_type, event_data = event_queue.get_nowait()
            yield await _format_sse_event(event_type, event_data)

        # Indicate that the tool execution would continue here
        # For P1, we simulate the completion
        tool_name = interrupt_data.get("tool_name", "")
        tool_args = interrupt_data.get("tool_args", {})

        # Simulate tool execution result
        if tool_name == "send_email":
            # Import and execute the actual tool
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
