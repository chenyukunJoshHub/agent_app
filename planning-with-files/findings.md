# 技术决策记录 (findings.md)

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
