"""
TaskRuntimeStore 持久化测试。

验证目标：
1) aset_plan 后可跨 runtime 实例恢复；
2) 步骤状态迁移会同步落盘。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.planner.orchestrator import PlanStepStatus, TaskPlanner, TaskRuntimeStore


@dataclass
class _StoredRecord:
    value: dict[str, Any]


class _FakeAsyncStore:
    """最小 AsyncPostgresStore 替身。"""

    def __init__(self) -> None:
        self._db: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}

    async def aput(self, namespace: tuple[str, ...], key: str, value: dict[str, Any]) -> None:
        self._db[(namespace, key)] = value

    async def aget(self, namespace: tuple[str, ...], key: str) -> Any:
        value = self._db.get((namespace, key))
        if value is None:
            return None
        return _StoredRecord(value=value)


class TestTaskRuntimeStorePersistence:
    @pytest.mark.asyncio
    async def test_aset_plan_should_be_loadable_from_another_runtime(self) -> None:
        store = _FakeAsyncStore()
        planner = TaskPlanner()

        runtime_a = TaskRuntimeStore(store=store)
        plan = planner.create_plan(
            session_id="persist_s1",
            user_goal="先检索合同再总结",
            history=["合同第12条有争议"],
        )
        await runtime_a.aset_plan("persist_s1", plan)

        runtime_b = TaskRuntimeStore(store=store)
        loaded = await runtime_b.aload_plan("persist_s1")

        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.user_goal == plan.user_goal
        assert len(loaded.steps) == len(plan.steps)

    @pytest.mark.asyncio
    async def test_step_status_transition_should_persist(self) -> None:
        store = _FakeAsyncStore()
        planner = TaskPlanner()
        runtime = TaskRuntimeStore(store=store)

        plan = planner.create_plan(
            session_id="persist_s2",
            user_goal="先查后写",
            history=[],
        )
        await runtime.aset_plan("persist_s2", plan)

        running = await runtime.amark_next_step_running("persist_s2", tool_name="web_search")
        assert running is not None
        assert running.status == PlanStepStatus.RUNNING

        succeeded = await runtime.amark_running_step_succeeded("persist_s2")
        assert succeeded is not None
        assert succeeded.status == PlanStepStatus.SUCCEEDED

        fresh_runtime = TaskRuntimeStore(store=store)
        reloaded = await fresh_runtime.aload_plan("persist_s2")
        assert reloaded is not None
        assert reloaded.steps[0].status == PlanStepStatus.SUCCEEDED
