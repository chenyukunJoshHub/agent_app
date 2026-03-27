"""Trace event helpers for fine-grained SSE observability."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any
from weakref import WeakKeyDictionary

from app.observability.trace_block import TraceBlockBuilder, emit_trace_block


_QUEUE_BUILDERS: WeakKeyDictionary[Any, TraceBlockBuilder] = WeakKeyDictionary()
_FALLBACK_BUILDERS: dict[int, TraceBlockBuilder] = {}


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


def _get_builder(queue: Any) -> TraceBlockBuilder:
    """Get/create a per-queue TraceBlockBuilder."""
    try:
        builder = _QUEUE_BUILDERS.get(queue)
    except TypeError:
        builder = _FALLBACK_BUILDERS.get(id(queue))
    if builder is not None:
        return builder
    builder = TraceBlockBuilder()
    try:
        _QUEUE_BUILDERS[queue] = builder
    except TypeError:
        _FALLBACK_BUILDERS[id(queue)] = builder
    return builder


def _drop_builder(queue: Any) -> None:
    """Drop per-queue builder once a turn is finished."""
    try:
        _QUEUE_BUILDERS.pop(queue, None)
    except TypeError:
        _FALLBACK_BUILDERS.pop(id(queue), None)


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
    event = build_trace_event(
        stage=stage,
        step=step,
        status=status,
        payload=payload,
    )
    put_result = queue.put(
        (
            "trace_event",
            event,
        )
    )
    if isawaitable(put_result):
        await put_result

    builder = _get_builder(queue)
    blocks = builder.on_trace_event(event)
    for block in blocks:
        await emit_trace_block(queue, block)

    if status == "error" or (stage == "react" and step == "turn_done"):
        _drop_builder(queue)


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
