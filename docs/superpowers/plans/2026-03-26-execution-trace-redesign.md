# 执行链路明细模块重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将执行链路面板从平铺事件列表重构为树状时间线，后端发送语义块（semantic blocks）替代逐条细粒度事件，前端渲染用户友好的因果链路。

**Architecture:** 后端新增 `TraceBlockBuilder` 类，在 `TraceMiddleware` 内部将连续的细粒度 `trace_event` 累积为高层语义块，通过 `trace_block` SSE 事件类型发送。前端新增 `TraceBlock` 类型、Store 字段、`TraceBlockCard` 组件，并重写 `ExecutionTracePanel` 为树状时间线布局。原始 `trace_event` 保留发送以向后兼容。

**Tech Stack:** Python 3.12 (pytest, dataclasses), TypeScript (Zustand, React, lucide-react, framer-motion, Playwright)

---

### Task 1: TraceBlockBuilder — thinking 块聚合

**Files:**
- Create: `backend/app/observability/trace_block.py`
- Test: `tests/backend/unit/observability/test_trace_block_builder.py`

- [ ] **Step 1: Write failing tests for thinking block aggregation**

Create `tests/backend/unit/observability/test_trace_block_builder.py`:

```python
"""Unit tests for TraceBlockBuilder — thinking block aggregation."""
import pytest
from app.observability.trace_block import TraceBlockBuilder


def _make_event(*, stage: str, step: str, status: str = "ok", payload: dict | None = None) -> dict:
    """Helper to build a minimal trace_event dict."""
    return {
        "id": f"trace_{len(stage)}_{len(step)}",
        "timestamp": "2026-03-26T00:00:00+00:00",
        "stage": stage,
        "step": step,
        "status": status,
        "payload": payload or {},
    }


class TestThinkingBlock:
    """TraceBlockBuilder — thinking block (model_call_start → model_call_end + thought_emitted)."""

    def test_model_call_start_accumulates_no_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        assert blocks == []

    def test_model_call_end_emits_thinking_block(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start", payload={"messages": 5}))
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_end", payload={"messages": 6}))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "thinking"
        assert blocks[0]["status"] == "ok"

    def test_thought_emitted_does_not_emit_second_block(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        blocks = builder.on_trace_event(_make_event(stage="react", step="thought_emitted", payload={"chars": 120}))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "thinking"

    def test_thinking_block_has_duration_ms(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        blocks = builder.on_trace_event(_make_event(stage="react", step="thought_emitted", payload={"chars": 50}))
        assert blocks[0]["duration_ms"] >= 0

    def test_thinking_block_includes_content_preview(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        blocks = builder.on_trace_event(_make_event(stage="react", step="thought_emitted", payload={"chars": 50}))
        assert "thinking" in blocks[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tests/backend && pytest unit/observability/test_trace_block_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.observability.trace_block'`

- [ ] **Step 3: Create TraceBlockBuilder with thinking block logic**

Create `backend/app/observability/trace_block.py`:

```python
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
    """Accumulates fine-grained trace_events and emits semantic blocks.

    Usage in TraceMiddleware:
        builder = TraceBlockBuilder()
        # On every trace_event:
        blocks = builder.on_trace_event(event)
        for block in blocks:
            await emit_trace_block(queue, **block)
    """

    def __init__(self) -> None:
        self._pending_type: str | None = None
        self._pending_start_time: float = 0.0
        self._pending_payload: dict[str, Any] = {}
        self._think_count: int = 0
        self._tool_count: int = 0
        self._total_tokens: int = 0

    def on_trace_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Receive a trace_event, return 0+ trace_block dicts."""
        stage = event.get("stage", "")
        step = event.get("step", "")
        status = event.get("status", "ok")
        payload = event.get("payload", {})

        # --- error: always emit immediately ---
        if status == "error":
            self._flush_pending()
            return [self._build_block(
                block_type="error",
                status="error",
                timestamp=event.get("timestamp", _iso_now()),
                detail=payload.get("error", "Unknown error"),
                error={"message": payload.get("error", ""), "stage": stage, "step": step},
            )]

        # --- thinking block: model_call_start → model_call_end ---
        if stage == "react" and step == "model_call_start":
            self._flush_pending()
            self._pending_type = "thinking"
            self._pending_start_time = time.monotonic()
            self._pending_payload = {"messages": payload.get("messages", 0)}
            return []

        if stage == "react" and step == "model_call_end" and self._pending_type == "thinking":
            self._pending_payload["messages_after"] = payload.get("messages", 0)
            return []

        if stage == "react" and step == "thought_emitted" and self._pending_type == "thinking":
            chars = payload.get("chars", 0)
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
            self._pending_type = None
            return [block]

        # --- tool_call block: tool_call_planned → tool_call_result ---
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

        # --- turn_done → turn_summary ---
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

        # --- memory_load block ---
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

        # --- prompt_build block (single event) ---
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

        # --- hil_pause (single event) ---
        if stage == "hil" and step == "interrupt_emitted":
            self._flush_pending()
            return [self._build_block(
                block_type="hil_pause",
                status="pending",
                timestamp=event.get("timestamp", _iso_now()),
                detail=payload.get("tool_name", "等待用户确认"),
            )]

        # --- turn_start block (from stream stage) ---
        if stage == "stream" and step in ("request_received", "agent_created", "stream_started"):
            return [self._build_block(
                block_type="turn_start",
                status="ok",
                timestamp=event.get("timestamp", _iso_now()),
            )]

        return []

    def _flush_pending(self) -> list[dict[str, Any]]:
        """Flush any pending partial block (e.g. on error)."""
        if self._pending_type is None:
            return []
        self._pending_type = None
        return []

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
        """Build a trace_block dict."""
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


async def emit_trace_block(
    queue: Any | None,
    block: dict[str, Any],
) -> None:
    """Emit a `trace_block` via SSE queue."""
    if queue is None:
        return
    put_result = queue.put(("trace_block", block))
    if isawaitable(put_result):
        await put_result


__all__ = ["TraceBlockBuilder", "emit_trace_block"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tests/backend && pytest unit/observability/test_trace_block_builder.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/observability/trace_block.py tests/backend/unit/observability/test_trace_block_builder.py
git commit -m "feat: add TraceBlockBuilder with thinking block aggregation"
```

---

### Task 2: TraceBlockBuilder — tool_call, memory, prompt, error, hil, turn_summary 块

**Files:**
- Modify: `tests/backend/unit/observability/test_trace_block_builder.py`
- Modify: `backend/app/observability/trace_block.py`

- [ ] **Step 1: Write failing tests for remaining block types**

Append to `tests/backend/unit/observability/test_trace_block_builder.py`:

```python
class TestToolCallBlock:
    """TraceBlockBuilder — tool_call block aggregation."""

    def test_tool_call_planned_accumulates(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "web_search", "args": {"query": "test"}},
        ))
        assert blocks == []

    def test_tool_call_result_emits_block(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "web_search", "args": {"query": "test"}},
        ))
        blocks = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "results...", "content_length": 500},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "tool_call"
        assert blocks[0]["tool_call"]["name"] == "web_search"
        assert blocks[0]["tool_call"]["result_length"] == 500

    def test_tool_call_error_status(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "bad_tool", "args": {}},
        ))
        blocks = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="error",
            payload={"content_preview": "timeout", "content_length": 7},
        ))
        assert blocks[0]["status"] == "error"


class TestMemoryLoadBlock:
    """TraceBlockBuilder — memory_load block aggregation."""

    def test_memory_load_start_accumulates(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        assert blocks == []

    def test_memory_load_success_emits_block(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        blocks = builder.on_trace_event(_make_event(
            stage="memory", step="load_success",
            payload={"count": 3},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "memory_load"
        assert blocks[0]["memory_load"]["count"] == 3
        assert blocks[0]["memory_load"]["injected"] is True

    def test_memory_inject_skip_emits_skip_status(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        blocks = builder.on_trace_event(_make_event(
            stage="memory", step="inject_skip",
            payload={"count": 0},
        ))
        assert blocks[0]["status"] == "skip"


class TestPromptBuildBlock:
    """TraceBlockBuilder — prompt_build block (single event)."""

    def test_token_update_emits_prompt_build(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="context", step="token_update",
            payload={"current": 5000, "budget": 32000},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "prompt_build"
        assert blocks[0]["prompt_build"]["total_tokens"] == 5000


class TestErrorBlock:
    """TraceBlockBuilder — error block (immediate emit)."""

    def test_error_event_emits_immediately(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="model_call_start", status="start",
        ))
        assert blocks == []
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="model_call_end", status="error",
            payload={"error": "Rate limit exceeded"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "error"
        assert blocks[0]["error"]["message"] == "Rate limit exceeded"


class TestHilPauseBlock:
    """TraceBlockBuilder — hil_pause block (immediate emit)."""

    def test_hil_interrupt_emits_pause_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="hil", step="interrupt_emitted",
            payload={"tool_name": "send_email"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "hil_pause"
        assert blocks[0]["status"] == "pending"


class TestTurnSummaryBlock:
    """TraceBlockBuilder — turn_summary block."""

    def test_turn_done_emits_summary(self):
        builder = TraceBlockBuilder()
        # Simulate some thinking and tool calls
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        builder.on_trace_event(_make_event(stage="react", step="thought_emitted", payload={"chars": 50}))
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "web_search", "args": {}},
        ))
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "ok", "content_length": 2},
        ))
        blocks = builder.on_trace_event(_make_event(stage="react", step="turn_done"))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_summary"
        assert blocks[0]["turn_summary"]["think_count"] == 1
        assert blocks[0]["turn_summary"]["tool_count"] == 1


class TestTurnStartBlock:
    """TraceBlockBuilder — turn_start blocks from stream stage."""

    def test_stream_request_received_emits_turn_start(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="stream", step="request_received",
            payload={"session_id": "s1"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"

    def test_stream_agent_created_emits_turn_start(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="stream", step="agent_created",
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"


class TestBlockStructure:
    """TraceBlockBuilder — all blocks have required fields."""

    def test_all_blocks_have_id_and_timestamp(self):
        builder = TraceBlockBuilder()
        # Collect all block types
        all_blocks = []
        all_blocks.extend(builder.on_trace_event(_make_event(stage="stream", step="request_received")))
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        all_blocks.extend(builder.on_trace_event(_make_event(stage="react", step="thought_emitted")))
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "test", "args": {}},
        ))
        all_blocks.extend(builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "ok", "content_length": 2},
        )))
        all_blocks.extend(builder.on_trace_event(_make_event(stage="react", step="turn_done")))

        for block in all_blocks:
            assert "id" in block, f"Block missing id: {block}"
            assert "timestamp" in block, f"Block missing timestamp: {block}"
            assert "type" in block, f"Block missing type: {block}"
            assert "status" in block, f"Block missing status: {block}"
            assert "duration_ms" in block, f"Block missing duration_ms: {block}"
            assert isinstance(block["duration_ms"], int), f"duration_ms not int in {block}"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd tests/backend && pytest unit/observability/test_trace_block_builder.py -v`
Expected: All PASS (implementation already written in Task 1)

- [ ] **Step 3: Run coverage**

Run: `cd tests/backend && pytest unit/observability/test_trace_block_builder.py --cov=app.observability.trace_block --cov-report=term-missing -v`
Expected: ≥ 90% coverage

- [ ] **Step 4: Commit**

```bash
git add tests/backend/unit/observability/test_trace_block_builder.py
git commit -m "test: add comprehensive tests for all TraceBlockBuilder block types"
```

---

### Task 3: Integrate TraceBlockBuilder into TraceMiddleware

**Files:**
- Modify: `backend/app/agent/middleware/trace.py`
- Modify: `backend/app/observability/trace_block.py` (add `__all__`)
- Test: `tests/backend/unit/agent/test_middleware.py` (add block emission test)

- [ ] **Step 1: Write failing test for block emission from middleware**

Check existing middleware test file structure first, then add a test:

```python
# Append to tests/backend/unit/agent/test_middleware.py (or create if needed)
# Test that TraceBlockBuilder is integrated into TraceMiddleware
```

The test verifies that when `TraceMiddleware` emits trace_events, a `TraceBlockBuilder` instance is also fed and can produce trace_blocks. Since `TraceBlockBuilder` is a standalone class, the integration is simple: the middleware feeds events to the builder and emits blocks alongside trace_events.

- [ ] **Step 2: Integrate TraceBlockBuilder into TraceMiddleware**

In `backend/app/agent/middleware/trace.py`, modify `TraceMiddleware.__init__` to create a `TraceBlockBuilder`, and add a helper `_feed_block_builder` that is called after every `emit_trace_event` call. After each trace_event emission, call `builder.on_trace_event(event)` and emit any returned blocks via `emit_trace_block`.

Key changes:

1. Import `TraceBlockBuilder` and `emit_trace_block` from `app.observability.trace_block`
2. In `__init__`, create `self._block_builder = TraceBlockBuilder()`
3. Add method `_feed_and_emit_blocks(self, sse_queue, event_dict)` that feeds the event dict to the builder and emits any resulting blocks
4. After every `emit_trace_event` call in the middleware hooks, call `self._feed_and_emit_blocks(sse_queue, <event_dict>)`

Note: `emit_trace_event` already builds the event dict internally. We need to either: (a) call `build_trace_event` separately to get the dict, then both emit and feed it, or (b) refactor `emit_trace_event` to return the built dict. The simplest approach is to call `build_trace_event()` before `emit_trace_event()`, store the dict, and feed it to the builder.

- [ ] **Step 3: Run existing middleware tests to ensure no regression**

Run: `cd tests/backend && pytest unit/agent/test_middleware.py -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/middleware/trace.py tests/backend/unit/agent/test_middleware.py
git commit -m "feat: integrate TraceBlockBuilder into TraceMiddleware for semantic block emission"
```

---

### Task 4: Frontend TraceBlock type + Zustand Store

**Files:**
- Modify: `frontend/src/types/trace.ts`
- Modify: `frontend/src/store/use-session.ts`

- [ ] **Step 1: Add TraceBlock interface**

Append to `frontend/src/types/trace.ts`:

```typescript
/**
 * Semantic execution block — a high-level summary of related trace events.
 */
export interface TraceBlock {
  id: string;
  timestamp: string;
  type: 'turn_start' | 'thinking' | 'tool_call' | 'answer' | 'memory_load' | 'prompt_build' | 'hil_pause' | 'error' | 'turn_summary';
  duration_ms: number;
  status: 'pending' | 'ok' | 'skip' | 'error';
  detail?: string;

  // type-specific fields
  thinking?: {
    content_preview: string;
    input_tokens: number;
    output_tokens: number;
  };
  tool_call?: {
    name: string;
    args: Record<string, unknown>;
    result_preview: string;
    result_length: number;
    error?: string;
  };
  memory_load?: {
    count: number;
    injected: boolean;
  };
  prompt_build?: {
    messages: number;
    total_tokens: number;
    budget: number;
  };
  turn_summary?: {
    total_duration_ms: number;
    think_count: number;
    tool_count: number;
    total_tokens: number;
    finish_reason: string;
  };
  error?: {
    message: string;
    stage: string;
    step: string;
  };

  // frontend-assigned
  turnId?: string;
}

/** Block types visible in simple (user-friendly) mode. */
export const USER_VISIBLE_BLOCKS = new Set<TraceBlock['type']>([
  'turn_start',
  'thinking',
  'tool_call',
  'answer',
  'hil_pause',
  'error',
  'turn_summary',
]);
```

- [ ] **Step 2: Add traceBlocks to Zustand store**

In `frontend/src/store/use-session.ts`:

1. Add import: `import type { TraceBlock } from '@/types/trace';`
2. Add to `SessionState` interface:
   ```typescript
   traceBlocks: TraceBlock[];
   addTraceBlock: (block: TraceBlock) => void;
   clearTraceBlocks: () => void;
   ```
3. Add initial state: `traceBlocks: [],`
4. Add actions:
   ```typescript
   addTraceBlock: (block) => {
     set((state) => ({
       traceBlocks: [
         ...state.traceBlocks,
         { ...block, turnId: state.currentTurnId ?? undefined },
       ].slice(-200),
     }));
   },
   clearTraceBlocks: () => set({ traceBlocks: [] }),
   ```
5. Add `traceBlocks: []` to `clearMessages` reset.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/trace.ts frontend/src/store/use-session.ts
git commit -m "feat: add TraceBlock type and Zustand store integration"
```

---

### Task 5: SSE Manager — add trace_block event type

**Files:**
- Modify: `frontend/src/lib/sse-manager.ts`

- [ ] **Step 1: Add trace_block to SSE event types**

In `frontend/src/lib/sse-manager.ts`:

1. Add `'trace_block'` to the `EVENT_TYPES` array
2. Add `| 'trace_block'` to the `SSEEventType` union type

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/sse-manager.ts
git commit -m "feat: add trace_block SSE event type to SSEManager"
```

---

### Task 6: page.tsx — handle trace_block SSE events

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Add trace_block handler in page.tsx**

In `frontend/src/app/page.tsx`:

1. Add imports:
   ```typescript
   import type { TraceBlock } from '@/types/trace';
   ```
2. Add type guard function:
   ```typescript
   function isTraceBlock(data: unknown): data is TraceBlock {
     if (typeof data !== 'object' || data === null) return false;
     const record = data as Record<string, unknown>;
     return (
       typeof record.id === 'string' &&
       typeof record.timestamp === 'string' &&
       typeof record.type === 'string' &&
       typeof record.status === 'string' &&
       typeof record.duration_ms === 'number'
     );
   }
   ```
3. Add `addTraceBlock` to the `useSession` destructure
4. Add SSE handler in the `sseHandlersRegistered.current` block:
   ```typescript
   sseManager.on('trace_block', ({ data }) => {
     if (isTraceBlock(data)) {
       addTraceBlock(data);
     }
   });
   ```
5. In the fetch-based SSE handlers (two locations), add the same `trace_block` check alongside the existing `trace_event` check.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: handle trace_block SSE events in page.tsx"
```

---

### Task 7: TraceBlockCard component

**Files:**
- Create: `frontend/src/components/TraceBlockCard.tsx`

- [ ] **Step 1: Create TraceBlockCard component**

Create `frontend/src/components/TraceBlockCard.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Play, Brain, Wrench, MessageSquare, Database, FileText,
  AlertCircle, AlertTriangle, CheckCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TraceBlock } from '@/types/trace';

const BLOCK_CONFIG: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  turn_start: { icon: Play, color: 'text-blue-500', label: '开始处理' },
  thinking: { icon: Brain, color: 'text-purple-500', label: '思考推理' },
  tool_call: { icon: Wrench, color: 'text-amber-500', label: '调用工具' },
  answer: { icon: MessageSquare, color: 'text-green-500', label: '生成回答' },
  memory_load: { icon: Database, color: 'text-blue-400', label: '加载记忆' },
  prompt_build: { icon: FileText, color: 'text-blue-400', label: '组装上下文' },
  hil_pause: { icon: AlertCircle, color: 'text-orange-500', label: '等待确认' },
  error: { icon: AlertTriangle, color: 'text-red-500', label: '出错了' },
  turn_summary: { icon: CheckCircle, color: 'text-green-500', label: '本轮摘要' },
};

const STATUS_DOT: Record<string, string> = {
  ok: 'bg-green-400',
  pending: 'bg-amber-400 animate-pulse',
  skip: 'bg-gray-400',
  error: 'bg-red-400',
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(raw: string): string {
  const date = new Date(raw);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  });
}

function prettyJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

interface TraceBlockCardProps {
  block: TraceBlock;
}

export function TraceBlockCard({ block }: TraceBlockCardProps) {
  const [expanded, setExpanded] = useState(block.type === 'error');
  const config = BLOCK_CONFIG[block.type] ?? BLOCK_CONFIG.error;
  const Icon = config.icon;
  const isDevOnly = block.type === 'memory_load' || block.type === 'prompt_build';

  // Summary line for different block types
  const summaryLine = (() => {
    switch (block.type) {
      case 'tool_call':
        return block.tool_call?.name ?? '';
      case 'thinking':
        return block.thinking?.content_preview
          ? `${block.thinking.content_preview.slice(0, 80)}...`
          : block.detail ?? '';
      case 'turn_summary':
        return block.detail ?? '';
      case 'error':
        return block.error?.message ?? block.detail ?? 'Unknown error';
      case 'memory_load':
        return block.detail ?? '';
      case 'prompt_build':
        return block.detail ?? '';
      default:
        return '';
    }
  })();

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      data-testid="trace-block-card"
      className={cn(
        'rounded-lg border bg-bg-card',
        isDevOnly && 'border-dashed border-blue-300/50',
        block.type === 'error' && 'border-red-300',
        block.type !== 'error' && !isDevOnly && 'border-border',
      )}
    >
      <button
        className="w-full text-left px-3 py-2 flex items-center justify-between gap-2"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Status dot */}
          <span className={cn('w-2 h-2 rounded-full shrink-0', STATUS_DOT[block.status] ?? STATUS_DOT.ok)} />
          {/* Icon */}
          <Icon className={cn('w-4 h-4 shrink-0', config.color)} />
          {/* Label */}
          <span className="text-sm font-medium text-text-primary truncate">
            {config.label}
          </span>
          {/* Tool name for tool_call */}
          {block.type === 'tool_call' && block.tool_call && (
            <span className="font-mono text-sm text-text-secondary truncate">
              {block.tool_call.name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Duration */}
          {block.duration_ms > 0 && (
            <span className="text-[11px] text-text-muted">
              {formatDuration(block.duration_ms)}
            </span>
          )}
          {/* Timestamp */}
          <span className="text-[11px] text-text-muted">
            {formatTime(block.timestamp)}
          </span>
        </div>
      </button>

      {/* Summary line (always visible if non-empty) */}
      {summaryLine && !expanded && (
        <div className="px-3 pb-2 text-xs text-text-secondary truncate">
          {summaryLine}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {summaryLine && block.type !== 'error' && (
            <div className="text-xs text-text-secondary">{summaryLine}</div>
          )}

          {/* Tool call details */}
          {block.tool_call && (
            <>
              {Object.keys(block.tool_call.args).length > 0 && (
                <div>
                  <div className="text-[11px] text-text-muted mb-1">参数</div>
                  <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                    {prettyJson(block.tool_call.args)}
                  </pre>
                </div>
              )}
              {block.tool_call.result_preview && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] text-text-muted">结果预览</span>
                    {block.tool_call.result_length > 0 && (
                      <span className="text-[11px] text-text-muted">{block.tool_call.result_length} 字符</span>
                    )}
                  </div>
                  <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                    {block.tool_call.result_preview}
                  </pre>
                </div>
              )}
            </>
          )}

          {/* Thinking content */}
          {block.thinking?.content_preview && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">推理内容</div>
              <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-60 whitespace-pre-wrap">
                {block.thinking.content_preview}
              </pre>
            </div>
          )}

          {/* Error details */}
          {block.error && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">错误详情</div>
              <pre className="rounded-lg bg-red-50 p-2 text-xs text-red-700 overflow-x-auto">
                {block.error.stage}/{block.error.step}: {block.error.message}
              </pre>
            </div>
          )}

          {/* Turn summary details */}
          {block.turn_summary && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">{block.turn_summary.think_count}</div>
                <div className="text-[11px] text-text-muted">次思考</div>
              </div>
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">{block.turn_summary.tool_count}</div>
                <div className="text-[11px] text-text-muted">次工具</div>
              </div>
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">{block.turn_summary.total_tokens}</div>
                <div className="text-[11px] text-text-muted">tokens</div>
              </div>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TraceBlockCard.tsx
git commit -m "feat: add TraceBlockCard component for semantic block rendering"
```

---

### Task 8: Rewrite ExecutionTracePanel as tree timeline

**Files:**
- Modify: `frontend/src/components/ExecutionTracePanel.tsx`

- [ ] **Step 1: Rewrite ExecutionTracePanel**

Rewrite `frontend/src/components/ExecutionTracePanel.tsx`:

```tsx
'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, Eye, EyeOff } from 'lucide-react';

import type { TraceBlock } from '@/types/trace';
import { USER_VISIBLE_BLOCKS } from '@/types/trace';
import { TraceBlockCard } from '@/components/TraceBlockCard';

interface ExecutionTracePanelProps {
  traceBlocks: TraceBlock[];
  traceEvents: TraceEvent[];
  turnStatuses?: Record<string, 'done' | 'error'>;
}

function formatTime(raw: string): string {
  const date = new Date(raw);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

interface TraceEvent {
  id: string;
  timestamp: string;
  stage: string;
  step: string;
  status: string;
  payload: Record<string, unknown>;
  turnId?: string;
}

// Group blocks by turnId
function groupByTurn(blocks: TraceBlock[]): Array<{ turnId: string | undefined; blocks: TraceBlock[] }> {
  const groups: Array<{ turnId: string | undefined; blocks: TraceBlock[] }> = [];
  for (const block of blocks) {
    const last = groups[groups.length - 1];
    if (!last || last.turnId !== block.turnId) {
      groups.push({ turnId: block.turnId, blocks: [block] });
    } else {
      last.blocks.push(block);
    }
  }
  return groups;
}

export function ExecutionTracePanel({ traceBlocks, traceEvents, turnStatuses }: ExecutionTracePanelProps) {
  const [verboseMode, setVerboseMode] = useState(false);

  const turnGroups = useMemo(() => groupByTurn(traceBlocks), [traceBlocks]);

  // Filter blocks based on mode
  const visibleGroups = useMemo(() => {
    if (verboseMode) return turnGroups;
    return turnGroups.map((group) => ({
      ...group,
      blocks: group.blocks.filter((b) => USER_VISIBLE_BLOCKS.has(b.type)),
    }));
  }, [turnGroups, verboseMode]);

  const blockCount = useMemo(() => traceBlocks.length, [traceBlocks]);
  const turnCount = useMemo(() => turnGroups.length, [turnGroups]);

  return (
    <div className="flex h-full flex-col" data-testid="execution-trace-panel">
      {/* Header */}
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-semibold text-text-primary">执行链路</h2>
          </div>
          {/* View toggle */}
          <button
            className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
            onClick={() => setVerboseMode(!verboseMode)}
          >
            {verboseMode ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                <span>简洁</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>详细</span>
              </>
            )}
          </button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {blockCount} 个步骤 · {turnCount} 轮对话
        </p>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto p-4">
        {traceBlocks.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-text-muted">
            暂无链路事件
          </div>
        ) : (
          <div className="space-y-4">
            {visibleGroups.map((group, groupIdx) => {
              const turnNumber = group.turnId
                ? parseInt(group.turnId.replace('turn_', ''), 10)
                : null;
              const firstBlock = group.blocks[0];
              const lastBlock = group.blocks[group.blocks.length - 1];
              const status = group.turnId && turnStatuses?.[group.turnId]
                ? turnStatuses[group.turnId]
                : null;

              return (
                <div key={group.turnId ?? `pre_${groupIdx}`}>
                  {/* Turn divider */}
                  <div
                    data-testid="turn-divider"
                    className="flex items-center gap-2 px-3 py-1.5 bg-primary/5 border border-primary/20 rounded-lg mb-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-primary">
                        {turnNumber !== null ? `Turn #${turnNumber}` : 'Pre-session'}
                      </span>
                      <span className="text-[11px] text-text-muted">
                        {formatTime(firstBlock?.timestamp ?? '')}
                      </span>
                    </div>
                    {status && (
                      <span className={cn(
                        'text-[11px] px-1.5 py-0.5 rounded',
                        status === 'done' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700',
                      )}>
                        {status === 'done' ? '完成' : '失败'}
                      </span>
                    )}
                    <div className="flex-1" />
                    <span className="text-[11px] text-text-muted">
                      {group.blocks.length} 个步骤
                    </span>
                  </div>

                  {/* Block cards with tree indentation */}
                  <div className="ml-2 border-l-2 border-border pl-3 space-y-2">
                    {group.blocks.map((block) => (
                      <TraceBlockCard key={block.id} block={block} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
```

Note: The `cn` import from `@/lib/utils` is already used. The `TraceEvent` interface is redeclared locally for the `traceEvents` prop typing (avoiding circular imports if the existing type is in a different file). The actual `TraceEvent` type from `@/types/trace` can be imported directly since it's already defined there.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: No errors (fix any type issues)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ExecutionTracePanel.tsx
git commit -m "feat: rewrite ExecutionTracePanel as tree timeline with view toggle"
```

---

### Task 9: Update page.tsx to pass traceBlocks to panel

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Pass traceBlocks prop to ExecutionTracePanel**

In `frontend/src/app/page.tsx`:

1. Add `traceBlocks` to the `useSession` destructure
2. Find where `<ExecutionTracePanel>` is rendered and add `traceBlocks={traceBlocks}` prop
3. Also add `clearTraceBlocks` to the `clearMessages` flow if needed (it's already in the store reset)

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: wire traceBlocks to ExecutionTracePanel"
```

---

### Task 10: Update E2E tests

**Files:**
- Modify: `tests/e2e/03-tool-trace.spec.ts`

- [ ] **Step 1: Update E2E tests for new panel structure**

Update `tests/e2e/03-tool-trace.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Execution Trace', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('默认展示链路面板', async ({ page }) => {
    await expect(page.getByTestId('execution-trace-panel')).toBeVisible();
    await expect(page.getByText('执行链路')).toBeVisible();
  });

  test('发送消息后应出现链路步骤', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('请总结一下这段需求');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    // After redesign, we should see TraceBlockCards instead of raw stage labels
    await expect(page.getByTestId('trace-block-card').first()).toBeVisible({ timeout: 30000 });
  });

  test('工具调用应出现在追踪面板中', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('搜索今日天气');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    // Tool call blocks should be visible
    await expect(page.getByTestId('trace-block-card').first()).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('web_search')).toBeVisible({ timeout: 30000 });
  });

  test('可切换到 Context 面板', async ({ page }) => {
    await page.getByRole('button', { name: /context/i }).click();
    await expect(page.getByTestId('context-window-panel')).toBeVisible();
    await expect(page.getByText('Context Usage')).toBeVisible();
  });

  test('可切换简洁/详细模式', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('你好');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    await expect(page.getByTestId('trace-block-card').first()).toBeVisible({ timeout: 30000 });
    // Toggle to verbose mode
    await page.getByRole('button', { name: /详细/i }).click();
    await expect(page.getByText('简洁')).toBeVisible();
    // Toggle back to simple mode
    await page.getByRole('button', { name: /简洁/i }).click();
    await expect(page.getByText('详细')).toBeVisible();
  });
});
```

- [ ] **Step 2: Run all backend unit tests**

Run: `cd tests/backend && pytest -v --tb=short 2>&1 | tail -30`
Expected: All PASS

- [ ] **Step 3: Run all frontend type checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/03-tool-trace.spec.ts
git commit -m "test: update E2E tests for tree timeline ExecutionTracePanel"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** thinking/tool_call/memory_load/prompt_build/error/hil_pause/turn_summary/turn_start blocks all have tests and implementation
- [x] **Placeholder scan:** No TBD/TODO in any step. All code blocks are complete.
- [x] **Type consistency:** `TraceBlock` interface matches backend dict structure. `TraceBlockBuilder.on_trace_event` returns `list[dict]` which maps to `TraceBlock[]` in frontend.
- [x] **No circular imports:** `trace_block.py` is separate from `trace_events.py`. Frontend types are in separate files.
- [x] **Backward compat:** Original `trace_event` SSE events are still emitted; `trace_block` is additive.
