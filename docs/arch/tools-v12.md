# Tool 模块架构设计文档 v12

> **严谨声明**：本文档所有来自外部工程的内容均有一手来源标注，不包含推断或捏造。
>
> **检索来源**：
> - **OpenCode**（anomalyco/opencode）：DeepWiki，commit `d15c2ce3`，索引日期 2026-03-08。工具清单、权限系统、Tool.Context、ToolRegistry、执行生命周期均来自该来源。
> - **Claude Code**（Anthropic 官方）：`blog.thepete.net/claude-code-tools`，工具完整定义，Dec 2025 快照。
> - **LangChain v1.2.13 / LangGraph v1.1.3**：官方文档（2026-03）。
>
> 文档结构：
> - **第一层（框架无关）**：完整架构图 → 完整时序图 → 按模块节点详解
> - **第二层（LangChain 实现）**：API 对照 · 目录结构 · 核心代码
> - **参考架构（调研）**：OpenCode 工具系统设计 · Claude Code 对比 · 三个关键工具深度设计
>
---

## 第一层：框架无关的 Tool 架构（本项目设计）

> 以下为作者结合 OpenCode / Claude Code 实践后，针对 Multi-Tool AI Agent Portfolio 的设计决策。

---

### 1.1 完整架构图

```
━━━ 层一：定义层 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────────┐
  │  只读工具                 │  │  写操作工具                 │  │  编排工具                 │
  │  副作用：read             │  │  副作用：external_write     │  │  副作用：orchestration    │
  │                         │  │                          │  │                         │
  │  web_search             │  │  send_email (mock)       │  │  task_dispatch           │
  │  csv_analyze            │  │                          │  │                         │
  │  activate_skill         │  │  requires_hil = True     │  │  不直接执行任务             │
  │                         │  │  幂等 = False             │  │  产出：子 Agent 报告       │
  │  幂等 = True             │  │  幂等键生成函数：必填        │  │  幂等 = True              │
  │  HIL = 否               │  │  HIL = 是                 │  │  HIL = 否                │
  └─────────────────────────┘  └──────────────────────────┘  └─────────────────────────┘

  每个工具：@tool 函数体 + docstring 三要素 + ToolMeta 元数据

                                    │ list[ToolSpec]
                                    ▼

━━━ 层二：注册层 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  build_tool_registry(enable_hil)
    → list[Tool]      ──────────────────────────────────► create_agent
    → ToolManager（工具管理器）     ┐
    → PolicyEngine（权限引擎）      ┘  三者共享同一份 ToolMeta，数据来源一致

  enable_hil=False → send_email 不注册（测试环境天然隔离）

                                    │
                                    ▼

━━━ 层三：管理层 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌───────────────────────┐        ┌────────────────────────────────────┐
  │  ToolManager          │ ◄────► │  PolicyEngine（权限引擎）            │
  │  （工具管理器）         │        │                                    │
  │                       │        │  allow（允许）                      │
  │  · 元数据查询 · 路由   │        │  ask  （等待确认）─────────────────► HIL 中断
  │  · can_retry（可否重试）│        │  deny （拒绝）                      │
  │  · list_available     │        │                                    │
  │    （工具列表）         │        │  effect_class 分级决策              │
  └───────────────────────┘        │  审批记录持久化                      │
                                    └────────────────────────────────────┘

  ApprovalCoordinator（审批协调器）：
    ask → 存 checkpoint → SSE 发 hil_interrupt
       → 等待用户 approve（批准）/ reject（拒绝）
       → resume（恢复）时前置工具结果保留，不重跑

                                    │
                                    ▼

━━━ 层四：执行层 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────────────────┐
  │  路径 A · 并行       │  │  路径 B · 串行       │  │  路径 C · 委托             │
  │                     │  │                     │  │                           │
  │  asyncio.gather     │  │  LLM 分次决策        │  │  task_dispatch            │
  │  无依赖 · 同一 step  │  │  有依赖 · 多 step    │  │  跨 session · 子 Agent 委托│
  └──────────┬──────────┘  └──────────┬──────────┘  └──────────────┬────────────┘
             └─────────────┬───────────┘                            │
                           ▼                                        │
  写操作前：查幂等键（idempotency_key）                               │
    → 已执行（resume 场景）→ 跳过，防止重复副作用                       │
    → 未执行 → 执行工具 → 记录幂等键                                  │
                           ▼                                        │
  ToolMessage → state["messages"] → checkpointer 持久化              │
                                                                    │
━━━ 子 Agent 层（路径 C 专属）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

  ┌──────────────────────────────────────────────────────────────────┐
  │  子 session                                                       │
  │                                                                  │
  │  · 独立 Context Window（不共享父 Agent 消息历史）                  │
  │  · 独立 checkpointer thread（子 Agent 中间过程对父 Agent 不可见）   │
  │  · 工具集 = 父 Agent 工具集 − hard-coded deny（task_dispatch · send_email）
  │  · 运行完整 ReAct 循环 → 生成最终报告字符串                        │
  │                                                                  │
  │  循环防护：                                                       │
  │    task_budget（水平上限）= 单父 Agent 最多派生几个子 Agent         │
  │    level_limit（垂直上限）= session 树最大深度，默认 5              │
  └──────────────────────────────────────────────────────────────────┘
           │ 子 Agent 最终报告（字符串）
           ▼
  封装为 ToolMessage → 追加到父 Agent state["messages"]

━━━ 外部交互 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ①  list[Tool] → create_agent → 框架提取 Schema → 注入 Slot⑦（工具定义区，整个 session 不变）
  ②  ToolMessage → Slot⑧（历史区）· checkpointer 自动持久化
  ③  activate_skill → Skill 模块 · 返回 SKILL.md 操作手册（非数据）
  ④  InjectedState（注入状态）→ 只读 session_id / user_id，禁止写入 state
  ⑤  task_dispatch → 子 Agent 层 · 子 session 独立运行 · 报告回写父 Agent
```

**架构核心原则：**

```
① effect_class（副作用级别）是贯穿全架构的核心字段：
   定义层声明 → 注册层传递 → 管理层 PolicyEngine 驱动权限决策 → 执行层决定幂等保护策略

② 决策者分离：
   LLM 决定「调用哪个工具 + 串行/并行/委托」
   PolicyEngine 决定「是否允许执行」
   执行层决定「如何执行 + 是否跳过（幂等）」

③ 三件事归一：
   build_tool_registry 同时输出 list[Tool] + ToolManager + PolicyEngine
   三者共享同一份 ToolMeta，数据来源一致，不会出现不对齐

④ 路径 A/B/C 的本质区别：
   路径 A（并行）= 同 session · 同 step · 多工具同时执行
   路径 B（串行）= 同 session · 多 step · 工具顺序执行
   路径 C（委托）= 跨 session · 子 Agent 独立 Context Window · 父 Agent 只收最终报告
```

---

### 1.2 完整时序图

```
─── 阶段一：Agent 启动 ──────────────────────────────────────────────────────

  定义层：加载工具函数 + ToolMeta（工具元数据）
        ↓
  注册层：build_tool_registry(enable_hil)
        → 生成 list[Tool] + ToolManager（工具管理器）+ PolicyEngine（权限引擎）
        ↓
  create_agent(tools=[...])
        → 框架提取每个工具的 JSON Schema（参数模式）
        → 注入 Slot⑦（工具定义区，整个 session 静态不变）

─── 阶段二：turn N 开始 ─────────────────────────────────────────────────────

  LLM 读取 Slot⑦ 中工具 Schema
        ↓
  LLM 推理，输出 AIMessage(tool_calls=[工具调用列表])

─── 阶段三：管理层权限决策 ──────────────────────────────────────────────────

  对 LLM 输出的每个 tool_call 独立决策：
  PolicyEngine.decide(工具名, 副作用级别, allowed_decisions)

  ┌── 所有工具均为 allow → 直接进入阶段五执行
  │
  ├── 存在 ask 工具（混合批次处理策略）：
  │     当前策略：整批暂停（HIL 工具和只读工具一起等待）
  │       → checkpointer 存断点（含所有未执行工具的调用指令）
  │       → SSE 推送 hil_interrupt（列出需要确认的工具）
  │       → 用户确认后整批恢复执行
  │     ⚠️ 已知权衡：只读工具被连带暂停，延迟更高；
  │        好处：避免只读工具先跑完、写工具被拒时状态不一致
  │
  └── 存在 deny 工具 → 该工具直接返回错误 ToolMessage，其余工具继续决策

─── 阶段四：HIL 人工确认流程（ask 时触发）──────────────────────────────────

  HumanInTheLoopMiddleware 拦截工具调用
        ↓
  checkpointer 存断点（保存所有已完成工具的结果）
        ↓
  SSE 推送 hil_interrupt 事件：
    {
      interrupt_id（中断标识）: "uuid-xxx",
      tool_name（工具名）:  "send_email",
      tool_args（工具参数）: { to: "boss@...", subject: "...", body: "..." }
    }
        ↓
  前端弹出确认框，等待用户操作
        ↓
  ┌── 用户 approve（批准）
  │     → POST /chat/resume { action: "approve" }
  │     → checkpointer 恢复断点
  │     → 前置只读工具结果保留，不重跑
  │     → 进入阶段五执行写操作
  │
  └── 用户 reject（拒绝）
        → POST /chat/resume { action: "reject" }
        → 注入拒绝 ToolMessage："用户取消了 send_email 操作"
        → LLM 读到后重新规划（如回复「已取消」）

─── 阶段五：执行层调度 ──────────────────────────────────────────────────────

  LLM 输出的 tool_calls 数量和类型决定路径：

  路径 A（并行）：LLM 一次输出多个 tool_calls，工具间无数据依赖
    asyncio.gather([web_search, csv_analyze])
    → 两个工具同时执行
    → 两个 ToolMessage 同时追加到 state["messages"]
    → LLM 一次性读取两个结果，综合决策

  路径 B（串行）：LLM 分次输出 tool_calls，后步依赖前步结果
    step 1: tool_calls = [query_contracts]
    → ToolMessage(合同列表)
    → LLM 读取合同列表，决策下一步
    step 2: tool_calls = [send_email(to=合同列表[0].owner)]

  路径 A + B 混合：同一任务内先并行后串行
    step 1（并行）: [web_search, csv_analyze]
    step 2（串行）: [send_email(content=综合结果)]

  路径 C（子Agent委托）：LLM 输出 task_dispatch 调用，见下方阶段五 C

─── 阶段五 C：子 Agent 委托流程（路径 C 专属）────────────────────────────────

  触发条件：LLM 输出 tool_calls 包含 task_dispatch

  ① 循环防护检查（执行前）
      读取 state["task_depth"]（当前 session 树深度）
        ┌── depth >= level_limit（垂直上限，默认 5）→ 拒绝派生，返回错误 ToolMessage
        └── depth < level_limit → 继续

      读取 state["task_budget"]（当前父 Agent 已派生子数量）
        ┌── budget 已耗尽 → 拒绝派生，返回错误 ToolMessage
        └── budget 未耗尽 → 继续

  ② 单个子 Agent 派生
      task_dispatch(
        subagent_goal（子任务目标）: str,    ← LLM 生成的子任务描述
        subagent_tools（子Agent可用工具）: list[str] | None  ← None 表示使用默认子集
      )
        ↓
      创建子 session：
        child_thread_id = f"{parent_thread_id}:child:{uuid}"（独立检查点键）
        child_tools = 父 Agent 工具集 去掉 hard-coded deny（task_dispatch · send_email）
        child_agent  = create_agent(tools=child_tools, ...)
        ↓
      子 Agent 运行完整 ReAct 循环：
        · 独立 Context Window（不共享父 Agent 消息历史）
        · 有自己的 checkpointer thread（独立持久化）
        · 只返回最终报告字符串，中间过程对父 Agent 不可见

  ③ 多个子 Agent 并发（一次 step 多个 task_dispatch）
      LLM 输出：tool_calls = [task_dispatch(goal="A"), task_dispatch(goal="B")]
        ↓
      asyncio.gather([child_agent_A.run(), child_agent_B.run()])
        → 两个子 Agent 并发执行（各自独立 Context Window）
        → 两个报告分别封装为 ToolMessage
        → 追加到父 Agent state["messages"]
        → 父 Agent LLM 综合两份报告决策

  ④ 子 Agent 结果回写
      子 Agent 最终报告（字符串）
        ↓
      父 Agent 执行层封装为 ToolMessage：
        { tool_call_id, content: "子Agent报告：..." }
        ↓
      追加到父 Agent state["messages"]
        ↓
      checkpointer 持久化（父 Agent thread）
        ↓
      父 Agent LLM 读取报告，决策下一步

─── 阶段六：幂等保护（写操作专属）────────────────────────────────────────────

  写操作执行前（effect_class = external_write / destructive）：
    计算幂等键：idempotency_key_fn（幂等键生成函数）(args)
      示例：f"email:{args['to']}:{args['subject']}"
        ↓
    IdempotencyStore.check_and_mark(幂等键)
      ┌── True（已执行，resume 场景）
      │     → 跳过执行，返回上次结果
      │     → 防止 resume 后重复发送邮件
      └── False（未执行）
            → 执行工具函数
            → 记录幂等键

─── 阶段七：结果持久化 ──────────────────────────────────────────────────────

  工具函数返回字符串结果
        ↓
  框架封装为 ToolMessage（工具消息）
        ↓
  追加到 state["messages"]（消息历史）
        ↓
  checkpointer 自动写入 PostgreSQL（每个 ReAct step 后触发）
        ↓
  LLM 读取 ToolMessage，决策：继续调工具 / 输出最终答案
```

---

### 1.3 架构模块节点详解

#### 1.3.1 定义层：工具契约

**工具清单（来源：OpenCode 工具系统，DeepWiki 2026-03-08）：**

| 工具名 | 副作用（effect_class）| 需人工确认 | 幂等 | 可并行 | 备注 |
|--------|----------------------|-----------|------|--------|------|
| `Bash` | write（写文件系统/执行）| 是（ask）| 否 | 否 | OpenCode 默认 allow，外部目录 ask；标为 write 而非 destructive，避免 PolicyEngine deny 导致不可用 |
| `Edit` | write（写文件）| 是（ask）| 否 | 否 | FileTime 校验新鲜度；外部目录 ask |
| `Write` | write（写文件）| 是（ask）| 否 | 否 | 复用 edit 权限 key |
| `ApplyPatch` | write（写文件）| 是（ask）| 否 | 否 | patch 格式批量修改 |
| `Read` | read（只读）| 否 | 是 | 是 | 读取后记录 FileTime 时间戳 |
| `Grep` | read（只读）| 否 | 是 | 是 | 正则搜索文件内容 |
| `Glob` | read（只读）| 否 | 是 | 是 | 文件路径模式匹配 |
| `List` | read（只读）| 否 | 是 | 是 | 列出目录结构 |
| `CodeSearch` | read（只读）| 否 | 是 | 是 | 语义代码搜索 |
| `WebSearch` | read（只读）| 否 | 是 | 是 | 联网搜索 |
| `WebFetch` | read（只读）| 否 | 是 | 是 | 抓取指定 URL |
| `Skill` | read（只读）| 否 | 是 | 是 | 读取 skill 操作手册 |
| `TodoRead` | read（只读）| 否 | 是 | 是 | 读取当前 session todo 列表 |
| `LSP` | read（只读）| 否 | 是 | 是 | 实验性；需 `OPENCODE_EXPERIMENTAL_LSP_TOOL=true` |
| `StructuredOutput` | read（只读）| 否 | 是 | 是 | 伪工具；`format.type=json_schema` 时自动注入 |
| `TodoWrite` | write（session 内写）| 否 | 是 | 否 | 用新列表替换整个 todo（replace-all 语义，相同参数多次调用结果一致）；子 Agent hard-coded deny |
| `Question` | read（交互阻塞）| 否（非 HIL）| 是 | 否 | 工具本身功能是主动向用户提问，不走 PolicyEngine ask 流程；仅 desktop/CLI client 启用 |
| `Task` | orchestration（编排）| 否 | 否 | 是（并发）| 写 SubtaskPart → loop 检测 → spawn child session；子 Agent 内写操作不幂等，max_retries=0 |
| `PlanExit` | orchestration（编排）| 否 | 是 | 否 | 实验性；退出 plan 模式专用；Flag 开启 |

**ToolSpec 完整数据模型（`@tool` 不内置，需自行开发）：**

ToolSpec 由两部分组成：`@tool` 函数体上的 `docstring`（LLM 可见的自然语言契约）+ `ToolMeta`（运行时行为元数据，LLM 不可见）。

```
─── 必填契约（Specification）──────────────────────────────────────────────────

name（工具名）: str
  · 唯一标识，小写字母 + 下划线，最长 64 字符
  · LLM 调用时使用此名称

args_schema（参数模式）: JSON Schema
  · 由 @tool 从函数类型注解自动提取，开发者无需手写
  · LLM 按此 Schema 填写工具调用参数
  · 即框架的 parameters 字段，此处改名以对齐 ToolSpec 语义

result_schema（返回值模式）: str | None
  · ⚠️ 文档约束，非运行时强制——@tool 框架层不校验返回值
  · 用途：描述工具返回字符串的语义结构，供团队协作和 LLM 理解
  · 示例：web_search → "JSON 字符串，含 title/url/snippet 字段列表"
  · 工具全部返回 str 时，此字段主要用于团队文档规范

docstring（工具说明）: str
  · LLM 选工具的唯一依据，三要素：做什么 / 适用 / 不适用
  · 详见下方「docstring 三要素」

─── 安全字段（Security）──────────────────────────────────────────────────────

effect_class（副作用级别）: str
  · 贯穿全架构的核心字段，驱动 PolicyEngine 权限决策和执行层幂等保护
  ┌──────────────────┬────────────────────────────┬──────────────────┐
  │ 取值              │ 含义                        │ 默认权限          │
  ├──────────────────┼────────────────────────────┼──────────────────┤
  │ "read"           │ 只读，无外部影响               │ allow（允许）     │
  │ "write"          │ 写本地状态，session 内可撤销   │ allow（允许）     │
  │ "external_write" │ 触达外部系统，不可撤回          │ ask（需确认）     │
  │ "destructive"    │ 不可逆破坏性操作               │ deny（拒绝）      │
  └──────────────────┴────────────────────────────┴──────────────────┘

requires_hil（需人工确认）: bool
  · True = PolicyEngine 决策为 ask，触发 HIL 中断流程
  · 等价于 effect_class 为 external_write 或 destructive

allowed_decisions（允许的权限决策范围）: list[str]
  · PolicyEngine 对该工具的决策范围约束，防御性字段
  · 示例：web_search → ["allow"]（只读工具永远不应被 deny）
  ·       send_email → ["ask", "deny"]（外部写工具永远不应被直接 allow）
  · PolicyEngine 决策后做 assert 校验，超出范围则抛出配置错误
  · 作用：配置错误时快速失败，避免只读工具被误配为 deny 导致 Agent 失能

─── 可靠性字段（Reliability）─────────────────────────────────────────────────

idempotent（幂等）: bool
  · True  = 相同参数多次调用结果一致，允许重试
  ·         web_search ✓ → max_retries=2
  · False = 有副作用，禁止重试
  ·         send_email ✗ → max_retries=0（重发邮件造成困扰）

idempotency_key_fn（幂等键生成函数）: Callable | None
  · resume 后执行写操作前先计算幂等键，已执行则跳过
  · read 类工具置 None
  · send_email 示例：lambda args: f"email:{args['to']}:{args['subject']}"

max_retries（最大重试次数）: int
  · 仅 idempotent=True 时有效，False 时框架强制为 0

timeout_seconds（超时秒数）: int
  · 默认 30 秒

backoff（重试退避策略）: dict | None
  · 重试之间的等待策略，由执行层在重试前读取
  · None = 不重试（max_retries=0 时）
  · 结构：{ "strategy": "fixed"|"linear"|"exponential", "base_seconds": int }
  ·   "fixed"        → 每次重试等待 base_seconds 秒（适合外部 API 限流）
  ·   "linear"       → 第 n 次重试等待 n × base_seconds 秒
  ·   "exponential"  → 第 n 次重试等待 2^(n-1) × base_seconds 秒（适合不稳定网络）
  · web_search 示例：{ "strategy": "exponential", "base_seconds": 1 }
  · ⚠️ 仅 idempotent=True 的工具配置此字段有意义
  · ⚠️ LangChain ToolNode 不原生支持 backoff，需在工具函数体内或 ToolNode 外层
  ·    包装 tenacity / asyncio.sleep 自行实现，否则此字段仅作文档声明

─── 调度字段（Scheduling）────────────────────────────────────────────────────

can_parallelize（可并行）: bool
  · 声明该工具是否允许与其他工具并行执行
  · send_email / Bash / Edit / Write 等写操作工具应置 False
  · False 时有两种消费方式（须明确选择一种并在代码中实现）：
  ·   ① System Prompt 软约束（当前实现）：
  ·       在 System Prompt 中注入「工具 X 不得与其他工具并行」
  ·       LLM 理解后自行决策，无运行时强制保证
  ·   ② 执行层硬约束（需自行开发，推荐生产使用）：
  ·       ToolNode 前置钩子读取 ToolMeta.can_parallelize
  ·       若同一批次中任一工具 can_parallelize=False，则整批串行执行
  · ⚠️ 当前 LangChain ToolNode 不原生感知此字段，
  ·    硬约束需在 ToolNode 外层包装实现，否则字段仅作文档声明

concurrency_group（并发互斥组）: str | None
  · 同组内工具互斥，同一时刻最多执行一个
  · None = 不参与任何互斥组，可与任意工具并行
  · 示例："external_io"（所有触达外部系统的工具同组，避免并发发送多封邮件）
  · 与 OpenCode Skill 的 mutex_group 概念对应
  · ⚠️ 需执行层或 System Prompt 配合消费，否则仅为文档声明

─── 治理字段（Governance）────────────────────────────────────────────────────

permission_key（权限键）: str
  · 供 PolicyEngine 匹配规则的键，默认取 tool_name
  · 外部写工具可细化，如 "email.send"（便于按操作类型配置不同规则）

audit_tags（审计标签）: list[str]
  · TraceMiddleware 写日志时附加的标签列表，用于可观测性过滤和统计
  · 示例：web_search → ["network", "search", "readonly"]
  ·       send_email → ["network", "email", "external", "write"]
  · 用途：日志平台按标签统计工具调用分布、报错率、延迟分位数
```

> **未采纳字段说明：**
> - `depends_on`（静态依赖声明）：工具之间的依赖由任务上下文决定，不是工具固有属性。在 ToolMeta 声明 `depends_on` 会把动态任务依赖硬编码为静态工具依赖，导致 LLM 在不需要依赖的场景里也无法并行。依赖关系应由 LLM 在每次 ReAct 时动态决策。
> - `pattern_extractor`（模式提取函数）：服务于 glob 细粒度权限匹配（如 `send_email to *.esign.cn → allow`），需同步改造 PolicyEngine 决策逻辑。当前 effect_class 分级已满足需求，此字段作为扩展方向保留，暂不实现。

**docstring 三要素（LLM 选工具的唯一依据，每个工具必须包含）：**

```
① 做什么（what）：工具的核心功能，一句话概括
② 适用场景（when）：何时应该调用，含典型触发词
③ 不适用场景（when NOT）：最有价值，帮 LLM 主动排除干扰

示例（web_search）：
  "搜索互联网获取实时信息。
   适用：最新法规动态、实时合同签署量、近期行业新闻、E签宝产品更新。
   不适用：静态知识（历史事件/数学公式）、用户上传文件的内容分析。
   参数 query（搜索关键词）：5-10 词效果最佳，避免完整疑问句。"

示例（activate_skill）：
  "激活指定 Agent Skill，获取该场景的完整操作指南。
   适用：当前任务涉及专业领域（法律法规/合同分析/数据报告）且需要标准化流程时。
   不适用：通用问答；本 session 已激活过同一 skill（历史中已可见时）。
   参数 name（技能名称）：取值来自 System Prompt 中的 [可用 Skills] 列表。"
```

---

#### 1.3.2 注册层：唯一装配口

```
build_tool_registry(enable_hil（是否启用人工确认）)
  职责：聚合工具定义，初始化管理组件，环境切换

  输出三件事，共享同一份 ToolMeta（工具元数据）：
    ① list[Tool]         → 交给 create_agent，框架自动提取 Schema 注入 Slot⑦
    ② ToolManager（工具管理器）→ 管理层使用，元数据查询
    ③ PolicyEngine（权限引擎）→ 管理层使用，权限决策

  三件事共享同一份 ToolMeta：
    数据来源唯一，不会出现「注册了但没权限规则」或「有权限规则但没注册」的不对齐问题

  enable_hil 环境控制：
    enable_hil=False（测试环境）→ send_email 整个不注册
      LLM 的 Slot⑦ 里没有 send_email → LLM 不会调用 → 测试时天然安全
    enable_hil=True（生产环境）→ send_email 注册，HIL 流程完整启用

  与 OpenCode 对应：
    ToolRegistry（内置工具集合）+ resolveTools()（三路合并后过滤）
    本项目简化：只有内置工具，不涉及 MCP + 自定义工具三路合并
```

---

#### 1.3.3 管理层：三个独立组件

管理层职责分离为三个组件，遵循单一职责原则：

**ToolManager（工具管理器）：元数据查询，不做权限决策**

```
ToolManager
  持有：所有工具的 ToolMeta 字典

  方法：
    get_meta(工具名)       → 返回 ToolMeta | None
    list_available()       → 返回所有已注册工具名列表
    can_retry(工具名)      → 判断该工具是否可安全重试
                             条件：idempotent（幂等）=True 且 max_retries（最大重试）> 0

  设计原则：
    · 只查询元数据，不做权限决策
    · 权限判断统一交给 PolicyEngine（权限引擎）
    · 新增工具只需在 build_tool_registry 里注册 ToolMeta，ToolManager 自动感知

  与 OpenCode 对应：Agent.state 中的工具元数据存储
```

**PolicyEngine（权限引擎）：权限决策，来源 OpenCode PermissionNext**

```
PolicyEngine
  决策依据（优先级从高到低）：
    1. session（会话）级用户授权记录
       用户选「本 session 总是允许」后缓存，优先级最高
    2. effect_class（副作用级别）默认规则
       read          → allow（允许）
       write         → allow（允许）
       external_write → ask（需确认）
       destructive   → deny（拒绝）
       orchestration → allow（编排工具直接放行，子 Agent 内部有独立权限控制）
       未知值         → ask（保守兜底，不明来源的工具先要求确认）

  方法：
    decide(工具名, 副作用级别, allowed_decisions=None)
      → 返回 "allow" / "ask" / "deny"
      → 决策结果不在 allowed_decisions 范围内时抛出 ValueError（配置错误快速失败）
    grant_session(工具名)      → 记录「本 session 总是允许」
    hil_required(工具名, 副作用级别, allowed_decisions=None)
      → 返回 bool，供 HIL 中间件使用

  与 OpenCode 对应：
    PermissionNext + Ruleset 合并机制
    差异：OpenCode 用 glob 模式匹配（如 "read *.env" → ask）
          本项目用 effect_class 分级（更简洁，适合工具数量少的场景）
```

**ApprovalCoordinator（审批协调器）：HIL 中断与恢复**

```
ApprovalCoordinator
  触发条件：PolicyEngine.decide() 返回 "ask"

  中断流程：
    HumanInTheLoopMiddleware 拦截工具调用
      → checkpointer 存当前断点
         （包含：已执行工具的所有 ToolMessage，未执行的工具调用指令）
      → SSE 推送 hil_interrupt 事件给前端
         payload: { interrupt_id（中断ID）, tool_name（工具名）, tool_args（工具参数）}
      → Agent 挂起，等待用户响应

  恢复流程：
    用户 approve（批准）：
      POST /chat/resume { action: "approve" }
      → checkpointer 恢复断点
      → 前置只读工具结果保留，不重跑（checkpointer 已持久化）
      → 进入幂等检查 → 执行写操作

    用户 reject（拒绝）：
      POST /chat/resume { action: "reject" }
      → 注入拒绝 ToolMessage
      → LLM 读到后重新规划

  与 OpenCode 对应：
    session 挂起 + permission.updated SSE + permission.replied 等待机制
```

---

#### 1.3.4 执行层：调度与保护

**路径 A（并行）：LLM 判断工具间无依赖时选择**

```
触发条件：LLM 一次输出多个 tool_calls（工具调用列表）

执行方式：
  asyncio.gather([tool1(args1), tool2(args2)])
  → 多个工具同时执行
  → 多个 ToolMessage（工具消息）同时追加到 state["messages"]

适用场景：
  web_search 和 csv_analyze 互不依赖 → 并行，减少总 ReAct 轮次

System Prompt 约束（来源：Claude Code / OpenCode）：
  "若工具间无数据依赖，优先在同一 step 并行调用，减少总 ReAct 轮次"
```

**路径 B（串行）：LLM 判断工具间有依赖时选择**

```
触发条件：LLM 分次输出 tool_calls，每次一个

执行方式：
  step 1 → ToolMessage(合同列表) → LLM 读取 → 决策 step 2
  step 2 → 使用 step 1 的结果作为参数

适用场景：
  查询合同列表（第一步）→ 用列表中的邮箱发提醒邮件（第二步，依赖第一步）
```

**幂等保护（写操作专属）：**

```
触发条件：effect_class（副作用级别）= external_write 或 destructive

执行前：
  计算幂等键：idempotency_key_fn（幂等键生成函数）(调用参数)
    示例：send_email 幂等键 = f"email:{收件人}:{主题}"

  查询 IdempotencyStore（幂等键存储）：
    已执行（resume 场景）→ 跳过，返回上次结果
                           防止 resume 后重复发送邮件
    未执行 → 执行 → 记录幂等键

目的：
  HIL 流程中，用户 approve 后 resume，写操作只执行一次
  不会因为 checkpointer 恢复而重复执行
```

**ToolMessage（工具消息）持久化：**

```
工具函数返回字符串
  → 框架自动封装为 ToolMessage
  → 追加到 state["messages"]（框架自动，无需手写）
  → checkpointer（检查点）每个 ReAct step 后自动写入 PostgreSQL

结果：
  · 同 session 后续 LLM 调用可见所有历史 ToolMessage
  · HIL 断点后 resume，前置工具结果不丢失
  · activate_skill 加载的 SKILL.md 内容也在此持久化，
    同 session 后续 turn 无需重复激活
```

---

#### 1.3.5 子 Agent 调度（task_dispatch）

task_dispatch 是架构中唯一跨 session 边界的工具，与其他工具有根本性差异：其他工具执行后直接返回结果字符串，task_dispatch 执行后启动一个完整的子 Agent，子 Agent 跑完整 ReAct 循环后才把报告返回给父 Agent。

**ToolMeta 配置：**

```
task_dispatch ToolMeta：
  effect_class      = "orchestration"（编排类）
  allowed_decisions = ["allow"]（编排工具不需要 HIL，子 Agent 有自己的权限控制）
  requires_hil      = False
  idempotent        = False
  ⚠️  task_dispatch 不能标为幂等：
      task_dispatch 本身是无状态触发，但它启动的子 Agent 内部可能执行写操作。
      重试 task_dispatch 会重新启动子 Agent，子 Agent 内的写操作会再次执行，
      无法保证整体幂等。正确做法：子 Agent 内部的写工具自行配置 idempotency_key_fn。
  max_retries       = 0（不重试，子 Agent 失败由父 Agent LLM 自行决策是否重新派发）
  backoff           = None
  can_parallelize   = True（多个子 Agent 可并发）
  concurrency_group = None（不互斥）
  audit_tags        = ["orchestration", "subagent"]

PolicyEngine 默认规则：
  "orchestration" → allow（编排工具直接放行）
  ⚠️  此规则必须在 _DEFAULT_RULES 中显式声明，否则走兜底 "ask" 触发 HIL
```

**task_dispatch 工具函数契约（docstring）：**

```
"将子任务委托给专用子 Agent 独立执行，获取最终报告。
 适用：任务可分解为独立子任务，且每个子任务复杂度足以支撑完整 ReAct 循环；
       多个子任务之间无数据依赖，需要并发提速。
 不适用：简单单步操作（直接调对应工具即可）；
         子任务依赖当前对话的私有上下文（子 Agent 无法访问父 Agent 消息历史）。
 参数 subagent_goal（子任务目标）: 清晰描述子 Agent 需要完成的目标，含必要背景信息。
 参数 subagent_tools（可用工具列表）: 可选，None 表示使用默认子工具集。"
```

**执行机制：**

```
task_dispatch(subagent_goal, subagent_tools=None)
  │
  ├─ ① 循环防护检查
  │     读取 state["task_depth"]（当前深度）
  │       ≥ level_limit（默认 5）→ 拒绝，返回错误 ToolMessage
  │     读取 state["task_budget"]（已用配额）
  │       已耗尽 → 拒绝，返回错误 ToolMessage
  │
  ├─ ② 子 Agent 配置
  │     child_thread_id = f"{parent_thread_id}:child:{uuid}"
  │     
  │     # subagent_tools 校验（非 None 时）
  │     if subagent_tools is not None:
  │         parent_tool_names = {t.name for t in parent_tools}
  │         hard_deny = {"task_dispatch", "send_email"}  # hard-coded deny 列表
  │         invalid = (set(subagent_tools) - parent_tool_names) | (set(subagent_tools) & hard_deny)
  │         if invalid:
  │             return f"错误：subagent_tools 包含无效工具 {invalid}"
  │     
  │     child_tools = 父 Agent 注册工具集
  │                   减去 hard-coded deny 列表：
  │                     task_dispatch（防止递归嵌套超出 level_limit）
  │                     send_email   （子 Agent 不应直接触达外部）
  │                   若 subagent_tools 非 None，进一步过滤只保留指定工具
  │     child_state  = { task_depth: parent_depth + 1, task_budget: N }
  │
  ├─ ③ 子 Agent 运行
  │     child_agent = create_agent(tools=child_tools, ...)
  │     report = await child_agent.run(
  │         input=subagent_goal,
  │         config={"configurable": {"thread_id": child_thread_id}}
  │     )
  │     → 子 Agent 内部完整 ReAct 循环
  │     → 独立 Context Window（不共享父 Agent 消息历史）
  │     → 独立 checkpointer thread（子 Agent 中间过程对父 Agent 不可见）
  │
  └─ ④ 结果回写
        return report  ← 最终报告字符串
        → 框架封装为 ToolMessage
        → 追加到父 Agent state["messages"]
        → 父 Agent LLM 读取报告，决策下一步

关键设计差异（与普通工具对比）：
  普通工具  → 执行函数体 → 直接返回字符串结果
  task_dispatch → 启动子 Agent → 子 Agent 跑完整 ReAct → 最终报告作为"结果"
  
  普通工具的中间状态   → 不存在（单次函数调用）
  task_dispatch 的中间状态 → 子 Agent 全部 ToolMessage（存在 child_thread 里，父 Agent 不可见）
```

**并发场景（多个子 Agent 同时执行）：**

```
LLM 输出：
  tool_calls = [
    task_dispatch(goal="分析华东区合同数据"),
    task_dispatch(goal="分析华南区合同数据"),
  ]
        ↓
asyncio.gather([child_agent_A.run(), child_agent_B.run()])
  → 两个子 Agent 并发运行（各自独立 Context Window）
  → 两份报告分别封装为 ToolMessage
  → 父 Agent 一次性读取两份报告，综合输出结论

注：并发数受 task_budget 限制，超出配额的调用被拒绝并返回错误 ToolMessage
```

**循环防护设计：**

```
水平限制 task_budget（每个父 Agent 可派生子 Agent 总数上限）：
  存储在 state["task_budget"]
  每次成功 spawn 递减 1
  配额耗尽时 task_dispatch 直接返回错误，LLM 重新规划

垂直限制 level_limit（session 树最大深度，默认 5）：
  存储在 state["task_depth"]，每层 +1
  task_dispatch 执行前检查，depth ≥ limit 时拒绝
  子 Agent 的 task_depth = 父 Agent task_depth + 1

设计意图：
  水平限制防止同一父 Agent 无限扩散（广度失控）
  垂直限制防止无限递归委托（深度失控）
  两者联合形成子 Agent 树的规模上界
```

---

#### 1.3.6 模块间交互边界

```
Tool ↔ Prompt/Context 模块
  list[Tool] → create_agent → Schema 自动注入 Slot⑦（工具定义区）
  ToolMessage → Slot⑧（历史区）· checkpointer 自动持久化
  docstring 三要素 = Prompt Engineering 在工具层的体现
  开发者只需写好 docstring，框架自动完成 Schema 注入，无需手动干预

Tool ↔ Skill 模块
  activate_skill 是唯一桥接点
  返回「SKILL.md 操作手册」← 告诉 LLM 如何行动
  普通工具返回「查询数据」← 告诉 LLM 外部世界的状态
  两者均为 ToolMessage，但语义完全不同

Tool ↔ Memory 模块
  InjectedState（注入状态）只读 session_id / user_id（会话标识 / 用户标识）
  
  工具函数内禁止的操作：
    ❌ 直接访问 Long Memory Store（长期记忆存储）
    ❌ 写入 state["memory_ctx"]（记忆上下文）
    ❌ 读写 state["messages"] 以外的任何 state 字段
  
  原因：工具函数在 ToolNode 内部执行，此时 LangGraph 的状态图正在运行中。
        工具函数内直接修改 state 会绕过 add_messages reducer，
        导致 checkpointer 持久化的状态与内存状态不一致，产生幽灵消息或消息丢失。
  
  合法的记忆访问路径：
    ✅ MemoryMiddleware.before_call() 在工具执行前将相关记忆注入 System Prompt
    ✅ MemoryMiddleware.after_call() 在工具执行后读取结果并回写 Long Memory Store
    ✅ InjectedState 只读访问 session_id / user_id 用于日志标记

Tool ↔ HIL 模块
  管理层 PolicyEngine.hil_required → 生成 HumanInTheLoopMiddleware 的 interrupt_on 字典
  interrupt_on 动态生成：新增工具后无需手动维护
  HIL 断点由 checkpointer 持久化，resume 时前置工具不重跑
```

---

### 1.4 Task Orchestration v1（2026-03-27 增量）

> 目标：从“只会调工具”的 ReAct 执行，升级为“会规划、会重规划、会检索”的任务级控制闭环。

#### 1.4.1 新增模块

```
app/planner/orchestrator.py
  ├─ TaskPlanner
  │   · create_plan(session_id, user_goal, history)
  │   · 复杂任务（>=3 步）规则分解
  │   · 轻量关键词检索 retrieval_hits（长上下文证据）
  │
  ├─ Replanner
  │   · should_replan(plan, error)
  │   · apply(plan, failed_step_id, error) 失败后追加恢复步骤
  │
  └─ TaskRuntimeStore
      · set/get_plan
      · mark_next_step_running
      · mark_running_step_succeeded / failed
      · should_replan / apply_replan
      · mark_plan_completed
```

#### 1.4.2 PlanState 与步骤状态机

```
PlanState:
  plan_id, session_id, user_goal, complexity(simple|complex),
  steps[], retrieval_hits[], current_step_index, replan_count, max_replans

PlanStep.status:
  pending -> running -> succeeded
                 └-> failed -> (replanner) -> pending(恢复步骤)
```

关键约束：

1. `mark_running_step_succeeded/failed` 仅允许在存在 RUNNING 步骤时调用；无 RUNNING 时抛错（防止非法状态迁移）。
2. `replan_count` 达上限后不再重规划，直接走错误收敛。
3. `mark_plan_completed` 在 turn 完成时补齐剩余 pending，避免“计划悬空”。

#### 1.4.3 执行链路增量（_execute_agent）

```
try astream()
  ├─ tool_start  -> TaskRuntimeStore.mark_next_step_running()
  ├─ tool_result -> TaskRuntimeStore.mark_running_step_succeeded()
  └─ done        -> TaskRuntimeStore.mark_plan_completed()

except Exception as e
  ├─ should_replan(session, e) == True
  │    -> emit trace_event: replanner/triggered
  │    -> apply_replan(session, e)
  │    -> emit trace_event: replanner/plan_updated
  │    -> retry once（当前 max_replans=1）
  └─ else
       -> emit error（终止）
```

这使“工具失败”从“直接报错结束”升级为“可控自愈（重规划后再试）”。

#### 1.4.4 SSE / 前端可视化增量

后端新增 trace stage：

| stage | step | 含义 |
|------|------|------|
| `planner` | `plan_created` / `plan_completed` | 计划创建与收敛 |
| `retrieval` | `context_retrieved` | 长上下文证据检索 |
| `replanner` | `triggered` / `plan_updated` | 失败触发重规划与更新结果 |

`TraceBlockBuilder` 新增 block 类型：

- `planning`
- `retrieval`
- `replanning`

前端 `ExecutionTracePanel` + `TraceBlockCard` 已支持上述类型，用户可直接看到“规划→检索→执行→重规划”全链路，不再是黑盒。

#### 1.4.5 评测与验收（本轮新增测试）

1. 复杂任务分解：`tests/backend/unit/planner/test_task_orchestration.py`
2. 故障触发重规划：`tests/backend/unit/api/test_chunk_processing.py::TestExecuteAgentReplan`
3. 长上下文对比基线：`tests/backend/integration/planner/test_long_context_success_baseline.py`
4. trace 可视化块回归：`tests/backend/unit/observability/test_trace_block_builder.py::TestPlannerBlocks`
5. 计划持久化恢复：`tests/backend/unit/planner/test_task_runtime_persistence.py`

#### 1.4.6 Planner 策略模式（rule / llm / hybrid）

```
settings.task_planner_mode:
  rule    -> 仅规则分解（默认，最稳定）
  llm     -> 优先走 LLM 结构化规划；失败自动回退 rule
  hybrid  -> 与 llm 相同（保留为策略别名，便于灰度）
```

LLM 规划输出约束：

1. 必须输出 JSON：`{ complexity, steps[] }`
2. `steps[].depends_on` 只能引用前序步骤索引（防循环依赖）
3. 超过 `task_planner_max_steps` 的步骤会被截断
4. 任一校验失败（超时/非 JSON/空步骤）立即回退规则规划，不中断主链路

这保证了“智能化”与“稳定性”同时成立：能用 LLM 时更智能，不能用时不掉线。

#### 1.4.7 TaskRuntimeStore 持久化（Postgres Store）

```
TaskRuntimeStore
  内存层：
    _plans[session_id] 作为热缓存（低延迟）

  持久层（可选）：
    AsyncPostgresStore namespace=("task_plans",), key=session_id
    value=PlanState 序列化 JSON（含 steps/status/replan_count）
```

读写策略：

1. 读取：`aload_plan(session_id)` 先查内存，未命中再查 Postgres 并回填缓存。  
2. 写入：`aset_plan / amark_* / aapply_replan / amark_plan_completed` 每次状态变更后落盘。  
3. 降级：若 `get_store()` 不可用，自动进入 memory-only 模式（不阻断主链路）。

效果：

- 进程重启后可从 `task_plans` 恢复计划状态，不再丢失中间步骤；
- 与 HIL/幂等机制配合后，任务级状态具备“可恢复、可追踪、可自愈”闭环。

---

## 第二层：LangChain 实现映射

> 标注：✅ 框架内置 · 🔧 自行开发 · ⚡ 胶水代码
> 依据：LangChain v1.2.13 / LangGraph v1.1.3（2026-03）

### 2.1 四层架构 → LangChain API 对照

| 架构层 | 职责 | LangChain 实现 | 归属 |
|--------|------|---------------|------|
| 定义层 | 工具函数 + docstring + ToolMeta（含 effect_class / idempotency_key_fn）| `@tool` + 自定义 ToolMeta | 🔧 自行开发 |
| 注册层 | 聚合 + 环境切换 | `tools/registry.py` | 🔧 自行开发 |
| 注册层 | Schema 注入 Slot⑦ | `create_agent(tools=[...])` | ✅ 框架内置 |
| 管理层 · ToolManager | 元数据查询、路由 | `tools/manager.py` | 🔧 自行开发 |
| 管理层 · PolicyEngine | 权限决策（allow/ask/deny）| `tools/policy.py` | 🔧 自行开发 |
| 管理层 · ApprovalCoordinator | HIL 中断/恢复 | `HumanInTheLoopMiddleware` | ✅ 框架内置（配置）|
| 执行层（路径 A）| 并行调度 | `ToolNode` asyncio.gather | ✅ 框架内置 |
| 执行层（路径 B）| 串行调度 | LLM 分次 tool_calls | ✅ 全自动 |
| 执行层 | 幂等保护（写操作 resume）| `tools/idempotency.py` | 🔧 自行开发 |
| 执行层 | ToolMessage 封装 + 历史追加 | LangGraph 自动 | ✅ 全自动 |
| 执行层 | 持久化 | checkpointer 自动 | ✅ 全自动 |

---

### 2.2 目录结构

```
tools/
├── base.py            # 🔧 ToolMeta dataclass（含 effect_class / idempotency_key_fn）
├── registry.py        # 🔧 build_tool_registry → (tools, ToolManager, PolicyEngine)
├── manager.py         # 🔧 ToolManager（元数据查询，不做权限决策）
├── policy.py          # 🔧 PolicyEngine（allow / ask / deny 决策；含 orchestration 规则）
├── idempotency.py     # 🔧 幂等键检查（写操作 resume 防重复副作用）
├── readonly/
│   ├── web_search.py      # effect_class=read
│   ├── csv_analyze.py     # effect_class=read
│   └── skill_loader.py    # effect_class=read，activate_skill
├── write/
│   └── send_email.py      # effect_class=external_write，requires_hil=True
└── orchestration/
    └── task_dispatch.py   # effect_class=orchestration，启动子 Agent，max_retries=0
```

---

### 2.3 核心代码：管理层三组件

```python
# tools/manager.py — 🔧 自行开发
# 职责：元数据查询与路由，不做权限决策

class ToolManager:
    def __init__(self, tool_metas: dict[str, ToolMeta]):
        self._metas = tool_metas  # 工具名 → ToolMeta 映射

    def get_meta(self, tool_name: str) -> ToolMeta | None:
        """获取工具元数据"""
        return self._metas.get(tool_name)

    def list_available(self) -> list[str]:
        """列出所有已注册工具名"""
        return list(self._metas.keys())

    def can_retry(self, tool_name: str) -> bool:
        """判断工具是否可安全重试：幂等=True 且 最大重试次数>0"""
        meta = self._metas.get(tool_name)
        return bool(meta and meta.idempotent and meta.max_retries > 0)


# tools/policy.py — 🔧 自行开发
# 职责：权限决策（allow / ask / deny），来源：OpenCode PermissionNext 设计

class PolicyEngine:
    """
    权限决策引擎。从 ToolManager 中独立，遵循单一职责原则。
    决策依据（优先级从高到低）：
      1. session 级用户授权记录（用户选「总是允许」后持久化）
      2. effect_class（副作用级别）默认规则
    """

    # 副作用级别 → 默认权限映射
    _DEFAULT_RULES: dict[str, str] = {
        "read":           "allow",   # 只读 → 允许
        "write":          "allow",   # 本地写 → 允许
        "external_write": "ask",     # 外部写 → 需确认
        "destructive":    "deny",    # 破坏性 → 拒绝
        "orchestration":  "allow",   # 编排工具 → 直接放行（子 Agent 内部有独立权限控制）
    }

    def __init__(self, store=None):
        self._store = store  # 可选：Long Memory Store，用于持久化审批历史
        self._session_grants: dict[str, str] = {}  # 运行时 session 级授权缓存

    def decide(self, tool_name: str, effect_class: str, allowed_decisions: list[str] | None = None) -> str:
        """
        返回权限决策：'allow'（允许） / 'ask'（需确认） / 'deny'（拒绝）
        allowed_decisions：该工具允许的决策范围，不在范围内则抛出配置错误（快速失败）
        """
        # 优先：session 级用户授权
        if tool_name in self._session_grants:
            decision = self._session_grants[tool_name]
        else:
            # 兜底：effect_class 默认规则；未知 effect_class 走 "ask" 保守兜底
            decision = self._DEFAULT_RULES.get(effect_class, "ask")

        # allowed_decisions 防御性校验：配置错误时快速失败
        # 防止只读工具被误配为 deny 导致 Agent 失能，或外部写工具被直接 allow 绕过 HIL
        if allowed_decisions and decision not in allowed_decisions:
            raise ValueError(
                f"PolicyEngine: tool '{tool_name}' 决策结果 '{decision}' "
                f"不在 allowed_decisions {allowed_decisions} 范围内，请检查 ToolMeta 配置"
            )
        return decision

    def grant_session(self, tool_name: str) -> None:
        """用户选「本 session 总是允许」时调用"""
        self._session_grants[tool_name] = "allow"

    def hil_required(self, tool_name: str, effect_class: str, allowed_decisions: list[str] | None = None) -> bool:
        """判断是否需要人工确认，供 HumanInTheLoopMiddleware 的 interrupt_on 动态生成"""
        return self.decide(tool_name, effect_class, allowed_decisions) == "ask"


# tools/idempotency.py — 🔧 自行开发
# 职责：写操作幂等保护，resume 后不重复副作用

class IdempotencyStore:
    """
    轻量幂等键存储。写操作执行前检查，已执行则跳过。
    幂等键由 ToolMeta.idempotency_key_fn（幂等键生成函数）(args) 生成。
    """

    def __init__(self):
        self._executed: set[str] = set()  # 生产场景可换为 Redis / PostgreSQL

    def check_and_mark(self, key: str) -> bool:
        """
        返回 True  → 已执行，跳过（resume 防重复）
        返回 False → 未执行，继续执行并记录
        """
        if key in self._executed:
            return True
        self._executed.add(key)
        return False
```

---

### 2.4 核心代码：注册层 + 胶水代码

```python
# tools/registry.py — 🔧 自行开发

def build_tool_registry(
    enable_hil: bool = False,  # 是否启用人工确认（生产=True，测试=False）
) -> tuple[list, ToolManager, PolicyEngine]:
    """
    唯一装配口：输出 list[Tool] + ToolManager（工具管理器）+ PolicyEngine（权限引擎）
    三者共享同一份 ToolMeta（工具元数据），数据来源一致。
    """
    tool_defs = [
        (web_search, ToolMeta(
            effect_class="read",            # 副作用=只读
            allowed_decisions=["allow"],    # 只读工具只允许被决策为 allow
            idempotent=True,                # 幂等=是
            max_retries=2,                  # 最大重试=2
            backoff={"strategy": "exponential", "base_seconds": 1},  # 指数退避
            can_parallelize=True,           # 可并行=是
            concurrency_group=None,         # 不参与互斥组
            permission_key="web_search",    # 权限键
            audit_tags=["network", "search", "readonly"],  # 审计标签
        )),
        (csv_analyze, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            backoff={"strategy": "fixed", "base_seconds": 1},
            can_parallelize=True,
            concurrency_group=None,
            permission_key="csv_analyze",
            audit_tags=["compute", "local", "readonly"],
        )),
        (activate_skill, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=1,
            backoff=None,
            can_parallelize=True,
            concurrency_group=None,
            permission_key="activate_skill",
            audit_tags=["skill", "readonly"],
        )),
    ]
    if enable_hil:
        tool_defs.append((
            send_email,
            ToolMeta(
                effect_class="external_write",  # 副作用=外部写
                allowed_decisions=["ask", "deny"],  # 外部写工具不允许被直接 allow
                requires_hil=True,              # 需人工确认=是
                idempotent=False,               # 幂等=否
                max_retries=0,                  # 最大重试=0（禁止重试）
                backoff=None,                   # 不重试，不需要退避
                idempotency_key_fn=lambda a: f"email:{a.get('to')}:{a.get('subject')}",
                can_parallelize=False,          # 不可并行（外部写操作需串行确认）
                concurrency_group="external_io",  # 互斥组：所有外部 IO 操作
                permission_key="email.send",    # 细化权限键
                audit_tags=["network", "email", "external", "write"],
            )
        ))

    tools         = [t for t, _ in tool_defs]
    manager       = ToolManager({t.name: m for t, m in tool_defs})
    policy_engine = PolicyEngine()
    return tools, manager, policy_engine


# agent/langchain_engine.py — ⚡ 胶水代码

tools, tool_manager, policy_engine = build_tool_registry(enable_hil=ENABLE_HIL)

agent = create_agent(
    model=llm_factory(),
    tools=tools,
    system_prompt=build_system_prompt(),
    middleware=[
        HumanInTheLoopMiddleware(
            # interrupt_on（中断条件）由 PolicyEngine 动态生成
            # 新增工具后无需手动维护
            interrupt_on={
                name: policy_engine.hil_required(
                    name,
                    tool_manager.get_meta(name).effect_class
                )
                for name in tool_manager.list_available()
                if tool_manager.get_meta(name)
            }
        ),
        MemoryMiddleware(memory_manager),
        TraceMiddleware(),
    ],
    checkpointer=checkpointer,
    store=store,
)
```

---

### 2.5 @tool 规范

```python
# tools/readonly/web_search.py — 🔧 自行开发

from langchain_core.tools import tool

@tool
def web_search(query: str) -> str:
    """
    搜索互联网获取实时信息。
    适用：最新法规动态、实时合同签署量、近期行业新闻、E签宝产品更新。
    不适用：静态知识（历史事件/数学公式）、用户上传文件的内容分析。
    参数 query（搜索关键词）：5-10 词效果最佳，避免使用完整疑问句。
    """
    result = tavily_client.search(query)
    return result[:1200]  # 截断防止 ToolMessage 过长


# tools/readonly/skill_loader.py — activate_skill

@tool
def activate_skill(name: str) -> str:
    """
    激活指定 Agent Skill，获取该场景的完整操作指南。
    适用：当前任务涉及专业领域（法律法规/合同分析/数据报告）且需要标准化流程时。
    不适用：通用问答；本 session 已激活过同一 skill（历史中已可见时）。
    参数 name（技能名称）：取值来自 System Prompt 中的 [可用 Skills] 列表。
    """
    return skill_registry.read(name)
    # 返回 SKILL.md 完整内容 → ToolMessage → 操作手册（不是查询数据）
    # checkpointer 持久化，同 session 后续 turn 持续可见，无需重复激活
```

---

### 2.6 InjectedState（注入状态）规范

```python
from langgraph.prebuilt import InjectedState
from typing import Annotated

@tool
def csv_analyze(file_path: str, state: Annotated[dict, InjectedState]) -> str:
    """..."""
    # ✅ 只读元数据（对应 OpenCode Tool.Context 中的 sessionID / agent）
    session_id = state.get("configurable", {}).get("thread_id", "")  # 会话标识
    user_id    = state.get("configurable", {}).get("user_id", "")    # 用户标识

    # ❌ 禁止：state["messages"]（消息历史）/ state["memory_ctx"]（记忆上下文）
    # ❌ 禁止写入任何 state 字段（破坏 add_messages reducer 和 checkpointer 一致性）
```

---

### 2.7 自行开发 vs 框架内置

```
✅ 框架内置，零额外代码：
  @tool                       Schema 自动提取
  create_agent(tools=[...])   Schema 注入 Slot⑦
  ToolNode                    asyncio.gather 并行（路径 A）
  串行调度                     LLM 分次 tool_calls（路径 B，全自动）
  InjectedState               state 访问，不暴露给 LLM
  HumanInTheLoopMiddleware    HIL 拦截（对应 OpenCode ask 权限）
  checkpointer                ToolMessage 自动落盘

🔧 自行开发：
  tools/base.py               ToolMeta dataclass（工具元数据结构）
  tools/registry.py           build_tool_registry，输出三件事
  tools/manager.py            ToolManager（元数据查询）
  tools/policy.py             PolicyEngine（权限决策）
  tools/idempotency.py        IdempotencyStore（幂等保护）
  工具函数体                   docstring 三要素 + 返回截断
  System Prompt 约束文本       「无依赖优先并行」+ 防死循环规则
```

---

## 参考架构：OpenCode 工具系统设计

> 来源：DeepWiki anomalyco/opencode `d15c2ce3`（2026-03-08 索引）

### OpenCode 工具定义 API

OpenCode 所有工具通过 `Tool.define` 创建，位于 `packages/opencode/src/tool/tool.ts`：

```
两种创建形式：

① 直接定义（Direct definition）
   Tool.define({ id, description, parameters, execute })

② 异步工厂（Async factory，用于需要初始化的工具）
   async () => Tool.define({ ... })
   BashTool 使用此形式：启动时加载 tree-sitter Bash WASM 语法后再返回定义
   来源：packages/opencode/src/tool/bash.ts L33-52
```

**Tool.Context（每次 execute 调用都会注入）：**

| 字段 | 类型 | 用途 |
|------|------|------|
| `sessionID` | string | 所属 session |
| `messageID` | string | 父 assistant message ID |
| `callID` | string | 本次调用唯一 ID |
| `agent` | string | 当前活跃的 agent 名称 |
| `abort` | AbortSignal | 用户取消时触发 |
| `messages` | MessageV2.WithParts[] | 完整对话历史 |
| `metadata(input)` | fn | 推送流式中间输出（BashTool 用此实时推 stdout/stderr）|
| `ask(req)` | async fn | 触发权限检查（ask 行为时挂起 session，SSE 通知 UI）|

> `metadata` 和 `ask` 是 OpenCode 工具系统与 LangChain 最显著的设计差异：
> LangChain 的工具执行是黑盒（返回字符串即 ToolMessage），OpenCode 的工具可以流式推送中间状态，并在执行中途主动请求权限。

---

### OpenCode 内置工具清单（来源：DeepWiki 2026-03-08）

| 工具 | 导出名 | 源文件 | 权限 Key |
|------|--------|--------|----------|
| **Bash** | BashTool | tool/bash.ts | `bash`, `external_directory` |
| **Edit** | EditTool | tool/edit.ts | `edit`, `external_directory` |
| **Read** | ReadTool | tool/read.ts | `read`, `external_directory` |
| **Write** | WriteTool | tool/write.ts | `edit`（复用 edit 权限）|
| **Grep** | GrepTool | tool/grep.ts | `grep` |
| **Glob** | GlobTool | tool/glob.ts | `glob` |
| **List** | ListTool | tool/ls.ts | `list` |
| **WebFetch** | WebFetchTool | tool/webfetch.ts | `webfetch` |
| **WebSearch** | WebSearchTool | tool/websearch.ts | `websearch` |
| **CodeSearch** | CodeSearchTool | tool/codesearch.ts | `codesearch` |
| **Task** | TaskTool | tool/task.ts | `task` |
| **Skill** | SkillTool | tool/skill.ts | `skill` |
| **TodoWrite** | TodoWriteTool | tool/todo.ts | `todowrite` |
| **TodoRead** | （同模块）| tool/todo.ts | `todoread` |
| **Question** | QuestionTool | — | 仅 `app/cli/desktop` client 启用 |
| **ApplyPatch** | ApplyPatchTool | — | `apply_patch` |
| **PlanExit** | PlanExitTool | — | 实验性，Flag 开启 |
| **LSP** | LspTool | — | 实验性，`OPENCODE_EXPERIMENTAL_LSP_TOOL=true` |
| **StructuredOutput** | （伪工具）| — | 用户消息指定 `format.type=json_schema` 时自动注入 |

---

### OpenCode ToolRegistry 架构

```
ToolRegistry（packages/opencode/src/tool/registry.ts）
  · 内置工具的中央集合
  · 被两处消费：
    1. session/prompt.ts → resolveTools() → 组装每次 agent step 的工具集
    2. UI component library → 将工具名映射到渲染组件

resolveTools()（packages/opencode/src/session/prompt.ts L25-41）
  三个来源合并：
  ① ToolRegistry 内置工具
  ② MCP 工具（外部 MCP Server 提供）
  ③ 自定义工具（.opencode/tool/*.ts 目录扫描）
         ↓
  根据当前 agent 的 permission 配置过滤
         ↓
  最终工具集注入 LLM 上下文
```

---

### OpenCode 权限系统

> 来源：packages/opencode/src/config/config.ts L579-645，packages/opencode/src/permission/next.ts

**权限三态：**

| Action | 行为 |
|--------|------|
| `allow` | 立即执行，不提示用户 |
| `deny` | 立即抛出，工具调用失败 |
| `ask` | 挂起 session，发送 `permission.updated` SSE，等待 UI 响应 `permission.replied` |

**PermissionRule 格式（opencode.json）：**

```json
{
  "permission": {
    "bash": "allow",
    "edit": "ask",
    "read": {
      "*.env": "ask",
      "*.env.*": "ask",
      "*": "allow"
    },
    "external_directory": {
      "/home/user/safe-dir/*": "allow",
      "*": "ask"
    }
  }
}
```

模式按声明顺序评估，先匹配先生效，`*` 是兜底规则。

**默认权限（build agent，来源：packages/opencode/src/agent/agent.ts L51-96）：**

| 权限 Key | 默认 Action |
|----------|------------|
| `*`（所有工具）| `allow` |
| `doom_loop` | `ask` |
| `external_directory *` | `ask` |
| `external_directory` skill dirs | `allow` |
| `read *.env` / `*.env.*` | `ask` |
| `read *` | `allow` |
| `question` | `allow` |

> `plan` agent 将 `edit` 设为 `deny`，防止规划阶段意外写文件。
> 自定义 agent 继承全局默认并叠加自身 `permission` 字段。

**权限 Ruleset 合并（PermissionNext.merge）：**

```
多个规则集按优先级合并：
  全局默认 < 项目 opencode.json < agent 定义 < session 运行时授权
  后者覆盖前者，Session.setPermission 持久化用户的"总是允许"选择
```

---

### OpenCode 工具执行生命周期

> 来源：packages/opencode/src/session/prompt.ts L274-670

```
agent loop 每次迭代：
      ↓
LLM 返回 tool_calls
      ↓
plugin hook: tool.execute.before（packages/opencode/src/session/prompt.ts L405-463）
      ↓
Tool.execute(params, ctx) 调用
      ↓
  ┌── 工具内部调用 ctx.ask(req) ──→ 触发权限检查
  │      ├── allow → 继续执行
  │      ├── deny  → 抛出，返回错误 ToolResult
  │      └── ask   → 挂起 session
  │                  发送 permission.updated SSE
  │                  等待 permission.replied
  │                  用户确认 → 继续
  │                  用户拒绝 → 抛出
  └── 执行完毕
      ctx.metadata() 推送流式中间状态（长任务用）
      返回工具结果
      ↓
plugin hook: tool.execute.after
      ↓
ToolResult 写入 assistant message（SubtaskPart / ToolPart 等）
      ↓
SSE 推送给所有客户端（BusEvent）
      ↓
loop() 检测 SubtaskParts → 若存在则 spawn child session（Task 工具的实现方式）
```

**Task 工具的特殊实现（来源：packages/opencode/src/tool/task.ts）：**

```
TaskTool 不直接执行子 Agent。
它只向当前 assistant message 写入 SubtaskPart。
loop() 下一次迭代检测到 pending SubtaskParts → 用指定 subagent_type spawn child session。
子 session 完成后将最终报告写回父 session。

这是 OpenCode 多 Agent 调度的核心机制：
  父 Agent → TaskTool → SubtaskPart → loop 检测 → spawn child session
```

**EditTool 的 FileTime 机制（来源：packages/opencode/src/tool/read.ts）：**

```
ReadTool 读取文件成功后 → FileTime.read(sessionID, filePath) 记录时间戳
EditTool 写入前         → FileTime.assert(sessionID, filePath) 校验新鲜度

如果文件在 Read 后被外部修改，EditTool 拒绝写入（防止 Agent 覆盖用户改动）
这是 OpenCode 工具系统防止数据竞争的关键设计。
```

---

### OpenCode vs Claude Code 工具架构对比

| 维度 | OpenCode | Claude Code |
|------|----------|-------------|
| 工具定义 API | `Tool.define({ id, execute, ... })` | 内部实现，未公开 |
| 工具上下文 | `Tool.Context`（含 messages、metadata、ask）| 未公开 |
| 流式中间输出 | `ctx.metadata()` 推送到 SSE | 未公开 |
| 权限系统 | 三态（allow/deny/ask）+ glob 模式 + Ruleset 合并 | 三态 + glob（PascalCase 键）|
| 权限触发 | 工具内 `ctx.ask()` 主动触发 | Middleware 层拦截 |
| 子 Agent 实现 | `Task` 工具写 SubtaskPart，loop 检测后 spawn | `Task` 工具直接 launch |
| 自定义工具加载 | `.opencode/tool/*.ts` 目录扫描，运行时加载 | `.claude/commands/` 斜杠命令 |
| Plugin 钩子 | `tool.execute.before/after` | 未公开 |
| 文件竞争保护 | FileTime 机制（Read 记录时间戳，Edit 校验）| 未公开 |
| 实验性工具 | LspTool、PlanExitTool（Flag 控制）| EnterPlanMode、ExitPlanMode |

---

### 三个关键工具的深度设计

> 来源：DeepWiki anomalyco/opencode `d15c2ce3`（2026-03-08）+ GitHub Issues（2026-01~02）

#### TaskTool（子 Agent 调度）

**核心机制：间接执行，不直接 spawn**

```
TaskTool.execute() 本身不启动子 Agent。
它只向当前 assistant message 写入一个 SubtaskPart。

父 Agent loop() 本次迭代：
  LLM 输出 tool_calls = [TaskTool(subagent_type="explore", prompt="...")]
        ↓
  TaskTool.execute()
  → 向 assistant message 写入 SubtaskPart { type: "subtask", pending: true }
  → 立即返回（不阻塞当前 loop 迭代）
        ↓
  loop() 下一次迭代
  → 检测到 pending SubtaskParts
  → Session.create(parentID=当前 session, 使用 getSmallModel() 优先用小模型)
  → 启动 child session，执行子 Agent 任务
  → child session 完成 → 最终报告写回父 session 的 ToolPart
  → 父 Agent 继续推理

来源：packages/opencode/src/session/prompt.ts L351-526
      packages/opencode/src/tool/task.ts L72-101
```

**子 Agent 并发（一条消息多个 TaskTool 调用）：**

```
一条消息中放多个 TaskTool tool_calls → 多个子 Agent 并发启动
每个子 Agent 有独立 Context Window 和独立 session
父 Agent 只收到每个子 Agent 的最终报告（1条 ToolPart）
子 Agent 的全部中间过程不进父 Agent 历史

对比普通工具并行：
  普通工具并行  所有 ToolMessage 进入父 Agent state["messages"]（同 session）
  TaskTool 并发 子 Agent 完整历史隔离，父 Agent 只看报告（跨 session）
```

**权限继承问题（已知 Bug，来源：Issue #12566，2026-02-07）：**

```
child session 权限合并逻辑：
  PermissionNext.merge(taskAgent.permission, child_session.permission)
  → 父 Agent 的 permission 规则不传递给子 Agent
  → 父 Agent 配置了 "*": "allow"（无人值守），子 Agent 仍用默认规则
  → 子 Agent 遇到 ask 权限工具 → 永久阻塞等待确认

硬编码 deny（所有 child session 固定）：
  todowrite → deny（子 Agent 不能操作父 Agent 的 todo 列表）
  todoread  → deny
  task      → 可选 deny（防止 spawn 无限嵌套，垂直深度 level_limit 默认 5）
来源：packages/opencode/src/tool/task.ts L72-101
```

**循环防护（来源：PR #7756，2026-01-22）：**

```
task_budget   水平限制：单个 Agent 最多 spawn 几个子 Agent
level_limit   垂直限制：session 树最大深度（默认 5），getSessionDepth() 计算
              spawn 前校验，超出直接拒绝

已知 Bug（Issue #11324，2026-01-30）：
  Agent 可以用 TaskTool dispatch 任务给自身（自 dispatch 递归）
  即使配置 permission.task = deny 也无法阻止 → 状态：Open
```

---

#### TodoWriteTool / TodoReadTool（任务列表管理）

**数据模型（来源：packages/opencode/src/tool/todo.ts + Issue #1373）：**

```typescript
// TodoWriteTool 参数（Zod schema）
{
  todos: z.array(z.object({
    content:    z.string().min(1),  // 任务描述，祈使句（如 "Run tests"）
    status:     z.enum(["pending", "in_progress", "completed"]),
    activeForm: z.string().min(1),  // 执行中展示文字（如 "Running tests"）
  }))
}

// TodoReadTool 参数
parameters: z.object({})  // 无参数

// ⚠️ 已知问题（Issue #8184，2026-01-13）：
//    空 object 的 JSON Schema 缺少 "required": []
//    SGLang 等严格验证后端会返回 400
```

**执行机制：**

```
TodoWriteTool.execute(params, ctx)
  → 更新当前 session 的 in-memory todo 列表
  → 发布 todo.updated SSE 事件 → UI 实时展示任务进度条
  → 不持久化到数据库（session 级，重启丢失）

TodoReadTool.execute(params, ctx)
  → 读取当前 session 的 todo 列表，返回给 LLM

权限 key：todowrite / todoread（两个工具各自独立，可分别配置）
```

**使用约束：**

```
父 Agent  → todowrite / todoread 均可用
子 Agent  → 两者均被 hard-coded deny
            子 Agent 无法操作父 Agent 的 todo 列表
            即使在 agent.md 中配置 tools: { todowrite: allow } 也无效（已知 Bug）

设计意图：todo 列表是 session 维度的工作状态
          子 Agent 有独立 session，不应干预父 Agent 任务管理

常见错误（来源：Issue #1373）：
  ❌ { "todos": "[{\"content\": \"...\"}]" }   → string，Zod 拒绝
  ✅ { "todos": [{ "content": "...", "status": "pending", "activeForm": "..." }] }
```

---

#### BatchTool（批量工具调用）

**定位：解决部分 LLM 不擅长原生并行 tool_calls 的模型适配问题**

```
背景：
  标准协议下，LLM 通过 tool_calls 数组声明并行意图，框架自动并行执行。
  但部分 LLM（开源 / 非 Claude 模型）不擅长一次输出多个 tool_calls，
  倾向于每次只输出一个工具调用，强制串行执行。

BatchTool 的解法：
  LLM 只调用一次 BatchTool，在 parameters 中声明多个工具调用。
  BatchTool 内部 Promise.all 并行执行，汇总结果返回单条 ToolMessage。
  → 对不支持 multi tool_calls 的 LLM 提供了一条并行执行路径。
```

**参数结构（来源：packages/opencode/src/tool/batch.ts + Issue #9519，2026-01-19）：**

```typescript
{
  tool_calls: z.array(z.object({
    tool_name:  z.string(),   // 要调用的工具名
    parameters: z.any(),      // 对应工具的参数
  }))
}

// 容量限制（来源：batch.ts L36-37，PR #9275，v1.1.26）：
const toolCalls      = params.tool_calls.slice(0, 25)  // 最多 25 个
const discardedCalls = params.tool_calls.slice(25)     // 超出部分静默丢弃
// ⚠️ 超出的调用被静默丢弃，LLM 不收到报错，只收到前 25 个结果
```

**BatchTool vs 原生 multi tool_calls 对比：**

| 维度 | 原生 multi tool_calls | BatchTool |
|------|----------------------|-----------|
| 调度决策者 | LLM（tool_calls 数组）| LLM（parameters 内嵌）|
| 框架感知粒度 | 每个工具独立可见 | 只看到一次 BatchTool 调用 |
| 结果粒度 | 每个工具独立 ToolMessage | 所有工具合并为一条 |
| 失败隔离 | 单工具失败不影响其他 | 一个失败可能影响合并结果 |
| 模型要求 | 需支持 multi tool_calls | 任何支持单次调用的模型 |
| 超出上限 | 框架无硬编码上限 | 超出 25 个静默丢弃 |

**启用方式（实验性，默认关闭）：**

```
config: { experimental: { batchTool: true } }
```

---

#### 三个工具的关系

```
TodoWriteTool   管理当前 Agent 的任务清单（session 内部状态，SSE 实时更新 UI）
TaskTool        把任务委托给子 Agent（跨 session，垂直扩展）
BatchTool       让不擅长并行声明的 LLM 也能并行执行多工具（同 session，模型适配）

三者解决的问题层次不同，互不替代：
  TodoWrite = Agent 的工作日志，用户可见进度
  Task      = 任务分解与委托，多层 session 树
  Batch     = 并行执行能力的向下兼容，弱模型适配层
```

---
