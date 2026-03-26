"""TraceBlockBuilder — accumulates fine-grained trace_events into semantic blocks."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _elapsed_ms(start_time: float) -> int:
    return int((time.monotonic() - start_time) * 1000)


class TraceBlockBuilder:
    """Accumulates fine-grained trace_events and emits semantic blocks."""

    def __init__(self) -> None:
        self._pending_type: str | None = None
        self._pending_start_time: float = 0.0
        self._pending_payload: dict[str, Any] = {}
        self._think_count: int = 0
        self._tool_count: int = 0
        self._total_tokens: int = 0
        self._last_thinking_block: dict[str, Any] | None = None

    def on_trace_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Receive a trace_event, return 0+ trace_block dicts."""
        stage = event.get("stage", "")
        step = event.get("step", "")
        status = event.get("status", "ok")
        payload = event.get("payload", {})

        # error: always emit immediately
        if status == "error":
            self._flush_pending()
            return [self._build_block(
                block_type="error",
                status="error",
                timestamp=event.get("timestamp", _iso_now()),
                detail=payload.get("error", "Unknown error"),
                error={"message": payload.get("error", ""), "stage": stage, "step": step},
            )]

        # thinking: model_call_start → model_call_end → thought_emitted
        if stage == "react" and step == "model_call_start":
            self._flush_pending()
            self._pending_type = "thinking"
            self._pending_start_time = time.monotonic()
            self._pending_payload = {"messages": payload.get("messages", 0)}
            self._last_thinking_block = None
            return []

        if stage == "react" and step == "model_call_end" and self._pending_type == "thinking" and status == "ok":
            self._pending_payload["messages_after"] = payload.get("messages", 0)
            self._think_count += 1
            block = self._build_block(
                block_type="thinking",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail="",
                thinking={
                    "content_preview": "",
                    "input_tokens": self._pending_payload.get("messages", 0),
                    "output_tokens": 0,
                },
            )
            self._last_thinking_block = block
            self._pending_type = None
            return [block]

        if stage == "react" and step == "model_call_end" and self._pending_type == "thinking" and status != "ok":
            # Non-ok model_call_end (e.g. "start" status); just accumulate, don't emit
            self._pending_payload["messages_after"] = payload.get("messages", 0)
            return []

        if stage == "react" and step == "thought_emitted" and self._pending_type == "thinking":
            # model_call_end was never received with ok status; emit now
            chars = payload.get("chars", 0)
            if self._think_count == 0 or self._last_thinking_block is None:
                self._think_count += 1
            block = self._build_block(
                block_type="thinking",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail=f"生成了 {chars} 字符的推理内容",
                thinking={
                    "content_preview": "",
                    "input_tokens": self._pending_payload.get("messages", 0),
                    "output_tokens": chars,
                },
            )
            self._last_thinking_block = block
            return [block]

        if stage == "react" and step == "thought_emitted" and self._last_thinking_block is not None:
            # model_call_end already emitted; re-emit that same block (no duplicate)
            return [self._last_thinking_block]

        # tool_call: tool_call_planned → tool_call_result
        if stage == "tools" and step == "tool_call_planned":
            self._flush_pending()
            self._pending_type = "tool_call"
            self._pending_start_time = time.monotonic()
            self._pending_payload = {
                "name": payload.get("tool_name", ""),
                "args": payload.get("args", {}),
            }
            return []

        if stage == "tools" and step == "tool_call_result" and self._pending_type == "tool_call":
            self._tool_count += 1
            block = self._build_block(
                block_type="tool_call",
                status=status,
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail=self._pending_payload.get("name", ""),
                tool_call={
                    "name": self._pending_payload.get("name", ""),
                    "args": self._pending_payload.get("args", {}),
                    "result_preview": payload.get("content_preview", ""),
                    "result_length": payload.get("content_length", 0),
                },
            )
            self._pending_type = None
            return [block]

        # turn_done → turn_summary
        if stage == "react" and step == "turn_done":
            self._flush_pending()
            block = self._build_block(
                block_type="turn_summary",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"{self._think_count} 次思考 · {self._tool_count} 次工具",
                turn_summary={
                    "think_count": self._think_count,
                    "tool_count": self._tool_count,
                    "total_tokens": self._total_tokens,
                    "total_duration_ms": 0,
                    "finish_reason": "stop",
                },
            )
            self._think_count = 0
            self._tool_count = 0
            self._total_tokens = 0
            return [block]

        # memory_load
        if stage == "memory" and step == "load_start":
            self._flush_pending()
            self._pending_type = "memory_load"
            self._pending_start_time = time.monotonic()
            self._pending_payload = {}
            return []

        if stage == "memory" and step in ("load_success", "inject_success", "inject_skip") and self._pending_type == "memory_load":
            count = payload.get("count", 0)
            block = self._build_block(
                block_type="memory_load",
                status="ok" if step != "inject_skip" else "skip",
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail=f"加载了 {count} 条记忆",
                memory_load={"count": count, "injected": step != "inject_skip"},
            )
            self._pending_type = None
            return [block]

        # prompt_build (single event)
        if stage == "context" and step == "token_update":
            self._total_tokens += payload.get("current", 0)
            block = self._build_block(
                block_type="prompt_build",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"Token: {payload.get('current', 0)}/{payload.get('budget', 0)}",
                prompt_build={
                    "messages": payload.get("messages", 0),
                    "total_tokens": payload.get("current", 0),
                    "budget": payload.get("budget", 0),
                },
            )
            return [block]

        # hil_pause (single event)
        if stage == "hil" and step == "interrupt_emitted":
            self._flush_pending()
            return [self._build_block(
                block_type="hil_pause",
                status="pending",
                timestamp=event.get("timestamp", _iso_now()),
                detail=payload.get("tool_name", "等待用户确认"),
            )]

        # turn_start (from stream stage)
        if stage == "stream" and step in ("request_received", "agent_created", "stream_started"):
            return [self._build_block(
                block_type="turn_start",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
            )]

        return []

    def _flush_pending(self) -> None:
        if self._pending_type is not None:
            self._pending_type = None

    def _build_block(
        self,
        *,
        block_type: str,
        status: str,
        timestamp: str,
        duration_ms: int = 0,
        detail: str = "",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        block: dict[str, Any] = {
            "id": f"block_{time.time_ns()}",
            "timestamp": timestamp,
            "type": block_type,
            "duration_ms": duration_ms,
            "status": status,
            "detail": detail,
        }
        block.update(extra_fields)
        return block


async def emit_trace_block(queue: Any | None, block: dict[str, Any]) -> None:
    """Emit a `trace_block` via SSE queue."""
    if queue is None:
        return
    put_result = queue.put(("trace_block", block))
    if isawaitable(put_result):
        await put_result


__all__ = ["TraceBlockBuilder", "emit_trace_block"]
