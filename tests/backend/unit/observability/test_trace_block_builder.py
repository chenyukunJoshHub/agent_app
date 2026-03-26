"""Unit tests for TraceBlockBuilder."""
import pytest
from app.observability.trace_block import TraceBlockBuilder


def _make_event(*, stage: str, step: str, status: str = "ok", payload: dict | None = None) -> dict:
    return {
        "id": f"trace_{len(stage)}_{len(step)}",
        "timestamp": "2026-03-26T00:00:00+00:00",
        "stage": stage,
        "step": step,
        "status": status,
        "payload": payload or {},
    }


class TestThinkingBlock:
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


class TestToolCallBlock:
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
    def test_memory_load_start_accumulates(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        assert blocks == []

    def test_memory_load_success_emits_block(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        blocks = builder.on_trace_event(_make_event(
            stage="memory", step="load_success", payload={"count": 3},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "memory_load"
        assert blocks[0]["memory_load"]["count"] == 3
        assert blocks[0]["memory_load"]["injected"] is True

    def test_memory_inject_skip_emits_skip_status(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="memory", step="load_start"))
        blocks = builder.on_trace_event(_make_event(
            stage="memory", step="inject_skip", payload={"count": 0},
        ))
        assert blocks[0]["status"] == "skip"


class TestPromptBuildBlock:
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
    def test_error_event_emits_immediately(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        assert builder.on_trace_event(_make_event(
            stage="react", step="model_call_end", status="start",
        )) == []
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="model_call_end", status="error",
            payload={"error": "Rate limit exceeded"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "error"
        assert blocks[0]["error"]["message"] == "Rate limit exceeded"


class TestHilPauseBlock:
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
    def test_turn_done_emits_summary(self):
        builder = TraceBlockBuilder()
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
    def test_stream_request_received_emits_turn_start(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="stream", step="request_received", payload={"session_id": "s1"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"

    def test_stream_agent_created_emits_turn_start(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="stream", step="agent_created"))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"


class TestBlockStructure:
    def test_all_blocks_have_required_fields(self):
        builder = TraceBlockBuilder()
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
