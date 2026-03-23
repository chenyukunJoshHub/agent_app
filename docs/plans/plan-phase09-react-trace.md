# Phase 09 — ReAct 链路可视化

## 目标

实现 ReAct 推理链可视化组件，展示 Agent 的完整思考过程、工具调用和结果，支持颜色编码和折叠展开。

## 架构文档参考

- agent claude code prompt.md §components/react-trace/
- Agent v13 §1.12 ReAct 链路展示

## 测试用例清单（TDD 先写）

### ReActPanel
- [ ] 正确渲染垂直时间轴
- [ ] Thought 步骤显示紫色边框
- [ ] Tool Call 步骤显示蓝色边框
- [ ] Tool Result 步骤显示青色边框
- [ ] Final Answer 步骤显示绿色边框
- [ ] HIL Interrupt 步骤显示琥珀色边框

### 步骤组件
- [ ] ThoughtStep 正确显示
- [ ] ToolCallStep 正确显示参数
- [ ] ObservationStep 正确显示结果
- [ ] 折叠展开功能正常

### 动画
- [ ] Framer Motion 动画正常
- [ ] 步骤按顺序进入

## 实现步骤（TDD 顺序）

### Step 1 — 数据结构
- 定义 ReActStep 类型
- 定义 ReActTrace 类型

### Step 2 — 基础组件
- 写测试，确认 RED
- 实现 ThoughtStep
- 实现 ToolCallStep
- 实现 ObservationStep
- 确认 GREEN

### Step 3 — ReActPanel
- 写测试，确认 RED
- 实现垂直时间轴
- 实现颜色编码
- 实现折叠展开
- 确认 GREEN

### Step 4 — 动画
- 集成 Framer Motion
- 实现交错进入动画

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] ReAct 链路完整展示
- [ ] 颜色编码正确
- [ ] 动画流畅
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
