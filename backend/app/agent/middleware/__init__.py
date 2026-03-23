"""Agent Middleware Stack.

Per architecture doc §2.7:
- MemoryMiddleware: Load user profile from Long Memory, inject into System Prompt
- SummarizationMiddleware: Compress conversation history when token limit exceeded
- TraceMiddleware: SSE streaming for observability
- HILMiddleware: Human-in-the-loop intervention for irreversible operations

Middleware Order (important!):
1. MemoryMiddleware (abefore_agent: load profile)
2. SummarizationMiddleware (before_model: compress history)
3. TraceMiddleware (after_model: stream events)
4. HILMiddleware (before_agent: check for pending approvals)
"""
from app.agent.middleware.hil import HILMiddleware
from app.agent.middleware.memory import MemoryMiddleware, MemoryState
from app.agent.middleware.summarization import (
    SummarizationMiddleware,
    create_summarization_middleware,
)
from app.agent.middleware.trace import TraceMiddleware

__all__ = [
    "MemoryMiddleware",
    "MemoryState",
    "SummarizationMiddleware",
    "create_summarization_middleware",
    "TraceMiddleware",
    "HILMiddleware",
]
