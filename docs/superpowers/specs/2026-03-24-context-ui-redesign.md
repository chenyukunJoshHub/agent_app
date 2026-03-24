# Design Spec: Context UI Redesign & Turn Visualization

**Date**: 2026-03-24
**Status**: Approved
**Scope**: Frontend (主) + Backend (done 事件小改)

---

## 概述

本次改动包含 6 项 UI 改进，目标是让 Context 面板数据动态化、链路面板更清晰、会话历史可视化真实后端状态，并强化 Turn 边界感知。

---

## 改动 1 — 链路模块：移除 Context Slot 内容快照

**文件**：`frontend/src/components/ExecutionTracePanel.tsx`

移除 `ExecutionTracePanel` 中 `slotDetails.length > 0` 条件包裹的 `<section>`（"Context Slot 内容快照"），因其与右侧 Context 面板重复。

- 删除第 86–127 行的 `slotDetails` 渲染区块
- 从组件 props 中移除 `slotDetails: SlotDetail[]`（如 `page.tsx` 调用处也不再传入）
- `SlotDetail` import 随之清理

---

## 改动 2 — Context 面板：全 10 Slot 空状态展示

**文件**：`frontend/src/app/page.tsx`、`frontend/src/components/ContextWindowPanel.tsx`、`frontend/src/types/context-window.ts`

**问题**：初始状态 `contextWindowData === null` 时，Context 面板整体不渲染，用户看不到任何 Slot 结构。

**方案**：
- 在 `context-window.ts` 中新增 `EMPTY_CONTEXT_DATA` 常量，包含全部 10 个 Slot，所有 token 值为 0
- `page.tsx` 中 `contextWindowData` 默认值改为 `EMPTY_CONTEXT_DATA`，去掉"暂无数据"占位分支，Context 面板始终渲染
- `ContextWindowPanel` 的 `slotUsage` 渲染固定按 ①–⑩ 顺序展示所有 Slot，tokens 为 0 时显示 `0/0 (0%)`，进度条宽度为 0

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
- `TraceEvent` 增加可选字段 `turnId: string`
- Store 增加 `currentTurnId: string | null` 和 `turnCounter: number`
- `addMessage`（用户消息）触发时，生成新 `turnId = turn_${++turnCounter}`，存入 store
- `addTraceEvent` 自动为每个事件打上当前 `currentTurnId`

**渲染变更**（`ExecutionTracePanel`）：
- 渲染前按 `turnId` 对事件分组
- 每组开头插入 Turn 分隔线：
  ```
  ──── Turn #N  HH:mm:ss ────
  ```
  样式：`text-xs text-text-muted bg-primary/10 rounded px-2 py-0.5`
- 收到 `done` 事件后，在该 turn 末尾追加完成 badge：
  ```
  ✓ Turn #N 完成 · X 个事件
  ```
  样式：`text-xs text-success-text`

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
      { "role": "tool", "content": "..." }
    ]
  }
}
```

**前端 Store 变更**：
- 新增 `stateMessages: StateMessage[]` 字段（区别于已有的 `messages`）
- 新增 `setStateMessages(msgs: StateMessage[])` action

**A. Slot ⑧ 展示（Context 面板）**：
- `ContextWindowPanel` 接收 `stateMessages` prop
- Slot ⑧（`history`）展示区域渲染 stateMessages 列表预览：角色标签 + 内容前 100 字符摘要
- tokens 数值沿用后端已有的 `history` slot usage

**B. MessageList（主聊天区）**：
- 收到 `done` 后用 `stateMessages` **替换**前端 `messages`（乐观渲染被真实数据覆盖）
- 新增 `tool` role 气泡：左对齐、灰色背景、🔧 图标 + tool name + 内容折叠
- assistant 中间步骤（有 tool_calls 无 content）以链式轻量气泡展示
- 替换策略：比较长度，若后端 messages 更完整则替换，否则保留前端状态

---

## 改动 5 — Compressor 压缩内容展示（C 方案）

**文件**：`frontend/src/components/MessageList.tsx`、`frontend/src/components/CompressionLog.tsx`

**MessageList 轻量提示**：
- 每当 `compressionEvents` 新增条目，在 MessageList 对应 Turn 边界后插入分隔气泡：
  ```
  💾  历史已压缩 · 节省 1,240 tokens  (summarization)
  ```
  样式：居中、灰色小字 `text-xs text-text-muted`、细横线两侧，不可交互

- 插入时机：`done` 事件到达后检查 `compressionEvents`，按 `timestamp` 匹配到对应 Turn

**Context 面板 CompressionLog（已有）**：
- 现有 `CompressionLog` 组件保持不变
- 如后端 `done` payload 中 compressionEvents 携带可选 `summary_text` 字段，则在每条记录追加可展开摘要内容区块
- 无 `summary_text` 时降级为现有展示，不破坏现有功能

---

## 数据流总图

```
用户发消息
  → store.currentTurnId = new turnId
  → SSE 建立连接
  → trace_event → addTraceEvent(event + turnId)
  → slot_details → setSlotDetails
  → context_window → setContextWindowData
  → token_update → 更新 contextWindowData.budget
  → done(answer + messages + compressionEvents)
      → setStateMessages(messages)         // Slot ⑧ + MessageList 替换
      → 追加 Turn 完成 badge
      → 检查 compressionEvents → 插入压缩提示气泡
```

---

## 不改动的部分

- `CompressionLog` 组件现有样式
- `ToolCallCard` 组件
- 整体布局（左侧聊天 + 右侧 Tab 面板）
- SSE 连接管理逻辑（`sseManager`）
- 其他 SSE 事件处理（`thought`、`hil_interrupt`、`error`）

---

## 验收标准

- [ ] 初始进入页面，Context 面板展示全部 10 个 Slot，均显示 `0/0 (0%)`
- [ ] 链路面板不再出现"Context Slot 内容快照"区块
- [ ] 事件流水每次 Turn 有分隔线，Turn 结束有完成 badge
- [ ] 发送消息后，MessageList 收到 `done` 后显示完整后端 messages（含 tool 角色气泡）
- [ ] Context 面板 Slot ⑧ 显示 stateMessages 摘要
- [ ] 压缩发生时 MessageList 出现轻量提示气泡，CompressionLog 保持现有功能
