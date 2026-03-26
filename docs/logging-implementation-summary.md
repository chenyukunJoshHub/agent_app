# 日志系统实现总结

> 本文档总结了基于四个架构文档的时序图分析，为整个项目设计的完整日志系统的实现方案。

---

## 已完成的工作

### 1. 设计文档 (docs/logging-design.md)

完整的日志系统设计文档，包含：

- **日志层级结构**：按照模块和流程深度设计
- **日志级别定义**：DEBUG、INFO、WARNING、ERROR、CRITICAL
- **上下文标识规范**：session_id、user_id、thread_id、step_id、trace_id
- **模块日志点设计**：覆盖所有关键执行路径、决策点、数据流
- **结构化 JSON 格式**：便于解析和查询
- **配置规范**：日志级别、输出目标、环境变量
- **使用示例**：各模块日志调用示例
- **查询与分析**：常用查询命令和性能分析方法
- **最佳实践**：日志编写原则、性能考虑、可观测性集成

### 2. 核心框架实现 (backend/app/logger/)

#### 目录结构
```
backend/app/logger/
├── __init__.py              # 统一入口
├── config.py                # 日志配置
├── formatter.py             # 结构化日志格式化器
├── modules/                 # 分模块 Logger
│   ├── __init__.py
│   ├── base.py             # BaseLogger 基类
│   ├── agent.py            # Agent 模块日志（已完成）
│   ├── context.py          # Context 模块日志（待实现）
│   ├── tools.py            # Tools 模块日志（待实现）
│   ├── skills.py           # Skills 模块日志（待实现）
│   ├── memory.py           # Memory 模块日志（待实现）
│   ├── api.py              # API 层日志（待实现）
│   └── sse.py             # SSE 流日志（待实现）
└── examples.py             # 使用示例
```

#### 已实现的功能

1. **配置系统 (config.py)**
   - 日志根目录管理
   - 全局日志级别配置
   - 模块级日志级别配置
   - 日志文件配置
   - 结构化日志字段定义
   - 性能阈值配置
   - 警告阈值配置
   - 追踪采样率配置

2. **格式化器 (formatter.py)**
   - StructuredFormatter：JSON 格式化器
   - LogContext：上下文管理器
   - ContextFilter：上下文过滤器
   - create_logger：Logger 创建工具函数

3. **BaseLogger (modules/base.py)**
   - 统一的日志接口
   - 上下文管理
   - Step 管理
   - 五个日志级别方法
   - 异常处理

4. **AgentLogger (modules/agent.py)**
   - Agent Turn 日志：turn_start、turn_end
   - Middleware 日志：before_agent、wrap_model_call、after_agent
   - Checkpointer 日志：restore、save（历史快照、HIL 断点）
   - HIL 日志：trigger、paused、user_action、resume、tool_executed、tool_rejected

5. **使用示例 (examples.py)**
   - Agent 模块日志示例
   - Tools 模块日志示例
   - Context 模块日志示例
   - Step 递增示例
   - 错误日志示例

---

## 待完成的模块 Logger

以下模块的 Logger 需要按照相同模式实现：

### 1. ContextLogger (modules/context.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| context_assemble_start | DEBUG | llm_call_index |
| context_slot1_system_prompt | DEBUG | tokens |
| context_slot3_dynamic_fewshot | INFO | count, total_tokens, retrieval_ms |
| context_slot4_rag_chunks | INFO | count, total_tokens, retrieval_ms |
| context_slot7_tool_schemas | DEBUG | tool_count, total_tokens |
| context_slot8_history | INFO | message_count, total_tokens, compressed |
| context_slot10_user_input | INFO | tokens |
| context_budget_check | INFO | total_tokens, max_tokens, overflow |
| context_compress_start | WARNING | current_tokens, target_tokens |
| context_compress_end | INFO | compressed_tokens, compression_ratio |
| context_assemble_end | INFO | total_input_tokens, max_output_tokens |

### 2. ToolsLogger (modules/tools.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| policy_decide_start | INFO | tool_name, effect_class |
| policy_decide_result | INFO | decision, reason |
| policy_session_grant | INFO | tool_name |
| policy_hil_required | WARNING | tool_name, effect_class |
| toolnode_execute_start | INFO | tool_names, parallel |
| toolnode_execute_tool_start | DEBUG | tool_name, args |
| toolnode_execute_tool_end | INFO | tool_name, result_length, latency_ms, error |
| toolnode_execute_end | INFO | total_latency_ms, success_count, error_count |
| toolnode_parallel_start | INFO | tool_count |
| toolnode_parallel_completed | INFO | results |
| toolnode_serial_step_start | INFO | step, tool_name |
| toolnode_serial_step_end | INFO | step, tool_name, result |
| idempotency_key_calculated | DEBUG | tool_name, key |
| idempotency_check | INFO | key, already_executed |
| idempotency_skip | INFO | key, reason |
| idempotency_mark | DEBUG | key |
| task_dispatch_guard_check | DEBUG | task_depth, task_budget |
| task_dispatch_guard_rejected | WARNING | reason |
| task_dispatch_child_created | INFO | child_thread_id, subagent_goal |
| task_dispatch_child_start | INFO | child_thread_id |
| task_dispatch_child_end | INFO | child_thread_id, total_steps |
| task_dispatch_concurrent_start | INFO | count |
| task_dispatch_concurrent_end | INFO | count, total_latency_ms |

### 3. SkillsLogger (modules/skills.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| skill_scan_start | INFO | skills_dir |
| skill_scan_file | DEBUG | path, status, file_size_bytes |
| skill_skip_file | DEBUG | path, reason |
| skill_scan_end | INFO | total_count, active_count, skipped_count |
| skill_snapshot_build_start | DEBUG | |
| skill_snapshot_chars_calc | DEBUG | full_format_chars, compact_format_chars |
| skill_snapshot_format_selected | INFO | format, reason |
| skill_snapshot_built | INFO | version, skill_count, prompt_tokens |
| skill_snapshot_injected | INFO | prompt_length, system_prompt_total_tokens |
| skill_llm_matched | INFO | skill_name, confidence |
| skill_read_file_call | DEBUG | skill_name, file_path |
| skill_read_file_loaded | INFO | skill_name, content_length, tokens, latency_ms |
| skill_history_found | DEBUG | skill_name, tool_message_id |
| skill_content_injected | INFO | skill_name, instructions_tokens, examples_tokens |
| skill_execution_completed | INFO | skill_name, used_tools |

### 4. MemoryLogger (modules/memory.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| memory_short_restore_start | DEBUG | thread_id |
| memory_short_restore_loaded | INFO | message_count, total_tokens |
| memory_short_save_start | DEBUG | |
| memory_short_save_saved | INFO | message_count, checkpoint_id |
| memory_long_load_start | DEBUG | namespace, key |
| memory_long_loaded | INFO | episodic_data, procedural_count |
| memory_long_write_start | DEBUG | namespace, key |
| memory_long_written | INFO | changes, interaction_count_new |
| memory_ephemeral_inject | DEBUG | type, tokens |

### 5. ApiLogger (modules/api.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| api_request_received | INFO | endpoint, method, session_id, message_length |
| api_request_validated | DEBUG | valid, errors |
| api_agent_invoked | INFO | session_id, user_id, message |
| api_sse_stream_start | INFO | session_id, client_ip |
| api_sse_event_sent | DEBUG | event_type, data_length |
| api_sse_stream_end | INFO | session_id, total_events, total_bytes |
| api_request_completed | INFO | session_id, status_code, total_latency_ms |
| api_request_error | ERROR | session_id, error_type, error_message, stack_trace |

### 6. SseLogger (modules/sse.py)

需要实现的日志点：

| 日志点 | 级别 | 数据字段 |
|--------|------|---------|
| sse_connection_established | INFO | session_id, client_ip |
| sse_event_push | DEBUG | event_type, event_data |
| sse_event_thought | INFO | token_text, cumulative_tokens |
| sse_event_tool_start | INFO | tool_name, args |
| sse_event_tool_result | INFO | tool_name, result_length |
| sse_event_hil_interrupt | INFO | interrupt_id, tool_name, tool_args |
| sse_event_done | INFO | final_answer_length, total_tokens |
| sse_event_error | ERROR | error_message |
| sse_connection_closed | INFO | session_id, reason, duration_seconds |

---

## 集成到现有代码

### 在 Agent 层添加日志

```python
# backend/app/agent/executor.py
from logger import AgentLogger

class AgentExecutor:
    def __init__(self, session_id: str, user_id: str, thread_id: str):
        self.logger = AgentLogger(
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
        )

    async def execute_turn(self, message: str):
        # 记录 Turn 开始
        self.logger.turn_start(
            message=message,
            message_tokens=len(message.split()),
        )

        try:
            # 执行 Agent 逻辑
            result = await self._run_agent(message)

            # 记录 Turn 结束
            self.logger.turn_end(
                total_tokens=result.total_tokens,
                total_latency_ms=result.latency_ms,
                final_answer_tokens=result.answer_tokens,
            )

            return result
        except Exception as e:
            self.logger.exception(
                "agent.turn_error",
                "Agent turn failed",
                data={"error_type": type(e).__name__},
            )
            raise
```

### 在 Middleware 层添加日志

```python
# backend/app/agent/middleware/memory.py
from logger import AgentLogger

class MemoryMiddleware:
    def __init__(self, logger: AgentLogger):
        self.logger = logger

    def before_agent(self, state: AgentState, config: RunnableConfig):
        self.logger.middleware_before_agent_start(
            namespace=("profile", config["configurable"]["user_id"]),
            user_id=config["configurable"]["user_id"],
        )

        # 加载用户画像
        episodic_data = self._load_episodic(config)

        self.logger.middleware_before_agent_loaded(
            episodic_data=episodic_data,
            interaction_count=episodic_data.get("interaction_count", 0),
            latency_ms=12,
        )

        # 写入 state
        state["memory_ctx"] = {"episodic": episodic_data}

        self.logger.middleware_before_agent_end(latency_ms=15)

        return state
```

### 在 API 层添加日志

```python
# backend/app/main.py
from logger import ApiLogger

@router.post("/chat")
async def chat(req: ChatRequest):
    logger = ApiLogger(
        session_id=req.session_id,
        user_id=req.user_id,
    )

    # 记录请求接收
    logger.api_request_received(
        endpoint="/chat",
        method="POST",
        session_id=req.session_id,
        message_length=len(req.message),
    )

    try:
        # 执行 Agent
        result = await agent_executor.execute_turn(req.message)

        # 记录请求完成
        logger.api_request_completed(
            session_id=req.session_id,
            status_code=200,
            total_latency_ms=result.latency_ms,
        )

        return StreamingResponse(
            self._sse_generator(result),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.api_request_error(
            session_id=req.session_id,
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
        raise
```

---

## 日志查询与分析

### 常用查询命令

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
jq 'select(.logger | contains("llm")) | {input_tokens: .data.input_tokens, output_tokens: .data.output_tokens}' logs/agent.log

# 查询 HIL 事件
jq 'select(.logger | contains("hil"))' logs/agent.log
```

### 性能分析示例

```python
import json

# 计算平均 LLM 调用延迟
with open('logs/agent.log') as f:
    logs = [json.loads(line) for line in f]

llm_calls = [log for log in logs if 'llm.invoke_end' in log['logger']]
avg_latency = sum(log['data']['latency_ms'] for log in llm_calls) / len(llm_calls)
print(f"Average LLM latency: {avg_latency:.2f}ms")

# 工具执行耗时分布
tool_calls = [log for log in logs if 'toolnode.execute_tool_end' in log['logger']]
tool_latencies = {}
for log in tool_calls:
    tool_name = log['data']['tool_name']
    if tool_name not in tool_latencies:
        tool_latencies[tool_name] = []
    tool_latencies[tool_name].append(log['data']['latency_ms'])

for tool, latencies in tool_latencies.items():
    print(f"{tool}: {sum(latencies)/len(latencies):.2f}ms avg, {max(latencies)}ms max")
```

---

## 最佳实践

### 1. 日志编写原则

- **上下文完整**：每次日志都包含 session_id、user_id、thread_id
- **数据结构化**：将详细信息放在 `data` 字段
- **级别合理**：
  - DEBUG：详细的执行流程、中间状态
  - INFO：关键业务事件、状态变更
  - WARNING：降级、重试、超时
  - ERROR：错误和异常
- **无敏感信息**：不要记录密码、Token、PII 数据

### 2. 性能考虑

- **避免高频 DEBUG 日志**：SSE token 推送可使用 DEBUG 或采样
- **异步写入**：使用 QueueHandler 避免阻塞主流程
- **日志轮转**：控制单文件大小，避免磁盘占满

### 3. 测试策略

为每个 Logger 模块编写单元测试，验证：

1. 日志格式正确（JSON 结构）
2. 所有字段完整
3. 日志级别正确
4. 上下文传递正确

---

## 后续工作

### 短期（本周）

1. ✅ 设计文档完成
2. ✅ 核心框架完成
3. ✅ AgentLogger 完成
4. ⏳ 实现其他模块 Logger（Context、Tools、Skills、Memory、API、SSE）
5. ⏳ 集成到现有代码
6. ⏳ 编写单元测试

### 中期（本月）

7. 添加日志聚合和分析工具
8. 添加性能监控面板
9. 添加告警机制
10. 优化日志性能

### 长期（下月）

11. 集成 OpenTelemetry
12. 添加分布式追踪
13. 添加日志存储和检索
14. 添加日志可视化和仪表板

---

## 参考

- 设计文档：`docs/logging-design.md`
- 使用示例：`backend/app/logger/examples.py`
- 架构文档：
  - `docs/arch/agent-v13.md`
  - `docs/arch/prompt-context-v20.md`
  - `docs/arch/tools-v12.md`
  - `docs/arch/skill-v3.md`
