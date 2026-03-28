"""Unit tests for TraceBlockBuilder."""
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

    def test_model_call_end_has_nonempty_detail(self):
        """Bug 3 fix: model_call_end should produce meaningful detail."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder._pending_payload["tool_count"] = 0
        builder._pending_payload["content_preview"] = "some preview"
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        assert blocks[0]["detail"] == "生成回答中"
        assert blocks[0]["thinking"]["content_preview"] == "some preview"

    def test_model_call_end_with_tools_has_detail(self):
        """Bug 3 fix: model_call_end with tool_calls should show tool count."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder._pending_payload["tool_count"] = 2
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        assert blocks[0]["detail"] == "决定调用 2 个工具"

    def test_thought_emitted_does_not_emit_second_block(self):
        """When model_call_end already emitted the block, thought_emitted should skip."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        blocks_from_end = builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        assert len(blocks_from_end) == 1
        blocks_from_thought = builder.on_trace_event(_make_event(stage="react", step="thought_emitted", payload={"chars": 120}))
        assert blocks_from_thought == []

    def test_thought_emitted_carries_content_preview(self):
        """Bug 2 fix: thought_emitted should pass content_preview to block."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="thought_emitted",
            payload={"chars": 200, "content_preview": "Python async/await allows..."},
        ))
        assert len(blocks) == 1
        assert blocks[0]["thinking"]["content_preview"] == "Python async/await allows..."

    def test_thinking_block_has_duration_ms(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        assert blocks[0]["duration_ms"] >= 0

    def test_thinking_block_includes_content_preview(self):
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        blocks = builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
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

    def test_multiple_tool_calls_queue_correctly(self):
        """Bug 5 fix: multiple tool_call_planned should queue and match results in order."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "web_search", "args": {"query": "A"}},
        ))
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "calculator", "args": {"expr": "1+1"}},
        ))
        # Only first planned, no block yet
        assert builder._pending_type == "tool_call"

        block1 = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "A result", "content_length": 10},
        ))
        assert len(block1) == 1
        assert block1[0]["tool_call"]["name"] == "web_search"

        block2 = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "2", "content_length": 1},
        ))
        assert len(block2) == 1
        assert block2[0]["tool_call"]["name"] == "calculator"

    def test_tool_call_result_without_planned_ignored(self):
        """Bug 5 fix: tool_call_result with no planned tools should be ignored."""
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "orphan result", "content_length": 5},
        ))
        assert blocks == []


class TestAnswerBlock:
    def test_answer_emitted_creates_answer_block(self):
        """Bug 4 fix: answer_emitted should create an answer block."""
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="answer_emitted",
            payload={"chars": 350, "content_preview": "Python async programming is..."},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "answer"
        assert blocks[0]["answer"]["content_preview"] == "Python async programming is..."
        assert blocks[0]["answer"]["char_count"] == 350
        assert "350 字符" in blocks[0]["detail"]


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
    def test_token_update_emits_prompt_build_once(self):
        """Bug 6 fix: first token_update emits prompt_build, subsequent are skipped."""
        builder = TraceBlockBuilder()
        blocks1 = builder.on_trace_event(_make_event(
            stage="context", step="token_update",
            payload={"current": 5000, "budget": 32000},
        ))
        assert len(blocks1) == 1
        assert blocks1[0]["type"] == "prompt_build"

        # Second token_update should NOT emit another prompt_build
        blocks2 = builder.on_trace_event(_make_event(
            stage="context", step="token_update",
            payload={"current": 8000, "budget": 32000},
        ))
        assert blocks2 == []

    def test_prompt_build_resets_after_turn_done(self):
        """Bug 6 fix: prompt_build flag resets after turn_done."""
        builder = TraceBlockBuilder()
        builder.on_trace_event(_make_event(
            stage="context", step="token_update",
            payload={"current": 5000, "budget": 32000},
        ))
        # Reset via turn_done
        builder.on_trace_event(_make_event(stage="react", step="turn_done"))
        # Next turn should emit prompt_build again
        blocks = builder.on_trace_event(_make_event(
            stage="context", step="token_update",
            payload={"current": 3000, "budget": 32000},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "prompt_build"


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
    def test_react_turn_start_emits_block(self):
        """Bug 1 fix: react/turn_start should emit turn_start block."""
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="react", step="turn_start",
            payload={"messages": 5},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"
        assert "消息历史 5 条" in blocks[0]["detail"]

    def test_stream_request_received_emits_turn_start(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(
            stage="stream", step="request_received", payload={"session_id": "s1"},
        ))
        assert len(blocks) == 1
        assert blocks[0]["type"] == "turn_start"

    def test_stream_agent_created_skipped(self):
        """Fix 1: agent_created and stream_started should be skipped to avoid duplicates."""
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="stream", step="agent_created"))
        assert blocks == []

    def test_stream_started_skipped(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(_make_event(stage="stream", step="stream_started"))
        assert blocks == []


class TestBlockStructure:
    def test_all_blocks_have_required_fields(self):
        builder = TraceBlockBuilder()
        all_blocks = []
        all_blocks.extend(builder.on_trace_event(_make_event(stage="react", step="turn_start", payload={"messages": 3})))
        builder.on_trace_event(_make_event(stage="react", step="model_call_start", status="start"))
        builder.on_trace_event(_make_event(stage="react", step="model_call_end"))
        all_blocks.extend(builder.on_trace_event(_make_event(
            stage="react", step="thought_emitted", payload={"chars": 50, "content_preview": "test content"},
        )))
        builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_planned", status="start",
            payload={"tool_name": "test", "args": {}},
        ))
        all_blocks.extend(builder.on_trace_event(_make_event(
            stage="tools", step="tool_call_result", status="ok",
            payload={"content_preview": "ok", "content_length": 2},
        )))
        all_blocks.extend(builder.on_trace_event(_make_event(
            stage="react", step="answer_emitted",
            payload={"chars": 100, "content_preview": "answer"},
        )))
        all_blocks.extend(builder.on_trace_event(_make_event(stage="react", step="turn_done")))

        for block in all_blocks:
            assert "id" in block, f"Block missing id: {block}"
            assert "timestamp" in block, f"Block missing timestamp: {block}"
            assert "type" in block, f"Block missing type: {block}"
            assert "status" in block, f"Block missing status: {block}"
            assert "duration_ms" in block, f"Block missing duration_ms: {block}"
            assert isinstance(block["duration_ms"], int), f"duration_ms not int in {block}"


class TestPlannerBlocks:
    def test_plan_created_emits_planning_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(
            _make_event(
                stage="planner",
                step="plan_created",
                payload={"plan_id": "p1", "step_count": 3, "complexity": "complex"},
            )
        )
        assert len(blocks) == 1
        assert blocks[0]["type"] == "planning"
        assert "3 步" in blocks[0]["detail"]

    def test_context_retrieved_emits_retrieval_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(
            _make_event(stage="retrieval", step="context_retrieved", payload={"hits": 2})
        )
        assert len(blocks) == 1
        assert blocks[0]["type"] == "retrieval"
        assert blocks[0]["retrieval"]["hits"] == 2

    def test_step_running_emits_pending_planning_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(
            _make_event(
                stage="planner",
                step="step_running",
                payload={"step_id": "s1", "title": "检索合同风险"},
            )
        )
        assert len(blocks) == 1
        assert blocks[0]["type"] == "planning"
        assert blocks[0]["status"] == "pending"
        assert "执行步骤中" in blocks[0]["detail"]

    def test_step_succeeded_emits_ok_planning_block(self):
        builder = TraceBlockBuilder()
        blocks = builder.on_trace_event(
            _make_event(
                stage="planner",
                step="step_succeeded",
                payload={"step_id": "s1", "title": "检索合同风险"},
            )
        )
        assert len(blocks) == 1
        assert blocks[0]["type"] == "planning"
        assert blocks[0]["status"] == "ok"
        assert "步骤完成" in blocks[0]["detail"]

    def test_replanner_events_emit_replanning_blocks(self):
        builder = TraceBlockBuilder()
        triggered = builder.on_trace_event(
            _make_event(
                stage="replanner",
                step="triggered",
                status="start",
                payload={"attempt": 1, "error": "timeout"},
            )
        )
        updated = builder.on_trace_event(
            _make_event(
                stage="replanner",
                step="plan_updated",
                payload={"old_step_count": 3, "new_step_count": 4, "replan_count": 1},
            )
        )
        assert len(triggered) == 1
        assert len(updated) == 1
        assert triggered[0]["type"] == "replanning"
        assert updated[0]["type"] == "replanning"
        assert updated[0]["status"] == "ok"
