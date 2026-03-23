# Phase 12 — HIL 人工介入 UI

## 目标

实现 HIL 确认对话框组件，支持全屏模态覆盖、approve/reject 流程和正确的参数显示。

## 架构文档参考

- agent claude code prompt.md §components/hil/
- Agent v13 §1.13 HIL 完整设计

## 测试用例清单（TDD 先写）

### HILConfirmDialog
- [ ] hil_interrupt 事件触发弹窗
- [ ] 正确显示工具名称
- [ ] 正确显示工具参数
  - [ ] to 参数正确显示
  - [ ] subject 参数正确显示
  - [ ] body 参数正确显示
- [ ] 警告文本正确显示

### Approve/Reject 流程
- [ ] 点击 Cancel 发送 reject 请求
- [ ] 点击 Confirm 发送 approve 请求
- [ ] POST /chat/resume 正确调用

### 对话框状态
- [ ] 弹窗打开时背景锁定
- [ ] 成功后弹窗关闭
- [ ] 错误处理正确

## 实现步骤（TDD 顺序）

### Step 1 — 类型定义
- 定义 HILInterrupt
- 定义 ResumeRequest

### Step 2 — HILConfirmDialog 组件
- 写测试，确认 RED
- 实现对话框 UI
- 确认 GREEN

### Step 3 — Approve/Reject 逻辑
- 写测试，确认 RED
- 实现按钮处理逻辑
- 确认 GREEN

### Step 4 — API 集成
- 集成 /chat/resume 接口
- 实现 SSE 事件监听

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] HIL 对话框正确显示
- [ ] Approve/Reject 流程完整
- [ ] API 集成正常
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
