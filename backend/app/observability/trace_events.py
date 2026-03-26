"""Trace event helpers for fine-grained SSE observability."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any


def _iso_now() -> str:
    """Return current UTC time in ISO8601 format."""
    return datetime.now(UTC).isoformat()


def build_trace_event(
    *,
    stage: str,
    step: str,
    status: str = "ok",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized trace event payload."""
    return {
        "id": f"trace_{time.time_ns()}",
        "timestamp": _iso_now(),
        "stage": stage,
        "step": step,
        "status": status,
        "payload": payload or {},
    }


async def emit_trace_event(
    queue: Any | None,
    *,
    stage: str,
    step: str,
    status: str = "ok",
    payload: dict[str, Any] | None = None,
) -> None:
    """Emit a `trace_event` via SSE queue when queue is available."""
    if queue is None:
        return
    put_result = queue.put(
        (
            "trace_event",
            build_trace_event(
                stage=stage,
                step=step,
                status=status,
                payload=payload,
            ),
        )
    )
    if isawaitable(put_result):
        await put_result


async def emit_slot_update(
    queue: Any | None,
    *,
    name: str,
    display_name: str,
    tokens: int,
    enabled: bool = True,
    content: str = "",
) -> None:
    """Emit a `slot_update` SSE event to refresh a single context slot in UI.
    
    Call this after any runtime injection that changes a slot's token count
    (e.g. episodic memory, RAG, procedural).
    
    Args:
        queue: SSE event queue (no-op if None)
        name: Slot name, e.g. "episodic", "rag", "procedural"
        display_name: Human-readable label shown in ContextPanel
        tokens: Actual token count after injection
        enabled: Whether slot is active
        content: Actual injected content (prompt text) for display in ContextPanel
    """
    if queue is None:
        return
    event_tuple = ("slot_update", {
        "name": name,
        "display_name": display_name,
        "tokens": tokens,
        "enabled": enabled,
        "content": content,
    })
    put_result = queue.put(event_tuple)
    if isawaitable(put_result):
        await put_result


__all__ = ["build_trace_event", "emit_trace_event", "emit_slot_update"]
