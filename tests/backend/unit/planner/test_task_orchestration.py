"""
Task Orchestration v1 单元测试（TDD RED 阶段）。

目标：
1) 复杂任务（>=3 步）可被正确分解
2) 失败后能触发重规划
3) 任务步骤状态机严格可控
4) 长上下文检索可返回相关证据
"""
from __future__ import annotations

from unittest.mock import MagicMock

import app.planner.orchestrator as orchestrator_module
from app.planner.orchestrator import (
    PlanStepStatus,
    Replanner,
    TaskPlanner,
    TaskRuntimeStore,
)


class TestTaskPlannerDecomposition:
    """TaskPlanner.create_plan() — 任务分解能力。"""

    def test_complex_goal_should_split_into_three_or_more_steps(self) -> None:
        """复杂目标应被拆成 >=3 个步骤。"""
        planner = TaskPlanner()

        plan = planner.create_plan(
            session_id="s1",
            user_goal="先检索本周合同风险，再汇总重点条款，最后输出执行建议并给出后续动作",
            history=[],
        )

        assert plan.complexity == "complex"
        assert len(plan.steps) >= 3
        assert all(step.status == PlanStepStatus.PENDING for step in plan.steps)

    def test_retrieval_should_return_relevant_history_hits(self) -> None:
        """历史检索应优先返回与当前目标相关的证据。"""
        planner = TaskPlanner()
        history = [
            "今天讨论的是前端配色",
            "合同里有自动续约条款风险",
            "法务建议增加违约责任上限",
            "晚饭吃什么",
        ]

        plan = planner.create_plan(
            session_id="s2",
            user_goal="分析合同风险并汇总法务建议",
            history=history,
        )

        assert len(plan.retrieval_hits) >= 1
        assert any("合同" in hit or "法务" in hit for hit in plan.retrieval_hits)


class TestTaskRuntimeStateMachine:
    """TaskRuntimeStore — 步骤状态机能力。"""

    def test_step_transition_should_follow_pending_running_succeeded(self) -> None:
        """步骤状态迁移应严格遵循状态机。"""
        planner = TaskPlanner()
        store = TaskRuntimeStore()

        plan = planner.create_plan(
            session_id="s3",
            user_goal="先检索数据，再整理，再输出",
            history=[],
        )
        store.set_plan("s3", plan)

        running = store.mark_next_step_running("s3", tool_name="web_search")
        assert running is not None
        assert running.status == PlanStepStatus.RUNNING

        done = store.mark_running_step_succeeded("s3")
        assert done is not None
        assert done.status == PlanStepStatus.SUCCEEDED

    def test_invalid_transition_should_raise(self) -> None:
        """未进入 RUNNING 的步骤不允许直接置为 SUCCEEDED。"""
        planner = TaskPlanner()
        store = TaskRuntimeStore()
        plan = planner.create_plan(
            session_id="s4",
            user_goal="先查再写再发",
            history=[],
        )
        store.set_plan("s4", plan)

        try:
            store.mark_running_step_succeeded("s4")
        except ValueError as exc:
            assert "RUNNING" in str(exc)
            return
        raise AssertionError("Expected ValueError for invalid transition")


class TestReplanner:
    """Replanner — 失败后的计划修复能力。"""

    def test_replanner_should_append_recovery_step_after_failure(self) -> None:
        """失败后应追加恢复步骤，并增加 replan_count。"""
        planner = TaskPlanner()
        replanner = Replanner(max_replans=2)
        plan = planner.create_plan(
            session_id="s5",
            user_goal="先查合同，再总结，再发送",
            history=[],
        )

        # 模拟第一步失败
        plan.steps[0].status = PlanStepStatus.FAILED
        plan.steps[0].last_error = "search timeout"

        new_plan = replanner.apply(
            plan=plan,
            failed_step_id=plan.steps[0].id,
            error="search timeout",
        )

        assert new_plan.replan_count == 1
        assert len(new_plan.steps) >= len(plan.steps)
        assert any("重试" in step.title or "降级" in step.title for step in new_plan.steps)


class TestTaskPlannerLLM:
    """LLM 规划与回退策略。"""

    def test_llm_planner_should_use_structured_plan_when_valid(self, monkeypatch) -> None:
        planner = TaskPlanner()

        class FakeResp:
            content = (
                '{"complexity":"complex","steps":['
                '{"title":"检索合同风险","depends_on":[]},'
                '{"title":"归纳法务建议","depends_on":[0]},'
                '{"title":"输出结论","depends_on":[1]}]}'
            )

        fake_llm = MagicMock()
        fake_llm.invoke.return_value = FakeResp()

        monkeypatch.setattr(orchestrator_module.settings, "task_planner_mode", "llm")
        monkeypatch.setattr(orchestrator_module, "llm_factory", lambda: fake_llm)

        plan = planner.create_plan(
            session_id="s_llm_1",
            user_goal="分析合同风险并输出建议",
            history=["合同第12条有争议风险"],
        )

        assert plan.complexity == "complex"
        assert len(plan.steps) == 3
        assert plan.steps[0].title == "检索合同风险"
        assert plan.steps[1].depends_on == [plan.steps[0].id]
        assert plan.steps[2].depends_on == [plan.steps[1].id]

    def test_llm_planner_should_fallback_to_rule_on_invalid_json(
        self, monkeypatch
    ) -> None:
        planner = TaskPlanner()

        class BadResp:
            content = "not-json-response"

        fake_llm = MagicMock()
        fake_llm.invoke.return_value = BadResp()

        monkeypatch.setattr(orchestrator_module.settings, "task_planner_mode", "llm")
        monkeypatch.setattr(orchestrator_module, "llm_factory", lambda: fake_llm)

        plan = planner.create_plan(
            session_id="s_llm_2",
            user_goal="先检索再总结最后给建议",
            history=[],
        )

        # 回退规则规划后应仍返回可执行计划。
        assert len(plan.steps) >= 1
        assert all(step.status == PlanStepStatus.PENDING for step in plan.steps)
