# Phase 10 — Context Window 面板

## 目标

实现 Token 上下文可视化面板，展示 10 个 Slot 的使用情况、颜色编码、进度条和压缩事件日志。

## 架构文档参考

- agent claude code prompt.md §components/context-window/
- Prompt v20 §1.2 十大子模块与 Context Window 分区

## 测试用例清单（TDD 先写）

### ContextWindowPanel
- [x] 正确渲染 4 个区域
  - [x] 总体进度条
  - [x] Slot 分解表
  - [x] 压缩事件日志
  - [x] 统计行

### SlotBar
- [x] 正确显示 Slot 名称
- [x] 颜色点正确显示
- [x] 迷你进度条正确
- [x] used/max tokens 正确显示
- [x] overflow 警告正确显示

### 压缩事件日志
- [x] 正确显示压缩事件
- [x] before/after tokens 正确显示
- [x] tokens_saved 正确计算

### 实时更新
- [x] SSE context_window 事件触发更新
- [x] 所有数据同步更新

## 实现步骤（TDD 顺序）

### Step 1 — 类型定义
- 定义 TokenBudgetState
- 定义 SlotUsage
- 定义 CompressionEvent

### Step 2 — SlotBar 组件
- 写测试，确认 RED
- 实现 SlotBar
- 确认 GREEN

### Step 3 — 压缩日志组件
- 写测试，确认 RED
- 实现 CompressionLog
- 确认 GREEN

### Step 4 — ContextWindowPanel
- 写测试，确认 RED
- 实现完整面板
- 确认 GREEN

### Step 5 — SSE 集成
- 集成 useSSE hook
- 实现 context_window 事件处理

## 完成标准

- [x] 所有测试用例实现且通过
- [x] 10 个 Slot 正确显示
- [x] 颜色编码符合设计
- [x] 实时更新正常
- [x] findings.md 中记录技术决策
- [x] progress.md 更新本阶段会话日志
- [x] task_plan.md 阶段状态更新为 ✅ done
