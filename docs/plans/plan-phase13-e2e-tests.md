# Phase 13 — E2E 测试

## 目标

实现完整的端到端测试套件，覆盖基础对话、ReAct 链路、Context Window、Skills 激活和 HIL 流程。

## 架构文档参考

- agent claude code prompt.md §E2E Tests
- 各阶段的功能需求

## 测试用例清单

### chat.spec.ts — 基础对话流程
- [ ] 页面加载 — 所有 3 个面板可见
- [ ] 发送消息 — SSE 流式开始
- [ ] thought 气泡渐进出现
- [ ] 工具调用触发 — ToolCallStep 正确渲染
- [ ] 最终答案 — done 事件触发
- [ ] 会话持久化 — 刷新后历史恢复
- [ ] 第二轮对话 — 记住上下文

### react-trace.spec.ts — ReAct 链路可视化
- [ ] ReActPanel 在 AI 消息下方渲染
- [ ] Thought 步骤紫色边框
- [ ] Tool Call 步骤蓝色边框
- [ ] Tool Result 步骤青色边框
- [ ] 步骤时间徽章正确
- [ ] 折叠展开动画正常
- [ ] 多工具 turn 步骤顺序正确

### context-window.spec.ts — Context Window 面板
- [ ] ContextWindowPanel 在右侧栏可见
- [ ] 总体进度条每次消息后更新
- [ ] 所有 Slot 行正确渲染
- [ ] Slot overflow 显示琥珀色警告
- [ ] 压缩事件出现在日志中
- [ ] 统计卡片更新
- [ ] Slot 颜色符合设计

### skills.spec.ts — Skills 激活流程
- [ ] SkillPanel 渲染所有 3 个 skills
- [ ] 状态徽章正确
- [ ] 点击 skill → SkillDetail 打开
- [ ] 触发 legal-search skill:
  - [ ] activate_skill 工具调用出现
  - [ ] legal-search SKILL.md 内容出现
  - [ ] legal-search skill 卡片显示 ACTIVE
- [ ] ContextWindow Slot ② 显示 legal-search token
- [ ] 第二轮不重复 activate_skill

### hil.spec.ts — HIL 确认流程
- [ ] 发送触发 send_email 的消息
- [ ] HILConfirmDialog 出现
- [ ] 对话框显示正确 tool_args
- [ ] 点击 Cancel → 取消消息
- [ ] 重复，点击 Confirm → 执行成功
- [ ] ContextWindowPanel 更新
- [ ] 会话检查点保持状态

## 实现步骤（TDD 顺序）

### Step 1 — Playwright 配置
- 配置 playwright.config.ts
- 设置 headless: false
- 设置 slowMo: 300
- 配置 webServer

### Step 2 — helpers.ts
- 实现 SSE 辅助函数
- 实现等待辅助函数

### Step 3 — chat.spec.ts
- 写所有测试
- 逐个实现 GREEN

### Step 4 — react-trace.spec.ts
- 写所有测试
- 逐个实现 GREEN

### Step 5 — context-window.spec.ts
- 写所有测试
- 逐个实现 GREEN

### Step 6 — skills.spec.ts
- 写所有测试
- 逐个实现 GREEN

### Step 7 — hil.spec.ts
- 写所有测试
- 逐个实现 GREEN

## Playwright 配置要求

```typescript
{
  use: {
    headless: false,        // 必须有头模式
    slowMo: 300,            // 人眼可跟随
    trace: "on-first-retry",
    screenshot: "on",
    video: "retain-on-failure",
  },
  webServer: [
    {
      command: "cd backend && uvicorn main:app --port 8000",
      port: 8000,
      reuseExistingServer: true,
    },
    {
      command: "cd frontend && npm run dev",
      port: 3000,
      reuseExistingServer: true,
    },
  ],
}
```

## 完成标准

- [ ] 所有 5 个 spec 文件实现且通过
- [ ] 所有测试用例覆盖
- [ ] headed mode 配置正确
- [ ] SSE 超时配置正确 (≥ 15000ms)
- [ ] 失败用例保留截图和录像
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
