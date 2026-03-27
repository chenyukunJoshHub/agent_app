# 技术决策记录 (findings.md)

## 2026-03-27 — 版本基线校验（LangChain / LangGraph）

### 决策 1：以官方源锁定 2026-03-27 基线版本
- **问题**：HIL 恢复链路需要确保基于最新 API 语义实现，避免沿用过期调用方式
- **查阅来源**：PyPI 官方 JSON API + LangChain 官方文档（human-in-the-loop / interrupts）
- **结论**：当前基线采用 `langchain==1.2.13`、`langgraph==1.1.3`（与本机安装一致）
- **原因**：PyPI 官方源是发布事实源；本机版本与最新一致后再实施 Phase 21，避免“版本错配导致假 bug”
- **影响文件**：`backend/app/api/chat.py`、`tests/backend/unit/api/test_chat.py`、`tests/backend/integration/tools/test_execution_layer_ab_mix.py`

### 决策 2：HIL 恢复严格使用 `Command(resume=...)`（不再 synthetic 分支）
- **问题**：`/chat/resume` 原实现在 approve/reject 分支使用手工模拟逻辑，偏离框架恢复路径
- **查阅章节**：LangGraph Interrupts 文档（Resuming interrupts / handling multiple interrupts）
- **结论**：统一改为 `thread_id + Command(resume={interrupt_id: {"decisions":[...]}})` 原生恢复
- **原因**：这是 2026 版本官方推荐路径，且支持 interrupt-id 显式映射，适配并发中断场景
- **影响文件**：`backend/app/api/chat.py`、`docs/plans/plan-phase21-hil-resume-reliability.md`

---

## 2026-03-27 — Phase 21：`/chat/resume` 幂等防重

### 决策 1：先修复写副作用重复执行，再推进 checkpoint 原生恢复
- **问题**：`/chat/resume` 批准路径会重复执行 `send_email`，同语义 payload 在多次 resume 下会重复副作用
- **查阅章节**：Agent v13 §1.13；Tools v12 §1.3.4；Memory v5 §1.2
- **结论**：在 `/chat/resume` 执行写工具前做幂等检查，命中重复时跳过副作用并返回去重结果
- **原因**：先堵住“重复副作用”风险，再逐步替换“模拟继续执行”为 checkpoint 原生恢复
- **影响文件**：`backend/app/api/chat.py`、`tests/backend/integration/tools/test_execution_layer_ab_mix.py`、`tests/backend/unit/api/test_chat.py`

### 决策 2：幂等键优先使用 ToolMeta 的 `idempotency_key_fn`
- **问题**：如何保证幂等键与工具契约一致，避免 `/chat/resume` 各处散落硬编码
- **查阅章节**：Tools v12 §1.3.1（ToolMeta）+ §1.3.4（幂等保护）
- **结论**：优先读取 registry 中 ToolMeta 的 `idempotency_key_fn(args)` 生成键；失败时退化为稳定 JSON 序列化
- **原因**：保持定义层与执行层一致，后续扩工具时无需改 `/chat/resume` 分支逻辑
- **影响文件**：`backend/app/api/chat.py`

### 决策 3：保留“先标记再执行”的并发安全，并在异常时回滚标记
- **问题**：如果先执行后标记会有并发重复执行风险；如果先标记后执行，工具异常会留下脏标记
- **查阅章节**：Tools v12 §1.3.4（幂等保护目标：防重副作用）
- **结论**：继续使用原子 `check_and_mark`，并新增 `discard(key)` 在执行异常时回滚
- **原因**：兼顾并发防重与失败可重试，避免“失败后永远被判定为已执行”
- **影响文件**：`backend/app/tools/idempotency.py`、`backend/app/api/chat.py`、`tests/backend/unit/tools/test_idempotency.py`

### 决策 4：Phase 21 验收必须包含真实 Postgres checkpointer 回归
- **问题**：仅靠 mock 级测试无法证明 `thread_id + Command(resume=...)` 在真实存储层下不会重放前置工具
- **查阅章节**：Agent v13 §1.13（HIL 完整时序）+ §2.4（SSE/恢复链路）
- **结论**：新增 `requires_db` 集成测试，直接使用 `AsyncPostgresSaver` 验证 approve/reject 两条恢复路径
- **原因**：把“原生恢复已实现”升级为“真实环境已验证”，避免阶段完成判定失真
- **影响文件**：`tests/backend/integration/test_hil_resume_checkpoint_recovery.py`、`docs/plans/plan-phase21-hil-resume-reliability.md`、`planning-with-files/task_plan.md`

---

## 2026-03-27 — Phase 22：Memory 写回双策略（B/C）+ Retain 轻量落地

### 决策 1：默认采用 B（规则提炼），C（LLM 提炼）按间隔触发
- **问题**：需要兼顾画像学习能力、成本与稳定性
- **查阅章节**：Memory v5 §1.3/§2.12；Agent v13 §1.4/§2.6
- **结论**：`MEMORY_PROFILE_UPDATE_MODE` 默认 `rule`；当 `llm` 模式时按 `MEMORY_PROFILE_LLM_INTERVAL=10` 轮触发
- **原因**：先保证可解释与低风险，再通过周期触发控制 C 模式成本
- **影响文件**：`backend/app/config.py`、`.env.example`、`tests/backend/unit/config/test_settings.py`

### 决策 2：按 baseline + dirty flag 执行写回
- **问题**：`aafter_agent` 每轮无差别写库会增加无意义 IO
- **查阅章节**：Memory v5 §1.3（步骤⑧）+ §2.12（dirty-flag）
- **结论**：`abefore_agent` 保存 `memory_ctx_baseline`；`aafter_agent` 比较 baseline 与更新后画像，仅 dirty 时 `save_episodic`
- **原因**：减少无效写操作，保持链路可解释且可测
- **影响文件**：`backend/app/agent/middleware/memory.py`、`tests/backend/unit/agent/test_memory_middleware.py`

### 决策 3：Retain 先做“轻量落地”，不改持久化 schema
- **问题**：是否引入新的结构化字段（如 `retain_entries`）会扩大改动面
- **查阅章节**：Memory v5 §2.9（UserProfile）+ Prompt v20 §1.5（画像注入）
- **结论**：Retain 仅写入 `summary` 文本块（`W/B/O/S`），`UserProfile` 不新增字段
- **原因**：快速交付且不破坏现有读写/注入契约，后续可平滑升级
- **影响文件**：`backend/app/agent/middleware/memory.py`、`tests/backend/integration/test_memory_profile_update_modes.py`

### 决策 4：`O(c=...)` 仅高置信观点合并到 preferences
- **问题**：LLM 低置信观点直接入偏好会导致画像漂移
- **查阅章节**：Memory v5 §2.12（规则提炼与写回策略）
- **结论**：仅当 `confidence >= MEMORY_PROFILE_OPINION_MIN_CONFIDENCE` 时把 O 类条目合并进 preferences
- **原因**：把“可读摘要”与“可执行偏好”分层，降低误写风险
- **影响文件**：`backend/app/agent/middleware/memory.py`、`tests/backend/unit/agent/test_memory_middleware.py`

### 决策 5：LLM 提炼异常回退 B 模式，不阻断主链路
- **问题**：C 模式涉及外部模型调用，可能超时/格式异常
- **查阅章节**：Agent v13 §2.6（可靠性优先）
- **结论**：LLM 异常或 JSON 解析失败时，保留 B 模式结果并继续流程
- **原因**：保证对话主链路稳定，避免“画像提炼失败影响主功能”
- **影响文件**：`backend/app/agent/middleware/memory.py`、`tests/backend/unit/agent/test_memory_middleware.py`

---

## 2026-03-26 — TraceBlock 重复 key bug 修复

### 决策 1：thought_emitted 收到时跳过而非重发
- **问题**：`model_call_end` 已发射 thinking block，随后 `thought_emitted` 再次返回同一 dict 对象，导致前端 React duplicate key 错误
- **结论**：`thought_emitted` 在 `_last_thinking_block is not None` 时返回空列表 `[]`，并清除 `_last_thinking_block` 引用
- **原因**：避免同一 block（相同 id）被发射两次到前端
- **影响文件**：`backend/app/observability/trace_block.py`、`tests/backend/unit/observability/test_trace_block_builder.py`

---

## 2026-03-26 — Layer4 执行层 + SSE 稳定化技术决策

### 决策 1：Layer4 时序结论以“确定性测试”而非真实模型作为判定基准
- **问题**：真实模型输出存在随机性，无法稳定验证 A/B/混合时序语义
- **结论**：以 `ScriptedModel + TimedTool + EventCapture` 的契约测试作为主证据；真实模型仅做冒烟
- **原因**：把“不稳定输入”与“执行层语义”解耦，保证可重复、可断言

### 决策 2：Path C（task_dispatch）本轮明确排除
- **问题**：用户要求仅验证 A/B/混合，不做 Path C
- **结论**：测试范围限定在 A、B、A+B；不新增 task_dispatch 相关实现
- **原因**：收敛范围，优先交付可验证的核心执行语义

### 决策 3：`token_counter` 保持内部工具，不注册到默认工具集合
- **问题**：`token_counter` 已实现，是否应加入默认 registry
- **结论**：不加入默认工具注册（保持 internal-only）
- **原因**：避免对外暴露不必要工具面，减少模型误调用与权限面扩张

### 决策 4：`search.py` 成功/失败统一 JSON 契约
- **问题**：错误路径返回非结构化文本，不利于前后端稳定消费
- **结论**：统一输出 `ok/error/query/answer/results`，并对 Tavily 异常做类型映射
- **原因**：前端与测试可按固定 schema 解析，减少分支判断和脆弱断言

### 决策 5：SSE 单次流在终止事件后关闭应视为“正常结束”
- **问题**：前端把 `readyState=CLOSED` 一律视为错误并重连，触发误报
- **结论**：在收到 `done/error/hil_interrupt` 后，`CLOSED` 走正常收尾，不重连
- **原因**：`/chat` 是 request-scoped SSE，服务端在终止后关闭连接属于预期行为

### 决策 6：忽略 stale EventSource 的迟到错误回调
- **问题**：`disconnect()` 后旧连接仍可能触发 `onerror`，被误当当前连接失败
- **结论**：监听器绑定当前 source，并在回调中校验 source 身份；stale 回调直接忽略
- **原因**：避免假阳性重连与“Max reconnect attempts reached”噪音

### 决策 7：`skill_invoked` 事件监听只注册一次
- **问题**：该监听在每次发送消息时重复注册，导致重复触发
- **结论**：并入一次性 SSE handler 注册块
- **原因**：避免监听器叠加导致 UI 状态重复写入

---

## 2026-03-26 — 执行链路明细重设计技术决策

### 决策 1：thinking 块在 model_call_end 时即发出（不等 thought_emitted）
- **问题**：spec 设计为收到 thought_emitted 后发出 thinking 块，但 LLM 可能不产生 thought（直接 tool_calls）
- **结论**：model_call_end 即发出 thinking 块；thought_emitted 收到时返回空列表（避免重复）
- **原因**：保证 thinking 块始终存在（即使无 thought content），UI 能显示"思考推理"步骤

### 决策 2：TraceBlockBuilder 独立模块（非嵌入 TraceMiddleware）
- **问题**：Builder 应放在 trace_events.py 还是独立文件
- **结论**：新建 `backend/app/observability/trace_block.py`
- **原因**：trace_events.py 是纯工具函数模块（~96 行），BlockBuilder 是有状态的类（~250 行），职责不同；独立文件便于单元测试

### 决策 3：前端保留原始 trace_event（向后兼容）
- **问题**：是否在后端停止发送原始 trace_event
- **结论**：后端同时发送 trace_block 和原始 trace_event
- **原因**：前端详细模式需要嵌套原始事件；避免一次性破坏现有消费方；后续可在前端默认关闭

### 决策 4：USER_VISIBLE_BLOCKS 使用 Set 而非硬编码 if/else
- **问题**：简洁模式下过滤块类型的实现方式
- **结论**：在 types/trace.ts 中导出 `USER_VISIBLE_BLOCKS` 常量（Set）
- **原因**：可维护性 — 新增块类型只需修改一处；可测试性 — 集中定义过滤规则

### 决策 5：traceBlocks 上限 200 条（与 traceEvents 一致）
- **问题**：Zustand store 中 traceBlocks 是否需要上限
- **结论**：addTraceBlock 使用 `.slice(-200)` 保持上限 200
- **原因**：长时间会话中防止内存溢出；与现有 traceEvents 的 200 上限策略一致

---

## 2026-03-26 — Procedural Memory Injector 技术决策

### 决策 1：schemas.py 是否需要修改（计划前置条件验证）
- **问题**：计划假设 `ProceduralMemory` 和 `MemoryContext.procedural` 已在 schemas.py 中定义（标注 ✅），但实际不存在
- **结论**：作为 Task 1 的前置步骤补充，在 schemas.py 中新增 `ProceduralMemory` 和 `MemoryContext.procedural` 字段
- **原因**：计划是基于预期状态编写的，实际工作树已有相关改动但未提交；执行时需对计划前置条件做实际验证

### 决策 2：BaseInjectionProcessor 使用 ClassVar[str] 而非裸注解
- **问题**：初始实现使用 `slot_name: str`（裸注解），子类遗漏该属性时 Python 不会报错，只在调用时 AttributeError
- **结论**：改为 `slot_name: ClassVar[str]`，启用类型检查器静态检测
- **原因**：BaseInjectionProcessor 设计为扩展点（未来 RAG/FewShot 处理器），ClassVar 让约束在类定义时可见，比运行时报错更好

### 决策 3：build_ephemeral_prompt 保留为 deprecated wrapper
- **问题**：若直接删除 build_ephemeral_prompt，现有 test_memory_middleware.py 中的测试会失败
- **结论**：保留 build_ephemeral_prompt，改为委托 `EpisodicProcessor().build_prompt(ctx)`
- **原因**：向后兼容；测试迁移是独立工作，不属于本次 scope；deprecated 注释明确传递意图

### 决策 4：save_episodic 超出 scope 变更回退
- **问题**：Task 3 提交时误提交了工作树中预存在的 save_episodic 实现代码（从 stub 变为真实写入），导致 test_save_episodic_is_noop_p0 失败原因发生变化
- **结论**：回退 save_episodic 为 P0 stub（pass），同时更新类 docstring
- **原因**：计划明确要求预存在失败原因不变；save_episodic P2 实现属于独立任务，不在本次 scope

### 决策 5：abefore_agent 接入 load_procedural（计划外补充）
- **问题**：计划标注 abefore_agent "已正确加载 procedural，无需改动"，但实际代码只加载 episodic，ProceduralProcessor 生产中永远看到空数据
- **结论**：在最终代码审查阶段补充修复，在 abefore_agent 中调用 load_procedural 并写入 MemoryContext
- **原因**：若不修复，整个 procedural 注入功能在生产环境是死代码；这是 E2E 关键缺口，优先级高于"不改动项"约定

### 决策 6：wrap_model_call 空 parts 时仍保持 history emit
- **问题**：当 memory_ctx 为 None 时 parts={}，通用迭代 loop 不执行，history slot 仍需独立 emit
- **结论**：history slot 保留在 for loop 之外单独 emit（`enabled=True`），不纳入 processor 管辖
- **原因**：history 不是 MemoryContext 的产物，不适合通过处理器建模；保持单一职责

---

## 2026-03-25 — Context 右侧面板重设计技术决策

### 决策 1：全量重写 vs 增量修改
- **问题**：重设计 Context 面板时，选择修改旧 ContextWindowPanel 还是新建 ContextPanel
- **结论**：全量重写（方案 A）。新建 4 个子组件 + 1 个组合组件，旧组件保留但不再使用
- **原因**：旧组件与新设计差异过大；新组件可单独测试；迁移时 page.tsx 只需替换一行 JSX

### 决策 2：lastActivityTime 类型为 number 而非 string
- **问题**：规格书建议 `string | null`，但实际存储 Unix 时间戳 ms
- **结论**：使用 `number | null`，在渲染层格式化
- **原因**：避免 Date → string 转换的精度损失；Zustand state 中 number 更易比较

### 决策 3：ContextPanel 使用显式 props（非 "zero props" 方案）
- **问题**：规格书提到"zero props"（直接读 store），但会降低可测试性
- **结论**：保留显式 props（sessionMeta, contextWindowData, slotDetails, stateMessages, lastActivityTime）
- **原因**：Vitest 测试无需 mock store；组件职责单一；符合 TDD 原则

### 决策 4：实时刷新 bug 根因与修复
- **问题**：发送第 2 条消息后，Context 面板仍显示第 1 条消息的旧数据
- **根因**：`handleSendMessage` 中缺少 store reset，旧数据持续到新 SSE 事件覆盖
- **修复**：在 `incrementTurn()` 后、`setLoading(true)` 前，重置 4 个字段：
  `setContextWindowData(EMPTY_CONTEXT_DATA)`、`setSlotDetails([])`、`setStateMessages([])`、`setSessionMeta(null)`

### 决策 5：Token 比例条使用 flex 而非百分比宽度
- **问题**：12 段 Token 比例条如何在 tokens 全为 0 时避免除零错误
- **结论**：使用 `flex: tokens` 属性（flex-grow），而非 `width: pct%`
- **原因**：当所有 flex 值为 0 时，浏览器均分空间（不报错）；无需计算百分比

### 决策 6：SSEEventType 需显式声明 session_metadata
- **问题**：新增 `session_metadata` SSE 事件后，TypeScript 报类型错误
- **结论**：在 `sse-manager.ts` 的 `SSEEventType` union 和 `EVENT_TYPES` 数组中均添加 `'session_metadata'`
- **影响文件**：`frontend/src/lib/sse-manager.ts`

---

## 2026-03-24 — assistant-ui 重新设计决策

### 问题
用户反馈当前项目设计过于简陋，希望基于 assistant-ui 重新设计。

### 查阅资料
1. **assistant-ui 官方文档** - 确认核心特性和集成方式
2. **UI/UX Pro Max 技能** - 生成专业设计系统
3. **项目现有代码** - 分析技术栈和组件结构

### 技术决策

#### 1. 选择 assistant-ui 的原因

| 因素 | assistant-ui | 自定义实现 |
|------|-------------|-----------|
| 流式响应 | ✅ 开箱即用 | ❌ 需手动实现 |
| 思维链展示 | ✅ 内置支持 | ❌ 需自定义 |
| 代码高亮 | ✅ 集成 Shiki | ❌ 需额外配置 |
| 分支管理 | ✅ 原生支持 | ❌ 复杂实现 |
| 可访问性 | ✅ WCAG 2.1 AA | ❌ 需持续维护 |
| 主题系统 | ✅ shadcn/ui 集成 | ⚠️ 自定义维护 |

**结论**: 使用 assistant-ui 可显著减少开发工作量，提升代码质量。

#### 2. 设计系统选择

**风格**: Dark Mode (OLED)
- 适合开发者工具场景
- OLED 屏幕节能
- 长时间使用护眼

**配色方案**:
- 主色: #3B82F6 (Blue 500) - 企业蓝，专业可信
- 强调色: #F97316 (Orange 500) - 活力橙，引导用户操作
- 背景: #0A0A0F - 近纯黑，OLED 优化

**排版**:
- 标题/正文: Inter - 现代无衬线，高可读性
- 代码: JetBrains Mono - 开发者友好，等宽优化

**结论**: 设计系统符合企业级 AI 工具定位。

#### 3. 集成策略

**保留现有功能**:
- SSE 流式响应逻辑
- Zustand 状态管理
- ExecutionTracePanel 和 ContextWindowPanel
- HIL 确认对话框

**渐进式迁移**:
1. 先集成 assistant-ui 核心组件
2. 自定义样式匹配设计系统
3. 保留现有侧边栏功能
4. 逐步优化交互体验

**结论**: 降低风险，平滑过渡。

#### 4. 自定义组件设计

每个组件都遵循设计系统：
- 使用 CSS 变量定义颜色
- Spring 物理动画 (150-300ms)
- Framer Motion 增强交互
- 响应式布局 (375px - 1440px)

**结论**: 确保视觉一致性和高质量交互。

### 影响文件

#### 新增文件
- `docs/design/assistant-ui-redesign.md`
- `docs/design/quick-start.md`
- `docs/plans/plan-phase15-assistant-ui-redesign.md`
- `frontend/src/lib/assistant-ui-theme.ts`
- `frontend/src/app/globals.assistant-ui.css`
- `frontend/src/components/assistant/*`
- `frontend/tailwind.config.assistant-ui.js`

#### 需修改文件
- `frontend/package.json`
- `frontend/tailwind.config.js`
- `frontend/src/app/globals.css`
- `frontend/src/app/page.tsx`
- `tests/e2e/*.spec.ts`

### 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| assistant-ui 版本更新破坏兼容性 | 中 | 锁定版本号，关注更新日志 |
| 现有 SSE 逻辑不兼容 | 低 | 在 Provider 层适配，保留原逻辑 |
| 样式冲突 | 低 | 使用 CSS 变量隔离，测试覆盖 |
| E2E 测试选择器失效 | 中 | 使用 data-testid 属性 |

### 下一步

1. 用户确认设计方案
2. 执行依赖安装
3. 合并配置文件
4. 创建 AssistantProvider
5. 重构页面组件
6. 运行测试验证

---

## 历史记录

*之前的技术决策记录位于项目文档中*
