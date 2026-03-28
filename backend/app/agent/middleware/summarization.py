"""Summarization Middleware - Framework-built, configured per architecture doc §2.6.

Per architecture doc §2.6:
- SummarizationMiddleware is framework-built (langchain.agents.middleware.summarization)
- Zero custom code needed, just configuration
- Trigger: Token fraction exceeds threshold (default 0.75 = 75%)
- Keep: Recent N messages after compression (default 5)
- Model: Use same provider as main LLM for Ollama compatibility

P0 Implementation:
- Factory function to create configured SummarizationMiddleware
- Integrated into middleware stack in langchain_engine.py
"""
from typing import Any

from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import HumanMessage, RemoveMessage
from loguru import logger


class ObservableSummarizationMiddleware(SummarizationMiddleware):
    """Summarization middleware with compression SSE observability."""

    async def abefore_model(
        self,
        state: dict[str, Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        update = await super().abefore_model(state, runtime)
        if not update:
            return update

        await self._emit_compression_event(messages, update, runtime)
        return update

    async def _emit_compression_event(
        self,
        original_messages: list[Any],
        update: dict[str, Any],
        runtime: Any,
    ) -> None:
        context = getattr(runtime, "context", None)
        sse_queue = getattr(context, "sse_queue", None)
        if sse_queue is None:
            return

        updated_messages = update.get("messages", [])
        persisted_messages = [
            msg for msg in updated_messages if not isinstance(msg, RemoveMessage)
        ]
        summary_text = ""
        for msg in persisted_messages:
            if (
                isinstance(msg, HumanMessage)
                and msg.additional_kwargs.get("lc_source") == "summarization"
            ):
                summary_text = str(msg.content)
                break

        before_tokens = int(self.token_counter(original_messages))
        after_tokens = int(self.token_counter(persisted_messages)) if persisted_messages else 0

        payload = {
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "method": "summarization",
            "affected_slots": ["history"],
            "summary_text": summary_text,
        }

        try:
            await sse_queue.put(("compression", payload))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to emit compression SSE event: {exc}")


def create_summarization_middleware(
    model: str | BaseChatModel | None = None,
    trigger: tuple[str, float | int] | list[tuple[str, float | int]] | None = None,
    keep: tuple[str, float | int] = ("messages", 5),
) -> SummarizationMiddleware:
    """
    Create configured SummarizationMiddleware instance.

    Per architecture doc §2.6:
    - Uses same LLM instance as main agent (or configured model string)
    - Triggers when token fraction exceeds threshold (default 75%)
    - Keeps recent N messages after compression (default 5)

    Args:
        model: Model to use for summarization:
            - BaseChatModel instance: uses this model directly
            - str: model identifier (e.g., "openai:gpt-4o-mini", "ollama:glm4")
            - None: uses default ("ollama:glm4" for Ollama setups)
        trigger: Trigger condition(s):
            - ("fraction", 0.75) = trigger at 75% of context window
            - ("tokens", 10000) = trigger at 10000 tokens
            - [("fraction", 0.75), ("messages", 50)] = OR logic
            - None = use default (75% fraction)
        keep: What to keep after compression:
            - ("messages", 5) = keep last 5 messages uncompressed
            - ("tokens", 3000) = keep last 3000 tokens uncompressed
            - ("fraction", 0.3) = keep last 30% uncompressed

    Returns:
        SummarizationMiddleware: Configured middleware instance

    Examples:
        >>> # With BaseChatModel instance (recommended for Ollama)
        >>> from app.llm.factory import llm_factory
        >>> llm = llm_factory()
        >>> mw = create_summarization_middleware(model=llm)
        >>>
        >>> # With model string (requires API keys for cloud providers)
        >>> mw = create_summarization_middleware(model="openai:gpt-4o-mini")
        >>>
        >>> # Default: uses "ollama:glm4"
        >>> mw = create_summarization_middleware()
    """
    if trigger is None:
        # Default trigger: 75% of context window
        trigger = ("fraction", 0.75)

    # Handle model parameter
    if model is None:
        # Default to ollama for local deployments
        from app.config import settings

        model = f"ollama:{settings.ollama_model}"
        logger.debug(f"Using default summarization model: {model}")
    elif isinstance(model, BaseChatModel):
        # Already a ChatModel instance, use directly
        logger.debug("Using provided ChatModel instance for summarization")

    middleware = ObservableSummarizationMiddleware(
        model=model,
        trigger=trigger,  # type: ignore
        keep=keep,  # type: ignore
    )

    logger.info(
        f"SummarizationMiddleware created: model={model}, "
        f"trigger={trigger}, keep={keep}"
    )

    return middleware


__all__ = [
    "ObservableSummarizationMiddleware",
    "create_summarization_middleware",
    "SummarizationMiddleware",
]
