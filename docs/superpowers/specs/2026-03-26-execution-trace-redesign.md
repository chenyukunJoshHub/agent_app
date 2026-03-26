# 执行链路明细模块重设计

> Date: 2026-03-26
> Status: Draft

## 问题

当前 `ExecutionTracePanel` 展示的事件流水存在两个核心问题：

1. **阶段名称不直观** — "流式层""ReAct 循环""Context 组装" 等标签对非开发者难以理解
2. **缺少上下文关联** — 事件逐条平铺，看不出 `model_call_start` → `thought_emitted` → `tool_call_planned` 之间的因果链路

次要问题：
- 细粒度事件过多（每 Turn 约 14 条），重要信息被噪音淹没
- 无 Turn 级别的摘要信息（总用时、调用了哪些工具）
- 无用户/开发者分层视图

## 目标

将事件流水从 "开发者日志列表" 重构为 "易懂的执行时间线"，同时满足普通用户和开发者两种受众。

## 设计决策

### 1. 后端：语义块聚合（Semantic Block Aggregation）

引入 `TraceBlockBuilder`，在 `TraceMiddleware` 内部将连续的细粒度 `trace_event` 累积为高层语义块，以 `trace_block` 事件类型发送。

#### 语义块类型

| 块类型 | 聚合的原事件 | 展示标签（用户） | 展示标签（开发者） | 可见性 |
|--------|------------|----------------|------------------|--------|
| `turn_start` | stream/request_received, stream/agent_created, stream/stream_started | 开始处理 | 初始化完成 | 两类 |
| `memory_load` | memory/load_start + memory/load_success/skip, memory/inject_* | — | 加载记忆 | 仅详细 |
| `prompt_build` | context/token_update | — | 组装上下文 | 仅详细 |
| `thinking` | react/model_call_start + model_call_end + thought_emitted | 思考推理 | 思考推理 (model_call) | 两类 |
| `tool_call` | tools/tool_call_planned + tools/tool_call_result | 调用工具 | 工具调用 | 两类 |
| `answer` | react/turn_done (finish_reason=stop) | 生成回答 | 回答生成 | 两类 |
| `turn_summary` | 计算值 | 本轮摘要 | Turn Summary | 两类 |
| `hil_pause` | hil/interrupt_emitted | 等待确认 | HIL 暂停 | 两类 |
| `error` | 任何 error 事件 | 出错了 | 错误 | 两类 |

#### 语义块数据结构

```typescript
interface TraceBlock {
  id: string;                    // "block_{nanoseconds}"
  timestamp: string;             // ISO8601 块开始时间
  type: string;                  // 块类型 (thinking, tool_call, ...)
  turnId: string;                // 所属 Turn
  duration_ms: number;           // 块持续时间（毫秒）
  status: 'pending' | 'ok' | 'skip' | 'error';

  // 各类型特定字段
  label?: string;                // 展示标签（用户友好）
  icon?: string;                 // lucide-react 图标名
  detail?: string;               // 单行摘要文本

  // 各类型可选 payload
  thinking?: {
    content_preview: string;     // 推理内容预览（前 200 字）
    input_tokens: number;
    output_tokens: number;
  };
  tool_call?: {
    name: string;
    args: Record<string, unknown>;
    result_preview: string;
    result_length: number;
    error?: string;
  };
  memory_load?: {
    count: number;
    injected: boolean;
  };
  prompt_build?: {
    messages: number;
    total_tokens: number;
    budget: number;
  };
  turn_summary?: {
    total_duration_ms: number;
    think_count: number;
    tool_count: number;
    total_tokens: number;
    finish_reason: string;
  };
  error?: {
    message: string;
    stage: string;
    step: string;
  };
}
```

#### TraceBlockBuilder 行为

```python
class TraceBlockBuilder:
    """在 TraceMiddleware 中累积细粒度事件，构建语义块"""

    def on_trace_event(self, event: dict) -> list[dict]:
        """
        接收原始 trace_event，返回 0 或 1 个 trace_block。
        当一个语义块完成时返回该块（如 model_call_end 表示 thinking 块结束）。
        """
```

聚合规则：

1. `thinking` 块：收到 `model_call_start` 开始累积，收到 `model_call_end` + `thought_emitted` 后发出
2. `tool_call` 块：收到 `tool_call_planned` 开始，收到 `tool_call_result` 后发出
3. `memory_load` 块：收到 `memory/load_start` 开始，收到 `memory/load_success` 或 `inject_*` 后发出
4. `prompt_build` 块：收到 `context/token_update` 直接发出（单事件块）
5. `turn_summary` 块：收到 `react/turn_done` 后计算并发出
6. `error` 块：收到任何 `status=error` 事件直接发出
7. `hil_pause` 块：收到 `hil/interrupt_emitted` 直接发出

#### 保留原始 trace_event

向后兼容：后端同时发送 `trace_block` 和原始 `trace_event`。前端根据视图模式选择消费哪种：

- 简洁模式：只消费 `trace_block`
- 详细模式：消费 `trace_block` + `trace_event`（嵌套在块内展示）

### 2. 前端：树状时间线（Tree Timeline）

#### ExecutionTracePanel 重写

从当前的平铺列表重构为树状时间线布局：

```
┌ Turn #1 ────────────────────────── 14:32:01 ┐
│
│  ○ 开始处理 ── 14:32:01.120
│
│  ┌─ 思考推理 ────────── 1.2s ──────┐
│  │  Agent 正在分析您的问题...       │
│  │  [展开查看推理内容]              │
│  └──────────────────────────────────┘
│
│  ┌─ 调用工具: web_search ─ 0.8s ──┐
│  │  参数: { query: "..." }         │
│  │  结果: 1280 字符                │
│  └──────────────────────────────────┘
│
│  ┌─ 思考推理 ────────── 0.6s ──────┐
│  │  [展开查看推理内容]              │
│  └──────────────────────────────────┘
│
│  ○ 生成回答
│
│  ✅ Turn #1 完成 · 3.2s · 2 次思考 · 1 次工具
└──────────────────────────────────────────────┘
```

#### 视图切换

面板顶部添加视图切换：

- **简洁模式（默认）**：只展示面向用户的块（thinking, tool_call, answer, hil_pause, error, turn_summary）
- **详细模式**：额外展示开发者块（memory_load, prompt_build），并嵌套展示原始 trace_event

#### 交互行为

- 语义块默认折叠，显示：图标 + 标签 + 耗时 + 摘要行
- 点击展开显示详情（推理内容、工具参数/结果等）
- Turn 摘要行显示：总用时、思考次数、工具调用次数
- 错误块高亮显示，始终展开
- 新块出现时使用 fade-in 动画

#### 图标映射

| 块类型 | lucide-react 图标 | 颜色 |
|--------|-----------------|------|
| turn_start | Play | blue |
| thinking | Brain | purple |
| tool_call | Wrench | amber |
| answer | MessageSquare | green |
| memory_load | Database | blue（详细模式） |
| prompt_build | FileText | blue（详细模式） |
| hil_pause | AlertCircle | orange |
| error | AlertTriangle | red |
| turn_summary | CheckCircle | green |

### 3. 数据流变更

#### 后端变更

```
TraceMiddleware
  ├─ 保留: 原始 trace_event → sse_queue
  └─ 新增: TraceBlockBuilder.on_trace_event() → sse_queue (type="trace_block")
```

#### SSE 事件流（每 Turn）

```
# 之前（~14 events/turn）
trace_event: { stage: stream, step: request_received }
trace_event: { stage: stream, step: agent_created }
trace_event: { stage: stream, step: stream_started }
trace_event: { stage: memory, step: load_start }
trace_event: { stage: memory, step: load_success }
trace_event: { stage: react, step: turn_start }
trace_event: { stage: react, step: model_call_start }
trace_event: { stage: react, step: model_call_end }
trace_event: { stage: react, step: thought_emitted }
trace_event: { stage: context, step: token_update }
trace_event: { stage: tools, step: tool_call_planned }
trace_event: { stage: tools, step: tool_call_result }
trace_event: { stage: react, step: turn_done }

# 之后（~6 blocks/turn，同时保留原始 trace_event）
trace_block: { type: turn_start, ... }
trace_block: { type: thinking, duration_ms: 1200, ... }
trace_block: { type: tool_call, name: web_search, ... }
trace_block: { type: thinking, duration_ms: 600, ... }
trace_block: { type: turn_summary, total_duration_ms: 3200, ... }
```

#### 前端变更

```
SSE Manager
  ├─ 保留: 'trace_event' handler → addTraceEvent()
  └─ 新增: 'trace_block' handler → addTraceBlock()

Zustand Store (use-session.ts)
  ├─ 保留: traceEvents: TraceEvent[]
  └─ 新增: traceBlocks: TraceBlock[]

ExecutionTracePanel
  ├─ 默认渲染: traceBlocks (树状时间线)
  └─ 详细模式: traceBlocks + 嵌套 traceEvents
```

### 4. 不改动的部分

- `TraceMiddleware` 的 middleware 钩子结构不变（before_model, after_model 等）
- `MemoryMiddleware`、`HILMiddleware` 不变
- `SSEEventQueue` 不变
- `SSEManager` 连接/重连逻辑不变
- `ToolCallCard` 组件保留（在 tool_call 块内复用）

### 5. 文件变更清单

#### 后端

| 文件 | 变更 |
|------|------|
| `backend/app/observability/trace_events.py` | 新增 `TraceBlockBuilder` 类、`build_trace_block()` 函数、`emit_trace_block()` 函数 |
| `backend/app/observability/events.py` | 新增 `TraceBlock` dataclass（或直接在 trace_events.py 中定义） |
| `backend/app/agent/middleware/trace.py` | 集成 `TraceBlockBuilder`，在现有钩子中同时发送 block |

#### 前端

| 文件 | 变更 |
|------|------|
| `frontend/src/types/trace.ts` | 新增 `TraceBlock` 接口 |
| `frontend/src/store/use-session.ts` | 新增 `traceBlocks` 状态和 `addTraceBlock` action |
| `frontend/src/lib/sse-manager.ts` | 新增 `trace_block` 事件类型监听 |
| `frontend/src/components/ExecutionTracePanel.tsx` | 重写为树状时间线渲染 |
| `frontend/src/components/TraceBlockCard.tsx` | 新建：单个语义块的渲染组件 |
| `frontend/src/app/page.tsx` | 新增 `trace_block` SSE 事件处理 |

#### 测试

| 文件 | 变更 |
|------|------|
| `tests/backend/unit/observability/test_trace_block_builder.py` | 新增：TraceBlockBuilder 单元测试 |
| `tests/backend/unit/observability/test_events.py` | 更新：新增 block 类型测试 |
| `tests/e2e/03-tool-trace.spec.ts` | 更新：适配新的 UI 结构 |

### 6. 实施步骤（TDD 顺序）

1. **后端 TraceBlockBuilder** — 纯逻辑，无 UI 依赖
   - 测试各块类型的累积/发出规则
   - 测试边界情况（无 thought、多工具并行、错误中断）
2. **前端类型 + Store** — 类型定义和状态管理
3. **前端 TraceBlockCard** — 单个块组件
4. **前端 ExecutionTracePanel 重写** — 树状时间线
5. **集成测试** — 端到端验证

### 7. 完成标准

- 后端 TraceBlockBuilder 单元测试覆盖率 ≥ 90%
- 前端简洁模式下每个 Turn 的事件数从 ~14 降至 ~6
- 树状时间线正确展示思考→工具→思考的因果链路
- 视图切换正常工作（简洁/详细）
- 现有 E2E 测试适配通过
