# Multi-Tool AI Agent · 完整架构设计文档 v13

参考学习网站
	1.	MiniMind 补 LLM 基础
	2.  microgpt.py  Andrej Karpathy 新作，仅 243 行纯 Python 实现 GPT 训练与推理，零外部依赖。适合专家级开发者深入理解 Transformer 核心机制与梯度下降本质。
	3.  Learn Claude Code -- 真正的 Agent Harness 工程
	2.	RAG from Scratch 入门 RAG
	3.	Hello-Agents 建立 Agent 整体认知  https://datawhalechina.github.io/hello-agents/#/
	4.	OpenCode 学 code agent 的工程实现  https://learnopencode.com/
	5.	OpenClaw 学更泛化的 agent platform 思路   https://openclaw101.dev/zh


Harness = Tools + Knowledge + Observation + Action Interfaces + Permissions
    Tools:          文件读写、Shell、网络、数据库、浏览器
    Knowledge:      产品文档、领域资料、API 规范、风格指南
    Observation:    git diff、错误日志、浏览器状态、传感器数据
    Action:         CLI 命令、API 调用、UI 交互
    Permissions:    沙箱隔离、审批流程、信任边界


Claude Code = 一个 agent loop
            + 工具 (bash, read, write, edit, glob, grep, browser...)
            + 按需 skill 加载
            + 上下文压缩
            + 子 agent 派生
            + 带依赖图的任务系统
            + 异步邮箱的团队协调
            + worktree 隔离的并行执行
            + 权限治理

实现状态标注：
  已实现（当前代码）     可在仓库运行链路中验证
  目标态（当前未实装）   架构预留设计，代码仅占位/预算配置
---

## 第一层：产品架构设计

> 框架无关，描述系统需要做什么

### 1.1 系统目标

一个能够自主规划、调用工具、持久记忆用户偏好的多工具 AI Agent。支持流式输出、多轮对话、人工确认介入，具备完整的可观测性。

### 1.2 系统全景图

```
┌──────────────────────────────────────────────────────────────────────┐
│                            用户界面层                                 │
│                                                                      │
│  对话输入 / 消息列表                                                   │
│  思考链实时展示（Agent 推理过程可视化）                                  │
│  工具调用链路展示（调用了哪个工具、入参、结果）                           │
│  人工确认弹窗（高风险操作需用户二次确认）                                │
│  SSE 流式接收与渲染                                                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ 流式通信（携带会话标识）
┌───────────────────────────────▼──────────────────────────────────────┐
│                            Agent 核心层                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                       推理引擎                               │    │
│  │                                                             │    │
│  │  ReAct 循环：思考 → 选工具 → 执行 → 观察 → 继续/结束         │    │
│  │  工具并行调度：多工具同时执行，汇聚结果                        │    │
│  │  人工介入（HIL）：特定条件暂停，等待用户确认后继续             │    │
│  │  结构化输出：最终答案符合预定 Schema                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │    LLM 模块       │  │   Memory 模块    │  │   Tool 模块       │   │
│  │                  │  │                 │  │                  │   │
│  │  多 Provider 支持 │  │  短期记忆        │  │  工具注册与管理   │   │
│  │  运行时切换       │  │  （会话历史）     │  │  工具执行与调度   │   │
│  │  本地 / 云端      │  │  长期记忆        │  │  工具结果注入     │   │
│  │  Fallback 兜底   │  │  （用户画像）     │  │  web_search      │   │
│  │                  │  │  Context 注入    │  │  csv_analyze     │   │
│  │                  │  │  消息压缩        │  │  send_email(mock)│   │
│  └──────────────────┘  └─────────────────┘  └──────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Prompt 模块                               │    │
│  │                                                             │    │
│  │  System Prompt 构建（角色定义 / 能力边界 / 行为约束）          │    │
│  │  用户画像动态注入（每次 LLM 调用前）                           │    │
│  │  Token 预算管理（各区块分配 / 超限压缩）                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   可观测性模块                                │    │
│  │                                                             │    │
│  │  每次执行完整记录（思考链 / 工具调用 / Token 用量）            │    │
│  │  SSE 实时推送执行过程                                         │    │
│  │  finish_reason 全量处理                                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                            存储层                                     │
│                                                                      │
│  短期记忆：会话级 AgentState 持久化（跨请求保持上下文）                  │
│  长期记忆：跨会话用户画像（偏好 / 历史摘要 / 领域信息）                  │
│  可观测性：Agent 执行日志（用于调试 / 评估 / 面试展示）                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.3 Memory 设计

```
短期记忆（within-session）
  会话历史、工具调用记录、中间推理状态
  thread_id 隔离，重启后可恢复
  消息过长时自动压缩为摘要
  只存储纯对话内容，不含 RAG chunk（见 RAG 注入策略）

长期记忆（cross-session）
  用户画像：领域偏好、语言偏好、交互风格
  namespace 隔离，不同类型独立存储
  每次 turn 开始加载，结束后写回
  扩展预留：Procedural（技能库）/ Semantic（向量检索）

Working Memory（单次 LLM Call 的 Context Window）
  System Prompt + 用户画像 + 会话历史 + 工具 Schema + 当前输入
  RAG chunk（P2，目标态，当前未实装）：每轮基于当前输入重新检索，ephemeral 注入
  Token 预算分配：各区块固定上限 + 弹性历史区
  超限时自动压缩旧消息
```

### 1.3.1 RAG Chunk 注入策略（P2，目标态，当前未实装）

```
设计决策：Ephemeral 注入

问题背景：
  RAG chunk 注入 Working Memory 后，LLM 回复连同 chunk 一起写入 Short Memory
  后续轮次 Short Memory 恢复，历史 chunk 持续占用 Token
  多轮后历史 chunk 堆积，与当前问题无关但消耗大量预算

选择的策略：Ephemeral 注入
  RAG chunk 在 wrap_model_call 里注入请求级 messages（与 episodic 同链路）
  属于请求级参数，不写回永久 state，不进入 checkpointer
  每轮基于当前用户输入重新检索，注入最相关的 chunk
  Short Memory 里只保存纯对话历史

结论：
  Short Memory  → 干净，只含对话历史，SummarizationMiddleware 压缩效果好
  RAG chunk     → 每轮 ephemeral，始终与当前问题相关
  Token 预算    → 可控，不会因多轮对话导致 chunk 无限堆积

三种策略对比：
  策略 A（当前选择）Ephemeral 注入
    chunk 不写入 Short Memory，每轮重新检索
    优点：Short Memory 干净，Token 可控
    缺点：LLM 无法感知"上轮引用了哪些知识"
    适用：RAG chunk 跨轮独立，不需要跨轮知识引用

  策略 B  持久化 + 压缩
    chunk 写入 Short Memory，依赖 SummarizationMiddleware 压缩
    优点：LLM 能感知历史引用，连贯性好
    缺点：压缩后 chunk 细节丢失，短期 Token 压力大

  策略 C  每轮覆盖
    新 chunk 覆盖旧 chunk，管理固定的 RAG slot
    优点：始终注入最相关内容
    缺点：需要额外管理 slot 位置，实现复杂
```

### 1.4 Middleware 执行流程

```
每次 Agent turn 完整生命周期：

  before_agent    → turn 开始，触发 1 次，加载长期记忆到 state
  before_model    → LLM 调用前，可修改永久 state（当前未使用）
  wrap_model_call → LLM 调用前，注入用户画像到请求级 messages
  [ LLM 调用 ]
  after_model     → LLM 调用后，解析结果推送 SSE
  wrap_tool_call  → 工具调用拦截（当前未使用）
  after_agent     → turn 结束，触发 1 次，写回长期记忆
```

**before_agent 内部流程：**

```
before_agent 触发（整个 turn 只执行一次）
      │
      ▼
从 AsyncPostgresStore 读取用户画像
  store.aget(namespace=("profile", user_id), key="episodic")
      │
      ▼
反序列化为 UserProfile
  {
    preferences:       { domain: "finance", language: "zh" },
    interaction_count: 12,
    summary:           "用户关注 A 股量化策略"
  }
  新用户 → 返回空的 UserProfile()
      │
      ▼
写入 state["memory_ctx"]
  后续所有 wrap_model_call 直接从 state 读缓存，不重复打数据库
      │
      ▼
把控制权还给 create_agent，开始 ReAct 循环

为什么只触发一次：
  一次 turn 内 ReAct 循环可能触发多次 LLM 调用
  before_agent 在 turn 入口读一次缓存进 state
  避免每次 LLM 调用都重复 IO
```

**after_agent 保存的内容：**

```
after_agent 触发（整个 turn 结束后执行一次）
  写回 state["memory_ctx"].episodic 到 AsyncPostgresStore

✅ 当前实现（已落地）：
  turn 结束后更新并写回用户画像：
  interaction_count +1（存在用户交互时）
  规则提炼本轮偏好（关键词触发）
  llm 模式可按 interval 触发结构化提炼
  dirty-flag 对比 baseline，仅变化时写库

⚪ 后续演进：
  继续优化提炼策略与冲突合并规则
  例：用户提到"茅台""A股"     → preferences.domain = "stock"
      用户提到"合同""签署"     → preferences.domain = "legal"（E签宝场景）
      用户使用中文              → preferences.language = "zh"

暂不实现：
  create_memory_store_manager 自动提炼（LLM 决策写入，质量更高）

核心原则：before_agent 把画像搬进内存，after_agent 把画像搬回数据库
          持续价值来自提炼逻辑与写回策略的迭代
```

### 1.5 完整数据流

```
用户输入
  → FastAPI 收到请求（session_id, user_id, message）
  → before_agent：从 AsyncPostgresStore 加载用户画像 → state["memory_ctx"]
  → Short Memory 自动恢复（AsyncPostgresSaver 全自动，无需手写）
  → wrap_model_call：注入用户画像到请求级 messages
                     ⚪ P2（目标态，当前未实装）：注入 RAG chunk（ephemeral，不写回 state）
  → ReAct 推理循环
      → LLM 决策（思考 / 调用工具 / 给出答案）
      → 工具执行（并行）
      → 结果注入 Context，继续循环
  → after_model：解析 content_blocks → SSE 实时推送
  → AsyncPostgresSaver 自动保存
      保存 HumanMessage + AIMessage + ToolMessage（含 read_file 等工具结果）
      RAG/Episodic 等 ephemeral 注入内容不写入，Short Memory 保持干净
  → after_agent：执行 interaction_count 更新 + 规则/LLM 提炼 + dirty-flag 写回
  → 记录 AgentTrace 日志
```

### 1.6 Context Window 区块分配

```
① System Prompt + 角色定义     < 600 Token   静态
② 用户画像（长期记忆）          < 200 Token   动态，每次 turn 注入
③ RAG chunk（⚪ P2，默认关闭，目标态，当前未实装）  < 500 Token
                                    ephemeral，每轮重新检索，不写入 Short Memory
④ 工具 Schema 定义             < 300 Token   自动注入
⑤ 会话历史                      弹性预算      超限时压缩，只含纯对话，不含历史 chunk
⑥ 输出格式规范                  < 100 Token   可合并入①
⑦ 本轮用户输入                  实时          最高优先级保留
──────────────────────────────────────────────────────
总预算：模型上限 × 75%，留 25% 给 ReAct 轨迹输出
RAG 启用时固定预算 = ① + ② + ③ + ④ + ⑥ ≈ 1700 Token
弹性历史区 = 总预算 - 固定预算 - 25% 输出预留
```

### 1.7 存储表设计

```
checkpoint 表   会话级 AgentState（短期记忆）        → 见 § 1.7.1
store 表        用户画像（长期记忆）
agent_traces 表 执行日志（可观测性）
  字段：session_id / user_id / user_input / final_answer
        thought_chain / tool_calls / token_usage
        latency_ms / finish_reason
```

### 1.7.1 Checkpointer 数据结构

```
核心概念：checkpoint 不是覆盖写，而是追加写，形成历史版本链

checkpoint 表一条记录的字段：
  thread_id      哪个会话（对应 session_id）
  checkpoint_id  本次快照的唯一 ID（UUID）
  parent_id      上一次快照的 ID（形成链表，null 表示起点）
  step           这是第几个 ReAct step
  state          序列化的 state 内容（JSON）
  created_at     时间戳

一次完整 turn 的版本链示例（含 HIL 场景）：
  checkpoint_1 (step=0, parent=null)    ← turn 开始
  checkpoint_2 (step=1, parent=1)       ← web_search 执行完
  checkpoint_3 (step=2, parent=2)       ← send_email 触发 HIL 暂停（断点）
  checkpoint_4 (step=3, parent=3)       ← 用户确认，send_email 执行完
  checkpoint_5 (step=4, parent=4)       ← turn 结束，最终答案

state 字段序列化内容（AgentState）：
  messages: [
    HumanMessage("搜茅台股价然后发邮件给老板"),
    AIMessage(tool_calls=[{name: "web_search", args: {...}}]),
    ToolMessage(content="茅台今日收盘价 1820 元", tool_call_id="xxx"),
    AIMessage(tool_calls=[{name: "send_email", args: {to: "boss@...", ...}}])
    ← HIL 断点处：send_email 的 tool_call 已在 messages 里，但还未执行
  ],
  memory_ctx: {
    episodic: { preferences: {...}, interaction_count: 12 }
  }

restore 策略：
  普通 turn 开始  → SELECT step 最大的 checkpoint（最新快照）
  HIL resume     → SELECT thread_id 对应的 checkpoint_3（断点快照）
                   state 里的 send_email tool_call 直接继续执行，不重跑前置步骤

为什么用版本链而不是覆盖写：
  覆盖写 → HIL resume 时丢失断点，只能从头执行
  版本链 → 任意历史断点可恢复，HIL / 调试 / 审计全部支持
```

### 1.7.2 Checkpointer 完整全景图

```
─── turn 1 · 第一次请求进来 ─────────────────────────────────────
FastAPI 收到请求（session_id = "abc"）
  → create_agent.invoke(config={thread_id: "abc"})
  → checkpointer.restore(thread_id="abc")
      SELECT * FROM checkpoints WHERE thread_id="abc" ORDER BY step DESC LIMIT 1
      第一次：无记录 → state = { messages: [] }
      后续次：有记录 → state 从 JSON 反序列化恢复到内存

─── ReAct 循环（纯内存操作）────────────────────────────────────
state.messages.append(HumanMessage)
  → LLM call → AIMessage(tool_calls=[web_search])
  → checkpointer.save(step=1)         ← 写入 PostgreSQL
  → web_search 执行 → ToolMessage
  → checkpointer.save(step=2)         ← 写入 PostgreSQL
  → LLM call → AIMessage(tool_calls=[send_email])
  → checkpointer.save(step=3)         ← 写入 PostgreSQL（HIL 断点）
  → HumanInTheLoopMiddleware 拦截 → SSE push hil_interrupt → 暂停

─── 用户在前端操作（可能等待 N 秒）──────────────────────────────
前端展示确认框，用户点确认
  → POST /chat/resume { interrupt_id, action: "approve" }

─── resume 请求进来 ─────────────────────────────────────────────
checkpointer.restore(thread_id="abc")
  SELECT checkpoint WHERE step=3    ← 恢复 HIL 断点，不是最新快照
  state 反序列化：messages 里有 send_email tool_call 等待执行
  → send_email 执行 → ToolMessage
  → checkpointer.save(step=4)
  → LLM 生成最终答案
  → checkpointer.save(step=5)         ← turn 结束快照
  → SSE push done

─── turn 2 · 下一轮对话进来 ─────────────────────────────────────
checkpointer.restore(thread_id="abc")
  SELECT step=5 的 checkpoint（最新快照）
  state.messages = [HumanMessage, AIMessage×2, ToolMessage×2, ...]
  完整历史恢复，Agent 感知上轮全部内容，继续对话

─── 关键设计原则 ────────────────────────────────────────────────
记忆时效 ≠ 存储介质：
  短期记忆 描述的是「用途」（session 级，对话结束即废弃）
  存 PostgreSQL 描述的是「位置」（持久化，跨请求存活）
  两个维度独立，短期记忆存 PostgreSQL 不矛盾

为什么不存内存：
  FastAPI 无状态，每个请求独立，上一请求的内存对象请求结束即 GC
  内存存活 → 单进程内有效，多进程 / 重启即丢失
  PostgreSQL 存活 → 跨进程、跨重启、HIL 断点恢复全部支持

为什么不用 Redis：
  PostgreSQL 已在栈里（长期记忆也用它），不增加基础设施
  LangGraph AsyncPostgresSaver 官方支持，零配置
  可以用 SQL 直接查历史 checkpoint，方便调试和面试展示
  Agent 场景写频率不高，PostgreSQL 写入延迟可接受
```

### 1.8 服务部署

```
frontend    Next.js        :3000
backend     FastAPI        :8000
database    PostgreSQL     :54322
studio      DB Dashboard   :54323
```

### 1.9 Agent Turn 完整时序

```
参与者：User / FastAPI / MemoryMiddleware / create_agent / LLM / PostgreSQL

User → FastAPI
  POST /chat {message, session_id}

FastAPI → create_agent
  invoke(message, config={thread_id: session_id})

─── ① before_agent（turn 开始，触发 1 次）────────────────────────────
create_agent → MemoryMiddleware.before_agent
  → PostgreSQL：store.aget(namespace=("profile", user_id), key="episodic")
  ← UserProfile → 写入 state["memory_ctx"]

─── ② Short Memory 自动恢复（LangChain 内置，全自动）────────────────
create_agent → PostgreSQL
  → AsyncPostgresSaver.restore(thread_id)
  ← messages[]（上轮对话历史）

─── ③ wrap_model_call（每次 LLM 调用前）────────────────────────────
create_agent → MemoryMiddleware.wrap_model_call
  → 从 state["memory_ctx"] 读用户画像（不打数据库）
  → 注入用户画像到请求级 messages（ephemeral，不写回 state）
  → ⚪ P2（目标态，当前未实装）：注入 RAG chunk（同样 ephemeral，不写回 state，不污染 Short Memory）

─── LLM 调用 ────────────────────────────────────────────────────────
create_agent → LLM
  → invoke(messages)  ← 包含：System Prompt + 用户画像 + 历史 + 当前输入
  ← AIMessage（content_blocks：TextBlock + ToolCallBlock）

─── ④ after_model（每次 LLM 调用后）────────────────────────────────
create_agent → TraceMiddleware.after_model
  → 解析 content_blocks
  → SSE push {type: "thought" / "tool_start"} → FastAPI → User

─── ⑤ Short Memory 自动保存（LangChain 内置，全自动）───────────────
create_agent → PostgreSQL
  → AsyncPostgresSaver.save(messages state)
  → 持久化对象含 HumanMessage + AIMessage + ToolMessage
  → RAG/Episodic 等 ephemeral 注入不写入，Short Memory 保持干净

─── ⑥ after_agent（turn 结束，触发 1 次）───────────────────────────
create_agent → MemoryMiddleware.after_agent
  → interaction_count 更新（有交互时 +1）
  → 规则提炼本轮偏好；llm 模式可按 interval 提炼
  → dirty-flag：无变化跳过写库
  → PostgreSQL：store.aput(namespace=("profile", user_id), key="episodic", value=UserProfile)

FastAPI → User
  ← {answer, session_id}

关键设计说明：
  ③ 中的用户画像和 RAG chunk 都是 ephemeral：注入请求级参数，不修改永久 state
  ⑤ Short Memory 干净：只存对话，不存 RAG chunk，SummarizationMiddleware 压缩效果好
  ① 和 ⑥ 各只触发一次：避免 ReAct 多轮循环重复读写数据库
  Short Memory 读写（② ⑤）全自动：不需要任何手写逻辑
```

### 1.10 部署架构范式对比

```
范式一：同步请求响应（当前实现）
─────────────────────────────────────────────────────────
Client → API Server → Agent Executor → 结果 → Client

特征：
  Client 发请求后 HTTP 连接一直挂着，等待结果返回
  API Server 直接调用 Agent Executor，串行执行
  Agent Executor 跑完才返回响应

适用：
  Portfolio 项目 / 面试展示
  任务耗时可控（< 10s）
  单用户或低并发场景

瓶颈：
  HTTP 连接超时（复杂任务 30s+）
  无法横向扩展 Worker
  任务失败即请求失败，无法重试
  无法取消正在执行的任务


范式二：事件驱动异步（主流生产架构）
─────────────────────────────────────────────────────────
Client → API Server → Job Queue → Worker → Agent Executor
                ↓                              ↓
          202 立即返回                    Result Store → Client

特征：
  API Server 收到请求后立刻入队，返回 job_id，HTTP 连接释放
  Worker 异步消费 Queue，独立于客户端连接
  结果通过 Result Store / Event Bus 推回给客户端

适用：
  复杂任务（多工具、多步推理、长时运行）
  高并发、多用户场景
  需要任务重试、取消、优先级调度

Job Queue 完整能力（不只是"API 不挂着"）：
  任务生命周期管理    created → queued → running → completed / failed / retrying
  任务重试            Worker 崩溃时任务回到 Queue 重试，不丢失
  任务取消            用户可随时 DELETE /jobs/{job_id}，Worker 检测到后中止
  优先级调度          VIP 用户任务插队，普通用户排队
  背压控制            Queue 积压时 API 返回 503，拒绝新请求保护 Worker
  并发控制            Queue 决定同时分发多少任务，Worker Pool 弹性伸缩
  任务幂等            同一 job_id 执行两次结果一致，保证重试安全

Worker Pool 完整能力：
  动态分配            任务与 Worker 动态绑定，Worker 完成后立刻接下一个任务
  横向扩展            Queue 积压增长时自动扩容 Worker 数量
  故障隔离            某个 Worker 挂了，任务转移到其他 Worker
  多任务并发          同一用户的多个任务可被不同 Worker 同时执行
```

### 1.11 Worker 与 Agent Executor 的关系

```
两者是包含关系，不是并列关系：

  ┌─────────────────────────────────────────────────┐
  │              Agent Worker（进程/容器壳）          │
  │                                                 │
  │  Task Manager                                   │
  │  · 从 Queue 取任务                               │
  │  · 管理任务状态（running / failed / completed）  │
  │  · 超时控制 / 重试逻辑                           │
  │  · 结果写回 Result Store                         │
  │                    ↓ 调用                        │
  │  ┌───────────────────────────────────────────┐  │
  │  │         Agent Executor（执行引擎核心）      │  │
  │  │                                           │  │
  │  │  ReAct 推理循环                            │  │
  │  │  LLM 调用                                 │  │
  │  │  工具调度（并行）                           │  │
  │  │  Memory 读写                              │  │
  │  │  Context 组装                             │  │
  │  │  SSE 推送                                 │  │
  │  └───────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────┘

Worker  = 管理任务的容器壳
Agent Executor  = 壳里真正执行 ReAct 的引擎

对应到当前项目：
  agent/executor.py  =  Agent Executor（已实现）
  Worker 壳          =  当前由 FastAPI Handler 直接扮演（范式一）

升级路径（范式一 → 范式二）：
  agent/executor.py 的代码完全不需要改动
  只需要在外层加 Worker 进程 + Job Queue
  FastAPI Handler 从"直接调用 executor"改为"把任务入队"
  Worker 从 Queue 取任务后调用同一个 executor.py

这就是为什么两种范式的升级成本不高：
  Agent Executor 已经是正确抽象，只是调用它的上层不同
```

### 1.12 Agent Executor 完整 Workflow（框架无关）

```
纯架构角度，一个完整的 Agent Executor 需要完成以下九个阶段：

─── ① Receive input ──────────────────────────────────────────────
  入口契约：message + session_id + user_id
  这是 Executor 接受的最小输入集合

─── ② Assemble context window ────────────────────────────────────
  这是整个 Executor 最核心的工程问题
  从 Short Memory 加载会话历史
  从 Long Memory 加载用户画像
  按 Token 预算填充各区块：
    system prompt · user profile · tool schemas · history · input
  超出预算时压缩旧消息为摘要
  ⚪ P2：同时注入 RAG chunk（ephemeral，不写入历史）

─── ③ LLM call ───────────────────────────────────────────────────
  把完整 Context Window 发给 LLM
  拿回原始输出（reasoning text + tool calls / final answer）

─── ④ Parse LLM output ───────────────────────────────────────────
  提取推理文本
  提取工具调用指令（name + args）或最终答案
  判断 finish_reason

─── ⑤ Decide: tool call? ─────────────────────────────────────────
  finish_reason = tool_calls  → 进入 ⑥ 工具执行
  finish_reason = stop        → 跳到 ⑦ 处理结束
  finish_reason = length / error / timeout → 跳到 ⑦ 异常处理

─── ⑥ Tool execution（ReAct 循环内部）────────────────────────────
  Iteration guard：检查已执行步数，超过 max_steps 强制终止
  并行 dispatch 所有工具调用
  收集 Observation（工具执行结果）
  把 Observation 追加进历史
  回到 ② 重新组装 Context Window，进入下一轮循环
  这就是 ReAct 的核心：Reason → Act → Observe → Reason ...

─── ⑦ Handle finish reason ──────────────────────────────────────
  stop        → 正常结束，输出最终答案
  length      → Token 超限，输出当前最佳答案
  error       → 模型报错，记录日志，返回降级响应
  timeout     → 执行超时，返回当前进度
  interrupted → 外部中断（HIL / 用户取消），保存中间状态
  max_steps   → 达到迭代上限，返回当前最佳答案

─── ⑧ Stream output ─────────────────────────────────────────────
  不是最后才推送，而是全程实时推送：
  · 每次 LLM 推理文本 → push "thought" event
  · 每次工具调用开始  → push "tool_start" event
  · 每次工具执行完成  → push "tool_result" event
  · 最终答案          → push "done" event

─── ⑨ Persist state ─────────────────────────────────────────────
  收尾契约，写三个地方：
  Short Memory  → 保存本轮 HumanMessage + AIMessage（不含 RAG chunk）
  Long Memory   → 更新用户画像（⚪ P2 第一步：+1 交互次数；⚪ P2 第二步：规则提炼偏好）
  Trace Log     → 写可观测性日志（thought_chain / tool_calls / token_usage / latency）

关键设计洞察：
  LangChain 覆盖的是通用机制（循环控制、工具调度、历史持久化）
  自行开发的是业务判断（流式推送策略、用户画像更新、日志记录）
  这个边界决定了哪些代码可以被框架替换，哪些必须自己写
```

---

### 1.13 HIL（Human-in-the-Loop）完整设计

#### HIL 本质判断：操作不可逆 → 需要人介入

```
判断标准：操作是否可逆 / 是否有外部副作用

可逆操作（只读 / 无副作用）→ 不需要 HIL，直接执行
  web_search              查询外部数据，无副作用
  csv_analyze             本地分析，无副作用
  查询类 API              只读，不改变任何状态

不可逆操作（写操作 / 外部副作用）→ 需要 HIL，暂停等用户确认
  send_email              邮件发出无法撤回
  post_to_social_media    发帖后影响已产生
  delete_file             删除后数据丢失
  place_order             订单提交后触发履约流程
  execute_trade           交易执行后资金变动

当前项目演示工具：
  send_email（mock 实现）  不真实发送，仅用于演示 HIL 完整流程
  触发 HumanInTheLoopMiddleware(interrupt_on={"send_email": True})
```

#### HIL vs MCP Elicitation vs MCP Sampling 对比

```
三者共同本质：执行中途"暂停等待外部输入"再继续

HIL（Human-in-the-Loop）
  暂停者：Agent 执行引擎
  等待谁：真实用户（人）
  触发时机：检测到高风险/不可逆工具调用前
  恢复方式：用户点确认 → POST /chat/resume → Agent 从 checkpoint 恢复
  状态存哪：LangGraph checkpointer（PostgreSQL）
  层级：AI Application 层

MCP Elicitation
  暂停者：MCP Server（Tool）
  等待谁：真实用户（人）
  触发时机：工具执行中发现信息不足，主动向用户索取
  恢复方式：Client 收到 elicitation 请求 → 弹窗 → 用户填写 → 返回 Server
  状态存哪：MCP Client 维持上下文
  层级：MCP Protocol 层

MCP Sampling
  暂停者：MCP Server（Tool）
  等待谁：另一个 LLM（不是人）
  触发时机：Server 需要 LLM 推理能力，自身无法完成
  恢复方式：Server 请求 Host → Host 调用 LLM → 结果同步返回 Server
  状态存哪：无需持久化，同步请求
  层级：MCP Protocol 层

结论：HIL ≈ MCP Elicitation，模式相同（暂停等人），层级不同（Application vs Protocol）
      MCP Sampling 是 LLM 调 LLM，与 HIL 无关
```

#### HIL 完整交互时序

```
演示场景：用户说"搜茅台股价然后发邮件给老板"

User → FastAPI
  POST /chat { message: "搜茅台股价然后发邮件给老板", session_id }

FastAPI → create_agent.invoke(message, config={thread_id})

─── ReAct 循环开始 ──────────────────────────────────────────
LLM 决策：先调 web_search
  → web_search 执行完毕
  → SSE push: { event: "tool_result", data: { tool: "web_search", result: "..." } }

LLM 决策：调用 send_email   ← HumanInTheLoopMiddleware 拦截
  → Agent 暂停（interrupt）

─── HIL 暂停阶段 ────────────────────────────────────────────
LangGraph 把当前 state 存入 PostgreSQL checkpoint
  （包含：消息历史 + web_search 结果 + 待执行的 send_email 调用）

SSE push: {
  event: "hil_interrupt",
  data: {
    interrupt_id: "uuid-xxxx",
    tool_name:    "send_email",
    tool_args: {
      to:      "boss@company.com",
      subject: "茅台股价报告",
      body:    "今日茅台收盘价 ..."
    },
    message: "Agent 准备执行以上操作，请确认"
  }
}

─── 前端响应 ────────────────────────────────────────────────
前端收到 hil_interrupt event
  → 停止 loading 动画
  → 弹出确认框，展示 tool_args 内容（邮件收件人 / 主题 / 正文）
  → 用户操作：

  确认 → POST /chat/resume { interrupt_id: "uuid-xxxx", action: "approve" }
  取消 → POST /chat/resume { interrupt_id: "uuid-xxxx", action: "reject"  }
  可选增强：确认时可附带「本会话内不再询问此工具」标记
    → 当前实现会把 grant 写入 PolicyEngine 的运行时内存
    → 同一 backend 进程存活期间，后续同工具调用可直接跳过 HIL
    → 该 grant 当前不持久化到 PostgreSQL；backend 重启后失效

─── Resume 阶段 ─────────────────────────────────────────────
FastAPI /resume 接口
  → 用 thread_id 从 PostgreSQL 恢复 checkpoint（web_search 结果已在 state，不重跑）

  approve 分支：
    → 继续执行 send_email
    → SSE push: { event: "tool_start",  data: { tool: "send_email" } }
    → SSE push: { event: "tool_result", data: { result: "邮件已发送" } }
    → LLM 生成最终答案
    → SSE push: { event: "done", data: { answer: "已帮你发送..." } }

  reject 分支：
    → 注入 ToolMessage: "用户取消了 send_email 操作"
    → LLM 重新决策（可能回复"好的，已取消"或建议其他操作）
    → SSE push: { event: "done", data: { answer: "好的，已取消发送..." } }

─── 关键设计说明 ────────────────────────────────────────────
checkpointer 的作用：
  resume 时从 interrupt 点继续，web_search 结果已在 state，不重新执行
  没有 checkpointer → resume 只能从头跑，前置工具全部重新执行

当前实现边界：
  HIL interrupt / checkpoint    → PostgreSQL 持久化，跨进程 / 跨重启可恢复
  session grant（本会话放行）→ 仅进程内运行时状态，backend 重启后丢失
  因此“恢复已暂停审批”和“记住本会话已放行”目前不是同一持久化等级

SSE event 类型完整列表（含 HIL）：
  thought       LLM 推理文本（思考过程）
  tool_start    工具开始执行（含 tool_name + args）
  tool_result   工具执行完成（含 result）
  hil_interrupt HIL 暂停，等待用户确认（含 interrupt_id + tool_args）
  done          最终答案，流结束
  error         异常，含错误信息

API 接口对应：
  POST /chat          发起新对话 turn，返回 SSE 流
  POST /chat/resume   HIL 确认/取消后恢复执行，返回 SSE 流（继续推送后续事件）
```

---

## 第二层：LangChain 实现映射

> 标注当前架构中哪些由 LangChain 内置覆盖，哪些需要自行开发

### 2.1 总览

```
✅ LangChain 内置，配置即用
  create_agent              ReAct 推理循环（langchain.agents）
  AgentMiddleware           Middleware 协议基类（langchain.agents.middleware）
  SummarizationMiddleware   消息压缩，Token 超限自动处理（langchain.agents.middleware）
  ToolNode                  工具并行调度（langgraph.prebuilt）
  InjectedState             工具内读取 AgentState（langgraph.prebuilt）
  AsyncPostgresSaver        短期记忆自动持久化（langgraph.checkpoint.postgres.aio）
  AsyncPostgresStore        长期记忆存储层（langgraph.store.postgres）
  HumanInTheLoopMiddleware  HIL 人工介入（langchain.agents.middleware）
                            interrupt_on={"send_email": True} 是 middleware 参数
                            非 create_agent 直接参数
                            完整交互设计见 § 1.13
  response_format           结构化输出（create_agent 参数）
  ChatOllama                本地 LLM（langchain_ollama）
  ChatZhipuAI               智谱 LLM（langchain_community）
  ChatOpenAI                OpenAI / DeepSeek 兼容（langchain_openai）

🔧 自行开发，业务逻辑
  MemoryMiddleware          before_agent 加载画像 / wrap_model_call 注入 / after_agent 写回
  TraceMiddleware           after_model 解析 content_blocks 推送 SSE
  MemoryManager             load_episodic / save_episodic / build_working_memory
  llm_factory()             读 .env 返回对应 ChatModel 实例 + Fallback 逻辑
  prompt/builder.py         build_system_prompt()，静态模板 + 动态画像拼装
  prompt/templates.py       角色定义 / 能力边界 / 行为约束静态模板
  tools/search.py           web_search（Tavily API 封装）
  tools/csv_analyze.py      CSV 分析工具（P0）
  agent/executor.py         Agent Executor 核心，ReAct 执行引擎
                            范式一：FastAPI Handler 直接调用
                            范式二升级：Worker 进程调用，代码不变
  agent/finish_handler.py   finish_reason 全量处理
  observability/tracer.py   AgentTrace 写入 agent_traces 表
  前端全部组件

⚡ 胶水代码，少量自行开发
  db/postgres.py            AsyncPostgresSaver + AsyncPostgresStore 初始化
  langchain_engine.py       create_agent 参数组装
  tools/registry.py         工具注册表
  tools/base.py             InjectedState 封装基类
  session/manager.py        session_id → thread_id 映射
```

### 2.2 Agent Executor Workflow → LangChain 映射

```
纯架构概念                         LangChain 实现                    归属
─────────────────────────────────────────────────────────────────────────
① Receive input                   FastAPI Handler 传入               ⚡ 胶水
② Assemble context window
   · 会话历史加载                  AsyncPostgresSaver 自动恢复         ✅ 内置
   · 消息超限压缩                  SummarizationMiddleware             ✅ 内置
   · 工具 Schema 注入              create_agent 自动处理               ✅ 内置
   · 用户画像注入                  MemoryMiddleware.wrap_model_call    🔧 自行开发
   · RAG chunk 注入（P2，目标态）   MemoryMiddleware.wrap_model_call    🔧 自行开发
③ LLM call                        create_agent 内部 ReAct 循环        ✅ 内置
④ Parse LLM output                content_blocks 自动解析             ✅ 内置
⑤ Decide: tool call?              finish_reason 判断（框架内部）       ✅ 内置
⑥ Tool execution
   · Iteration guard               max_iterations 参数                ✅ 内置
   · 并行 dispatch                 ToolNode 并行调度                   ✅ 内置
   · Observation 注入历史          create_agent 自动追加               ✅ 内置
   · 回到 ② 循环                   ReAct loop 自动驱动                 ✅ 内置
⑦ Handle finish reason            agent/finish_handler.py            🔧 自行开发
⑧ Stream output                   TraceMiddleware.after_model        🔧 自行开发
⑨ Persist state
   · Short Memory                  AsyncPostgresSaver 全自动           ✅ 内置
   · Long Memory                   MemoryMiddleware.after_agent       🔧 自行开发
   · Trace Log                     observability/tracer.py            🔧 自行开发

核心边界：
  ✅ LangChain 覆盖  →  通用机制（循环控制、工具调度、历史持久化）
  🔧 自行开发        →  业务判断（流式推送策略、用户画像更新、日志记录）
```

### 2.3 Middleware 钩子职责分配

> **钩子分两类，签名完全不同（已通过 LangChain 官方文档验证）**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  类型一：Node-style hooks（操作 AgentState）                              │
│  签名：def hook(self, state: AgentState, runtime: Runtime)               │
│        -> dict[str, Any] | None                                          │
│  返回 dict → 更新 state；返回 None → 不改变 state                         │
└─────────────────────────────────────────────────────────────────────────┘

钩子              触发时机               职责                       归属
──────────────────────────────────────────────────────────────────────────
before_agent     每次 turn 开始，1 次    从 AsyncPostgresStore 加载  🔧 MemoryMiddleware
                                        UserProfile
                                        存入 state["memory_ctx"]
                                        后续 wrap_model_call
                                        直接读缓存，不重复 IO

before_model     每次 LLM 调用前         （当前未使用）               —
                                        可用于修改永久 state

after_model      每次 LLM 调用后         写 AgentTrace 日志           🔧 TraceMiddleware
                                        ⚠️ 不负责 SSE（见 §2.6）
                                        state["messages"][-1] 是
                                        本次 LLM 的完整 AIMessage

after_agent      每次 turn 结束，1 次    写回 UserProfile 到          🔧 MemoryMiddleware
                                        AsyncPostgresStore
                                        ✅ 当前实现：interaction_count +1
                                        ✅ 当前实现：关键词规则提炼偏好
                                           示例：消息含"合同""签署"
                                           → preferences.domain = "legal-tech"
                                        ✅ 当前实现：dirty-flag 变更写回
                                        ⚪ 后续：langmem 自动提炼

┌─────────────────────────────────────────────────────────────────────────┐
│  类型二：Wrap-style hooks（包裹 LLM / 工具的请求+响应）                    │
│  ⚠️ 不操作 AgentState，通过 request.override() 修改请求                   │
└─────────────────────────────────────────────────────────────────────────┘

钩子              触发时机               职责                       归属
──────────────────────────────────────────────────────────────────────────
wrap_model_call  每次 LLM 调用，包裹     注入用户画像到请求级          🔧 MemoryMiddleware
                 实际调用               messages
                                        ephemeral，不写回永久 state
                                        ⚪ P2（目标态，当前未实装）：同时注入 RAG chunk
                                        用 request.override(
                                          messages=[...]
                                        ) 而不是把注入内容持久写入 state["messages"]

wrap_tool_call   每次工具调用，包裹      （当前未使用）               —
                 实际调用               可用于工具参数审计
```

**关键区别——为什么用户画像注入必须用 `wrap_model_call` 而不是 `before_model`：**

```
before_model（Node-style）
  操作 AgentState，修改会写入 checkpointer 快照
  → 用户画像 text 会被持久化进 Short Memory
  → 下轮恢复时，画像作为历史消息重复出现 ← ❌ 污染 Short Memory

wrap_model_call（Wrap-style）
  操作 ModelRequest，ephemeral，不写入 AgentState
  → 用户画像只在本次 LLM 调用的请求里，用完即弃
  → Short Memory 只保存纯对话历史 ← ✅ 干净
  → 体现在 E签宝 场景：
     用户上传合同模板 → Agent 分析 → 短期记忆只存对话，不存每次注入的角色画像
```

### 2.4 SSE 流式架构（已验证）

> **核心结论：SSE 推送完全由 `agent.astream()` 承担，不需要在 Middleware 里手写推送逻辑。**

#### stream_mode 映射表

```
agent.astream() 同时监听两个模式：stream_mode=["messages", "updates"]

stream_mode       数据内容                          → SSE event 类型
─────────────────────────────────────────────────────────────────────
"messages"        AIMessageChunk.text               → thought
                  AIMessageChunk.tool_call_chunks   → tool_start（含工具名和入参）

"updates"         source="model"                   → （已由 messages 处理，跳过）
                  source="tools"                   → tool_result（含工具返回值）
                  source="__interrupt__"            → hil_interrupt（HIL 暂停）
                  source="end"                     → done（最终答案）
```

#### FastAPI SSE 接口实现模式（P0）

```python
# 🔴 P0：合同查询演示场景
# 用户："帮我查一下我们公司最近的电子签名法规变化"
# Agent：调用 web_search → 流式输出推理 → 返回结果
from typing import TypedDict

@router.post("/chat")
async def chat(req: ChatRequest):
    class AgentContext(TypedDict):
        user_id: str

    async def event_generator():
        async for stream_mode, data in agent.astream(
            {"messages": [HumanMessage(content=req.message)]},
            config={"configurable": {"thread_id": req.session_id}},
            context=AgentContext(user_id=req.user_id),
            stream_mode=["messages", "updates"],
        ):
            if stream_mode == "messages":
                token, metadata = data
                if isinstance(token, AIMessageChunk):
                    if token.text:
                        yield f"event: thought\ndata: {token.text}\n\n"
                    if token.tool_call_chunks:
                        yield f"event: tool_start\ndata: {json.dumps(token.tool_call_chunks)}\n\n"

            elif stream_mode == "updates":
                for source, update in data.items():
                    if source == "tools":
                        result = update["messages"][-1].content
                        yield f"event: tool_result\ndata: {json.dumps({'result': result})}\n\n"
                    if source == "__interrupt__":
                        interrupt_data = update[0].value
                        yield f"event: hil_interrupt\ndata: {json.dumps(interrupt_data)}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

#### TraceMiddleware 重新定位

```
❌ 旧设计：TraceMiddleware.after_model 负责 SSE 推送
✅ 新设计：TraceMiddleware.after_model 只负责写 agent_traces 日志

before TraceMiddleware 职责：
  SSE 推送     → agent.astream() 在 FastAPI 层处理   ✅ 框架原生
  日志记录     → TraceMiddleware.after_model         🔧 自行开发

after TraceMiddleware 重写：
  def after_model(
      self,
      state: AgentState,
      runtime: Runtime,
  ) -> dict[str, Any] | None:
      # 从 state 读已完成的 AIMessage，写入 agent_traces 表
      # 🟡 P1：面试加分项，展示可观测性能力
      last_msg = state["messages"][-1]
      if isinstance(last_msg, AIMessage):
          await self.tracer.record(
              session_id  = state["session_id"],
              content_blocks = last_msg.content_blocks,
              token_usage = last_msg.usage_metadata,
          )
      return None  # 不改变 state
```

#### 优先级标注

```
🔴 P0  agent.astream() 基础 SSE（thought + tool_result + done）
        → 面试演示必须：展示 Agent 思考链路
🟡 P1  tool_start event（工具入参展示）
        → 加分项：说明 "Agent 选了什么工具、传了什么参数"
🟡 P1  TraceMiddleware 写 agent_traces（Supabase Studio 里可查）
        → 加分项：展示可观测性设计
⚪ P2  hil_interrupt + resume 接口
        → 完整度：演示 HIL 合同审批确认场景
```

### 2.5 存储层职责分配

```
存储对象           建表方式                               归属
──────────────────────────────────────────────────────────────────────
checkpoint 表     AsyncPostgresSaver.setup() 自动建      ✅ LangChain 内置
store 表          AsyncPostgresStore.setup() 自动建      ✅ LangChain 内置
agent_traces 表   手写 migration SQL                     🔧 自行开发
```

### 2.6 Memory 职责分配

```
能力                    实现方式                                归属
──────────────────────────────────────────────────────────────────────
短期记忆持久化           AsyncPostgresSaver                     ✅ LangChain 内置，全自动    🔴 P0
短期记忆读取             checkpointer 自动恢复                   ✅ LangChain 内置，全自动    🔴 P0
消息压缩                 SummarizationMiddleware                 ✅ LangChain 内置，零配置    🔴 P0
长期记忆存储层           AsyncPostgresStore                     ✅ LangChain 内置            🔴 P0
长期记忆读写逻辑         MemoryManager                          🔧 自行开发                  🔴 P0/⚪P2
  已实现：load_episodic / load_procedural（读取链路）
  已实现：save_episodic（写回链路）
  已实现：aafter_agent 内 interaction_count + 规则提炼 + dirty-flag 写回
  后续目标：提炼策略增强与冲突合并规则
用户画像注入逻辑         MemoryMiddleware.wrap_model_call        🔧 自行开发                  🔴 P0
RAG chunk 注入          MemoryMiddleware.wrap_model_call         🔧 自行开发                  ⚪ P2（目标态）
  策略：Ephemeral，每轮重新检索，不写入 Short Memory
  位置：请求级 messages，不写回永久 state
暂不实现：langmem create_manage_memory_tool / create_memory_store_manager
```

### 2.6 目录结构

```
backend/
├── main.py
├── config.py
├── db/
│   ├── client.py                  # ⚡ Supabase 单例
│   └── postgres.py                # ⚡ AsyncPostgresSaver + AsyncPostgresStore 初始化
├── supabase/
│   └── migrations/0001_init.sql   # 🔧 只建 agent_traces 表
├── agent/
│   ├── executor.py                # 🔧 主入口，SSE 推送控制
│   ├── langchain_engine.py        # ⚡ create_agent 参数组装
│   ├── finish_handler.py          # 🔧 finish_reason 处理
│   ├── error_recovery.py          # 🔧 业务层兜底
│   └── middleware/
│       ├── memory.py              # 🔧 MemoryMiddleware
│       └── trace.py               # 🔧 TraceMiddleware
├── llm/
│   ├── factory.py                 # ⚡ llm_factory()
│   ├── ollama_provider.py         # ⚡
│   ├── zhipu_provider.py          # ⚡
│   ├── deepseek_provider.py       # ⚡
│   └── openai_provider.py         # ⚡
├── memory/
│   ├── manager.py                 # 🔧 MemoryManager
│   ├── schemas.py                 # 🔧 UserProfile / ProceduralMemory / MemoryContext / EpisodicData(P2预留)
│   └── long_term/
│       ├── episodic.py            # 🔧 🔴P0 基础版（+1）；🟡P1 规则提炼
│       ├── procedural/            # ⚪ P2 预留
│       └── semantic.py            # ⚪ P2 预留，默认关闭
├── prompt/
│   ├── builder.py                 # 🔧 build_system_prompt()
│   └── templates.py               # 🔧 静态模板
├── tools/
│   ├── registry.py                # ⚡ 工具注册表
│   ├── base.py                    # ⚡ InjectedState 封装
│   └── search.py                  # 🔧 web_search（Tavily）
├── observability/
│   ├── tracer.py                  # 🔧 AgentTrace 写入
│   └── store.py                   # 🔧 Trace 查询
└── session/
    └── manager.py                 # ⚡ session_id → thread_id 映射
```

### 2.7 实现优先级

> 优先级说明：
> 🔴 P0  面试前必须实现，跑不通就没法演示
> 🟡 P1  面试时加分项，有时间就做
> ⚪ P2  完整度提升，面试后再做

---

**🔴 P0 · 面试前必须完成 · 最小可演示链路**

```
目标验收：能在面试现场完整演示一次 ReAct 对话，含工具调用和流式输出

后端基础设施
  ⚡ Supabase Docker 启动
  ⚡ config.py + .env（配通一个 LLM Provider 即可）
  ⚡ db/postgres.py（AsyncPostgresSaver + AsyncPostgresStore 初始化，自动建表）

核心 Agent 链路
  ⚡ langchain_engine.py（create_agent + SummarizationMiddleware）
  🔧 llm/factory.py（优先跑通一个 Provider，Fallback 暂缓）
  🔧 tools/search.py（web_search，Tavily）
  🔧 agent/middleware/memory.py（MemoryMiddleware · before_agent / wrap_model_call / after_agent 基础版）
  🔧 agent/middleware/trace.py（TraceMiddleware · after_model 推送 SSE）
  🔧 agent/finish_handler.py
  🔧 main.py（POST /chat SSE 接口）

短期记忆
  ✅ AsyncPostgresSaver 自动持久化（零配置）
  验收：第二轮对话能记住第一轮内容

前端
  🔧 对话输入 / 消息列表
  🔧 SSE 流式接收与渲染
  🔧 工具调用链路展示（工具名 / 入参 / 结果）

演示场景（E签宝视角）：
  "帮我查一下茅台今天的股价"
  → Agent 调用 web_search → 流式输出推理过程 → 返回结果
  → 第二轮："和昨天比怎么样？" → Agent 记住上轮结果继续回答
```

---

**🟡 P1 · 面试加分项 · 有时间就做**

```
HIL 完整流程（见 § 1.13）
  🔧 tools/send_email.py（mock 实现，不真实发送）
  🔧 HumanInTheLoopMiddleware(interrupt_on={"send_email": True})
  🔧 SSE hil_interrupt event 推送
  🔧 POST /chat/resume 接口（approve / reject 两条分支）
  🔧 前端确认弹窗（展示 tool_args · 确认 / 取消按钮）
  演示场景："帮我查茅台股价，然后发邮件给老板"
  → Agent 暂停 → 前端弹窗 → 用户确认 → 继续执行

可观测性
  🔧 agent_traces 表建表（手写 migration SQL）
  🔧 observability/tracer.py（写入 thought_chain / tool_calls / token_usage / latency）
  验收：面试时能展示 Supabase Studio 里的执行日志

多 LLM Provider
  🔧 llm/factory.py 完整版（Ollama / ZhipuAI / DeepSeek / OpenAI）
  演示：现场切换 Provider，说明多模型兜底设计
```

---

**⚪ P2 · 面试后做 · 完整度提升**

```
长期记忆（用户画像）
  当前已实现：
    ✅ MemoryMiddleware.before_agent 加载画像 → state["memory_ctx"]
    ✅ MemoryMiddleware.aafter_agent 写回 AsyncPostgresStore
    ✅ interaction_count + 规则提炼 + dirty-flag 写回链路

  P2 继续演进：
    🔧 提炼策略增强（结构化约束、低置信度过滤）
    🔧 跨来源偏好冲突合并（规则提炼 vs LLM 提炼）
    ⚪ langmem create_manage_memory_tool（Agent 主动存取记忆）
    ⚪ langmem create_memory_store_manager（LLM 自动提炼偏好）

LLM Fallback 自动切换
  🔧 llm/factory.py Fallback 逻辑（触发条件：超时 / 限流 / 报错）

工具扩展
  🔧 tools/csv_analyze.py
  🔧 tools/weather.py
  ⚡ response_format 结构化输出

RAG 集成（见 § 1.3.1）
  ⚪ P2（目标态）：Semantic Memory（pgvector + RAG）
  ⚪ P2（目标态）：RAG chunk ephemeral 注入（MemoryMiddleware.wrap_model_call）

高级 Agent 模式
  🔧 Reflection 反思节点
  ⚡ Plan-and-Execute
  ⚡ LLMCompiler
  ⚡ Orchestrator Supervisor 多 Agent 协作

评估体系
  🔧 Agent 评估（LLM-as-Judge）
```

---

## 附录：.env 配置

```bash
# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=glm4
ZHIPU_API_KEY=
ZHIPU_MODEL=glm-4-flash
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LLM_FALLBACK_PROVIDER=zhipu

# 工具
TAVILY_API_KEY=

# 存储
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres

# 记忆
ENABLE_LONG_TERM_MEMORY=true
ENABLE_EPISODIC_MEMORY=true
ENABLE_SEMANTIC_MEMORY=false

# Agent 安全
MAX_ITERATIONS=10
MAX_EXECUTION_TIME=60
ENABLE_CHECKPOINT=true
ENABLE_HUMAN_IN_LOOP=false

# 可观测性
ENABLE_TRACE=true
```
