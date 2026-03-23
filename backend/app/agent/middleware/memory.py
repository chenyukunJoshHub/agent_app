"""
Memory Middleware for Long Memory (User Profile).

P0 Version: Load profile from store, inject into System Prompt (ephemeral).

Per architecture doc §2.5:
- abefore_agent: Load user profile from store to state.memory_ctx
- wrap_model_call: Ephemeral injection into System Prompt
- aafter_agent: P0 no-op (will write back in P2)

Hooks:
- abefore_agent: Load user profile from store (P0: loads empty profile if not found)
- wrap_model_call: Ephemeral injection into System Prompt (P0: injects if preferences exist)
- aafter_agent: Write back updated profile (P0: no-op)
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage
from loguru import logger

from app.memory.manager import MemoryManager
from app.memory.schemas import MemoryContext
from app.observability.trace_events import emit_trace_event


class MemoryState(TypedDict, total=False):
    """Middleware state schema per architecture doc §2.5.

    This defines additional state fields introduced by MemoryMiddleware.
    The framework automatically merges this into the Agent's state.
    """

    memory_ctx: MemoryContext  # turn-level cache, written by abefore_agent


class MemoryMiddleware(AgentMiddleware):
    """
    Middleware for managing Long Memory (user profiles).

    P0: Loads profile from store, injects into System Prompt (ephemeral).
    P2: Will write back updated profile with dirty flag optimization.

    Per architecture doc §2.5:
    - Uses state_schema to introduce memory_ctx field
    - abefore_agent loads profile from AsyncPostgresStore
    - wrap_model_call injects profile via request.override()
    - aafter_agent is no-op in P0
    """

    state_schema = MemoryState  # Per architecture doc §2.5 solution A

    def __init__(
        self,
        memory_manager: MemoryManager,
        sse_queue: Any | None = None,
    ) -> None:
        """Initialize MemoryMiddleware.

        Args:
            memory_manager: MemoryManager instance for store operations
            sse_queue: Optional SSE queue for detailed trace events
        """
        self.mm = memory_manager
        self.sse_queue = sse_queue
        logger.info("MemoryMiddleware initialized (P0 mode: load + inject)")

    async def abefore_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the start of each agent turn.

        Per architecture doc §2.5 §2.8: Loads user profile from store.

        Args:
            state: Current agent state
            runtime: Agent runtime information (contains config)

        Returns:
            dict | None: State updates with memory_ctx
        """
        logger.debug("MemoryMiddleware: abefore_agent called")
        await emit_trace_event(
            self.sse_queue,
            stage="memory",
            step="load_start",
            status="start",
        )

        # Get user_id from runtime.config["configurable"]
        user_id = ""
        if hasattr(runtime, "config") and "configurable" in runtime.config:
            user_id = runtime.config["configurable"].get("user_id", "")

        # Load user profile from store (returns empty UserProfile if not found)
        episodic = await self.mm.load_episodic(user_id)

        # Create MemoryContext and inject into state
        memory_ctx = MemoryContext(episodic=episodic)

        logger.debug(
            f"MemoryMiddleware: loaded profile for user={user_id}, "
            f"preferences={len(episodic.preferences)} items"
        )
        await emit_trace_event(
            self.sse_queue,
            stage="memory",
            step="load_success",
            payload={
                "user_id": user_id,
                "preferences_count": len(episodic.preferences),
            },
        )

        return {"memory_ctx": memory_ctx}

    def wrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (sync version).

        Per architecture doc §2.5: Ephemeral injection into System Prompt.
        Per architecture doc §1.4: Uses request.override() to avoid polluting history.

        Args:
            request: Model request (contains messages and state)
            handler: Next handler in chain

        Returns:
            Model response from handler
        """
        logger.debug("MemoryMiddleware: wrap_model_call called")

        # Get memory_ctx from request.state
        memory_ctx = None
        if request.state and "memory_ctx" in request.state:
            memory_ctx = request.state["memory_ctx"]

        if not memory_ctx:
            # No profile to inject, pass through
            if self.sse_queue is not None:
                try:
                    import asyncio

                    asyncio.create_task(
                        emit_trace_event(
                            self.sse_queue,
                            stage="memory",
                            step="inject_skip",
                            status="skip",
                            payload={"reason": "no_memory_ctx"},
                        )
                    )
                except RuntimeError:
                    pass
            return handler(request)

        # Build ephemeral prompt
        memory_text = self.mm.build_ephemeral_prompt(memory_ctx)
        if not memory_text:
            # Empty preferences, pass through
            if self.sse_queue is not None:
                try:
                    import asyncio

                    asyncio.create_task(
                        emit_trace_event(
                            self.sse_queue,
                            stage="memory",
                            step="inject_skip",
                            status="skip",
                            payload={"reason": "empty_preferences"},
                        )
                    )
                except RuntimeError:
                    pass
            return handler(request)

        # Inject into System Message via request.override()
        existing = request.system_message
        new_content = (existing.content + memory_text) if existing else memory_text

        logger.debug(f"MemoryMiddleware: injecting profile ({len(memory_text)} chars)")
        if self.sse_queue is not None:
            try:
                import asyncio

                asyncio.create_task(
                    emit_trace_event(
                        self.sse_queue,
                        stage="memory",
                        step="inject_success",
                        payload={"injected_chars": len(memory_text)},
                    )
                )
            except RuntimeError:
                pass

        return handler(request.override(system_message=SystemMessage(content=new_content)))

    async def awrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """
        Hook called before each LLM invocation (async version).

        P0: Delegates to sync wrap_model_call.

        Args:
            request: Model request (contains messages and state)
            handler: Next handler in chain

        Returns:
            Model response from handler
        """
        logger.debug("MemoryMiddleware: awrap_model_call called")

        # Call sync version, handle both coroutines and direct results
        result = self.wrap_model_call(request, handler)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """
        Hook called at the end of each agent turn.

        P0: No-op (does not write back to store).
        P2: Will extract learnings and write to store with dirty flag.

        Args:
            state: Final agent state after execution
            runtime: Agent runtime information

        Returns:
            dict | None: State updates (P0: None)
        """
        logger.debug("MemoryMiddleware: aafter_agent called (P0: no-op)")
        await emit_trace_event(
            self.sse_queue,
            stage="memory",
            step="save_skip",
            status="skip",
            payload={"mode": "P0_noop"},
        )
        # P0: Don't write to store yet
        return None


__all__ = ["MemoryMiddleware", "MemoryState"]
