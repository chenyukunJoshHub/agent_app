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
        self._block_counter: int = 0
        # Fix 5: track planned tool calls for correct pairing
        self._pending_tool_calls: list[dict[str, Any]] = []
        self._tool_call_start_time: float = 0.0
        # Fix 6: deduplicate prompt_build within a turn
        self._prompt_build_emitted: bool = False
        self._turn_started: bool = False
        self._turn_start_time: float = 0.0

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

        # turn_start from middleware (react stage)
        if stage == "react" and step == "turn_start":
            self._flush_pending()
            if self._turn_started:
                return []
            self._turn_started = True
            self._turn_start_time = time.monotonic()
            return [self._build_block(
                block_type="turn_start",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"消息历史 {payload.get('messages', 0)} 条",
            )]

        # thinking: model_call_start → model_call_end → thought_emitted
        if stage == "react" and step == "model_call_start":
            self._flush_pending()
            self._pending_type = "thinking"
            self._pending_start_time = time.monotonic()
            self._pending_payload = {"messages": payload.get("messages", 0)}
            self._last_thinking_block = None
            return []

        # model_call_end — meaningful detail + carry content_preview
        if stage == "react" and step == "model_call_end" and self._pending_type == "thinking" and status == "ok":
            self._pending_payload["messages_after"] = payload.get("messages", 0)
            self._pending_payload["tool_count"] = payload.get(
                "tool_count",
                self._pending_payload.get("tool_count", 0),
            )
            self._pending_payload["content_preview"] = payload.get(
                "content_preview",
                self._pending_payload.get("content_preview", ""),
            )
            self._think_count += 1
            tool_count = self._pending_payload.get("tool_count", 0)
            detail = f"决定调用 {tool_count} 个工具" if tool_count > 0 else "生成回答中"
            block = self._build_block(
                block_type="thinking",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail=detail,
                thinking={
                    "content_preview": self._pending_payload.get("content_preview", ""),
                    "input_tokens": self._pending_payload.get("messages", 0),
                    "output_tokens": 0,
                },
            )
            self._last_thinking_block = block
            self._pending_type = None
            return [block]

        if stage == "react" and step == "model_call_end" and self._pending_type == "thinking" and status != "ok":
            self._pending_payload["messages_after"] = payload.get("messages", 0)
            return []

        # thought_emitted — use actual content_preview from payload
        if stage == "react" and step == "thought_emitted" and self._pending_type == "thinking":
            chars = payload.get("chars", 0)
            content_preview = payload.get("content_preview", "")
            if self._think_count == 0 or self._last_thinking_block is None:
                self._think_count += 1
            block = self._build_block(
                block_type="thinking",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=_elapsed_ms(self._pending_start_time),
                detail=f"生成了 {chars} 字符的推理内容",
                thinking={
                    "content_preview": content_preview,
                    "input_tokens": self._pending_payload.get("messages", 0),
                    "output_tokens": chars,
                },
            )
            self._last_thinking_block = block
            return [block]

        if stage == "react" and step == "thought_emitted" and self._last_thinking_block is not None:
            self._last_thinking_block = None
            return []

        # tool_call — track multiple planned calls, match by queue order
        if stage == "tools" and step == "tool_call_planned":
            if self._pending_type and self._pending_type != "tool_call":
                self._flush_pending()
            self._pending_tool_calls.append({
                "name": payload.get("tool_name", ""),
                "args": payload.get("args", {}),
            })
            if len(self._pending_tool_calls) == 1:
                self._pending_type = "tool_call"
                self._tool_call_start_time = time.monotonic()
            return []

        if stage == "tools" and step == "tool_call_result" and self._pending_tool_calls:
            tool = self._pending_tool_calls.pop(0)
            self._tool_count += 1
            duration = _elapsed_ms(self._tool_call_start_time) if self._tool_call_start_time else 0
            block = self._build_block(
                block_type="tool_call",
                status=status,
                timestamp=event.get("timestamp", _iso_now()),
                duration_ms=duration,
                detail=tool.get("name", ""),
                tool_call={
                    "name": tool.get("name", ""),
                    "args": tool.get("args", {}),
                    "result_preview": payload.get("content_preview", ""),
                    "result_length": payload.get("content_length", 0),
                },
            )
            if not self._pending_tool_calls:
                self._pending_type = None
                self._tool_call_start_time = 0.0
            return [block]

        # answer block (emitted before turn_done)
        if stage == "react" and step == "answer_emitted":
            self._flush_pending()
            chars = payload.get("chars", 0)
            content_preview = payload.get("content_preview", "")
            return [self._build_block(
                block_type="answer",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"生成了 {chars} 字符的回答",
                answer={"content_preview": content_preview, "char_count": chars},
            )]

        # turn_done → turn_summary
        if stage == "react" and step == "turn_done":
            self._flush_pending()
            total_duration_ms = (
                _elapsed_ms(self._turn_start_time)
                if self._turn_started and self._turn_start_time > 0
                else 0
            )
            block = self._build_block(
                block_type="turn_summary",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"{self._think_count} 次思考 · {self._tool_count} 次工具",
                turn_summary={
                    "think_count": self._think_count,
                    "tool_count": self._tool_count,
                    "total_tokens": self._total_tokens,
                    "total_duration_ms": total_duration_ms,
                    "finish_reason": payload.get("finish_reason", "stop"),
                },
            )
            self._think_count = 0
            self._tool_count = 0
            self._total_tokens = 0
            # reset per-turn state for next turn
            self._prompt_build_emitted = False
            self._turn_started = False
            self._turn_start_time = 0.0
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

        # prompt_build — only emit once per turn
        if stage == "context" and step == "token_update":
            self._total_tokens = int(payload.get("current", self._total_tokens))
            if not self._prompt_build_emitted:
                self._prompt_build_emitted = True
                return [self._build_block(
                    block_type="prompt_build",
                    status="ok",
                    timestamp=event.get("timestamp", _iso_now()),
                    detail=f"Token: {payload.get('current', 0)}/{payload.get('budget', 0)}",
                    prompt_build={
                        "messages": payload.get("messages", 0),
                        "total_tokens": payload.get("current", 0),
                        "budget": payload.get("budget", 0),
                    },
                )]
            return []

        # hil_pause (single event)
        if stage == "hil" and step == "interrupt_emitted":
            self._flush_pending()
            return [self._build_block(
                block_type="hil_pause",
                status="pending",
                timestamp=event.get("timestamp", _iso_now()),
                detail=payload.get("tool_name", "等待用户确认"),
            )]

        # planning
        if stage == "planner" and step == "plan_created":
            self._flush_pending()
            step_count = int(payload.get("step_count", 0))
            complexity = str(payload.get("complexity", "simple"))
            return [self._build_block(
                block_type="planning",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"已生成计划：{step_count} 步（{complexity}）",
                planning={
                    "plan_id": str(payload.get("plan_id", "")),
                    "step_count": step_count,
                    "complexity": complexity,
                },
            )]

        if stage == "planner" and step == "step_running":
            self._flush_pending()
            return [self._build_block(
                block_type="planning",
                status="pending",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"执行步骤中：{payload.get('title', '')}",
                planning={
                    "plan_id": str(payload.get("plan_id", "")),
                    "step_count": int(payload.get("step_count", 0)),
                    "complexity": "in_progress",
                },
            )]

        if stage == "planner" and step == "step_succeeded":
            self._flush_pending()
            return [self._build_block(
                block_type="planning",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"步骤完成：{payload.get('title', '')}",
                planning={
                    "plan_id": str(payload.get("plan_id", "")),
                    "step_count": int(payload.get("step_count", 0)),
                    "complexity": "in_progress",
                },
            )]

        if stage == "planner" and step == "plan_completed":
            self._flush_pending()
            step_count = int(payload.get("step_count", 0))
            replan_count = int(payload.get("replan_count", 0))
            return [self._build_block(
                block_type="planning",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"计划完成：{step_count} 步，重规划 {replan_count} 次",
                planning={
                    "plan_id": str(payload.get("plan_id", "")),
                    "step_count": step_count,
                    "complexity": "completed",
                },
            )]

        # retrieval
        if stage == "retrieval" and step == "context_retrieved":
            self._flush_pending()
            hits = int(payload.get("hits", 0))
            return [self._build_block(
                block_type="retrieval",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"检索到 {hits} 条相关历史证据",
                retrieval={
                    "hits": hits,
                },
            )]

        # replanning
        if stage == "replanner" and step == "triggered":
            self._flush_pending()
            return [self._build_block(
                block_type="replanning",
                status="pending",
                timestamp=event.get("timestamp", _iso_now()),
                detail=f"触发重规划：{payload.get('error', 'unknown')}",
                replanning={
                    "attempt": int(payload.get("attempt", 0)),
                    "error": str(payload.get("error", "")),
                },
            )]

        if stage == "replanner" and step == "plan_updated":
            self._flush_pending()
            return [self._build_block(
                block_type="replanning",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
                detail=(
                    f"重规划完成：{payload.get('old_step_count', 0)} -> "
                    f"{payload.get('new_step_count', 0)} 步"
                ),
                replanning={
                    "attempt": int(payload.get("replan_count", 0)),
                    "error": "",
                },
            )]

        # turn_start (from stream stage — only emit once per turn)
        if stage == "stream" and step in ("request_received", "agent_created", "stream_started"):
            if self._turn_started:
                return []
            if step == "request_received":
                self._turn_started = True
                self._turn_start_time = time.monotonic()
                return [self._build_block(
                    block_type="turn_start",
                    status="ok",
                    timestamp=event.get("timestamp", _iso_now()),
                    detail="请求已接收",
                )]
            return []

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
        self._block_counter += 1
        block: dict[str, Any] = {
            "id": f"block_{time.time_ns()}_{self._block_counter}",
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
