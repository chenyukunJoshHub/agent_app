# Phase 04 — Agent 核心

## 目标

实现 LangChain Engine 和 TraceMiddleware，组装完整的 Agent 执行器，支持 ReAct 循环、HIL 人工介入和可观测性。

## 架构文档参考

- Agent v13 §2.1 Workflow 映射
- Agent v13 §2.2 Middleware 执行流程
- Agent v13 §1.13 HIL 完整设计

## 测试用例清单（TDD 先写）

### build_agent()
- [ ] 成功创建 agent 实例
- [ ] checkpointer 正确配置
- [ ] store 正确配置
- [ ] middleware 列表正确加载

### TraceMiddleware
- [ ] after_model 正确解析 AIMessage
- [ ] 正确提取 thought 文本
- [ ] 正确提取 tool_calls
- [ ] emit SSE 事件

### LLM Factory
- [ ] 支持 OpenAI provider
- [ ] 支持 Anthropic provider
- [ ] 支持 Ollama provider
- [ ] 错误 provider 抛出异常

## 实现步骤（TDD 顺序）

### Step 1 — LLM Factory
- 写测试，确认 RED
- 实现 llm_factory()
- 支持多 provider
- 确认 GREEN

### Step 2 — TraceMiddleware
- 写测试，确认 RED
- 实现 after_model 钩子
- 实现 thought/tool_calls 提取
- 确认 GREEN

### Step 3 — build_agent
- 写测试，确认 RED
- 组装所有组件
- 配置 middleware
- 确认 GREEN

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] Agent 可正常执行 ReAct 循环
- [ ] SSE 事件正确推送
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
