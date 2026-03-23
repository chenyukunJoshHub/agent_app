"""Summarization Middleware - Framework-built, configured per architecture doc §2.6.

Per architecture doc §2.6:
- SummarizationMiddleware is framework-built (langchain.agents.middleware.summarization)
- Zero custom code needed, just configuration
- Trigger: Token fraction exceeds threshold (default 0.75 = 75%)
- Keep: Recent N messages after compression (default 5)
- Model: Use smaller model (gpt-4o-mini) for cost efficiency

P0 Implementation:
- Factory function to create configured SummarizationMiddleware
- Integrated into middleware stack in langchain_engine.py
"""
from langchain.agents.middleware.summarization import SummarizationMiddleware
from loguru import logger


def create_summarization_middleware(
    model: str = "openai:gpt-4o-mini",
    trigger: tuple[str, float | int] | list[tuple[str, float | int]] | None = None,
    keep: tuple[str, float | int] = ("messages", 5),
) -> SummarizationMiddleware:
    """
    Create configured SummarizationMiddleware instance.

    Per architecture doc §2.6:
    - Uses smaller model (gpt-4o-mini) for cost efficiency
    - Triggers when token fraction exceeds threshold (default 75%)
    - Keeps recent N messages after compression (default 5)

    Args:
        model: Model to use for summarization (default: gpt-4o-mini)
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
        >>> # Default: trigger at 75%, keep 5 messages
        >>> mw = create_summarization_middleware()
        >>>
        >>> # Custom: trigger at 80%, keep 10 messages
        >>> mw = create_summarization_middleware(
        ...     trigger=("fraction", 0.8),
        ...     keep=("messages", 10),
        ... )
        >>>
        >>> # Multiple triggers (OR logic)
        >>> mw = create_summarization_middleware(
        ...     trigger=[("fraction", 0.75), ("messages", 50)],
        ... )
    """
    if trigger is None:
        # Default trigger: 75% of context window
        trigger = ("fraction", 0.75)

    middleware = SummarizationMiddleware(
        model=model,
        trigger=trigger,  # type: ignore
        keep=keep,  # type: ignore
    )

    logger.info(
        f"SummarizationMiddleware created: model={model}, "
        f"trigger={trigger}, keep={keep}"
    )

    return middleware


__all__ = ["create_summarization_middleware", "SummarizationMiddleware"]
