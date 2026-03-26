# 日志系统设计文档

> 基于 agent-v13、prompt-context-v20、tools-v12、skill-v3 四个架构文档的时序图分析，设计完整的日志系统。

---

## 设计目标

1. **全覆盖**：覆盖所有关键执行路径、决策点、数据流
2. **可追溯**：每个日志点包含完整的上下文标识
3. **结构化**：使用 JSON 格式，便于解析和查询
4. **可观测**：支持实时监控、问题诊断、性能分析

---

## 1. 日志系统架构

### 1.1 日志层级

```
logger/
├── __init__.py                 # 统一入口
├── config.py                   # 日志配置
├── formatter.py               # 结构化日志格式化
├── context.py                 # 日志上下文管理器
├── modules/                   # 分模块 Logger
│   ├── __init__.py
│   ├── base.py               # BaseLogger 基类
│   ├── agent.py              # Agent 模块日志
│   ├── context.py            # Context 模块日志
│   ├── tools.py              # Tools 模块日志
│   ├── skills.py             # Skills 模块日志
│   ├── memory.py             # Memory 模块日志
│   ├── api.py                # API 层日志
│   └── sse.py               # SSE 流日志
└── utils.py                  # 工具函数
```

### 1.2 日志级别

| 级别 | 用途 | 典型场景 |
|------|------|---------|
| DEBUG | 详细执行流程 | 每个函数入口/出口、中间状态 |
| INFO | 关键业务事件 | Turn 开始/结束、工具调用、状态变更 |
| WARNING | 非致命异常 | 重试、降级、超时 |
| ERROR | 错误和异常 | 工具失败、权限拒绝、LLM 错误 |
| CRITICAL | 严重故障 | 数据库连接失败、进程崩溃 |

### 1.3 上下文标识

所有日志必须包含以下核心字段：

```python
{
  "timestamp": "2026-03-25T10:30:45.123Z",    # ISO 8601
  "level": "INFO",                            # 日志级别
  "module": "agent",                          # 模块名称
  "component": "memory_middleware",            # 组件名称
  "session_id": "sess_abc123",                # 会话 ID
  "user_id": "user_456",                      # 用户 ID
  "thread_id": "thread_789",                  # Thread ID（checkpointer）
  "step_id": 5,                              # ReAct Step 编号
  "trace_id": "trace_xyz",                    # 分布式追踪 ID（可选）
  "message": "User profile loaded from Long Memory",
  "data": {                                   # 结构化数据
    "namespace": ("profile", "user_456"),
    "episodic": {...},
    "latency_ms": 12
  }
}
```

---

## 2. 模块日志点设计

### 2.1 Agent 模块 (agent.py)

#### 2.1.1 Agent Turn 完整时序

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **用户请求** | `agent.turn_start` | INFO | session_id, user_id, message, message_tokens |
| **Agent 调用** | `agent.invoke_start` | DEBUG | thread_id, config |
| **before_agent** | `middleware.before_agent_start` | INFO | namespace, user_id |
| | `middleware.before_agent_loaded` | DEBUG | episodic_data, interaction_count |
| | `middleware.before_agent_end` | INFO | latency_ms |
| **Short Memory 恢复** | `memory.short_restore_start` | DEBUG | thread_id |
| | `memory.short_restore_loaded` | INFO | message_count, total_tokens |
| **wrap_model_call** | `middleware.wrap_model_call_start` | DEBUG | llm_call_index |
| | `middleware.wrap_model_call_profile_injected` | DEBUG | profile_tokens, ephemeral: bool |
| | `middleware.wrap_model_call_rag_injected` | DEBUG | rag_chunks, rag_tokens (P2) |
| | `middleware.wrap_model_call_end` | DEBUG | total_system_tokens |
| **LLM 调用** | `llm.invoke_start` | INFO | model, input_tokens, stream: bool |
| | `llm.invoke_stream_token` | DEBUG | token_text, chunk_index |
| | `llm.invoke_end` | INFO | output_tokens, latency_ms, finish_reason |
| **after_model** | `middleware.after_model_start` | DEBUG | |
| | `middleware.after_model_parsed` | INFO | content_blocks: list, tool_calls: list |
| | `middleware.after_model_sse_pushed` | INFO | events: list |
| | `middleware.after_model_end` | DEBUG | |
| **Short Memory 保存** | `memory.short_save_start` | DEBUG | |
| | `memory.short_save_saved` | INFO | message_count, checkpoint_id |
| **after_agent** | `middleware.after_agent_start` | INFO | turn_duration_ms |
| | `middleware.after_agent_profile_updated` | INFO | interaction_count, preferences (P2) |
| | `middleware.after_agent_end` | INFO | |
| **返回结果** | `agent.turn_end` | INFO | total_tokens, total_latency_ms, final_answer_tokens |

#### 2.1.2 Checkpointer 版本链

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **restore 开始** | `checkpoint.restore_start` | DEBUG | thread_id |
| **restore 首次** | `checkpoint.restore_first` | INFO | state: {messages: []} |
| **restore 历史快照** | `checkpoint.restore_history` | INFO | step_id, checkpoint_id, message_count |
| **restore HIL 断点** | `checkpoint.restore_interrupt` | INFO | step_id, checkpoint_id, pending_tool |
| **save 开始** | `checkpoint.save_start` | DEBUG | thread_id, step_id |
| **save 完成** | `checkpoint.save_end` | INFO | checkpoint_id, parent_id, message_count, state_size_bytes |

#### 2.1.3 HIL 流程

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **触发 HIL** | `hil.trigger` | INFO | tool_name, tool_args, effect_class |
| **暂停 Agent** | `hil.agent_paused` | INFO | interrupt_id, checkpoint_id |
| **SSE 推送** | `hil.sse_interrupt_sent` | INFO | interrupt_id, tool_name, tool_args |
| **用户操作** | `hil.user_action` | INFO | action: "approve"/"reject", interrupt_id |
| **恢复执行** | `hil.resume_start` | INFO | interrupt_id, action |
| **执行批准** | `hil.tool_executed` | INFO | tool_name, result_summary |
| **执行拒绝** | `hil.tool_rejected` | INFO | tool_name, rejection_reason |
| **继续循环** | `hil.loop_resumed` | INFO | |

### 2.2 Context 模块 (context.py)

#### 2.2.1 Context Window 组装

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **组装开始** | `context.assemble_start` | DEBUG | llm_call_index |
| **Slot ①** | `context.slot1_system_prompt` | DEBUG | tokens: {role, skill_registry, fewshot, profile} |
| **Slot ③** | `context.slot3_dynamic_fewshot` | INFO | count, total_tokens, retrieval_ms (P1) |
| **Slot ④** | `context.slot4_rag_chunks` | INFO | count, total_tokens, retrieval_ms (P2) |
| **Slot ⑦** | `context.slot7_tool_schemas` | DEBUG | tool_count, total_tokens |
| **Slot ⑧** | `context.slot8_history` | INFO | message_count, total_tokens, compressed: bool |
| **Slot ⑩** | `context.slot10_user_input` | INFO | tokens |
| **Token 检查** | `context.budget_check` | INFO | total_tokens, max_tokens, overflow: bool |
| **压缩触发** | `context.compress_start` | WARNING | current_tokens, target_tokens |
| **压缩完成** | `context.compress_end` | INFO | compressed_tokens, compression_ratio |
| **组装完成** | `context.assemble_end` | INFO | total_input_tokens, max_output_tokens |

#### 2.2.2 Memory 读写

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **Long Memory 加载** | `memory.long_load_start` | DEBUG | namespace, key |
| | `memory.long_loaded` | INFO | episodic_data: {...}, procedural_count |
| **Long Memory 写回** | `memory.long_write_start` | DEBUG | namespace, key |
| | `memory.long_written` | INFO | changes: {...}, interaction_count_new |
| **Ephemeral 注入** | `memory.ephemeral_inject` | DEBUG | type: "profile"/"rag"/"fewshot", tokens |

### 2.3 Tools 模块 (tools.py)

#### 2.3.1 权限决策

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **PolicyEngine 决策** | `policy.decide_start` | INFO | tool_name, effect_class, allowed_decisions |
| | `policy.decide_result` | INFO | decision: "allow"/"ask"/"deny", reason: string |
| **session 授权** | `policy.session_grant` | INFO | tool_name, user_decision: "always_allow" |
| **HIL 要求** | `policy.hil_required` | WARNING | tool_name, effect_class |

#### 2.3.2 工具执行

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **ToolNode 执行** | `toolnode.execute_start` | INFO | tool_names: list, parallel: bool |
| | `toolnode.execute_tool_start` | DEBUG | tool_name, args |
| | `toolnode.execute_tool_end` | INFO | tool_name, result_length, latency_ms, error: string\|null |
| | `toolnode.execute_end` | INFO | total_latency_ms, success_count, error_count |
| **并行执行** | `toolnode.parallel_start` | INFO | tool_count |
| | `toolnode.parallel_completed` | INFO | results: [{tool, latency, status}] |
| **串行执行** | `toolnode.serial_step_start` | INFO | step, tool_name |
| | `toolnode.serial_step_end` | INFO | step, tool_name, result |

#### 2.3.3 幂等保护

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **幂等键计算** | `idempotency.key_calculated` | DEBUG | tool_name, key |
| **幂等检查** | `idempotency.check` | INFO | key, already_executed: bool |
| **幂等跳过** | `idempotency.skip` | INFO | key, reason: "resume_scenario" |
| **幂等记录** | `idempotency.mark` | DEBUG | key |

#### 2.3.4 子 Agent 委托

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **循环防护检查** | `task_dispatch.guard_check` | DEBUG | task_depth, task_budget, level_limit |
| **循环防护拒绝** | `task_dispatch.guard_rejected` | WARNING | reason: "depth_exceeded"/"budget_exceeded" |
| **子 Agent 创建** | `task_dispatch.child_created` | INFO | child_thread_id, subagent_goal, tools_count |
| **子 Agent 开始** | `task_dispatch.child_start` | INFO | child_thread_id |
| **子 Agent 完成** | `task_dispatch.child_end` | INFO | child_thread_id, total_steps, final_report_length |
| **子 Agent 并发** | `task_dispatch.concurrent_start` | INFO | count |
| | `task_dispatch.concurrent_end` | INFO | count, total_latency_ms |

### 2.4 Skills 模块 (skills.py)

#### 2.4.1 Skill 扫描

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **扫描开始** | `skill.scan_start` | INFO | skills_dir |
| **扫描文件** | `skill.scan_file` | DEBUG | path, status, file_size_bytes |
| **扫描跳过** | `skill.skip_file` | DEBUG | path, reason: "disabled"/"draft"/"oversized" |
| **扫描完成** | `skill.scan_end` | INFO | total_count, active_count, skipped_count |

#### 2.4.2 SkillSnapshot 构建

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **快照构建** | `skill.snapshot_build_start` | DEBUG | |
| **字符计算** | `skill.snapshot_chars_calc` | DEBUG | full_format_chars, compact_format_chars |
| **格式选择** | `skill.snapshot_format_selected` | INFO | format: "full"/"compact"/"truncated", reason |
| **快照完成** | `skill.snapshot_built` | INFO | version, skill_count, prompt_tokens |
| **注入 Slot ①** | `skill.snapshot_injected` | INFO | prompt_length, system_prompt_total_tokens |

#### 2.4.3 Skill 激活

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **LLM 识别** | `skill.llm_matched` | INFO | skill_name, confidence: float (可选) |
| **read_file 调用** | `skill.read_file_call` | DEBUG | skill_name, file_path |
| **read_file 读取** | `skill.read_file_loaded` | INFO | skill_name, content_length, tokens, latency_ms |
| **历史中已存在** | `skill.history_found` | DEBUG | skill_name, tool_message_id |
| **内容注入** | `skill.content_injected` | INFO | skill_name, instructions_tokens, examples_tokens |
| **执行完成** | `skill.execution_completed` | INFO | skill_name, used_tools: list |

### 2.5 API 模块 (api.py)

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **请求接收** | `api.request_received` | INFO | endpoint, method, session_id, user_id, message_length |
| **请求验证** | `api.request_validated` | DEBUG | valid: bool, errors: list |
| **Agent 启动** | `api.agent_invoked` | INFO | session_id, user_id, message |
| **SSE 流启动** | `api.sse_stream_start` | INFO | session_id, client_ip |
| **SSE 事件推送** | `api.sse_event_sent` | DEBUG | event_type, data_length |
| **SSE 流结束** | `api.sse_stream_end` | INFO | session_id, total_events, total_bytes |
| **请求完成** | `api.request_completed` | INFO | session_id, status_code, total_latency_ms |
| **请求错误** | `api.request_error` | ERROR | session_id, error_type, error_message, stack_trace |

### 2.6 SSE 模块 (sse.py)

| 阶段 | 日志点 | 级别 | 数据字段 |
|------|--------|------|---------|
| **连接建立** | `sse.connection_established` | INFO | session_id, client_ip |
| **事件推送** | `sse.event_push` | DEBUG | event_type, event_data |
| **thought 事件** | `sse.event_thought` | INFO | token_text, cumulative_tokens |
| **tool_start 事件** | `sse.event_tool_start` | INFO | tool_name, args |
| **tool_result 事件** | `sse.event_tool_result` | INFO | tool_name, result_length |
| **hil_interrupt 事件** | `sse.event_hil_interrupt` | INFO | interrupt_id, tool_name, tool_args |
| **done 事件** | `sse.event_done` | INFO | final_answer_length, total_tokens |
| **error 事件** | `sse.event_error` | ERROR | error_message |
| **连接关闭** | `sse.connection_closed` | INFO | session_id, reason, duration_seconds |

---

## 3. 日志格式规范

### 3.1 结构化 JSON 格式

```json
{
  "timestamp": "2026-03-25T10:30:45.123456Z",
  "level": "INFO",
  "logger": "agent.memory_middleware",
  "module": "agent",
  "component": "memory_middleware",
  "session_id": "sess_abc123",
  "user_id": "user_456",
  "thread_id": "thread_789",
  "step_id": 5,
  "trace_id": "trace_xyz",
  "message": "User profile loaded from Long Memory",
  "data": {
    "namespace": ["profile", "user_456"],
    "episodic": {
      "user_id": "user_456",
      "preferences": {
        "domain": "legal-tech",
        "language": "zh"
      },
      "interaction_count": 15
    },
    "latency_ms": 12
  },
  "tags": ["memory", "long_memory", "profile"]
}
```

### 3.2 日志消息规范

- **简洁性**：消息文本控制在 50 字符以内，详细数据在 `data` 字段
- **动词时态**：统一使用过去时（loaded、saved、executed）
- **一致性**：相同操作使用相同动词（execute 执行，invoke 调用，inject 注入）
- **主语清晰**：明确日志的主体（User profile、Agent、Tool、Skill）

### 3.3 Tags 标签系统

用于快速过滤和聚合查询：

```python
# 按模块
tags = ["agent", "context", "tools", "skills", "memory", "api", "sse"]

# 按操作类型
tags = ["read", "write", "invoke", "execute", "inject", "save", "load"]

# 按阶段
tags = ["before_agent", "after_agent", "wrap_model_call", "after_model"]

# 按数据类型
tags = ["short_memory", "long_memory", "ephemeral", "persistent"]
```

---

## 4. 日志配置

### 4.1 日志级别配置

```yaml
# config/logging.yaml
loggers:
  agent:
    level: INFO
    handlers: [console, file]
  context:
    level: DEBUG
    handlers: [console, file]
  tools:
    level: INFO
    handlers: [console, file]
  skills:
    level: INFO
    handlers: [console, file]
  memory:
    level: DEBUG
    handlers: [console, file]
  api:
    level: INFO
    handlers: [console, file]
  sse:
    level: INFO
    handlers: [console, file]

handlers:
  console:
    class: logging.StreamHandler
    formatter: structured
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    formatter: structured
    filename: logs/agent.log
    maxBytes: 10485760  # 10MB
    backupCount: 10
    encoding: utf-8

formatters:
  structured:
    class: logger.formatter.StructuredFormatter
    format: "%(message)s"  # JSON 输出
```

### 4.2 环境变量

```bash
# 日志级别（全局覆盖）
LOG_LEVEL=INFO

# 日志输出路径
LOG_FILE_PATH=/var/log/agent/

# 是否启用调试模式
DEBUG=true

# 是否启用追踪采样（采样率）
TRACE_SAMPLING_RATE=0.1  # 10%
```

---

## 5. 日志使用示例

### 5.1 Agent 模块

```python
from logger.modules.agent import AgentLogger

logger = AgentLogger(
    session_id="sess_abc123",
    user_id="user_456",
    thread_id="thread_789"
)

# Turn 开始
logger.turn_start(
    message="帮我查合同123的签署状态",
    message_tokens=12
)

# before_agent
logger.middleware_before_agent_loaded(
    episodic_data={"domain": "legal-tech", "language": "zh"},
    interaction_count=15
)

# LLM 调用
logger.llm_invoke_start(
    model="claude-sonnet-4",
    input_tokens=2456,
    stream=True
)

logger.llm_invoke_end(
    output_tokens=324,
    latency_ms=1234,
    finish_reason="tool_calls"
)
```

### 5.2 Tools 模块

```python
from logger.modules.tools import ToolsLogger

logger = ToolsLogger(
    session_id="sess_abc123",
    user_id="user_456",
    thread_id="thread_789",
    step_id=3
)

# 权限决策
logger.policy_decide_result(
    tool_name="send_email",
    effect_class="external_write",
    decision="ask",
    reason="External write operations require user confirmation"
)

# 工具执行
logger.toolnode_execute_tool_start(
    tool_name="send_email",
    args={"to": "boss@...", "subject": "..."}
)

logger.toolnode_execute_tool_end(
    tool_name="send_email",
    result_length=45,
    latency_ms=234,
    error=None
)
```

### 5.3 Skills 模块

```python
from logger.modules.skills import SkillsLogger

logger = SkillsLogger(
    session_id="sess_abc123",
    user_id="user_456",
    thread_id="thread_789",
    step_id=2
)

# Skill 激活
logger.skill_llm_matched(
    skill_name="legal-search",
    confidence=0.95
)

logger.skill_read_file_loaded(
    skill_name="legal-search",
    content_length=1234,
    tokens=320,
    latency_ms=15
)

logger.skill_content_injected(
    skill_name="legal-search",
    instructions_tokens=280,
    examples_tokens=40
)
```

---

## 6. 日志查询与分析

### 6.1 常用查询

```bash
# 查询某个 session 的完整日志
jq 'select(.session_id == "sess_abc123")' logs/agent.log

# 查询某个 turn 的所有日志
jq 'select(.session_id == "sess_abc123" and .step_id == 5)' logs/agent.log

# 查询所有错误日志
jq 'select(.level == "ERROR")' logs/agent.log

# 查询工具调用耗时
jq 'select(.component == "toolnode") | {tool_name: .data.tool_name, latency_ms: .data.latency_ms}' logs/agent.log

# 查询 Token 使用统计
jq 'select(.logger | contains("llm")) | {input_tokens: .data.input_tokens, output_tokens: .data.output_tokens}' logs/agent.log
```

### 6.2 性能分析

```python
# 计算平均 LLM 调用延迟
import json

logs = []
with open('logs/agent.log') as f:
    for line in f:
        logs.append(json.loads(line))

llm_calls = [log for log in logs if 'llm.invoke_end' in log['logger']]
avg_latency = sum(log['data']['latency_ms'] for log in llm_calls) / len(llm_calls)
print(f"Average LLM latency: {avg_latency:.2f}ms")

# 工具执行耗时分布
tool_calls = [log for log in logs if 'toolnode.execute_tool_end' in log['logger']]
tool_latencies = {log['data']['tool_name']: [] for log in tool_calls}
for log in tool_calls:
    tool_latencies[log['data']['tool_name']].append(log['data']['latency_ms'])

for tool, latencies in tool_latencies.items():
    print(f"{tool}: {sum(latencies)/len(latencies):.2f}ms avg, {max(latencies)}ms max")
```

---

## 7. 最佳实践

### 7.1 日志编写原则

1. **上下文完整**：每次日志都包含 session_id、user_id、thread_id
2. **数据结构化**：将详细信息放在 `data` 字段，便于查询
3. **级别合理**：
   - DEBUG：详细的执行流程、中间状态
   - INFO：关键业务事件、状态变更
   - WARNING：降级、重试、超时
   - ERROR：错误和异常
4. **无敏感信息**：不要记录密码、Token、PII 数据

### 7.2 性能考虑

1. **避免高频 DEBUG 日志**：SSE token 推送可使用 DEBUG 或采样
2. **异步写入**：使用 QueueHandler 避免阻塞主流程
3. **日志轮转**：控制单文件大小，避免磁盘占满

### 7.3 可观测性集成

```python
# 与 OpenTelemetry 集成（可选）
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("agent_turn") as span:
    span.set_attribute("session_id", session_id)
    logger.turn_start(...)
    # ... 执行逻辑 ...
```

---

## 8. 日志测试

### 8.1 单元测试

```python
# tests/logger/test_agent_logger.py
import pytest
from logger.modules.agent import AgentLogger
import json

def test_turn_start_log_format():
    logger = AgentLogger(session_id="test", user_id="test")
    logger.turn_start(message="test", message_tokens=5)

    log_entry = json.loads(captured_logs[-1])
    assert log_entry['logger'] == 'agent.turn_start'
    assert log_entry['session_id'] == 'test'
    assert log_entry['data']['message'] == 'test'
    assert log_entry['data']['message_tokens'] == 5
```

### 8.2 集成测试

```python
# tests/integration/test_full_flow_logging.py
def test_agent_turn_complete_logs(caplog):
    # 执行完整的 Agent Turn
    result = agent.run(message="查合同123状态")

    # 验证关键日志点
    logs = [json.loads(r.message) for r in caplog.records]

    # 验证 Turn 开始
    assert any(log['logger'] == 'agent.turn_start' for log in logs)

    # 验证 before_agent
    assert any(log['logger'] == 'middleware.before_agent_loaded' for log in logs)

    # 验证 LLM 调用
    assert any(log['logger'] == 'llm.invoke_end' for log in logs)

    # 验证 Turn 结束
    assert any(log['logger'] == 'agent.turn_end' for log in logs)
```
