"""
Task Orchestration v1.

本模块负责三件事：
1) TaskPlanner：将用户目标分解为可执行步骤，并做轻量上下文检索；
2) Replanner：当执行失败时，基于失败点追加恢复步骤；
3) TaskRuntimeStore：维护每个 session 的步骤状态机，提供运行时状态更新。

设计目标：
- 不替代 LangGraph 的 ReAct 主循环，而是补齐“任务级”控制面；
- 通过结构化 PlanState 提供可持久化/可观测的计划状态；
- 与现有工具系统解耦，避免侵入 Tool 实现细节。
"""

from __future__ import annotations

import copy
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.config import settings
from app.llm.factory import llm_factory

if TYPE_CHECKING:
    from langgraph.store.postgres import AsyncPostgresStore


class PlanStepStatus(StrEnum):
    """步骤状态机。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class PlanStep:
    """单个任务步骤。"""

    id: str
    title: str
    status: PlanStepStatus = PlanStepStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 1
    last_error: str | None = None


@dataclass
class PlanState:
    """任务计划状态。"""

    plan_id: str
    session_id: str
    user_goal: str
    complexity: str
    steps: list[PlanStep]
    retrieval_hits: list[str] = field(default_factory=list)
    current_step_index: int = -1
    replan_count: int = 0
    max_replans: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def clone(self) -> PlanState:
        """深拷贝，避免原对象被重规划函数原地修改。"""
        return copy.deepcopy(self)


class TaskPlanner:
    """
    任务分解器。

    说明：
    - P0 采用规则分解（可解释、可测试）；
    - 后续可替换为 LLM Planner，但输出协议保持不变，便于平滑升级。
    """

    _STOPWORDS = {
        "请",
        "然后",
        "最后",
        "并且",
        "以及",
        "我们",
        "需要",
        "这个",
        "那个",
        "进行",
        "然后再",
        "then",
        "and",
        "finally",
    }

    _SPLIT_PATTERN = re.compile(
        r"(?:先|然后|接着|再|最后|并且|以及|and then|then|finally|next|,|，|。|；|;|\n)+",
        flags=re.IGNORECASE,
    )

    _TOKEN_PATTERN = re.compile(r"[A-Za-z]{2,}|[\u4e00-\u9fff]+")

    def create_plan(
        self,
        *,
        session_id: str,
        user_goal: str,
        history: list[str] | None = None,
    ) -> PlanState:
        """
        创建计划。

        Args:
            session_id: 会话 ID（用于计划归属）
            user_goal: 用户目标原文
            history: 历史文本列表（用于轻量检索）
        """
        all_history = history or []
        retrieval_hits = self._retrieve_context_hints(
            user_goal=user_goal,
            history=all_history,
            limit=3,
        )

        # LLM 规划优先（llm/hybrid），失败自动回退规则规划。
        planner_mode = settings.task_planner_mode
        if planner_mode in {"llm", "hybrid"}:
            llm_plan = self._create_plan_with_llm(
                session_id=session_id,
                user_goal=user_goal,
                history=all_history,
                retrieval_hits=retrieval_hits,
            )
            if llm_plan is not None:
                return llm_plan

            logger.warning(
                "TaskPlanner: llm planning failed, fallback to rule planner "
                f"(mode={planner_mode}, session={session_id})"
            )

        segments = self._split_goal(user_goal)
        complexity = "complex" if len(segments) >= 3 else "simple"

        # 复杂任务强制至少 3 步，避免“只有一个大步骤”的伪计划。
        if complexity == "complex":
            segments = self._ensure_minimum_complex_steps(segments, user_goal)
        elif len(segments) == 0:
            segments = ["理解目标并执行"]

        steps = self._build_steps(segments)
        return PlanState(
            plan_id=f"plan_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            user_goal=user_goal,
            complexity=complexity,
            steps=steps,
            retrieval_hits=retrieval_hits,
        )

    def _split_goal(self, goal: str) -> list[str]:
        """将自然语言目标拆分为候选步骤。"""
        raw_parts = [p.strip() for p in self._SPLIT_PATTERN.split(goal) if p.strip()]

        # 过滤过短片段，避免把“再/然后”这类连词当成步骤。
        segments = [p for p in raw_parts if len(p) >= 2]

        # 如果规则拆分失败，保留整句为一个步骤。
        if not segments and goal.strip():
            return [goal.strip()]
        return segments

    def _ensure_minimum_complex_steps(self, segments: list[str], goal: str) -> list[str]:
        """
        复杂任务最少 3 步：
        1) 理解/检索
        2) 执行核心动作
        3) 汇总输出
        """
        normalized = list(segments)
        if len(normalized) >= 3:
            return normalized

        padded = normalized[:]
        if len(padded) == 1:
            padded = [
                "理解目标与约束",
                f"执行核心动作：{goal[:28]}",
                "整理结论并输出结果",
            ]
        elif len(padded) == 2:
            padded.append("整理结论并输出结果")
        return padded

    def _build_steps(self, segments: list[str]) -> list[PlanStep]:
        """将文本片段转为有依赖关系的步骤列表。"""
        steps: list[PlanStep] = []
        prev_id: str | None = None
        for idx, seg in enumerate(segments, start=1):
            step_id = f"step_{idx}_{uuid.uuid4().hex[:6]}"
            step = PlanStep(
                id=step_id,
                title=seg,
                status=PlanStepStatus.PENDING,
                depends_on=[prev_id] if prev_id else [],
                max_attempts=2,
            )
            steps.append(step)
            prev_id = step_id
        return steps

    def _keywords(self, text: str) -> set[str]:
        """抽取关键词，用于轻量检索打分。"""
        tokens: set[str] = set()
        for tok in self._TOKEN_PATTERN.findall(text):
            t = tok.lower().strip()
            if not t:
                continue
            # 英文 token 直接使用
            if re.fullmatch(r"[a-z]{2,}", t):
                tokens.add(t)
                continue

            # 中文 token：加入 2-gram / 3-gram，提升无分词场景的召回率。
            if re.fullmatch(r"[\u4e00-\u9fff]+", t):
                if len(t) <= 3:
                    tokens.add(t)
                else:
                    for n in (2, 3):
                        if len(t) < n:
                            continue
                        for i in range(0, len(t) - n + 1):
                            tokens.add(t[i : i + n])
                continue

            tokens.add(t)

        return {t for t in tokens if t and t not in self._STOPWORDS}

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        """从模型输出中提取第一个 JSON object。"""
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("No JSON object found in planner response")
        payload = json.loads(text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("Planner response is not a JSON object")
        return payload

    def _normalize_dep_indices(self, raw_depends: Any, step_index: int) -> list[int]:
        """
        依赖索引校验：
        - 只能依赖已出现的前序步骤（防环）
        - 非法索引忽略
        """
        if not isinstance(raw_depends, list):
            return []
        deps: list[int] = []
        for item in raw_depends:
            if isinstance(item, int) and 0 <= item < step_index:
                deps.append(item)
        # 去重并保持顺序
        seen: set[int] = set()
        uniq: list[int] = []
        for dep in deps:
            if dep in seen:
                continue
            seen.add(dep)
            uniq.append(dep)
        return uniq

    def _create_plan_with_llm(
        self,
        *,
        session_id: str,
        user_goal: str,
        history: list[str],
        retrieval_hits: list[str],
    ) -> PlanState | None:
        """
        通过 LLM 生成结构化计划。

        失败返回 None，由调用方回退规则规划。
        """
        try:
            llm = llm_factory()
            hint_history = retrieval_hits if retrieval_hits else history[-3:]
            context_text = "\n".join(hint_history)[:1800]

            system_prompt = (
                "你是任务规划器。输出严格 JSON，不要解释。"
                "Schema: {"
                "\"complexity\":\"simple|complex\","
                "\"steps\":[{\"title\":string,\"depends_on\":[int]}]"
                "}。"
                "规则：复杂任务至少 3 步；depends_on 只能引用前序步骤索引。"
            )
            human_prompt = (
                f"目标：{user_goal}\n\n"
                f"相关上下文：\n{context_text}\n\n"
                f"最大步骤数：{settings.task_planner_max_steps}"
            )

            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            )
            raw = response.content if isinstance(response.content, str) else str(response.content)
            payload = self._extract_json_object(raw)

            raw_steps = payload.get("steps", [])
            if not isinstance(raw_steps, list) or not raw_steps:
                raise ValueError("Planner response has no valid steps")

            max_steps = max(1, settings.task_planner_max_steps)
            raw_steps = raw_steps[:max_steps]

            steps: list[PlanStep] = []
            index_to_id: list[str] = []
            for idx, item in enumerate(raw_steps):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "")).strip()
                if not title:
                    continue

                step_id = f"step_{idx + 1}_{uuid.uuid4().hex[:6]}"
                dep_indices = self._normalize_dep_indices(item.get("depends_on", []), idx)
                step = PlanStep(
                    id=step_id,
                    title=title,
                    status=PlanStepStatus.PENDING,
                    depends_on=[],
                    max_attempts=2,
                )
                steps.append(step)
                index_to_id.append(step_id)

                # 第二轮映射前先暂存索引
                step.depends_on = [str(dep) for dep in dep_indices]

            if not steps:
                raise ValueError("Planner response produced zero usable steps")

            # 将 depends_on 从索引字符串映射为 step_id。
            for step in steps:
                dep_ids: list[str] = []
                for dep in step.depends_on:
                    dep_idx = int(dep)
                    if 0 <= dep_idx < len(index_to_id):
                        dep_ids.append(index_to_id[dep_idx])
                step.depends_on = dep_ids

            complexity_raw = str(payload.get("complexity", "")).strip().lower()
            complexity = complexity_raw if complexity_raw in {"simple", "complex"} else (
                "complex" if len(steps) >= 3 else "simple"
            )
            if complexity == "complex" and len(steps) < 3:
                # 复杂任务兜底补齐，避免 LLM 违规输出。
                tail = self._ensure_minimum_complex_steps([s.title for s in steps], user_goal)
                steps = self._build_steps(tail)

            return PlanState(
                plan_id=f"plan_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                user_goal=user_goal,
                complexity=complexity,
                steps=steps,
                retrieval_hits=retrieval_hits,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"TaskPlanner: llm plan generation failed: {exc}")
            return None

    def _retrieve_context_hints(
        self,
        *,
        user_goal: str,
        history: list[str],
        limit: int,
    ) -> list[str]:
        """
        从长历史中检索与目标最相关的证据片段。

        当前采用关键词重叠打分：
        - 优点：无需额外向量库，零依赖；
        - 局限：语义召回一般，后续可替换为 Embedding 检索。
        """
        if not history:
            return []

        goal_keywords = self._keywords(user_goal)
        if not goal_keywords:
            return []

        scored: list[tuple[int, int, str]] = []
        for idx, item in enumerate(history):
            item_text = item.strip()
            if not item_text:
                continue
            item_keywords = self._keywords(item_text)
            score = len(goal_keywords.intersection(item_keywords))
            # 第二关键字：索引越大越新，分值相同优先近历史。
            if score > 0:
                scored.append((score, idx, item_text))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item for _, _, item in scored[: max(1, limit)]]


class Replanner:
    """失败后重规划器。"""

    def __init__(self, max_replans: int = 1) -> None:
        self.max_replans = max(0, max_replans)

    def should_replan(self, plan: PlanState, error: str) -> bool:
        """判断当前计划是否还能重规划。"""
        _ = error  # 预留：后续可按错误类型做策略分流。
        return plan.replan_count < min(plan.max_replans, self.max_replans or plan.max_replans)

    def apply(self, *, plan: PlanState, failed_step_id: str | None, error: str) -> PlanState:
        """
        对失败计划做最小修复：
        - 标记失败步骤；
        - 在失败步骤后插入“重试/降级”恢复步骤；
        - 递增 replan_count。
        """
        if not self.should_replan(plan, error):
            return plan.clone()

        new_plan = plan.clone()
        new_plan.replan_count += 1
        new_plan.updated_at = time.time()

        failed_index = 0
        if failed_step_id:
            for idx, step in enumerate(new_plan.steps):
                if step.id == failed_step_id:
                    failed_index = idx
                    break

        failed_step = new_plan.steps[failed_index]
        failed_step.status = PlanStepStatus.FAILED
        failed_step.last_error = error

        recovery_step = PlanStep(
            id=f"step_recover_{uuid.uuid4().hex[:6]}",
            title=f"重试并降级执行：{failed_step.title}",
            status=PlanStepStatus.PENDING,
            depends_on=[failed_step.id],
            max_attempts=1,
        )
        new_plan.steps.insert(failed_index + 1, recovery_step)
        return new_plan


class TaskRuntimeStore:
    """
    运行时计划存储（按 session 维度）。

    说明：
    - 当前为进程内存实现，适用于单进程开发/测试；
    - 生产可替换为 Redis/Postgres，接口保持兼容。
    """

    def __init__(
        self,
        max_replans: int = 1,
        store: AsyncPostgresStore | None = None,
    ) -> None:
        self._plans: dict[str, PlanState] = {}
        self._replanner = Replanner(max_replans=max_replans)
        self.store = store
        self.namespace = ("task_plans",)

    @staticmethod
    def _serialize_step(step: PlanStep) -> dict[str, Any]:
        return {
            "id": step.id,
            "title": step.title,
            "status": step.status.value,
            "depends_on": list(step.depends_on),
            "attempts": step.attempts,
            "max_attempts": step.max_attempts,
            "last_error": step.last_error,
        }

    @staticmethod
    def _deserialize_step(raw: dict[str, Any]) -> PlanStep:
        status_raw = str(raw.get("status", PlanStepStatus.PENDING.value))
        try:
            status = PlanStepStatus(status_raw)
        except ValueError:
            status = PlanStepStatus.PENDING
        return PlanStep(
            id=str(raw.get("id", f"step_{uuid.uuid4().hex[:8]}")),
            title=str(raw.get("title", "未命名步骤")),
            status=status,
            depends_on=[str(x) for x in raw.get("depends_on", []) if str(x)],
            attempts=int(raw.get("attempts", 0)),
            max_attempts=max(1, int(raw.get("max_attempts", 1))),
            last_error=str(raw.get("last_error")) if raw.get("last_error") is not None else None,
        )

    def _serialize_plan(self, plan: PlanState) -> dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "session_id": plan.session_id,
            "user_goal": plan.user_goal,
            "complexity": plan.complexity,
            "steps": [self._serialize_step(s) for s in plan.steps],
            "retrieval_hits": list(plan.retrieval_hits),
            "current_step_index": plan.current_step_index,
            "replan_count": plan.replan_count,
            "max_replans": plan.max_replans,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    def _deserialize_plan(self, raw: dict[str, Any]) -> PlanState:
        return PlanState(
            plan_id=str(raw.get("plan_id", f"plan_{uuid.uuid4().hex[:12]}")),
            session_id=str(raw.get("session_id", "")),
            user_goal=str(raw.get("user_goal", "")),
            complexity=str(raw.get("complexity", "simple")),
            steps=[
                self._deserialize_step(x)
                for x in raw.get("steps", [])
                if isinstance(x, dict)
            ],
            retrieval_hits=[str(x) for x in raw.get("retrieval_hits", []) if str(x)],
            current_step_index=int(raw.get("current_step_index", -1)),
            replan_count=int(raw.get("replan_count", 0)),
            max_replans=max(0, int(raw.get("max_replans", 1))),
            created_at=float(raw.get("created_at", time.time())),
            updated_at=float(raw.get("updated_at", time.time())),
        )

    async def _persist_plan(self, session_id: str) -> None:
        if self.store is None:
            return
        plan = self._plans.get(session_id)
        if plan is None:
            return
        await self.store.aput(
            namespace=self.namespace,
            key=session_id,
            value=self._serialize_plan(plan),
        )

    async def aload_plan(self, session_id: str) -> PlanState | None:
        """
        从内存或持久化存储读取计划（优先内存）。
        """
        plan = self._plans.get(session_id)
        if plan is not None:
            return plan
        if self.store is None:
            return None
        item = await self.store.aget(namespace=self.namespace, key=session_id)
        if item is None:
            return None
        if not isinstance(item.value, dict):
            return None
        plan = self._deserialize_plan(item.value)
        self._plans[session_id] = plan
        return plan

    async def aset_plan(self, session_id: str, plan: PlanState) -> None:
        self.set_plan(session_id, plan)
        await self._persist_plan(session_id)

    def set_plan(self, session_id: str, plan: PlanState) -> None:
        """写入/覆盖 session 计划。"""
        self._plans[session_id] = plan

    def get_plan(self, session_id: str) -> PlanState | None:
        """读取 session 计划。"""
        return self._plans.get(session_id)

    def mark_next_step_running(self, session_id: str, tool_name: str | None = None) -> PlanStep | None:
        """
        将下一个 PENDING 步骤标记为 RUNNING。

        Args:
            session_id: 会话 ID
            tool_name: 当前触发该步骤的工具名（仅用于调试注释，不写入状态）
        """
        _ = tool_name
        plan = self._plans.get(session_id)
        if plan is None:
            return None

        for idx, step in enumerate(plan.steps):
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.RUNNING
                step.attempts += 1
                plan.current_step_index = idx
                plan.updated_at = time.time()
                return step
        return None

    async def amark_next_step_running(
        self, session_id: str, tool_name: str | None = None
    ) -> PlanStep | None:
        await self.aload_plan(session_id)
        step = self.mark_next_step_running(session_id, tool_name=tool_name)
        if step is not None:
            await self._persist_plan(session_id)
        return step

    def _get_running_step(self, plan: PlanState) -> PlanStep | None:
        for step in plan.steps:
            if step.status == PlanStepStatus.RUNNING:
                return step
        return None

    def mark_running_step_succeeded(self, session_id: str) -> PlanStep | None:
        """
        将当前 RUNNING 步骤标记为 SUCCEEDED。

        Raises:
            ValueError: 当前没有 RUNNING 步骤（非法状态迁移）
        """
        plan = self._plans.get(session_id)
        if plan is None:
            return None

        step = self._get_running_step(plan)
        if step is None:
            raise ValueError("No RUNNING step to mark as SUCCEEDED")

        step.status = PlanStepStatus.SUCCEEDED
        plan.updated_at = time.time()
        return step

    async def amark_running_step_succeeded(self, session_id: str) -> PlanStep | None:
        await self.aload_plan(session_id)
        step = self.mark_running_step_succeeded(session_id)
        if step is not None:
            await self._persist_plan(session_id)
        return step

    def mark_running_step_failed(self, session_id: str, error: str) -> PlanStep | None:
        """
        将当前 RUNNING 步骤标记为 FAILED。

        Raises:
            ValueError: 当前没有 RUNNING 步骤（非法状态迁移）
        """
        plan = self._plans.get(session_id)
        if plan is None:
            return None

        step = self._get_running_step(plan)
        if step is None:
            raise ValueError("No RUNNING step to mark as FAILED")

        step.status = PlanStepStatus.FAILED
        step.last_error = error
        plan.updated_at = time.time()
        return step

    async def amark_running_step_failed(self, session_id: str, error: str) -> PlanStep | None:
        await self.aload_plan(session_id)
        step = self.mark_running_step_failed(session_id, error)
        if step is not None:
            await self._persist_plan(session_id)
        return step

    def mark_plan_completed(self, session_id: str) -> PlanState | None:
        """
        将剩余 PENDING 步骤补齐为 SUCCEEDED。

        用途：某些短路径没有显式 tool_start/tool_result 事件时，保证计划能收敛。
        """
        plan = self._plans.get(session_id)
        if plan is None:
            return None
        for step in plan.steps:
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.SUCCEEDED
        plan.updated_at = time.time()
        return plan

    async def amark_plan_completed(self, session_id: str) -> PlanState | None:
        await self.aload_plan(session_id)
        plan = self.mark_plan_completed(session_id)
        if plan is not None:
            await self._persist_plan(session_id)
        return plan

    def should_replan(self, session_id: str, error: str) -> bool:
        """对外暴露重规划触发判断。"""
        plan = self._plans.get(session_id)
        if plan is None:
            return False
        return self._replanner.should_replan(plan, error)

    async def ashould_replan(self, session_id: str, error: str) -> bool:
        plan = await self.aload_plan(session_id)
        if plan is None:
            return False
        return self._replanner.should_replan(plan, error)

    def apply_replan(self, session_id: str, error: str) -> dict[str, Any]:
        """执行重规划并返回摘要。"""
        plan = self._plans.get(session_id)
        if plan is None:
            return {"updated": False, "reason": "plan_not_found"}

        failed_step_id: str | None = None
        running = self._get_running_step(plan)
        if running is not None:
            running.status = PlanStepStatus.FAILED
            running.last_error = error
            failed_step_id = running.id
        else:
            # 若无 RUNNING，则取最近一个 FAILED 步骤。
            for step in reversed(plan.steps):
                if step.status == PlanStepStatus.FAILED:
                    failed_step_id = step.id
                    break

        old_count = len(plan.steps)
        new_plan = self._replanner.apply(
            plan=plan,
            failed_step_id=failed_step_id,
            error=error,
        )
        self._plans[session_id] = new_plan
        return {
            "updated": True,
            "plan_id": new_plan.plan_id,
            "replan_count": new_plan.replan_count,
            "old_step_count": old_count,
            "new_step_count": len(new_plan.steps),
            "failed_step_id": failed_step_id,
        }

    async def aapply_replan(self, session_id: str, error: str) -> dict[str, Any]:
        await self.aload_plan(session_id)
        summary = self.apply_replan(session_id, error)
        if summary.get("updated"):
            await self._persist_plan(session_id)
        return summary


def evaluate_long_context_cases(
    *,
    planner: TaskPlanner,
    cases: list[dict[str, Any]],
    baseline_window: int = 3,
) -> dict[str, float]:
    """
    评估“长上下文成功率对比基线提升”。

    baseline:
      - 只取最近 baseline_window 条历史
      - 不做相关性检索
    planner:
      - 使用 TaskPlanner 的关键词相关检索
    """
    if not cases:
        return {"baseline_success_rate": 0.0, "planner_success_rate": 0.0}

    baseline_success = 0
    planner_success = 0

    for idx, case in enumerate(cases):
        goal = str(case.get("goal", ""))
        history = [str(x) for x in case.get("history", [])]
        expected_keywords = [str(x) for x in case.get("expected_keywords", []) if str(x)]

        baseline_text = "\n".join(history[-baseline_window:])
        if any(k in baseline_text for k in expected_keywords):
            baseline_success += 1

        plan = planner.create_plan(
            session_id=f"eval_{idx}",
            user_goal=goal,
            history=history,
        )
        planner_text = "\n".join(plan.retrieval_hits)
        if any(k in planner_text for k in expected_keywords):
            planner_success += 1

    total = float(len(cases))
    return {
        "baseline_success_rate": baseline_success / total,
        "planner_success_rate": planner_success / total,
    }
