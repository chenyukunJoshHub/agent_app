# Design Spec: Context UI Redesign & Turn Visualization

**Date**: 2026-03-24
**Status**: Approved
**Scope**: Frontend (主) + Backend (done 事件小改)

---

## 概述

本次改动包含 6 项 UI 改进，目标是让 Context 面板数据动态化、链路面板更清晰、会话历史可视化真实后端状态，并强化 Turn 边界感知。

---

## 改动 1 — 链路模块：移除 Context Slot 内容快照

**文件**：`frontend/src/components/ExecutionTracePanel.tsx`、`frontend/src/app/page.tsx`

移除 `ExecutionTracePanel` 中 `slotDetails.length > 0` 条件包裹的 `<section>`（"Context Slot 内容快照"），因其与右侧 Context 面板重复。

具体删除项：
- 第 86–127 行的 `slotDetails` 渲染区块（整个 `<section>`）
- `openSlots` state（第 55 行）和 `toggleSlot` handler（第 69–71 行）——仅服务于被删除区块的死代码
- 组件 props 接口中的 `slotDetails: SlotDetail[]`（第 13–15 行）
- 文件顶部的 `SlotDetail` import（第 9 行）
- `page.tsx` 中 `<ExecutionTracePanel>` 调用处的 `slotDetails={slotDetails}` 传参

---

## 改动 2 — Context 面板：全 10 Slot 空状态展示

**文件**：`frontend/src/app/page.tsx`、`frontend/src/components/ContextWindowPanel.tsx`、`frontend/src/types/context-window.ts`

**问题**：初始状态 `contextWindowData === null` 时，Context 面板整体不渲染。

**方案**：
- 在 `context-window.ts` 中新增 `EMPTY_CONTEXT_DATA` 常量，包含全部 10 个 Slot，所有 token 值为 0
- `page.tsx` 中将 `contextWindowData` store 初始值改为 `EMPTY_CONTEXT_DATA`，去掉"暂无数据"占位分支，Context 面板始终渲染
- `ContextWindowPanel` 的 `slotUsage` 渲染固定按 ①–⑩ 顺序展示所有 Slot，tokens 为 0 时显示 `0/0 (0%)`

**关于 `slotDetails` prop 和"完整 Slot 快照"区块**：
- `ContextWindowPanel` 中第 263–268 行的"完整 Slot 快照"区块（`slotDetails` 驱动）**保留不动**——该区块由 `slot_details` SSE 事件填充，是有独立价值的内容快照；与改动 1 删除的是链路面板里的同名区块，两者不同
- `slotDetails?: SlotDetail[]` prop 继续保留在 `ContextWindowPanel`

**关于 Slot ⑨/⑩ 在 category-aggregate 视图的问题**：
- `ContextWindowPanel` 第 108–142 行的 `categoryUsage` aggregate 当前只聚合 8 个 key（不含 `output_format`、`user_input`），导致 ⑨/⑩ 在"Estimated usage by category"小节中不显示
- 修复：将 `aggregate` 初始化对象扩展为包含全部 10 个 key，`rawToCanonical` 映射表增加 `output_format: 'output_format'` 和 `user_input: 'user_input'` 两条，`categoryLabels` 增加对应中文名
- "Slot 预算分解"子节（第 282 行，直接渲染 `slotUsage` 数组）已天然展示所有 Slot，无需额外修改

**`token_update` 行为变化说明**：
- 改动前 `contextWindowData` 初始为 null，`token_update` handler 中 `if (ctx)` 守卫使其成为空操作
- 改动后默认值为 `EMPTY_CONTEXT_DATA`，`token_update` 到达时将立即更新面板数字，早于 `context_window` 完整事件
- 这是**预期行为**——用户可更早看到 token 计数变化；实现时确认 `if (ctx)` 守卫可移除或简化

**10 个 Slot 顺序**：
| 编号 | key | 显示名 |
|------|-----|--------|
| ① | `system` | System Prompt + Skill Registry |
| ② | `active_skill` | 活跃技能内容 |
| ③ | `few_shot` | 动态 Few-shot |
| ④ | `rag` | RAG 背景知识 |
| ⑤ | `episodic` | 用户画像 |
| ⑥ | `procedural` | 程序性记忆 |
| ⑦ | `tools` | 工具定义 Schema |
| ⑧ | `history` | 会话历史 |
| ⑨ | `output_format` | 输出格式规范 |
| ⑩ | `user_input` | 本轮用户输入 |

---

## 改动 3 — 事件流水：Turn 开始与结束标记

**文件**：`frontend/src/app/page.tsx`、`frontend/src/store/use-session.ts`、`frontend/src/components/ExecutionTracePanel.tsx`

**Store 变更**：
- `TraceEvent`（`trace.ts`）增加可选字段 `turnId?: string`
- Store 新增字段：`currentTurnId: string | null`（初始 `null`）、`turnCounter: number`（初始 `0`）
- 每次用户发送消息（`handleSendMessage`）时，执行 `turnCounter += 1`，生成 `currentTurnId = \`turn_${turnCounter}\``
- `addTraceEvent` 自动为每个事件打上当前 `currentTurnId`（若为 null 则 `turnId` 留 undefined）
- `clearMessages` 同时重置 `currentTurnId = null` 和 `turnCounter = 0`

**turnId 为 null/undefined 的处理**：
- 渲染前按 `turnId` 分组时，`turnId` 为 undefined 的事件归入一个匿名前置组，渲染为无标题的灰色小字"Pre-session"分隔线，不显示编号

**渲染变更**（`ExecutionTracePanel`）：
- 渲染前按 `turnId` 对事件分组，组内保持原有事件顺序
- 每组开头插入 Turn 分隔线：
  ```
  ──── Turn #N  HH:mm:ss ────
  ```
  样式：`text-xs text-text-muted bg-primary/10 rounded px-2 py-0.5`

- 收到 `done` 事件后，在**当前 Turn**（`currentTurnId`）末尾追加完成 badge：
  ```
  ✓ Turn #N 完成 · X 个事件
  ```
  样式：`text-xs text-success-text`

**HIL 流程说明**：Turn 完成 badge **仅在主 SSE 流程**（`sseManager.on('done', ...)`）触发。HIL resume 路径（`handleConfirm` / `handleCancel`）使用独立的 `consumeSSEStream`，不触发 Turn badge，该路径的 trace 事件仍会被打上同一 `turnId`（HIL 属于同一 Turn 的延续）。

**错误处理**：若主 SSE 流收到 `error` 事件，当前 Turn badge 显示为失败状态：
```
✗ Turn #N 失败
```
样式：`text-xs text-error-text`

---

## 改动 4 — MessageList + state["messages"] 同步

**后端改动**：`backend/app/agent/langchain_engine.py`（或 SSE 推送处）

在 `done` SSE 事件 payload 中追加 `messages` 字段：
```json
{
  "event": "done",
  "data": {
    "answer": "...",
    "messages": [
      { "role": "user", "content": "..." },
      { "role": "assistant", "content": "...", "tool_calls": [...] },
      { "role": "tool", "content": "...", "tool_call_id": "..." }
    ]
  }
}
```

**新增 TypeScript 类型**（`frontend/src/store/use-session.ts` 或单独 types 文件）：
```typescript
export interface StateMessage {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;  // 仅 role=tool 时有值
}
```

注意：`StateMessage` 独立于现有的 `Message` 接口，不修改 `Message.role` 联合类型。

**前端 Store 变更**：
- 新增字段 `stateMessages: StateMessage[]`（初始 `[]`）
- 新增 action `setStateMessages(msgs: StateMessage[]): void`
- `clearMessages` 同时重置 `stateMessages: []`

**A. Slot ⑧ 展示（Context 面板）**：
- `ContextWindowPanel` 接收新 prop `stateMessages?: StateMessage[]`
- Slot ⑧（`history`）行点击展开后，显示 stateMessages 预览列表：`[role] 内容前 80 字符...`
- tokens 数值沿用后端已有的 `history` slot usage 字段

**B. MessageList（主聊天区）**：
- 收到 `done` 后，若 `messages.length`（后端）`>=` `messages.length`（前端），则用 `stateMessages` **替换** `messages`（前端乐观渲染被真实数据覆盖）；否则保留前端状态
- 新增 `tool` role 气泡：左对齐、灰色背景 `bg-bg-muted`、🔧 图标 + tool name 标题 + 内容折叠展开
- `assistant` 中间步骤（有 `tool_calls` 但 `content` 为空）以链式轻量气泡展示，区别于最终回答气泡
- `MessageBubble` 扩展支持 `StateMessage` 类型渲染（或新建 `StateMessageBubble` 组件）

---

## 改动 5 — Compressor 压缩内容展示（C 方案）

**文件**：`frontend/src/components/MessageList.tsx`、`frontend/src/types/context-window.ts`、`frontend/src/components/CompressionLog.tsx`

**类型扩展**（`context-window.ts`）：
```typescript
export interface CompressionEvent {
  // ...现有字段不变...
  summary_text?: string;  // 新增：压缩摘要文本，后端可选提供
}
```

**MessageList 轻量提示**：
- 每当 `compressionEvents` 新增条目（在 `done` 事件处理后对比前后数量），在 MessageList 对应 Turn 边界后插入分隔气泡：
  ```
  💾  历史已压缩 · 节省 1,240 tokens  (summarization)
  ```
  样式：居中、灰色小字 `text-xs text-text-muted`、细横线两侧，不可交互
- 插入位置：`done` 事件处理时，追加到当前 Turn 最后一条消息之后

**Context 面板 CompressionLog**：
- 现有 `CompressionLog` 组件结构不变
- 若 `CompressionEvent.summary_text` 存在，在每条记录末尾追加可展开的"摘要"区块：`<pre>` 渲染压缩摘要文本，最大高度 200px 可滚动
- 无 `summary_text` 时降级为现有展示，不破坏现有功能

---

## 数据流总图

```
用户发消息
  → store: turnCounter++, currentTurnId = "turn_N"
  → SSE 建立连接
  → trace_event  → addTraceEvent(event + currentTurnId)
  → slot_details → setSlotDetails（Context 面板"完整 Slot 快照"刷新）
  → context_window → setContextWindowData（覆盖 EMPTY_CONTEXT_DATA）
  → token_update → 更新 contextWindowData.budget（现在初始非 null，立即生效）
  → done(answer + messages + compressionEvents)
      → setStateMessages(messages)      // Slot ⑧ 预览 + MessageList 替换
      → 检查 compressionEvents 新增条目 → 插入压缩提示气泡
      → 主 SSE 流：追加 Turn #N 完成/失败 badge
      → setLoading(false)

clearMessages()
  → 重置 messages=[], stateMessages=[], traceEvents=[]
  → 重置 currentTurnId=null, turnCounter=0
  → 重置 contextWindowData=EMPTY_CONTEXT_DATA
```

---

## 不改动的部分

- `CompressionLog` 组件现有样式与数据渲染
- `ToolCallCard` 组件
- 整体布局（左侧聊天 + 右侧 Tab 面板）
- SSE 连接管理逻辑（`sseManager`）
- 其他 SSE 事件处理（`thought`、`hil_interrupt`、`error`）
- `ContextWindowPanel` 中的"完整 Slot 快照"区块（`slotDetails` 驱动，保留）

---

## 验收标准

- [ ] 初始进入页面，Context 面板展示全部 10 个 Slot，均显示 `0/0 (0%)`，包含 ⑨ 输出格式 和 ⑩ 用户输入
- [ ] 链路面板不再出现"Context Slot 内容快照"区块
- [ ] 事件流水每次 Turn 有分隔线（含编号和时间戳），Turn 正常结束有 ✓ 完成 badge，异常结束有 ✗ 失败 badge
- [ ] 发送消息后，MessageList 收到 `done` 后用后端真实 messages 替换，包含 tool 角色气泡和 assistant 中间步骤
- [ ] Context 面板 Slot ⑧ 展开后显示 stateMessages 摘要列表
- [ ] 压缩发生时 MessageList 出现轻量提示气泡，CompressionLog 如有 `summary_text` 则展示可展开摘要
- [ ] 执行 `clearMessages()` 后，Turn 计数器归零，新一轮 Turn 从 #1 重新开始
- [ ] HIL 中断/恢复后，trace 事件仍归属原 Turn，不新增 Turn 分隔线
