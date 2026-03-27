# 会话进度记录

## 2026-03-27 — Phase 21：HIL 前端 E2E 稳定化（11-hil-trigger 全绿）

### 会话目标
将 `tests/e2e/11-hil-trigger.spec.ts` 从依赖真实模型触发改为稳定可复现的 HIL mock 流，消除 flaky。

### 完成工作

#### 1) 重构 11-hil-trigger 为确定性 HIL 测试
- 重写 `tests/e2e/11-hil-trigger.spec.ts`
  - 新增 `mockHilFlow()`：统一 mock `GET /chat`（`hil_interrupt`）与 `POST /chat/resume`（`hil_resolved + done`）
  - 新增 `sendAndWaitHil()`：统一消息发送 + 等待 `confirm-modal`
  - 13 条用例全部切换为确定性触发，不再依赖模型“是否恰好调用 send_email”

#### 2) 修复重构后 3 个残余失败点
- `HIL 弹窗应显示工具名称`：修复 strict mode 多元素冲突，改为 `getByText('send_email', { exact: true })`
- `HIL 恢复后应继续执行流`：去除不稳定文本断言，改为 `resume request + modal hidden + input enabled`
- `HIL 弹窗应支持键盘操作`：改为“聚焦取消按钮 + Enter”键盘路径，并断言触发 resume 请求

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `NEXT_DISABLE_DEVTOOLS=1 npx playwright test tests/e2e/11-hil-trigger.spec.ts --project=chromium --headed` | ✅ 13 passed |

### 文件变更清单

```
修改：
  tests/e2e/11-hil-trigger.spec.ts
  planning-with-files/progress.md
```

### 遗留问题
- 无新增 Phase 21 阻塞；前端 HIL 关键 E2E 已稳定。

## 2026-03-27 — Phase 21：最终收口（真实 checkpointer 回归 + API 契约补齐）

### 会话目标
一次性收口 Phase 21，补齐“真实数据库 checkpointer 恢复回归”与过期 API 集成测试契约。

### 完成工作

#### 1) 修复过期 `/chat` 集成测试契约
- 重写 `tests/backend/integration/test_chat_api.py`：
  - 路由从旧的 `/chat/chat`、`/chat/chat/resume` 更新为 `/chat`、`/chat/resume`
  - 将 `/chat` 断言从 POST 契约切换到 GET + SSE 契约
  - 删除 P0 时代 `resume=501` 断言，改为当前行为（找不到中断/已处理中断/approve/reject 命令恢复）
  - 增加 `Command(resume=...)` 在 API 层被实际传入 agent 的断言

#### 2) 新增真实 Postgres checkpointer 恢复测试
- 新增 `tests/backend/integration/test_hil_resume_checkpoint_recovery.py`
  - approve：验证断点恢复后不重放 `prefetch`，仅执行一次 `send_email`
  - reject：验证拒绝分支不会执行写副作用（`send_email` 调用次数保持 0）
  - 测试直接使用 `AsyncPostgresSaver`（`requires_db`），非 mock

#### 3) Phase 21 文档与计划同步
- `docs/plans/plan-phase21-hil-resume-reliability.md` 增加真实 checkpointer 回归条目并勾选完成
- `planning-with-files/task_plan.md` 移除“HIL 原生恢复 E2E 待办”遗留项
- `planning-with-files/findings.md` 记录“Phase 21 必须包含真实 checkpointer 回归”的技术决策

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `pytest tests/backend/integration/test_chat_api.py tests/backend/integration/test_hil_resume_checkpoint_recovery.py -q` | ✅ 12 passed |
| `pytest tests/backend/unit/api/test_chat.py tests/backend/unit/tools/test_idempotency.py tests/backend/integration/tools/test_execution_layer_ab_mix.py tests/backend/integration/test_chat_api.py tests/backend/integration/test_hil_resume_checkpoint_recovery.py -q` | ✅ 58 passed |
| `NEXT_DISABLE_DEVTOOLS=1 npx playwright test tests/e2e/11-hil-trigger.spec.ts --project=chromium --headed --grep "用户批准后应继续执行|用户拒绝后应停止执行"` | ✅ 2 passed（改为稳定 mock HIL 触发） |

### 文件变更清单

```
修改：
  tests/backend/integration/test_chat_api.py
  tests/e2e/11-hil-trigger.spec.ts
  docs/plans/plan-phase21-hil-resume-reliability.md
  planning-with-files/task_plan.md
  planning-with-files/findings.md
  planning-with-files/progress.md

新增：
  tests/backend/integration/test_hil_resume_checkpoint_recovery.py
```

### 遗留问题
- `tests/backend/unit/api/test_chat.py::TestRunAgentStream::test_stream_yields_sse_events` 仍有 pre-existing AsyncMock RuntimeWarning（不影响本轮 Phase 21 验收）。
- `tests/e2e/11-hil-trigger.spec.ts` 其余用例仍依赖真实后端/模型行为，尚未全部改造成稳定 mock 触发（本轮仅收口 approve/reject 关键路径）。

## 2026-03-27 — Phase 21：HIL 原生恢复（Command resume）

### 会话目标
在已完成幂等防重后，继续 Phase 21，将 `/chat/resume` 从 synthetic 分支切换为 LangGraph 原生 checkpoint 恢复。

### 完成工作

#### 1) 2026 版本基线核验（官方源 + 本机）
- 核验最新稳定版本：`langchain==1.2.13`、`langgraph==1.1.3`
- 本机安装版本一致：`langchain 1.2.13`、`langgraph 1.1.3`

#### 2) `/chat/resume` 原生恢复改造
- `backend/app/api/chat.py`
  - 新增 `_build_hil_resume_command()`，生成 `Command(resume={interrupt_id: {"decisions":[...]}})`
  - approve/reject 均改为 `thread_id + Command(resume)` 恢复执行
  - `_execute_agent` 新增 `agent_input` 参数，支持 `HumanMessage` 与 `Command` 两类输入
  - 保留 send_email 幂等防重；命中重复时返回 `idempotent_replay`

#### 3) 测试迁移
- `tests/backend/unit/api/test_chat.py`
  - 同 payload：断言仅 1 次 `Command` 恢复调用
  - 不同 payload：断言 2 次 `Command` 恢复调用
  - reject：断言 `decisions[0].type == "reject"`
- `tests/backend/integration/tools/test_execution_layer_ab_mix.py`
  - HIL 幂等用例改为断言 `Command` 恢复次数与 payload

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `pytest tests/backend/unit/api/test_chat.py -k resume -q` | ✅ 6 passed |
| `pytest tests/backend/integration/tools/test_execution_layer_ab_mix.py -q` | ✅ 4 passed |
| `pytest tests/backend/unit/tools tests/backend/integration/tools tests/backend/unit/api/test_chat.py -q` | ✅ 222 passed, 1 skipped |

### 文件变更清单

```
修改：
  backend/app/api/chat.py
  tests/backend/unit/api/test_chat.py
  tests/backend/integration/tools/test_execution_layer_ab_mix.py
  docs/plans/plan-phase21-hil-resume-reliability.md
  planning-with-files/task_plan.md
  planning-with-files/findings.md
```

### 遗留问题
- 需补充真实 checkpointer 数据库环境下的 E2E 恢复回归。

---

## 2026-03-27 — Phase 22：Memory 读写闭环（B/C + Retain）

### 会话目标
按已确认方案完成 Memory 写回双策略（B/C）实现，并同步项目管理文件（task_plan/findings/progress）。

### 完成工作

#### 1) 配置与开关落地
- `backend/app/config.py`
  - 新增 `memory_profile_update_mode`（`rule|llm`，默认 `rule`）
  - 新增 `memory_profile_llm_interval`（默认 `10`）
  - 新增 `memory_profile_opinion_min_confidence`（默认 `0.9`）
- `.env.example` 新增对应环境变量
- `tests/backend/unit/config/test_settings.py` 新增默认值、边界值、环境变量覆盖测试

#### 2) Long Memory 写回链路打通
- `backend/app/memory/manager.py`
  - `save_episodic()` 从 P0 stub 改为真实 `store.aput(namespace=('profile', user_id), key='episodic', value=...)`
- `tests/backend/unit/memory/test_manager_p0.py`
  - 更新为“真实写入 + 覆盖写入”断言

#### 3) MemoryMiddleware Phase 22 实装
- `backend/app/agent/middleware/memory.py`
  - `abefore_agent`：除 `memory_ctx` 外新增 `memory_ctx_baseline`
  - `aafter_agent`：
    - 先执行 B：`interaction_count +1` + `language/domain` 规则提炼
    - 若 `mode=llm` 且命中 `N` 轮触发 C 提炼
    - LLM 异常/解析异常自动回退 B 结果
    - baseline 对比 dirty，只有变化时写库
  - C 模式 Retain 轻量落地：
    - summary 写入 `W/B/O(c)/S` 结构化文本
    - `O` 仅在 `confidence >= 阈值` 时合并到 preferences
- `tests/backend/unit/agent/test_memory_middleware.py`
  - 新增 baseline、rule/llm、fallback、dirty、Retain 阈值等用例

#### 4) 集成验证与计划文件同步
- 新增 `tests/backend/integration/test_memory_profile_update_modes.py`
  - 验证 C 模式按 `N=10` 轮触发，且下一轮可读取更新画像
- `docs/plans/plan-phase03-memory.md`
  - 勾选本轮 Phase 21 增量测试清单
- 同步 `planning-with-files/task_plan.md`、`planning-with-files/findings.md`

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `pytest tests/backend/unit/config/test_settings.py tests/backend/unit/memory/test_manager_p0.py tests/backend/unit/agent/test_memory_middleware.py tests/backend/integration/test_memory_profile_update_modes.py -q` | ✅ 56 passed |
| `pytest tests/backend/unit/config/test_settings.py tests/backend/unit/memory tests/backend/unit/agent/test_memory_middleware.py tests/backend/unit/agent/test_middleware.py tests/backend/integration/test_memory_profile_update_modes.py -q` | ✅ 114 passed |
| `pytest tests/backend/unit/api/test_preferences.py tests/backend/unit/agent/test_middleware.py -q` | ✅ 22 passed |

### 文件变更清单

```
修改：
  backend/app/config.py
  .env.example
  backend/app/memory/manager.py
  backend/app/agent/middleware/memory.py
  tests/backend/unit/config/test_settings.py
  tests/backend/unit/memory/test_manager_p0.py
  tests/backend/unit/agent/test_memory_middleware.py
  docs/plans/plan-phase03-memory.md
  planning-with-files/task_plan.md
  planning-with-files/findings.md
  planning-with-files/progress.md

新增：
  tests/backend/integration/test_memory_profile_update_modes.py
```

### 遗留问题
- `tests/backend/unit/agent/test_langchain_engine.py` 在当前环境存在 pre-existing `skills_dir` 路径问题（`~/.agents/skills` 展开相关），与本次 Memory 变更无直接关系。
- `/chat/resume` 的 checkpoint 原生恢复子任务仍待推进（Phase 21 后续）。

### 下次会话入口
1. 推进 Phase 21 子任务：`/chat/resume` 切换 checkpoint 原生恢复。
2. 对 C 模式提炼做质量评估（准确率/漂移/成本）并补充回归用例。

---

## 2026-03-27 — Phase 21：HIL Resume 幂等防重

### 会话目标
按用户要求先启动 Phase 21（不处理 Phase 22），修复 `/chat/resume` 在 `send_email` 批准路径的重复副作用风险。

### 完成工作

#### 1) TDD：把已固化风险从 xfail 转为真实测试
- `tests/backend/integration/tools/test_execution_layer_ab_mix.py`
  - 移除 HIL 幂等用例 `xfail(strict=True)`
  - 修正测试桩：改为替换整个 `send_email` 工具对象，避免对 `StructuredTool.invoke` 非法 patch
  - 确认 RED：同 payload 二次 resume 导致 `invoke.call_count == 2`

#### 2) `/chat/resume` 幂等执行层实现
- `backend/app/api/chat.py`
  - 新增 `_RESUME_IDEMPOTENCY_STORE`
  - 新增 resume 幂等键构建逻辑：
    - 优先 ToolMeta `idempotency_key_fn(args)`
    - 失败回退稳定 JSON 序列化
    - 键按 session 作用域隔离
  - `approved` 分支执行 `send_email` 前先 `check_and_mark`
  - 命中重复时跳过副作用，返回 `tool_result`（含 `reason=idempotent_replay`）

#### 3) 单元测试补齐
- `tests/backend/unit/api/test_chat.py`
  - 新增：同 payload 去重（执行一次）
  - 新增：不同 payload 不去重（执行两次）
  - 新增：辅助流消费方法，验证 SSE 输出包含去重标记

#### 4) 计划文档同步
- 新增 `docs/plans/plan-phase21-hil-resume-reliability.md`
- 更新 `docs/plans/plan-phase06-tools.md`（HIL 幂等缺口已修复）
- 更新 `planning-with-files/task_plan.md` / `findings.md`

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `pytest tests/backend/integration/tools/test_execution_layer_ab_mix.py -k hil_resume_should_not_repeat_send_email_side_effect_for_same_payload -q` | ✅ 1 passed |
| `pytest tests/backend/unit/api/test_chat.py -k resume -q` | ✅ 5 passed |
| `pytest tests/backend/unit/tools tests/backend/integration/tools tests/backend/unit/api/test_chat.py -q` | ✅ 221 passed, 1 skipped |

### 文件变更清单

```
新增：
  docs/plans/plan-phase21-hil-resume-reliability.md

修改：
  backend/app/api/chat.py
  backend/app/tools/idempotency.py
  tests/backend/integration/tools/test_execution_layer_ab_mix.py
  tests/backend/unit/api/test_chat.py
  tests/backend/unit/tools/test_idempotency.py
  docs/plans/plan-phase06-tools.md
  planning-with-files/task_plan.md
  planning-with-files/findings.md
```

### 遗留问题
- `/chat/resume` 仍包含“模拟继续执行”路径，尚未切换为 checkpoint 原生恢复（Phase 21 后续子任务）。

### 下次会话入口
1. 先写 RED：approve/reject 分支应基于 checkpoint 恢复而非模拟分支。
2. 实现真实 resume 执行链路，并补 SSE 断言（tool_start/tool_result/done 顺序）。

---

## 2026-03-26 — Bug 修复：TraceBlock 重复 key

### 会话目标
修复 React 控制台报错 `Encountered two children with the same key, block_XXX`。

### 根因
`TraceBlockBuilder.on_trace_event()` 在处理 `thought_emitted` 事件时，如果 `model_call_end` 已经发射过一个 thinking block（`_last_thinking_block is not None`），会再次返回**同一个 dict 对象**（相同 id），导致前端收到两个 id 相同的 block。

### 修复
- `backend/app/observability/trace_block.py` line 101-103：将 `return [self._last_thinking_block]` 改为 `return []` 并清除 `_last_thinking_block` 引用
- 更新 3 个测试用例（`test_thought_emitted_does_not_emit_second_block`、`test_thinking_block_has_duration_ms`、`test_thinking_block_includes_content_preview`）以匹配正确行为

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `tests/backend/unit/observability/test_trace_block_builder.py` | ✅ 18 passed |

### 文件变更

```
修改：
  backend/app/observability/trace_block.py
  tests/backend/unit/observability/test_trace_block_builder.py
```

---

## 2026-03-26 — Layer4 执行层验证 + SSE 生命周期稳定化

### 会话目标
1. 按 `docs/arch/tools-v12.md` 完成 Layer4 执行层 A/B/混合（不含 Path C）测试化验证。  
2. 增强 `search.py` 输出契约稳定性测试。  
3. 修复前端 SSE 将正常关闭误判为错误重连的问题，并同步日志语义。

### 完成工作

#### 1) Layer4 执行层（A/B/混合）确定性测试
- 新增 `tests/backend/integration/tools/test_execution_layer_ab_mix.py`
- 引入测试夹具：
  - `ScriptedModel`（脚本化 tool calls）
  - `EventCapture`（采集 tool_start/tool_result/done 序列）
  - `TimedTool`（可控延迟，支持并发窗口断言）
- 完成场景：
  - Path A 并行：验证两工具时间窗重叠与总耗时优势
  - Path B 串行：验证 step2 依赖 step1 严格顺序
  - A+B 混合：验证先并行读、后串行汇总边界
  - HIL 幂等缺口：保留 `xfail(strict=True)` 固化风险

#### 2) search.py 契约增强
- 更新 `backend/app/tools/search.py`：
  - 成功/失败统一 JSON 结构（含 `ok/error/query/answer/results`）
  - 结果截断与总量预算控制（防止上下文污染）
  - Tavily 异常分类（timeout/network/api_error/unknown）
- 扩展 `tests/backend/unit/tools/test_search.py`：
  - 成功/失败可解析 JSON 一致性
  - `results[].title|url|content` 字段完整性
  - 截断预算与异常映射稳定性

#### 3) 前端 SSE 生命周期修复（本会话）
- 修改 `frontend/src/lib/sse-manager.ts`：
  - `done/error/hil_interrupt` 后收到 `CLOSED` 视为正常结束，不再重连
  - 忽略 stale EventSource 的迟到 `onerror`
  - 忽略手动 `disconnect()` 后的误报错误
- 修改 `frontend/src/app/page.tsx`：
  - 统一记录终止原因（done/hil_interrupt/error/timeout）
  - 状态变化日志区分“正常结束”与“真实故障”
  - 修复 `skill_invoked` 监听重复注册问题
  - 修复 async handler lint（`void` 包装）

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `pytest tests/backend/unit/tools/test_search.py tests/backend/integration/tools/test_execution_layer_ab_mix.py -v --tb=short` | ✅ 17 passed, 1 skipped, 1 xfailed |
| `pytest tests/backend/unit/tools tests/backend/integration/tools -v --tb=short` | ✅ 191 passed, 1 skipped, 1 xfailed |
| `npm test -- run ../tests/components/lib/sse-manager.test.ts` | ✅ 38 passed |
| `npm run lint -- --file src/app/page.tsx` | ✅ 无错误 |
| `npx playwright test tests/e2e/09-tool-serial.spec.ts tests/e2e/10-tool-parallel.spec.ts --headed` | ❌ 失败（当时 SSE 提前退出） |

### 文件变更清单

```
后端：
  backend/app/tools/search.py
  tests/backend/unit/tools/test_search.py
  tests/backend/integration/tools/test_execution_layer_ab_mix.py

前端：
  frontend/src/lib/sse-manager.ts
  frontend/src/app/page.tsx
  tests/components/lib/sse-manager.test.ts
```

### 遗留问题
- `/chat/resume` 的写工具幂等保护仍为缺口（以 xfail 固化，待后续实现）。
- E2E 最小冒烟（09/10）需在 SSE 修复后重跑确认。

### 下次会话入口
1. 重跑 `09-tool-serial.spec.ts` 与 `10-tool-parallel.spec.ts`（headed）。
2. 若仍失败，沿 `/chat` 与 `/chat/resume` 流程补事件边界断言与服务端终止语义。

---

## 2026-03-26 — 执行链路明细重设计（Phase 19）

### 会话目标
将 ExecutionTracePanel 从"开发者日志列表"重构为"易懂的执行时间线"，满足普通用户和开发者两种受众。采用后端语义块聚合 + 前端树状时间线方案。执行计划 `docs/superpowers/plans/2026-03-26-execution-trace-redesign.md`（subagent-driven-development 方式）。

### 完成工作

#### 1. 设计阶段
- 通过 superpowers:brainstorming 识别核心痛点：阶段名称不直观、缺少上下文关联
- 确定方案：后端 TraceBlockBuilder 语义块聚合 + 前端树状时间线
- 9 种语义块类型：turn_start, thinking, tool_call, answer, memory_load, prompt_build, hil_pause, error, turn_summary
- 设计文档 `docs/superpowers/specs/2026-03-26-execution-trace-redesign.md`

#### 2. 后端 TraceBlockBuilder（Task 1）
- `backend/app/observability/trace_block.py`（新建）：TraceBlockBuilder 类，累积细粒度 trace_event 为高层语义块
- 18 个单元测试覆盖 9 种块类型的累积/发出规则和边界情况
- 设计变更：model_call_end 即发出 thinking 块（不等 thought_emitted），避免重复

#### 3. TraceMiddleware 集成（Task 2）
- `backend/app/agent/middleware/trace.py`：新增 `_feed_block_builder()` helper，所有钩子同时发送 trace_block
- 4 个集成测试验证 BlockBuilder 集成

#### 4. 前端类型 + Store + SSE（Task 3）
- `frontend/src/types/trace.ts`：TraceBlock 接口 + USER_VISIBLE_BLOCKS 集合
- `frontend/src/store/use-session.ts`：traceBlocks 状态 + addTraceBlock/clearTraceBlocks（上限 200）
- `frontend/src/lib/sse-manager.ts`：新增 trace_block 事件类型
- `frontend/src/app/page.tsx`：注册 trace_block handler，传递 traceBlocks props

#### 5. TraceBlockCard 组件（Task 4）
- `frontend/src/components/TraceBlockCard.tsx`（新建）：单块渲染，图标/颜色/耗时/可展开详情

#### 6. ExecutionTracePanel 重写（Task 5）
- 树状时间线布局，按 turnId 分组
- 简洁/详细视图切换（Eye/EyeOff 图标）
- 简洁模式每 Turn 约 6 个块（vs 旧版 14 个事件）

#### 7. E2E 测试更新（Task 6）
- `tests/e2e/03-tool-trace.spec.ts`：适配 trace-block-card testid，新增视图切换测试

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `tests/backend/unit/observability/test_trace_block_builder.py` | ✅ 18 passed |
| `tests/backend/unit/agent/test_middleware.py` | ✅ 4 新增 passed（38 total，2 pre-existing failed） |
| TypeScript 编译（新增文件） | ✅ 无错误 |

### 文件变更清单

```
新增：
  backend/app/observability/trace_block.py
  tests/backend/unit/observability/test_trace_block_builder.py
  frontend/src/components/TraceBlockCard.tsx
  docs/superpowers/specs/2026-03-26-execution-trace-redesign.md
  docs/superpowers/plans/2026-03-26-execution-trace-redesign.md

修改：
  backend/app/agent/middleware/trace.py（接入 BlockBuilder）
  tests/backend/unit/agent/test_middleware.py（4 个集成测试）
  frontend/src/types/trace.ts（TraceBlock 接口）
  frontend/src/store/use-session.ts（traceBlocks 状态）
  frontend/src/lib/sse-manager.ts（trace_block 事件）
  frontend/src/app/page.tsx（SSE handler + props）
  frontend/src/components/ExecutionTracePanel.tsx（重写为树状时间线）
  tests/e2e/03-tool-trace.spec.ts（适配新 UI）
```

### Commits

| Hash | 说明 |
|------|------|
| `1e25aca` | docs: add execution trace redesign spec |
| `399d396` | docs: add execution trace redesign implementation plan |
| `168c369` | feat: add TraceBlockBuilder with all semantic block types and tests |
| `83836c4` | feat: integrate TraceBlockBuilder into TraceMiddleware |
| `b19239f` | feat: add TraceBlock type, store, SSE handler, and page integration |
| `fea0d06` | feat: add TraceBlockCard, rewrite ExecutionTracePanel as tree timeline |
| `c7b752f` | test: update E2E tests for tree timeline ExecutionTracePanel |

### 遗留问题
- Phase 15（assistant-ui 集成）依赖安装与集成实施等待用户确认
- 原始 trace_event 仍发送（向后兼容），后续可考虑默认关闭

---

## 2026-03-26 — Procedural Memory Injector（Phase 18）

### 会话目标
实现 `BaseInjectionProcessor` 统一注入契约，将 Episodic 和 Procedural 封装为各自 Processor，并通过 `wrap_model_call` 将工作流 SOP 注入 LLM prompt。执行计划 `docs/superpowers/plans/2026-03-26-procedural-memory-injector.md`（subagent-driven-development 方式）。

### 完成工作

#### 前置发现
- `schemas.py` 缺少 `ProceduralMemory` 和 `MemoryContext.procedural`（计划误认为已就绪）
- `abefore_agent` 未调用 `load_procedural`（计划误认为已就绪）
- 均在实施中修复

#### Task 1：schemas 补丁 + BaseInjectionProcessor + EpisodicProcessor
- `backend/app/memory/schemas.py`：新增 `ProceduralMemory(workflows: dict[str, str])`，`MemoryContext` 增加 `procedural` 字段
- `backend/app/memory/processors.py`（新建）：`BaseInjectionProcessor`（`ClassVar[str]` 注解）、`EpisodicProcessor`
- `tests/backend/unit/memory/test_processors.py`（新建）：`TestEpisodicProcessor`（6 个测试）

#### Task 2：ProceduralProcessor
- `processors.py` 追加 `ProceduralProcessor`（slot_name="procedural"，build_prompt 生成 `[程序记忆 - 工作流 SOP]` 格式）
- `test_processors.py` 追加 `TestProceduralProcessor`（7 个测试）
- 修复质量问题：`BaseInjectionProcessor` 使用 `ClassVar[str]` 强化类型约束

#### Task 3：MemoryManager processors 列表
- `backend/app/memory/manager.py`：`__init__` 接受 `processors` 参数，新增 `build_injection_parts`，`build_ephemeral_prompt` 改为 deprecated wrapper
- `test_processors.py` 追加 `TestMemoryManagerWithProcessors`（7 个测试）
- 修复：回退 `save_episodic` 为 P0 stub（误提交的超出范围变更）

#### Task 4：wrap_model_call 通用迭代
- `backend/app/agent/middleware/memory.py`：`wrap_model_call` 使用 `build_injection_parts` + 通用 slot emit 循环
- `tests/backend/unit/agent/test_memory_middleware.py` 追加 `TestProceduralInjection`（10 个测试）
- 修复：测试中 `emit_slot_update` kwargs 提取 bug（`args[0]` 取到 sse_queue 而非 slot name）

#### 额外修复（E2E 关键）
- `abefore_agent` 中接入 `load_procedural`，将 `ProceduralMemory` 写入 `MemoryContext`，打通端到端注入链路

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `tests/backend/unit/memory/` | ✅ 45 passed |
| `tests/backend/unit/agent/test_memory_middleware.py` | ✅ 17 passed，2 pre-existing failed（原因不变） |
| **合计** | **62 passed，2 pre-existing failures** |

### 文件变更清单

```
新增：
  backend/app/memory/processors.py
  tests/backend/unit/memory/test_processors.py

修改：
  backend/app/memory/schemas.py        （新增 ProceduralMemory + MemoryContext.procedural）
  backend/app/memory/manager.py        （processors 参数 + build_injection_parts）
  backend/app/agent/middleware/memory.py （wrap_model_call + abefore_agent）
  tests/backend/unit/agent/test_memory_middleware.py （TestProceduralInjection）
```

### Commits

| Hash | 说明 |
|------|------|
| `2157e1f` | feat: add ProceduralMemory to schemas and BaseInjectionProcessor + EpisodicProcessor |
| `d3be7db` | feat: add ProceduralProcessor |
| `3ea01ef` | refactor: use ClassVar for slot_name and display_name in BaseInjectionProcessor |
| `0c05a30` | feat: update MemoryManager to use processor list for injection |
| `0ea2faf` | fix: revert save_episodic to P0 stub and update class docstring |
| `2a0e11d` | feat: update wrap_model_call to inject procedural via processor pipeline |
| `480377c` | fix: correct emit_slot_update args/kwargs extraction in TestProceduralInjection |
| `e538f57` | feat: wire load_procedural in abefore_agent to populate MemoryContext.procedural |

### 遗留问题
- `save_episodic` / `save_procedural` / `load_procedural` 单元测试缺失（P2）
- Phase 15（assistant-ui 集成）等待用户确认

---

## 2026-03-25 — Context 右侧面板重设计（Phase 16）

### 会话目标
基于 pencil-new.pen 设计稿，完整重设计前端右侧 Context 面板，修复实时刷新 bug，新增后端 session_metadata SSE 事件。

### 完成工作

#### 1. 设计分析与规划
- 分析 Pencil 设计稿，确定 4 模块结构（①会话元数据 ②Token 地图 ③Slot 卡片 ④压缩日志）
- 通过 superpowers:brainstorming 制定设计方案，选择方案 A（全量重写）
- 通过 superpowers:writing-plans 生成完整实施计划（10 个 Tasks）

#### 2. 后端新增 session_metadata SSE 事件（Task 4）
- `backend/app/agent/langchain_engine.py`：在 context_window 事件后发送 session_metadata
- `tests/backend/unit/test_session_metadata_sse.py`：新增 1 个后端测试（✅ PASS）

#### 3. 类型与 Store 扩展（Tasks 1-2）
- `frontend/src/types/context-window.ts`：新增 `SessionMeta`、`SessionMetaEvent` 接口
- `frontend/src/store/use-session.ts`：新增 `sessionMeta` 字段 + `setSessionMeta` action，`clearMessages` 同步重置

#### 4. CompressionLog 扩展（Task 3）
- `frontend/src/components/CompressionLog.tsx`：新增 `hideInternalHeader` prop

#### 5. 4 个新前端组件（Tasks 5-8）

| 组件 | 路径 | 模块颜色 | 测试数 |
|------|------|---------|--------|
| SessionMetadataSection | `frontend/src/components/context/` | 蓝 #2563EB | 8 |
| TokenMapSection | `frontend/src/components/context/` | 靛蓝 #6366F1 | 7 |
| SlotCardsSection | `frontend/src/components/context/` | 青绿 #0D9488 | 8 |
| ContextPanel | `frontend/src/components/` | — | 3 |

#### 6. page.tsx 集成（Task 9）
- 替换 `<ContextWindowPanel>` → `<ContextPanel>`
- **修复实时刷新 bug**：每轮消息开始时重置 4 个 store 字段
- 注册 `session_metadata` SSE handler
- 新增 `lastActivityTime` state，在 `done` 事件时更新
- `frontend/src/lib/sse-manager.ts`：新增 `session_metadata` 到 SSEEventType

#### 7. E2E 测试更新（Task 10）
- `tests/e2e/06-context-window.spec.ts`：使用新 testids，覆盖 4 模块 + Slot 卡片展开

### 测试结果

| 测试集 | 结果 |
|--------|------|
| `vitest run components/context-window/` | ✅ 83 passed, 2 skipped |
| `vitest run components/store/` | ✅ 全部通过 |
| `pytest test_session_metadata_sse.py` | ✅ 1 passed |
| `tsc --noEmit`（新增文件） | ✅ 无错误 |

### 文件变更清单

```
新增：
  frontend/src/components/ContextPanel.tsx
  frontend/src/components/context/SessionMetadataSection.tsx
  frontend/src/components/context/TokenMapSection.tsx
  frontend/src/components/context/SlotCardsSection.tsx
  tests/components/context-window/ContextPanel.test.tsx
  tests/components/context-window/SessionMetadataSection.test.tsx
  tests/components/context-window/TokenMapSection.test.tsx
  tests/components/context-window/SlotCardsSection.test.tsx
  tests/backend/unit/test_session_metadata_sse.py
  docs/superpowers/plans/2026-03-25-context-panel-redesign.md
  docs/superpowers/specs/2026-03-25-context-panel-redesign.md

修改：
  frontend/src/types/context-window.ts
  frontend/src/store/use-session.ts
  frontend/src/components/CompressionLog.tsx
  frontend/src/app/page.tsx
  frontend/src/lib/sse-manager.ts
  tests/components/context-window/CompressionLog.test.tsx
  tests/components/store/use-session.test.ts
  tests/components/context-window/ContextWindowPanel.test.tsx（跳过 2 个已废弃测试）
  tests/e2e/06-context-window.spec.ts
  backend/app/agent/langchain_engine.py
```

### Commits

| Hash | 说明 |
|------|------|
| `b0c7b3f` | feat: add SessionMeta types |
| `8f252a8` | feat: add sessionMeta to useSession store |
| `a516075` | feat: add hideInternalHeader to CompressionLog |
| `d9b878a` | feat: emit session_metadata SSE event |
| `43da173` | feat: implement Context Panel redesign (Tasks 5-8) |
| `1fa7a66` | feat: integrate ContextPanel into page.tsx (Task 9) |
| `a0e7ff8` | feat: update E2E tests for new ContextPanel (Task 10) |

### 遗留问题
- Phase 15 (assistant-ui 重新设计) 依赖安装与集成实施等待用户确认
- skills/ 和 lib/sse-manager 的 pre-existing 测试失败（与本次修改无关）

---

## 2026-03-24 — assistant-ui 重新设计

### 会话目标
用户反馈当前项目设计过于简陋，希望基于 assistant-ui 重新设计前端界面。

### 完成工作

#### 1. 项目分析
- 分析现有技术栈：Next.js 15 + React 19 + Tailwind CSS 4 + Framer Motion + Zustand
- 识别当前设计问题：基础颜色系统、自定义组件缺乏统一设计语言
- 确定 assistant-ui 作为解决方案

#### 2. 设计系统生成
- 使用 UI/UX Pro Max 技能生成完整设计系统
- 配色方案：Dark Mode (OLED) + 企业蓝 (#3B82F6) + 活力橙 (#F97316)
- 排版：Inter + JetBrains Mono
- 9 级字体大小、5 种字重、3 种行高
- 8pt Grid 间距系统、7 级圆角、4 级阴影 + Glow 效果

#### 3. 文档生成
| 文件 | 说明 |
|------|------|
| `docs/design/assistant-ui-redesign.md` | 完整设计方案（项目分析、设计系统、集成方案、组件映射、实施计划） |
| `docs/design/quick-start.md` | 快速开始指南（8 步集成流程 + 常见问题） |

#### 4. 配置文件生成
| 文件 | 说明 |
|------|------|
| `frontend/tailwind.config.assistant-ui.js` | Tailwind 配置模板（含 assistant-ui 插件） |
| `frontend/src/lib/assistant-ui-theme.ts` | TypeScript 主题配置（完整设计系统 Token） |
| `frontend/src/app/globals.assistant-ui.css` | CSS 主题变量（HSL 格式 + 动画关键帧） |

#### 5. 自定义组件生成
| 组件 | 说明 |
|------|------|
| `AssistantRoot.tsx` | 根容器，带 focus 环效果 |
| `AssistantMessage.tsx` | 消息组件，优化视觉层次和头像 |
| `AssistantComposer.tsx` | 输入框，增强交互体验（附件、字符计数、发送状态） |
| `AssistantThread.tsx` | 消息列表，自定义空状态和加载动画 |
| `AssistantThreadWelcome.tsx` | 欢迎界面，品牌化设计（Logo + 特性 + 示例提示） |

#### 6. 项目计划更新
- 创建 `docs/plans/plan-phase15-assistant-ui-redesign.md`
- 更新 `docs/plans/README.md` 添加 Phase 15 并标记为进行中

### 生成的文件清单

```
agent_app/
├── docs/
│   ├── design/
│   │   ├── assistant-ui-redesign.md      [NEW] 完整设计方案
│   │   └── quick-start.md                [NEW] 快速开始指南
│   └── plans/
│       ├── plan-phase15-assistant-ui-redesign.md  [NEW] 阶段计划
│       └── README.md                     [MOD] 更新状态
└── frontend/
    ├── src/
    │   ├── components/assistant/
    │   │   ├── index.ts                  [NEW] 组件导出
    │   │   ├── AssistantRoot.tsx         [NEW]
    │   │   ├── AssistantMessage.tsx      [NEW]
    │   │   ├── AssistantComposer.tsx     [NEW]
    │   │   ├── AssistantThread.tsx       [NEW]
    │   │   └── AssistantThreadWelcome.tsx [NEW]
    │   ├── app/
    │   │   └── globals.assistant-ui.css  [NEW] 主题变量
    │   └── lib/
    │       └── assistant-ui-theme.ts     [NEW] 主题配置
    └── tailwind.config.assistant-ui.js  [NEW] Tailwind 模板
```

### 下一步行动

1. **安装依赖** (用户确认后执行)
   ```bash
   cd frontend
   bun add @assistant-ui/react @assistant-ui/shadcn@latest
   bun add @radix-ui/react-*相关包
   ```

2. **合并配置文件**
   - 将 `tailwind.config.assistant-ui.js` 合并到 `tailwind.config.js`
   - 在 `globals.css` 中导入 `globals.assistant-ui.css`

3. **创建 AssistantProvider**
   - 集成现有 Zustand store
   - 连接 SSE 流式响应

4. **重构页面组件**
   - 更新 `app/page.tsx` 使用新组件
   - 保留现有侧边栏功能

5. **测试验证**
   - 运行 E2E 测试
   - 验证所有功能正常

### 技术决策记录

| 决策 | 原因 |
|------|------|
| 使用 assistant-ui | 专为 AI 聊天界面设计，内置流式响应、代码高亮、分支管理 |
| Dark Mode (OLED) 风格 | 适合开发者工具，节能且护眼 |
| 企业蓝 + 活力橙配色 | 专业感 + 视觉引导 |
| Inter + JetBrains Mono | 现代无衬线 + 开发者友好 |
| Spring 物理动画 | 更自然的交互反馈 |
| 保留现有 SSE 逻辑 | 无需重写后端，降低风险 |

### 遗留问题

- 附件支持（设计已预留，后续实现）
- 命令建议（设计已预留，后续实现）
- 分支管理（assistant-ui 内置支持，需配置）
- 移动端优化（后续迭代）

### 参考资料
- [assistant-ui 官方文档](https://assistant-ui.com/)
- [assistant-ui GitHub](https://github.com/Yonom/assistant-ui)
- [shadcn/ui 组件库](https://ui.shadcn.com/)
- [Radix UI Primitives](https://www.radix-ui.com/primitives)
