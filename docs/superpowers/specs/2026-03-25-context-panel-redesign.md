# Context 右侧面板重设计规格

**日期：** 2026-03-25
**设计稿：** `pencil-new.pen`（亮色 + 暗色两套，均已审阅）
**方案：** A — 全量重写

---

## 1. 目标

将右侧 Context 面板从现有的 5+ 混杂区块重构为 4 个清晰模块，同时修复数据不实时刷新的 bug。

---

## 2. 现有问题

| 问题 | 描述 |
|------|------|
| 重复区块 | `Slot 快照` 与 `Slot 预算分解` 内容高度重叠 |
| 实时刷新 bug | 每轮新对话 store 中旧数据不重置，导致上一轮数据残留显示 |
| 缺少会话元数据 | 没有模型名、消息计数、创建/活动时间等基础信息展示 |
| Token 地图不直观 | 只有简单进度条，无 12 档彩色分段和等宽数据表 |

---

## 3. 新设计结构

### 3.1 4 模块布局

```
ContextPanel (440px, 可滚动)
├── [蓝色左条]   模块一：会话元数据与 Token 统计
├── [靛蓝左条]   模块二：上下文窗口 · Token 地图
├── [青绿左条]   模块三：各 Slot 原文与 Prompt
└── [灰色左条]   模块四：压缩日志（compressionEvents.length > 0 时渲染）
```

**节头通用样式：**

```tsx
// 每个模块的 section header 结构
<div className="flex items-center gap-3 pb-3.5 border-b border-border">
  <div className="w-[5px] h-[20px] rounded-sm" style={{ background: accentColor }} />
  <span className="text-base font-semibold text-text-primary">{title}</span>
</div>
```

---

### 3.2 模块一：会话元数据与 Token 统计

**左色条：** `#2563EB`

**双列网格**（`grid-cols-2`，`gap-4`），12 个字段，每字段：

```tsx
<div className="flex flex-col gap-1">
  <span className="text-[11px] text-text-muted">{label}</span>
  <span className="text-sm font-semibold text-text-primary">{value}</span>
</div>
```

**字段映射表：**

| 字段 | 数据来源 | 更新时机 | 列 |
|------|---------|---------|-----|
| 会话名称 | `sessionMeta.session_name` | `session_metadata` SSE | 左 |
| 上下文限制 | `budget.model_context_window` | `context_window` | 左 |
| 总 token | `budget.usage.total_used` | `context_window` / `token_update` | 左 |
| 输入 token | `budget.usage.input_budget` | `context_window` | 左 |
| 用户消息 | `stateMessages.filter(m => m.role === 'user').length` | `done` 事件 | 左 |
| 创建时间 | `sessionMeta.created_at` | `session_metadata` SSE | 左 |
| 消息数量 | `stateMessages.length` | `done` 事件 | 右 |
| 激活模型 | `sessionMeta.model` | `session_metadata` SSE | 右 |
| 使用率 | 初始渲染：`budget.usage.total_used / budget.working_budget * 100`；`token_update` 到来后：`current / budget * 100`（两者语义相同，`token_update.current` 即 `total_used` 的实时值） | `context_window` 初始化；`token_update` 实时刷新 | 右 |
| 输出 token | `budget.usage.output_reserve` | `context_window` | 右 |
| 助手消息 | `stateMessages.filter(m => m.role === 'assistant').length` | `done` 事件 | 右 |
| 最后活动 | 每次 `done` 事件时记录 `new Date().toLocaleString('zh-CN')` | `done` 事件 | 右 |

> **注意：** `token_update` SSE payload 字段名为 `{ current: number, budget: number }`（不是 `total_used`/`working_budget`）。使用率计算：`(current / budget * 100).toFixed(1)`

**使用率颜色规则（复用现有逻辑）：**

| 使用率 | 颜色 CSS 变量 |
|--------|-------------|
| < 70% | `text-success-text` |
| 70–90% | `text-warning-text` |
| ≥ 90% | `text-error-text` |

**激活模型：** 字体 13px（防长字符串溢出），`truncate` 类。

---

### 3.3 模块二：上下文窗口 · Token 地图

**左色条：** `#6366F1`
**数据来源：** `context_window` SSE 事件

**子组件 Props：**

```tsx
interface TokenMapSectionProps {
  budget: TokenBudgetState;
  slotUsage: SlotUsage[];
}
```

内部白色卡片（`bg-bg-card border border-border rounded-[10px] p-4`）：

1. **标题：** `"12 档 Token 占比（32k 工作窗口）"` (12px/600, `text-text-muted`)

2. **12 档彩色进度条：**
   - Height: 8px，外层圆角 4px，`overflow-hidden`
   - 各段宽度：`(tokens / working_budget) * 100 + '%'`，按 `SLOT_VISUAL_ORDER` 排列，末尾追加"剩余"和"压缩预留"
   - 颜色：`TWELVE_SEGMENT_CONTEXT_COLORS`（已在 `context-window.ts` 定义）
   - 动画：`framer-motion` width 过渡 `duration: 0.5, ease: 'easeOut'`

3. **图例 2 行（flex wrap）：** 每项 `色点(5px 圆) + "① - 6.4%"` (10px, `text-text-secondary`)

4. **等宽明细表：**
   - 字体：JetBrains Mono 12.5px，`lineHeight: 1.55`，`text-text-secondary`
   - 12 行，格式：`① 系统提示词  2.05k   6.4%`（等宽对齐用空格/`\t`）
   - 数值格式：`(n / 1000).toFixed(2) + 'k'`（≥ 1000）

---

### 3.4 模块三：各 Slot 原文与 Prompt

**左色条：** `#0D9488`
**数据来源：** `slot_details` SSE 事件

**子组件 Props：**

```tsx
interface SlotCardsSectionProps {
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
}
```

**卡片列表规则：**
- 排序：按 `slot.tokens` 降序（组件内部 `useMemo` 排序，后端顺序不依赖）
- 间距：`gap-2`

**单张卡片（默认状态）：**

```tsx
// bg-bg-card border border-border rounded-lg p-3
// 布局：flex justify-between items-center
<div>
  <span className="text-xs font-semibold text-text-primary">{slot.display_name}</span>
</div>
<ChevronDown className="w-4 h-4 text-text-muted" />
```

**禁用 Slot（`!slot.enabled`）：**
- `opacity-60`，`pointer-events-none`，不可展开

**展开状态（`isExpanded = true`）：**

```tsx
// 展开内容区域，mt-3 pt-3 border-t border-border
<pre className="text-[10px] font-mono text-text-secondary whitespace-pre-wrap break-words overflow-y-auto max-h-64">
  {slot.content}
</pre>
```

**⑧ 会话历史特殊处理：**
- 图标：`ChevronsUpDown`（lucide）替代 `ChevronDown`
- 展开显示 `stateMessages` 列表（`max-h-[300px] overflow-y-auto`）：
  ```tsx
  {stateMessages.map((msg, i) => (
    <div key={i} className="text-[10px] font-mono text-text-secondary">
      <span className="text-text-muted mr-1">[{msg.role}]</span>
      {(msg.content || '').slice(0, 200)}
    </span>
  ))}
  ```

**无摘要**：卡片默认状态不显示任何内容预览。

---

### 3.5 模块四：压缩日志

**左色条：** `#6B7280`
**条件渲染：** `compressionEvents.length > 0` 时才渲染整个模块

**实现方案：** 为 `CompressionLog.tsx` 新增 `hideInternalHeader?: boolean` prop（默认 `false`），模块四调用时传入 `hideInternalHeader={true}`，由外层 `ContextPanel` 统一渲染节头。

```tsx
// 修改后的 CompressionLog.tsx props
interface CompressionLogProps {
  events: CompressionEvent[];
  hideInternalHeader?: boolean; // 新增，true 时隐藏内部 header
}
```

---

## 4. 空状态与加载状态

| 场景 | 表现 |
|------|------|
| 初始化（无数据）| 模块一：所有字段显示 `—`；模块二：进度条全灰；模块三：显示"等待首轮对话…"占位文字 |
| 每轮发送时重置 | 同上（store reset 后立刻恢复初始状态，SSE 事件到来时逐步更新） |
| `sessionMeta` 未到达 | 会话名称显示 `—`，模型显示 `—` |
| `slotDetails` 为空 | 模块三显示空列表占位 `text-text-muted italic` |

---

## 5. 主题适配

遵循现有 CSS 变量，不硬编码颜色（模块左色条固定色除外）：

| 角色 | CSS 变量 |
|------|---------|
| 页面背景 | `bg-bg-base` |
| 卡片背景 | `bg-bg-card` |
| 边框 | `border-border` |
| 主文本 | `text-text-primary` |
| 次要文本 | `text-text-secondary` |
| 静音文本 | `text-text-muted` |

---

## 6. 实时刷新修复

### 6.1 根因

每轮新对话开始前，`contextWindowData` / `slotDetails` / `stateMessages` 等 Zustand store 字段未重置，旧数据残留至新轮数据到达前。SSE handlers 本身注册逻辑没问题（Zustand setters 为稳定引用，不需要重新注册）。

### 6.2 修复方案（`page.tsx`）

```typescript
const handleSendMessage = async (message: string) => {
  addMessage({ role: 'user', content: message });
  incrementTurn();

  // ✅ 每轮发送前重置 Context 相关数据
  setContextWindowData(EMPTY_CONTEXT_DATA);
  setSlotDetails([]);
  setStateMessages([]);
  setSessionMeta(null);  // 新增 store action

  setLoading(true);
  setError(null);
  // ... 其余逻辑不变
};
```

### 6.3 后端要求

后端每轮请求必须在响应中发送：
1. `session_metadata` — 在响应开始时发送一次
2. `context_window` — 在响应过程中至少发送一次
3. `slot_details` — 在响应结束前发送一次

---

## 7. 新增 TypeScript 类型（`types/context-window.ts`）

```typescript
export interface SessionMeta {
  session_name: string;
  model: string;
  created_at: string;  // ISO 8601 字符串，如 "2026-03-25T09:00:00Z"
}

export interface SessionMetaEvent {
  type: 'session_metadata';
  data: SessionMeta;
}
```

---

## 8. Store 修改（`store/use-session.ts`）

在 `SessionState` interface 新增：

```typescript
// 新增字段
sessionMeta: SessionMeta | null;

// 新增 action
setSessionMeta: (meta: SessionMeta | null) => void;
```

初始值：`sessionMeta: null`

实现：`setSessionMeta: (meta) => set({ sessionMeta: meta })`

---

## 9. 组件 Props 接口

```tsx
// ContextPanel.tsx（根组件）
interface ContextPanelProps {
  // 所有数据从 store 内部订阅，无外部 props
}

// SessionMetadataSection.tsx
interface SessionMetadataSectionProps {
  sessionMeta: SessionMeta | null;
  budget: TokenBudgetState;
  stateMessages: StateMessage[];
  lastActivityTime: string | null;  // 由父组件在 done 事件时更新
}

// TokenMapSection.tsx
interface TokenMapSectionProps {
  budget: TokenBudgetState;
  slotUsage: SlotUsage[];
}

// SlotCardsSection.tsx
interface SlotCardsSectionProps {
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
}
```

> `ContextPanel` 从 `useSession` 读取所有数据，通过 props 传给子组件。子组件不直接访问 store，保持纯组件可测试性。

---

## 10. 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建 | `frontend/src/components/ContextPanel.tsx` |
| 新建 | `frontend/src/components/context/SessionMetadataSection.tsx` |
| 新建 | `frontend/src/components/context/TokenMapSection.tsx` |
| 新建 | `frontend/src/components/context/SlotCardsSection.tsx` |
| 修改 | `frontend/src/types/context-window.ts`（**新增** `SessionMeta`、`SessionMetaEvent` 接口，当前文件中不存在） |
| 修改 | `frontend/src/store/use-session.ts`（**新增** `sessionMeta: SessionMeta \| null` 字段、`setSessionMeta` action 及初始值 `null`，当前 `SessionState` 中不存在） |
| 修改 | `frontend/src/app/page.tsx`（替换 `ContextWindowPanel` → `ContextPanel`；新增 `session_metadata` SSE handler；在 `handleSendMessage` 开头**新增** 4 行 store reset，当前代码中不存在） |
| 修改 | `frontend/src/components/CompressionLog.tsx`（新增 `hideInternalHeader` prop） |
| 修改 | `backend/app/api/context.py`（新增 `session_metadata` SSE 事件） |
| 废弃 | `frontend/src/components/ContextWindowPanel.tsx` |
| 废弃 | `frontend/src/components/SlotDetail.tsx` |
| 废弃 | `frontend/src/components/SlotBar.tsx` |

---

## 11. 测试要求（TDD）

### 前端单元测试（`tests/backend/` 风格的前端组件测试）

**SessionMetadataSection：**
- 12 个字段全部渲染，值来自 props
- `sessionMeta = null` 时所有字段显示 `—`
- 使用率 < 70% 显示 `text-success-text`
- 使用率 70–90% 显示 `text-warning-text`
- 使用率 ≥ 90% 显示 `text-error-text`

**TokenMapSection：**
- 12 段进度条渲染，每段宽度比例正确
- 等宽表格显示 12 行
- `slotUsage` 全零时进度条全灰（free space = 100%）

**SlotCardsSection：**
- 默认状态：卡片只显示标题，无内容
- 点击启用卡片展开显示 `slot.content`
- `!slot.enabled` 的卡片有 `opacity-60` 且不可展开
- ⑧ 会话历史卡片使用 `ChevronsUpDown` 图标
- 展开 ⑧ 后显示 `stateMessages` 列表
- 卡片按 `tokens` 降序排列

**ContextPanel（集成）：**
- `session_metadata` 事件触发后，模块一显示模型名
- `token_update` 事件触发后，使用率更新
- 发送新消息时，所有数据重置为初始空状态

### E2E 测试

- 发送消息 → `session_metadata` 到达 → 断言模型名显示
- 发送两轮消息 → 断言第二轮使用率重置后重新更新（验证刷新 bug 修复）
- 点击 Slot ① → 断言内容展开；点击 Slot ⑧ → 断言 stateMessages 列表显示

---

## 12. 完成标准

- [ ] 4 个模块按设计稿渲染，左色条节头统一样式
- [ ] 主题 CSS 变量自动适配（亮色/暗色）
- [ ] 每轮新对话数据正确重置并实时更新
- [ ] `CompressionLog` 无双层 header
- [ ] 后端 `session_metadata` SSE 事件实现
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] E2E 测试覆盖 3 条核心路径
