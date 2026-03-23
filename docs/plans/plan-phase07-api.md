# Phase 07 — FastAPI SSE 接口

## 目标

实现 FastAPI 后端 API，包含 /chat SSE 流式接口、/chat/resume HIL 恢复接口、/skills 查询接口。

## 架构文档参考

- Agent v13 §2.4 SSE 流式架构
- Agent v13 §1.13 HIL 完整设计

## 测试用例清单（TDD 先写）

### POST /chat
- [ ] 返回 SSE 流
- [ ] 正确推送 thought 事件
- [ ] 正确推送 tool_start 事件
- [ ] 正确推送 tool_result 事件
- [ ] 正确推送 context_window 事件
- [ ] 正确推送 hil_interrupt 事件
- [ ] 正确推送 done 事件
- [ ] 错误处理正常

### POST /chat/resume
- [ ] 正确恢复会话
- [ ] approve 操作继续执行
- [ ] reject 操作返回取消消息

### GET /skills
- [ ] 返回所有 skills
- [ ] 格式正确

### GET /skills/{skill_id}/content
- [ ] 返回 skill 内容
- [ ] 不存在的 skill 返回 404

### GET /session/{session_id}/context
- [ ] 返回 TokenBudgetState
- [ ] 格式正确

## 实现步骤（TDD 顺序）

### Step 1 — Pydantic 模型
- 定义 ChatRequest
- 定义 ResumeRequest

### Step 2 — /chat 接口
- 写测试，确认 RED
- 实现 SSE 流式逻辑
- 确认 GREEN

### Step 3 — /chat/resume 接口
- 写测试，确认 RED
- 实现恢复逻辑
- 确认 GREEN

### Step 4 — 辅助接口
- 实现 /skills
- 实现 /skills/{skill_id}/content
- 实现 /session/{session_id}/context

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] SSE 流式推送正常
- [ ] HIL 恢复正常
- [ ] 所有接口工作正常
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
