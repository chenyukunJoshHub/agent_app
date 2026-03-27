# 项目任务计划 (task_plan.md)

## 项目概述

**项目名称**: Multi-Tool AI Agent
**项目类型**: 企业级 AI Agent 应用
**技术栈**: Next.js 15 + React 19 + Tailwind CSS 4 + Framer Motion + Zustand
**架构**: LangGraph + LangChain + PostgreSQL + SSE

---

## 阶段进度总览

| 阶段 | 名称 | 状态 | 计划文件 |
|------|------|------|---------|
| 01 | 数据库设置 | ✅ done | plan-phase01-db-setup.md |
| 02 | SkillManager | ✅ done | plan-phase02-skill-manager.md |
| 03 | Memory 系统 | ✅ done | plan-phase03-memory.md |
| 04 | Agent 核心 | ✅ done | plan-phase04-agent-core.md |
| 05 | Prompt 构建 | ✅ done | plan-phase05-prompt.md |
| 06 | Tools 工具 | ✅ done | plan-phase06-tools.md |
| 07 | API 路由 | ✅ done | plan-phase07-api.md |
| 08 | 前端布局 | ✅ done | plan-phase08-frontend-layout.md |
| 09 | ReAct 链路可视化 | ✅ done | plan-phase09-react-trace.md |
| 10 | Context Window 面板 | ✅ done | plan-phase10-context-window.md |
| 11 | Skills UI | ✅ done | plan-phase11-skills-ui.md |
| 12 | HIL 人工介入 | ✅ done | plan-phase12-hil.md |
| 13 | E2E 测试 | ✅ done | plan-phase13-e2e-tests.md |
| 14 | Slot Token 实时统计 | ✅ done | plan-phase14-slot-token-stats.md |
| 15 | assistant-ui 集成 | ✅ done | plan-phase15-assistant-ui-redesign.md |
| 16 | Context 右侧面板重设计 | ✅ done | plan-phase16-context-panel-redesign.md |
| 17 | 内存 Slot 修复 + 用户偏好初始化 | ✅ done | — |
| 18 | Procedural Memory Injector | ✅ done | docs/superpowers/plans/2026-03-26-procedural-memory-injector.md |
| 19 | 执行链路明细重设计 | ✅ done | docs/superpowers/plans/2026-03-26-execution-trace-redesign.md |
| 20 | Layer4 执行层验证 + SSE 生命周期稳定化 | ✅ done | tests/backend/integration/tools/test_execution_layer_ab_mix.py |
| 21 | HIL Resume 可靠性闭环 | ✅ done | docs/plans/plan-phase21-hil-resume-reliability.md |
| 22 | Memory 读写闭环 | ✅ done | docs/plans/plan-phase03-memory.md（Phase 21 增量） |

---

## 当前状态

**日期**: 2026-03-27
**当前阶段**: Phase 22 — Memory 读写闭环（user-owned） / Phase 21 已完成
**阶段状态**: 🔄 进行中

### Phase 15 — assistant-ui 集成

| 任务 | 状态 | 说明 |
|------|------|------|
| npm 调研 + 安装 | ✅ done | `@assistant-ui/react@0.12.20`，删除废弃 tailwind config |
| API 验证 | ✅ done | 确认 primitives 模式，无 shadcn/tailwind-plugin |
| chat-runtime.ts (ExternalStoreAdapter) | ✅ done | Zustand → ThreadMessageLike 桥接 |
| useSSEHandlers hook | ✅ done | 从 page.tsx 提取全部 SSE handler（12 个事件） |
| ChatProvider | ✅ done | AssistantRuntimeProvider 包装器 |
| 5 个 Wrapper 组件重写 | ✅ done | 适配 Thread/Message/Composer primitives API |
| page.tsx 重构 | ✅ done | 617→330 行，移除 SSE 内联逻辑 |
| 构建验证 | ✅ done | `next build` 通过，lint 无新增错误 |

### Phase 16 进度

| 任务 | 状态 | 说明 |
|------|------|------|
| 设计分析与规划 | ✅ done | 基于 pencil-new.pen 设计稿，制定完整实施计划 |
| Task 1: SessionMeta 类型 | ✅ done | context-window.ts 新增 SessionMeta / SessionMetaEvent |
| Task 2: Store 新增字段 | ✅ done | use-session.ts 新增 sessionMeta + setSessionMeta |
| Task 3: CompressionLog hideInternalHeader | ✅ done | 新增 prop 避免双重 header |
| Task 4: 后端 SSE 事件 | ✅ done | langchain_engine.py 新增 session_metadata 事件 |
| Task 5: SessionMetadataSection | ✅ done | 模块① 蓝色 #2563EB，含 8 个测试 |
| Task 6: TokenMapSection | ✅ done | 模块② 靛蓝 #6366F1，12 段 Token 比例条，含 7 个测试 |
| Task 7: SlotCardsSection | ✅ done | 模块③ 青绿 #0D9488，可展开卡片，含 8 个测试 |
| Task 8: ContextPanel 主组件 | ✅ done | 4 模块组合，含 3 个测试 |
| Task 9: page.tsx 集成 | ✅ done | 替换旧组件，修复实时刷新 bug，注册 session_metadata handler |
| Task 10: E2E 测试更新 | ✅ done | 06-context-window.spec.ts 使用新 testids |

---

## Phase 17 — 内存 Slot 修复 + 用户偏好初始化

| 任务 | 状态 | 说明 |
|------|------|------|
| 实现 save_episodic | ✅ done | manager.py 实际写入 store，移除 P0 stub |
| 新增 load/save_procedural | ✅ done | manager.py 新增程序记忆读写方法 |
| 新建 preferences API | ✅ done | /api/user/preferences + /api/user/procedural 端点 |
| 修复 wrap_model_call | ✅ done | 始终 emit episodic + history slot_update |
| history slot enabled=True | ✅ done | builder.py 由 P2 占位符改为激活 |
| 写入用户偏好 (dev_user) | ✅ done | 3条 episodic 偏好写入 DB |
| 写入程序记忆 (dev_user) | ✅ done | 3条 workflow SOP 写入 DB |

---

## Phase 18 进度

| 任务 | 状态 | 说明 |
|------|------|------|
| schemas.py 更新 | ✅ done | 新增 ProceduralMemory、MemoryContext.procedural |
| processors.py 新建 | ✅ done | BaseInjectionProcessor（ClassVar）+ EpisodicProcessor |
| ProceduralProcessor | ✅ done | slot_name="procedural"，build_prompt 格式化 SOP |
| MemoryManager processors 列表 | ✅ done | __init__ 接受 processors、build_injection_parts、deprecated wrapper |
| wrap_model_call 通用迭代 | ✅ done | 替换 build_ephemeral_prompt，slot emit 改为通用循环 |
| abefore_agent 接入 procedural | ✅ done | load_procedural 写入 MemoryContext.procedural（E2E 关键） |
| 测试（20 + 10 个） | ✅ done | 62 passed，2 预存在失败不变 |

---

## Phase 19 — 执行链路明细重设计

| 任务 | 状态 | 说明 |
|------|------|------|
| 设计文档（spec） | ✅ done | 语义块聚合 + 树状时间线设计方案 |
| 实施计划（plan） | ✅ done | 10-task TDD 实施计划 |
| Task 1: TraceBlockBuilder | ✅ done | 后端 9 种语义块类型累积/发出规则，18 个单元测试 |
| Task 2: TraceMiddleware 集成 | ✅ done | trace.py 接入 BlockBuilder，4 个集成测试 |
| Task 3: 前端类型 + Store | ✅ done | TraceBlock 接口、traceBlocks 状态、SSE handler |
| Task 4: TraceBlockCard | ✅ done | 单块渲染组件（图标/颜色/展开折叠） |
| Task 5: ExecutionTracePanel 重写 | ✅ done | 树状时间线，Turn 分组，简洁/详细视图切换 |
| Task 6: E2E 测试更新 | ✅ done | 03-tool-trace.spec.ts 适配新 UI 结构 |

---

## Phase 20 — Layer4 执行层验证 + SSE 生命周期稳定化

| 任务 | 状态 | 说明 |
|------|------|------|
| Layer4 A/B/混合确定性测试 | ✅ done | 新增 `test_execution_layer_ab_mix.py`，验证并行/串行/混合 |
| HIL 幂等缺口固化 | ✅ done | `/chat/resume` 写工具幂等缺口用 `xfail(strict=True)` 固化 |
| `search.py` 契约增强 | ✅ done | 成功/失败统一 JSON，异常分类，结果截断预算 |
| 后端工具测试回归 | ✅ done | `unit/tools + integration/tools` 全量通过（含 1 xfail） |
| SSE 正常关闭误报修复 | ✅ done | 前端不再将终止后 CLOSED 视为重连错误 |
| SSE 生命周期日志清晰化 | ✅ done | done/hil/error/timeout 终止原因区分 |
| E2E 09/10 最小冒烟重跑 | ⏳ pending | 需在当前修复后再次验证 |

---

## Phase 21 — HIL Resume 可靠性闭环

| 任务 | 状态 | 说明 |
|------|------|------|
| 移除 HIL 幂等 xfail | ✅ done | `test_execution_layer_ab_mix.py` 不再依赖 xfail |
| `/chat/resume` 幂等防重 | ✅ done | `send_email` 批准路径按幂等键去重 |
| API 单测补充 | ✅ done | 新增同 payload 去重与不同 payload 执行测试 |
| 工具回归 | ✅ done | `unit/tools + integration/tools + unit/api/test_chat.py` 全绿 |
| checkpoint 真实恢复 | ✅ done | `thread_id + Command(resume=...)` 原生恢复，移除 synthetic approve/reject 分支 |

---

## Phase 22 — Memory 读写闭环（B/C + Retain）

| 任务 | 状态 | 说明 |
|------|------|------|
| 配置项落地 | ✅ done | 新增 `MEMORY_PROFILE_UPDATE_MODE/LLM_INTERVAL/OPINION_MIN_CONFIDENCE` |
| `save_episodic` 实装 | ✅ done | `MemoryManager.save_episodic` 改为真实 `store.aput` |
| baseline + dirty flag | ✅ done | `abefore_agent` 记录 baseline，`aafter_agent` 差异写回 |
| B 模式规则提炼 | ✅ done | `interaction_count +1` + `language/domain` 提炼 |
| C 模式周期提炼 | ✅ done | `llm` 模式按 `N=10` 轮触发，失败自动回退 B |
| Retain 轻量格式 | ✅ done | `summary` 写入 `W/B/O/S`，`O(c)` 阈值控制偏好合并 |
| TDD 用例与集成验证 | ✅ done | 新增/更新 unit+integration 测试，核心链路全绿 |

---

## 阻塞项

**当前无阻塞项**

---

## 遗留技术债务

- `save_procedural` / `load_procedural` 仍缺完整单测覆盖
- C 模式提炼提示词与输出 schema 需线上观测与回归评估（漂移/成本）
- assistant-ui 消息层仍使用自定义 MessageList（未迁移到 MessagePrimitive.Content 渲染）

---

## 下一阶段

1. **assistant-ui 消息层迁移** - 将 MessageList 迁移到 MessagePrimitive.Content + 自定义 part renderers
2. **Memory C 模式质量评估** - 提炼准确率/成本/漂移观测

---

## 项目里程碑

| 里程碑 | 日期 | 状态 |
|--------|------|------|
| 后端核心完成 | 2026-03-20 | ✅ |
| 前端基础完成 | 2026-03-22 | ✅ |
| 全链路可视化完成 | 2026-03-23 | ✅ |
| UI 重新设计 | 2026-03-24 | ✅ |
| assistant-ui 集成 | 2026-03-27 | ✅ |
| Context 面板重设计 | 2026-03-25 | ✅ |
| Procedural Memory 注入 | 2026-03-26 | ✅ |
| 执行链路明细重设计 | 2026-03-26 | ✅ |
| Layer4 执行层验证 + SSE 稳定化 | 2026-03-26 | ✅ |
| 生产部署 | 待定 | ⏳ |

---

## 技术债务

### P0 - 高优先级
- 无

### P1 - 中优先级
- 代码覆盖率提升到 90%+
- 性能优化（Bundle 大小、加载时间）
- 移动端体验优化

### P2 - 低优先级
- 国际化支持
- 更多主题选项
- 附件功能

---

## 资源链接

### 架构文档
- [Multi-Tool AI Agent v13](../arch/agent-v13.md)
- [Memory 模块 v5](../arch/memory-v5.md)
- [Prompt + Context v20](../arch/prompt-context-v20.md)
- [Agent Skill v3](../arch/skill-v3.md)

### 设计文档
- [assistant-ui 重新设计方案](../design/assistant-ui-redesign.md)
- [快速开始指南](../design/quick-start.md)

### 计划文档
- [阶段计划索引](./README.md)
- [Phase 15 详细计划](../plans/plan-phase15-assistant-ui-redesign.md)

---

*最后更新: 2026-03-27（同步：Phase 21 最终收口）*
