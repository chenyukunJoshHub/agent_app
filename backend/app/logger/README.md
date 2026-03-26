# 日志系统 README

> 基于四个架构文档（agent-v13、prompt-context-v20、tools-v12、skill-v3）的时序图分析，为整个 Multi-Tool AI Agent 项目设计的完整日志系统。

---

## 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [架构设计](#架构设计)
- [使用指南](#使用指南)
- [日志查询](#日志查询)
- [最佳实践](#最佳实践)
- [参考文档](#参考文档)

---

## 功能特性

### 1. 结构化日志

所有日志输出为 JSON 格式，便于解析和查询：

```json
{
  "timestamp": "2026-03-25T10:30:45.123456Z",
  "level": "INFO",
  "logger": "agent.turn_start",
  "module": "agent",
  "component": "agent_core",
  "session_id": "sess_abc123",
  "user_id": "user_456",
  "thread_id": "thread_789",
  "step_id": 0,
  "message": "Agent turn started",
  "data": {
    "message": "帮我查合同123的签署状态",
    "message_tokens": 12
  },
  "tags": ["agent", "turn_start"]
}
```

### 2. 完整的上下文追踪

每个日志点都包含完整的上下文标识：
- `session_id`: 会话 ID
- `user_id`: 用户 ID
- `thread_id`: Thread ID（checkpointer）
- `step_id`: ReAct Step 编号
- `trace_id`: 分布式追踪 ID（可选）

### 3. 模块化设计

每个模块都有独立的 Logger 类：
- `AgentLogger`: Agent 模块日志
- `ContextLogger`: Context 模块日志
- `ToolsLogger`: Tools 模块日志
- `SkillsLogger`: Skills 模块日志
- `MemoryLogger`: Memory 模块日志
- `ApiLogger`: API 层日志
- `SseLogger`: SSE 流日志

### 4. 覆盖所有关键流程

基于四个架构文档的时序图分析，覆盖所有关键执行路径：
- Agent Turn 完整生命周期
- Middleware 钩子（before_agent、wrap_model_call、after_agent）
- Checkpointer 版本链（恢复、保存、HIL 断点）
- HIL（Human-in-the-Loop）流程
- Context Window 组装
- Tool 执行（并行/串行/子 Agent）
- Skill 激活和执行
- Memory 读写（Short/Long）
- API 请求和 SSE 流

---

## 快速开始

### 1. 创建 Logger

```python
from logger import AgentLogger

# 创建 AgentLogger
logger = AgentLogger(
    session_id="sess_abc123",
    user_id="user_456",
    thread_id="thread_789",
)
```

### 2. 记录日志

```python
# 记录 Turn 开始
logger.turn_start(
    message="帮我查合同123的签署状态",
    message_tokens=12,
)

# 记录 before_agent
logger.middleware_before_agent_start(
    namespace=("profile", "user_456"),
    user_id="user_456",
)

logger.middleware_before_agent_loaded(
    episodic_data={"domain": "legal-tech", "language": "zh"},
    interaction_count=15,
    latency_ms=12,
)

# 设置 Step
logger.set_step(1)

# 记录 wrap_model_call
logger.middleware_wrap_model_call_start(llm_call_index=0)
logger.middleware_wrap_model_call_profile_injected(
    profile_tokens=100,
    ephemeral=True,
)
logger.middleware_wrap_model_call_end(total_system_tokens=1200)

# 记录 Turn 结束
logger.turn_end(
    total_tokens=3456,
    total_latency_ms=2345,
    final_answer_tokens=234,
)
```

### 3. 运行示例

```bash
cd backend/app/logger
python examples.py
```

---

## 架构设计

### 目录结构

```
backend/app/logger/
├── __init__.py              # 统一入口
├── config.py                # 日志配置
├── formatter.py             # 结构化日志格式化器
├── modules/                 # 分模块 Logger
│   ├── __init__.py
│   ├── base.py             # BaseLogger 基类
│   ├── agent.py            # Agent 模块日志 ✅
│   ├── context.py          # Context 模块日志 ⏳
│   ├── tools.py            # Tools 模块日志 ⏳
│   ├── skills.py           # Skills 模块日志 ⏳
│   ├── memory.py           # Memory 模块日志 ⏳
│   ├── api.py              # API 层日志 ⏳
│   └── sse.py             # SSE 流日志 ⏳
└── examples.py             # 使用示例
```

### 组件说明

#### 1. BaseLogger

所有模块 Logger 的基类，提供统一的日志接口：
- `debug()`: DEBUG 级别日志
- `info()`: INFO 级别日志
- `warning()`: WARNING 级别日志
- `error()`: ERROR 级别日志
- `critical()`: CRITICAL 级别日志
- `exception()`: 异常日志（自动包含异常信息）
- `update_context()`: 更新日志上下文
- `set_step()`: 设置当前 Step ID
- `increment_step()`: 递增 Step ID

#### 2. StructuredFormatter

结构化 JSON 格式化器，自动将日志转换为 JSON 格式。

#### 3. LogContext

上下文管理器，用于跨函数传递上下文字段：
```python
with LogContext(session_id="xxx", user_id="yyy"):
    logger.info("Message")
```

#### 4. ContextFilter

上下文过滤器，自动将 LogContext 中的字段添加到日志记录。

---

## 使用指南

### AgentLogger

Agent 模块日志，覆盖 Agent Turn、Middleware、Checkpointer、HIL。

#### Agent Turn 日志

```python
logger.turn_start(message="...", message_tokens=12)
logger.turn_end(total_tokens=3456, total_latency_ms=2345, final_answer_tokens=234)
```

#### Middleware 日志

```python
# before_agent
logger.middleware_before_agent_start(namespace=..., user_id=...)
logger.middleware_before_agent_loaded(episodic_data=..., interaction_count=15, latency_ms=12)
logger.middleware_before_agent_end(latency_ms=15)

# wrap_model_call
logger.middleware_wrap_model_call_start(llm_call_index=0)
logger.middleware_wrap_model_call_profile_injected(profile_tokens=100, ephemeral=True)
logger.middleware_wrap_model_call_end(total_system_tokens=1200)

# after_agent
logger.middleware_after_agent_start(turn_duration_ms=2345)
logger.middleware_after_agent_profile_updated(interaction_count=16, preferences={...})
logger.middleware_after_agent_end()
```

#### Checkpointer 日志

```python
# restore
logger.checkpoint_restore_start(thread_id="thread_789")
logger.checkpoint_restore_first()
logger.checkpoint_restore_history(step_id=5, checkpoint_id="cp_123", message_count=12)
logger.checkpoint_restore_interrupt(step_id=3, checkpoint_id="cp_int", pending_tool="send_email")

# save
logger.checkpoint_save_start(thread_id="thread_789", step_id=3)
logger.checkpoint_save_end(checkpoint_id="cp_123", parent_id="cp_122", message_count=12, state_size_bytes=1024)
```

#### HIL 日志

```python
logger.hil_trigger(tool_name="send_email", tool_args={...}, effect_class="external_write")
logger.hil_agent_paused(interrupt_id="int_123", checkpoint_id="cp_int")
logger.hil_sse_interrupt_sent(interrupt_id="int_123", tool_name="send_email", tool_args={...})
logger.hil_user_action(interrupt_id="int_123", action="approve")
logger.hil_resume_start(interrupt_id="int_123", action="approve")
logger.hil_tool_executed(tool_name="send_email", result_summary="Email sent successfully")
logger.hil_tool_rejected(tool_name="send_email", rejection_reason="User cancelled")
logger.hil_loop_resumed()
```

### Step 管理

```python
# 设置 Step
logger.set_step(1)

# 递增 Step
logger.increment_step()  # Step 变为 2
logger.increment_step()  # Step 变为 3
```

### 上下文更新

```python
# 更新上下文字段
logger.update_context(trace_id="trace_xyz")
```

---

## 日志查询

### 使用 jq 查询 JSON 日志

```bash
# 查询某个 session 的完整日志
jq 'select(.session_id == "sess_abc123")' logs/agent.log

# 查询某个 turn 的所有日志
jq 'select(.session_id == "sess_abc123" and .step_id == 5)' logs/agent.log

# 查询所有错误日志
jq 'select(.level == "ERROR")' logs/agent.log

# 查询工具调用耗时
jq 'select(.logger == "toolnode.execute_tool_end") | {tool_name: .data.tool_name, latency_ms: .data.latency_ms}' logs/agent.log

# 查询 Token 使用统计
jq 'select(.logger | contains("llm.invoke_end")) | {input_tokens: .data.input_tokens, output_tokens: .data.output_tokens}' logs/agent.log

# 查询 HIL 事件
jq 'select(.logger | contains("hil"))' logs/agent.log
```

### 使用 Python 分析日志

```python
import json

# 读取日志
with open('logs/agent.log') as f:
    logs = [json.loads(line) for line in f]

# 按标签过滤
agent_logs = [log for log in logs if 'agent' in log.get('tags', [])]

# 按模块过滤
tool_logs = [log for log in logs if log.get('module') == 'tools']

# 按级别过滤
error_logs = [log for log in logs if log.get('level') == 'ERROR']

# 计算平均延迟
llm_calls = [log for log in logs if 'llm.invoke_end' in log.get('logger', '')]
avg_latency = sum(log['data']['latency_ms'] for log in llm_calls) / len(llm_calls)
print(f"Average LLM latency: {avg_latency:.2f}ms")
```

---

## 最佳实践

### 1. 日志级别选择

| 场景 | 日志级别 | 示例 |
|------|---------|------|
| 详细的执行流程、中间状态 | DEBUG | 函数入口/出口、中间变量 |
| 关键业务事件、状态变更 | INFO | Turn 开始/结束、工具调用 |
| 降级、重试、超时 | WARNING | Token 超限、工具重试 |
| 错误和异常 | ERROR | 工具失败、LLM 错误 |
| 严重故障 | CRITICAL | 数据库连接失败 |

### 2. 日志编写原则

- **上下文完整**：每次日志都包含 session_id、user_id、thread_id
- **数据结构化**：将详细信息放在 `data` 字段
- **消息简洁**：消息文本控制在 50 字符以内
- **无敏感信息**：不要记录密码、Token、PII 数据

### 3. 性能考虑

- **避免高频 DEBUG 日志**：SSE token 推送可使用 DEBUG 或采样
- **异步写入**：使用 QueueHandler 避免阻塞主流程
- **日志轮转**：控制单文件大小，避免磁盘占满

---

## 参考文档

- [日志系统设计文档](../../docs/logging-design.md) - 完整的设计规范和日志点列表
- [日志系统实现总结](../../docs/logging-implementation-summary.md) - 实现进度和待办事项
- [使用示例](./examples.py) - 各模块日志调用示例

### 架构文档

日志系统基于以下四个架构文档的时序图分析设计：
- [Agent 架构 v13](../../docs/arch/agent-v13.md)
- [Prompt + Context 架构 v20](../../docs/arch/prompt-context-v20.md)
- [Tools 架构 v12](../../docs/arch/tools-v12.md)
- [Skill 架构 v3](../../docs/arch/skill-v3.md)
