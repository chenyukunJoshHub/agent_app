# 框架 API 速查手册 · Multi-Tool AI Agent

> 面向 LangChain / LangGraph 不熟悉的读者。
> 每个 API 说明：**是什么 → 做什么 → 为什么用它 → 我们怎么用**。

---

## 一、LangChain Core（`langchain-core`）

### `BaseChatModel`
- **是什么**：所有聊天模型的抽象基类
- **做什么**：定义统一接口（`invoke` / `ainvoke` / `stream`），屏蔽不同模型 API 的差异
- **为什么用**：写 `llm_factory()` 返回类型用它，保证上层代码不依赖具体模型
- **我们怎么用**：`def llm_factory() -> BaseChatModel`

### `HumanMessage` / `AIMessage` / `SystemMessage` / `ToolMessage`
- **是什么**：LangChain 定义的消息类型，对应对话里的不同角色
- **做什么**：统一表示对话历史，不同模型 API 格式不同，这层做了抹平
- **为什么用**：`AgentState["messages"]` 存的就是这些对象，框架自动处理序列化
- **我们怎么用**：`HumanMessage(content=user_input)` 作为 Agent 入参

### `AIMessage.content_blocks`
- **是什么**：`AIMessage` 的结构化内容列表
- **做什么**：把 LLM 的一次输出拆成多个 Block——文字是 `TextBlock`，工具调用是 `ToolCallBlock`
- **为什么用**：不用字符串解析 LLM 输出，直接读结构化数据，更可靠
- **我们怎么用**：`TraceMiddleware` 里遍历 `result.content_blocks`，按类型推 SSE 事件

---

## 二、LangChain Agents（`langchain.agents`）

### `create_agent`
- **是什么**：LangChain 1.0 的标准 Agent 构造函数（唯一引擎）
- **做什么**：把 LLM + 工具 + Middleware + checkpointer 组装成一个可运行的 ReAct Agent，底层跑在 LangGraph StateGraph 上
- **为什么用**：替代 deprecated 的 `create_react_agent`，是官方推荐的 1.0 标准 API
- **我们怎么用**：
  ```python
  agent = create_agent(
      model=llm_factory(),
      tools=tools,
      system_prompt=build_system_prompt(),
      middleware=[SummarizationMiddleware(), MemoryMiddleware(), TraceMiddleware()],
      checkpointer=checkpointer,
  )
  ```

### `agent.astream(..., version="v2")`
- **是什么**：Agent 的异步流式输出方法
- **做什么**：逐步产出 Agent 执行过程中的事件（消息、工具调用等），而不是等全部完成再返回
- **为什么用**：前端实时渲染需要流式数据，等全部完成再返回用户体验很差
- **我们怎么用**：`async for part in agent.astream(..., version="v2")` → 推 SSE 给前端

---

## 三、LangGraph Core（`langgraph`）

### `StateGraph`
- **是什么**：LangGraph 的图构造器
- **做什么**：让你定义节点（node）和边（edge），把多个处理步骤组装成有向图
- **为什么用**：`create_agent` 底层就跑在 StateGraph 上；Plan-and-Execute（P2）等复杂 Agent 需要直接用它
- **我们怎么用**：Phase 1 不直接用，P2 的 Plan-and-Execute 会用到

### `AgentState`（`TypedDict`）
- **是什么**：Agent 运行期间的状态容器，用 Python TypedDict 定义
- **做什么**：在整个 ReAct 循环里传递和共享数据，每一步都能读写
- **为什么用**：LangGraph 的核心设计——状态显式可见，方便调试和扩展
- **我们怎么用**：
  ```python
  class AgentState(TypedDict):
      messages:           Annotated[list, add_messages]
      session_id:         str
      user_id:            str
      memory_ctx:         MemoryContext   # MemoryMiddleware 写入
      tool_records:       list[dict]
      intermediate_state: dict
      error_log:          list[dict]
      token_usage:        dict
  ```

### `add_messages`
- **是什么**：`Annotated` 里用的 reducer 函数
- **做什么**：告诉 LangGraph 每次更新 `messages` 字段时是"追加"而不是"覆盖"
- **为什么用**：对话历史只能追加，不能整体替换，用这个声明式地表达这个语义
- **我们怎么用**：`messages: Annotated[list, add_messages]`

### `END`
- **是什么**：LangGraph 内置的终止节点标识符
- **做什么**：告诉图"这条边走到头了，结束执行"
- **为什么用**：`add_edge("save_memory", END)` 表示 save_memory 节点执行完就结束
- **我们怎么用**：P2 的 Plan-and-Execute 图里用到

---

## 四、LangGraph Prebuilt（`langgraph.prebuilt`）

### `ToolNode`
- **是什么**：LangGraph 内置的工具执行节点（v2 版本）
- **做什么**：接收 LLM 输出的工具调用列表，自动并行执行所有工具，收集结果返回给 Agent
- **为什么用**：不用手写工具调度逻辑，自动并行（Send API），比串行快
- **我们怎么用**：`create_agent` 内部自动使用，不需要手动初始化

### `InjectedState`
- **是什么**：工具函数参数的依赖注入标记
- **做什么**：让工具函数在运行时自动拿到当前 `AgentState`，不需要通过全局变量传递
- **为什么用**：工具需要读取用户偏好（如语言设置）时，能干净地从 state 获取
- **我们怎么用**：
  ```python
  async def web_search(
      query: str,
      state: Annotated[AgentState, InjectedState],  # 框架自动注入
  ) -> str: ...
  ```

### `InjectedStore`
- **是什么**：工具函数参数的 Store 依赖注入标记
- **做什么**：让工具函数在运行时自动拿到 `PostgresStore` 实例
- **为什么用**：工具需要读写长期记忆时，能直接访问 Store
- **我们怎么用**：P1 接入 langmem 工具时会用到

---

## 五、LangGraph Checkpoint（`langgraph-checkpoint`）

### `AsyncPostgresSaver`
- **是什么**：LangGraph 官方的 PostgreSQL 异步 Checkpoint 实现
- **做什么**：在每一步 Agent 执行后，自动把完整的 `AgentState` 存入 PostgreSQL；下次用同一个 `thread_id` 请求时自动恢复
- **为什么用**：这就是"短期记忆"——消息历史、工具调用记录全部自动持久化，不需要手写 Redis
- **我们怎么用**：
  ```python
  checkpointer = AsyncPostgresSaver(pool)
  await checkpointer.setup()  # 自动建 checkpoint 表
  # 传给 create_agent，之后全自动
  agent = create_agent(..., checkpointer=checkpointer)
  # 用 thread_id 隔离不同会话
  agent.astream(..., config={"configurable": {"thread_id": session_id}})
  ```

### `checkpointer.setup()`
- **是什么**：Checkpoint 初始化方法
- **做什么**：在数据库里自动建 `langgraph_checkpoints` 等表
- **为什么用**：不需要手写建表 SQL，框架自己维护 schema
- **我们怎么用**：服务启动时调用一次

---

## 六、LangGraph Store（`langgraph.store`）

### `PostgresStore`
- **是什么**：LangGraph 官方的 PostgreSQL Store 实现，实现了 `BaseStore` 接口
- **做什么**：提供 key-value 存储，支持 namespace 隔离，用于跨会话的长期记忆
- **为什么用**：这就是"长期记忆"的存储层，`("episodic", user_id)` 这样的 namespace 设计天然支持多类型记忆扩展
- **我们怎么用**：
  ```python
  store = PostgresStore(pool)
  await store.setup()  # 自动建 store 表
  # 写
  await store.aput(namespace=("episodic", user_id), key="profile", value={...})
  # 读
  item = await store.aget(namespace=("episodic", user_id), key="profile")
  ```

### `store.setup()`
- **是什么**：Store 初始化方法
- **做什么**：自动建 `langgraph_store` 表
- **为什么用**：不需要手写建表 SQL
- **我们怎么用**：服务启动时和 `checkpointer.setup()` 一起调用

### `BaseStore`
- **是什么**：LangGraph Store 的抽象基类
- **做什么**：定义统一接口（`aget` / `aput` / `adelete` / `asearch`）
- **为什么用**：`MemoryManager` 依赖注入时用这个类型，不绑定具体实现，方便测试和替换
- **我们怎么用**：`def __init__(self, store: BaseStore)`

---

## 七、LangChain Middleware（`langchain.agents.middleware`）

> ✅ 官方包，`pip install langchain`，LangChain 1.0 原生提供
> ❌ 旧版本文档曾误标为 `deepagents` 来源，已于 v3.1 修正

### `AgentMiddleware`（`langchain.agents.middleware`）
- **是什么**：Middleware 协议基类，继承后实现各钩子
- **做什么**：在 Agent 执行生命周期的 6 个节点插入自定义逻辑
- **为什么用**：`create_agent` 的标准扩展点，无需修改框架代码
- **我们怎么用**：`MemoryMiddleware` 和 `TraceMiddleware` 都继承它

### `SummarizationMiddleware`（`langchain.agents.middleware`）
- **是什么**：官方内置的消息压缩 Middleware
- **做什么**：监控 Token 用量，超过阈值时自动调用 LLM 压缩历史消息为摘要
- **为什么用**：零代码处理 Token 超限，直接配置即用
- **我们怎么用**：
  ```python
  from langchain.agents.middleware import SummarizationMiddleware
  middleware=[
      SummarizationMiddleware(llm=llm_factory()),  # 🔴 P0：配置即用
      MemoryMiddleware(...),
      TraceMiddleware(...),
  ]
  ```

### `HumanInTheLoopMiddleware`（`langchain.agents.middleware`）
- **是什么**：官方内置的 HIL 拦截 Middleware
- **做什么**：当 Agent 准备调用指定工具时暂停，等待用户确认
- **为什么用**：不可逆操作（如发邮件、删文件）需要人工确认
- **我们怎么用**：
  ```python
  # 🟡 P1：E签宝场景——发送合同审批通知前需要人工确认
  HumanInTheLoopMiddleware(interrupt_on={"send_email": True})
  ```

### 六个钩子（已验证完整列表）

> 钩子分两类，签名完全不同，混淆会导致注入逻辑失效

```
┌─ Node-style（state 操作）────────────────────────────────────────────┐
│  签名：async def hook(self, state: AgentState, runtime: Runtime)      │
│        -> dict[str, Any] | None                                       │
│                                                                        │
│  before_agent    turn 开始，触发一次    加载长期记忆 → state           │
│  before_model    每次 LLM 调用前        （当前未使用）                  │
│  after_model     每次 LLM 调用后        写 agent_traces 日志           │
│  after_agent     turn 结束，触发一次    写回长期记忆 ← state            │
└───────────────────────────────────────────────────────────────────────┘

┌─ Wrap-style（请求/响应包裹）──────────────────────────────────────────┐
│  签名：def hook(self, request: ModelRequest,                           │
│                 handler: Callable[[ModelRequest], ModelResponse])       │
│        -> ModelResponse                                                 │
│  ⚠️ 同步，不操作 state，通过 request.override() 修改请求               │
│                                                                        │
│  wrap_model_call  每次 LLM 调用包裹     ephemeral 注入用户画像          │
│  wrap_tool_call   每次工具调用包裹      （当前未使用）                  │
└───────────────────────────────────────────────────────────────────────┘
```

### `ModelRequest` / `ModelResponse`（Wrap-style 专用）
- **是什么**：`wrap_model_call` 的请求/响应对象，不是 `AgentState`
- **`request.system_message`**：当前 System Prompt（`SystemMessage` 对象）
- **`request.system_message.content_blocks`**：System Prompt 的结构化内容块列表
- **`request.override(system_message=...)`**：创建修改后的请求副本（不改原对象）
- **我们怎么用**：
  ```python
  # 在现有 System Prompt 末尾追加用户画像（E签宝：合同管理员角色说明）
  existing = list(request.system_message.content_blocks)
  existing.append({"type": "text", "text": "[用户画像] domain: legal-tech, role: 合同管理员"})
  return handler(request.override(
      system_message=SystemMessage(content=existing)
  ))
  ```

---

## 八、LangChain Chat Models

### `ChatOllama`（`langchain-ollama`）
- **是什么**：连接本地 Ollama 服务的 ChatModel 实现
- **做什么**：把 LangChain 的标准消息格式转成 Ollama API 请求，返回标准 `AIMessage`
- **为什么用**：本地开发不需要付费 API，glm4 跑在 Ollama 上
- **我们怎么用**：`LLM_PROVIDER=ollama` 时 `llm_factory()` 返回它

### `ChatZhipuAI`（`langchain-community`）
- **是什么**：连接智谱 AI（GLM 系列）的 ChatModel 实现
- **做什么**：把标准消息转成智谱 API 请求
- **为什么用**：上线后切换到 `glm-4-flash`（免费额度大）
- **我们怎么用**：`LLM_PROVIDER=zhipu` 时 `llm_factory()` 返回它

### `ChatOpenAI`（`langchain-openai`）
- **是什么**：连接 OpenAI 兼容接口的 ChatModel 实现
- **做什么**：支持 OpenAI、DeepSeek、任何 OpenAI 格式兼容的 API
- **为什么用**：DeepSeek 兼容 OpenAI 格式，用同一个类通过 `base_url` 切换
- **我们怎么用**：`LLM_PROVIDER=deepseek` 或 `openai` 时返回它

---

## 九、asyncpg

### `asyncpg.create_pool`
- **是什么**：Python 异步 PostgreSQL 连接池
- **做什么**：维护一批数据库连接，复用连接避免每次请求都重新握手，支持并发
- **为什么用**：`AsyncPostgresSaver` 和 `PostgresStore` 都需要传入连接池实例
- **我们怎么用**：
  ```python
  pool = await asyncpg.create_pool(settings.SUPABASE_DB_URL)
  checkpointer = AsyncPostgresSaver(pool)
  store = PostgresStore(pool)
  ```

---

## 十、langmem（P1/P2，`pip install langmem`）

### `create_manage_memory_tool`
- **是什么**：langmem 提供的工具工厂函数
- **做什么**：创建一个让 Agent 主动保存记忆的工具——Agent 自己决定"这件事值得记住"，调用工具写入 Store
- **为什么用**：被动提炼偏好不如 Agent 主动记忆准确
- **我们怎么用**：P1 接入，加入 `tools` 列表

### `create_search_memory_tool`
- **是什么**：langmem 提供的记忆检索工具工厂函数
- **做什么**：让 Agent 主动搜索历史记忆
- **为什么用**：用户提到历史事项时 Agent 能主动检索，而不是被动等注入
- **我们怎么用**：P1 接入，加入 `tools` 列表

### `create_memory_store_manager`
- **是什么**：langmem 的后台记忆管理器
- **做什么**：在对话结束后自动分析对话内容，提炼用户偏好写入 Store，无需手写提炼逻辑
- **为什么用**：替代 Phase 1 的简单规则提炼，更智能
- **我们怎么用**：P2 接入，替代 `save_episodic` 里的手写逻辑

---

## 十一、概念速查

| 概念 | 一句话解释 |
|------|-----------|
| ReAct 循环 | LLM 交替做"推理（Thought）→ 调工具（Action）→ 看结果（Observation）"，直到任务完成 |
| Checkpoint | 每步执行后把完整状态存数据库，服务重启或断线后能恢复 |
| thread_id | 隔离不同会话的 checkpoint，等同于我们的 session_id |
| namespace | PostgresStore 的 key 前缀，`("episodic", user_id)` 表示某用户的 episodic 记忆 |
| Middleware | 洋葱模型的拦截器，在 Agent 执行的关键节点插入自定义逻辑 |
| content_blocks | AIMessage 的结构化内容，比字符串解析更可靠 |
| InjectedState | 工具函数的依赖注入，运行时由框架自动传入 AgentState |
| Working Memory | 每次 LLM 调用前动态组装的 Context Window，不是持久存储 |
| Short-term Memory | 会话内记忆，AsyncPostgresSaver 自动管理 |
| Long-term Memory | 跨会话记忆，PostgresStore 存储，自行读写 |
