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
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.agent.context import AgentContext
from app.memory.manager import MemoryManager
from app.memory.schemas import MemoryContext, ProceduralMemory
from app.observability.trace_events import emit_slot_update, emit_trace_event


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

    def __init__(self, memory_manager: MemoryManager) -> None:
        """Initialize MemoryMiddleware.

        Args:
            memory_manager: MemoryManager instance for store operations.
                SSE queue and user_id are injected per-request via
                runtime.context (AgentContext).
        """
        self.mm = memory_manager
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
        # user_id and sse_queue come from per-request AgentContext
        ctx: AgentContext | None = getattr(runtime, "context", None)
        sse_queue = ctx.sse_queue if ctx else None
        user_id = ctx.user_id if ctx else ""

        await emit_trace_event(
            sse_queue,
            stage="memory",
            step="load_start",
            status="start",
        )

        # Load user profile from store (returns empty UserProfile if not found)
        logger.info(f"MemoryMiddleware: abefore_agent  load_episodic + load_procedural")
        episodic = await self.mm.load_episodic(user_id)

        # Load procedural memory (workflow SOPs) from store
        procedural_data = await self.mm.load_procedural(user_id)
        procedural = ProceduralMemory(workflows=procedural_data.get("workflows", {})) if procedural_data else ProceduralMemory()

        # Create MemoryContext and inject into state
        memory_ctx = MemoryContext(episodic=episodic, procedural=procedural)

        logger.debug(
            f"MemoryMiddleware: loaded profile for user={user_id}, "
            f"preferences(偏好设置)={len(episodic.preferences)} items"
        )
        await emit_trace_event(
            sse_queue,
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

        Always emits slot_update for both 'episodic' and 'history' slots so the
        ContextPanel reflects real-time token usage even when no profile exists.

        Args:
            request: Model request (contains messages and state)
            handler: Next handler in chain

        Returns:
            Model response from handler
        """
        import asyncio
        from langchain_core.messages import SystemMessage
        from app.utils.token import count_tokens

        logger.debug("MemoryMiddleware: wrap_model_call called llm之前")

        ctx: AgentContext | None = getattr(getattr(request, "runtime", None), "context", None)
        sse_queue = ctx.sse_queue if ctx else None

        # --- 1. Build ephemeral memory text (may be empty) ---
        memory_ctx = None
        if request.state and "memory_ctx" in request.state:
            memory_ctx = request.state["memory_ctx"]

        # Build injection text from all processors via unified contract.
        # Each processor (EpisodicProcessor, ProceduralProcessor, ...) returns "" if nothing to inject.
        # Order in parts dict determines injection order (episodic before procedural).
        #
        # Note: Architecture doc §1.4 specifies request.override(system_message=...),
        # but injecting into HumanMessage is used instead (more reliable with this framework).
        # Functionally equivalent — content is ephemeral and does not pollute history semantics.
        parts: dict[str, str] = {}
        if memory_ctx:
            logger.info("MemoryMiddleware: wrap_model_call  build_injection_parts")
            parts = self.mm.build_injection_parts(memory_ctx)
        memory_text = "".join(parts.values())

        # --- 2. Inject into messages if profile exists ---
        messages = list(request.messages)
        if memory_text:
            injected_tokens = count_tokens(memory_text)
            logger.debug(
                f"MemoryMiddleware: injecting profile ({len(memory_text)} chars, {injected_tokens} tokens)"
            )
            last_human_idx = next(
                (i for i in reversed(range(len(messages))) if isinstance(messages[i], HumanMessage)),
                None,
            )
            if last_human_idx is not None:
                original = messages[last_human_idx]
                original_content = original.content if isinstance(original.content, str) else str(original.content)
                messages[last_human_idx] = HumanMessage(
                    content=memory_text + "\n\n---\n\n" + original_content
                )
            else:
                messages.append(HumanMessage(content=memory_text))

            if sse_queue is not None:
                try:
                    asyncio.create_task(
                        emit_trace_event(
                            sse_queue, stage="memory", step="inject_success",
                            payload={"injected_chars": len(memory_text), "injected_tokens": injected_tokens},
                        )
                    )
                except RuntimeError:
                    pass
        else:
            reason = "no_memory_ctx" if not memory_ctx else "empty_preferences"
            if sse_queue is not None:
                try:
                    asyncio.create_task(
                        emit_trace_event(
                            sse_queue, stage="memory", step="inject_skip",
                            status="skip", payload={"reason": reason},
                        )
                    )
                except RuntimeError:
                    pass

        # --- 3. Emit slot_update for each processor + history ---
        # Build display_name lookup from processors (required by emit_slot_update signature).
        display_names = {p.slot_name: p.display_name for p in self.mm.processors}
        
        # Emit per-processor slot (generic — works for any future processor).
        # emit_slot_update handles sse_queue=None as a no-op, so always called.
        # Called via _fire_slot to handle both async (production) and sync (test) contexts.
        for slot_name, text in parts.items():
            coro = emit_slot_update(
                sse_queue,
                name=slot_name,
                display_name=display_names.get(slot_name, ""),
                tokens=count_tokens(text) if text else 0,
                enabled=bool(text),
                content=text,
            )
            try:
                asyncio.create_task(coro)
            except RuntimeError:
                # No running event loop (e.g. sync test context); discard safely.
                coro.close()

        # history slot (not a processor, emitted separately)
        if sse_queue is not None:
            try:
                history_tokens = sum(
                    count_tokens(str(m.content or ""))
                    for m in messages
                    if not isinstance(m, SystemMessage)
                )
                asyncio.create_task(
                    emit_slot_update(
                        sse_queue, name="history", display_name="对话历史",
                        tokens=history_tokens, enabled=True,
                    )
                )
            except RuntimeError:
                pass

        return handler(request.override(messages=messages))

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
        ctx: AgentContext | None = getattr(runtime, "context", None)
        sse_queue = ctx.sse_queue if ctx else None
        await emit_trace_event(
            sse_queue,
            stage="memory",
            step="save_skip",
            status="skip",
            payload={"mode": "P0_noop"},
        )
        # P0: Don't write to store yet
        return None


__all__ = ["MemoryMiddleware", "MemoryState"]
