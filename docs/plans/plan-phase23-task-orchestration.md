# Phase 23 — Task Orchestration v1（Planner / Replanner / Retrieval）

## 目标

从“仅 ReAct + 工具调用”升级到“任务级控制闭环”：

1. 引入 Task Planner（任务分解 + 步骤状态机）
2. 工具失败触发 Replan（不是直接报错结束）
3. 长上下文任务具备检索增强，并通过基线对比验证提升
4. 前端 Execution Trace 可见 planning/retrieval/replanning 全链路

## 架构文档参考

- `docs/arch/tools-v12.md` §1.3（执行层）+ §1.4（Task Orchestration v1 增量）
- `docs/arch/agent-v13.md` §1.12（Executor Workflow）+ §1.13（HIL）
- `docs/arch/prompt-context-v20.md` §1.2（Context Window）+ §1.4（组装时序）

## 测试用例清单（TDD 先写）

### TaskPlanner 分解/检索
- [x] 复杂任务（>=3步）应拆分为 >=3 个步骤
- [x] 历史检索应命中与目标相关证据
- [x] LLM 结构化规划输出可被解析并执行
- [x] LLM 输出异常时自动回退规则规划

### TaskRuntimeStore 状态机
- [x] `pending -> running -> succeeded` 正常迁移
- [x] 非法迁移（无 RUNNING 直接 succeeded）抛错

### Replanner 自愈
- [x] 失败后应追加恢复步骤并递增 `replan_count`
- [x] `_execute_agent` 首次失败后应触发 replan 并重试成功

### TaskRuntimeStore 持久化
- [x] 计划可写入 Postgres Store（`task_plans` namespace）
- [x] 新 runtime 实例可恢复既有计划状态
- [x] 步骤状态迁移后自动落盘

### 长上下文基线对比
- [x] Planner 成功率应高于 baseline
- [x] 成功率提升幅度至少 20%

### 前端可视化
- [x] `TraceBlockBuilder` 生成 `planning/retrieval/replanning` 块
- [x] `ExecutionTracePanel` 回归通过（不破坏现有展示）

## 实现步骤（TDD 顺序）

### Step 1 — RED
- 新增 Planner/Replanner/长上下文对比/执行重规划测试并确认失败

### Step 2 — GREEN（后端）
- 新增 `backend/app/planner/orchestrator.py`
- 在 `chat.py` 注入计划创建、步骤迁移、失败重规划与重试
- 新增 `task_planner_mode`（rule/llm/hybrid）与 `task_planner_max_steps`

### Step 3 — GREEN（可观测 + 前端）
- `trace_block.py` 新增三类任务块映射
- 前端 trace 类型与卡片渲染支持新块

### Step 4 — 回归
- 运行后端单测/集成 + 前端组件测试

## 完成标准

- [x] Planner / Replanner / Retrieval 后端闭环可用
- [x] 工具失败触发 replan 并可自愈（测试可复现）
- [x] 长上下文成功率对比 baseline 有提升
- [x] 前端可见新执行链路块
- [x] `tools-v12.md` 已同步新增架构章节
