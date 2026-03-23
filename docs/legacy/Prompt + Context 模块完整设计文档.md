# Prompt + Context 模块完整设计文档V20

> 双层架构：
>
> - **第一层（框架无关）**：Context Window 的核心问题、10大子模块职责、Token 预算策略、组装时序（含 Memory 读写节点 + Skill 加载节点）、数据结构定义
> - **第二层（LangChain 实现）**：子模块 → API 映射、关键代码、自行开发 vs 框架内置

---

## 第一层：框架无关的 Prompt + Context 架构

### 1.1 核心问题：LLM 只有一个输入口

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM 的唯一输入                            │
│                                                             │
│   [ Context Window ]  ← 有上限，例如 8k / 32k / 128k Token  │
│                                                             │
│   你能控制的只有：往这个窗口里塞什么、怎么塞、塞多少         │
└─────────────────────────────────────────────────────────────┘
```

Prompt + Context 模块要解决的就是这个问题：
**在有限的 Token 预算里，以最优的方式组装 LLM 的每次输入。**

### 1.2 十大子模块与 Context Window 分区

```
┌───────────────────────────────────────────────────────────────────────┐
│                       Prompt + Context 模块                            │
│                                                                       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ ① System Prompt │  │  ② Token Budget  │  │  ③ Agent Skill       │  │
│  │    Builder      │  │    Manager       │  │    Manager           │  │
│  │ 静态+Skill元数据 │  │  预算分配 + 监控  │  │ 注册元数据+@tool激活  │  │
│  └────────┬────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                    │                        │               │
│  ┌────────▼────────────────────▼────────────────────────▼──────────┐   │
│  │                     Context Assembler（组装器）                   │   │
│  │                                                                  │   │
│  │  10 个 Slot 按优先级填入 Context Window（优先级从低→高）：          │   │
│  │  ┌────────────────────────────────────────────────────────────┐ │   │
│  │  │ Slot ①  System Prompt + Skill Registry 元数据 + Few-shot   │ │   │
│  │  │ Slot ②  活跃技能内容（Active Skill，经 ToolMessage 进历史） │ │   │
│  │  │ Slot ③  动态 Few-shot（P1）                                 │ │   │
│  │  │ Slot ④  RAG 背景知识（P2）                                  │ │   │
│  │  │ Slot ⑤  用户画像（Episodic Memory）                         │ │   │
│  │  │ Slot ⑥  程序性记忆（Procedural，P2）                        │ │   │
│  │  │ Slot ⑦  工具定义 Schema（框架自动注入）                      │ │   │
│  │  │ Slot ⑧  会话历史（含推理轨迹 + Active Skill ToolMessage）   │ │   │
│  │  │ Slot ⑨  输出格式规范                                        │ │   │
│  │  │ Slot ⑩  本轮用户输入                                        │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│           │                                                              │
│  ┌────────▼──────────────────────────────────────────────────────┐      │
│  │                     六大处理器                                  │      │
│  │                                                                │      │
│  │  ④ Token Counter  ⑤ Compressor  ⑥ Memory Injector              │      │
│  │  Token 计数        消息压缩       Episodic + Procedural          │      │
│  │                                                                │      │
│  │  ⑦ Tool Schema Formatter   ⑧ RAG Retriever（P2）   ⑨ Few-shot Retriever（P1）│  │
│  │  Schema 生成+注入            语义检索背景知识         语义检索示例对            │  │
│  └────────────────────────────────────────────────────────────────┘      │
└───────────────────────────────────────────────────────────────────────┘

来源分类（决定 Slot 内容从哪里来）：
  静态内容      ：System Prompt 模板、Skill Registry 元数据、静态 Few-shot → 代码中硬编码
  Agent Skills  ：activate_skill @tool 调用 → ToolMessage → Slot ⑧ 历史区  → Skill 文件系统（@tool 读取，持久化）
  短期记忆      ：会话历史 + ReAct 推理轨迹（Slot ⑧）                      → Short Memory（DB → RAM）
  长期记忆      ：Episodic（Slot ⑤）+ Procedural（Slot ⑥）                → Long Memory（DB → RAM）
  动态检索      ：RAG chunk（Slot ④）+ 动态 Few-shot（Slot ③）             → 向量存储（DB → RAM，P2）
  框架自动注入  ：工具 Schema（Slot ⑦）                                    → create_agent(tools=[...]) 自动

补充说明：
  推理轨迹（Thought/Observation）→ Slot ⑧ 的 AIMessage / ToolMessage 内容，
                                   ReAct 每步自动追加到 state["messages"]，随 Short Memory 持久化
  内部操作 Prompt               → 不占用 Context Window Slot，各子系统独立持有（见 §1.3 ⑩）
```

### 1.3 十大子模块职责（框架无关定义）

#### ① System Prompt Builder

**职责**：把"静态模板"、"Skill Registry 元数据"、"静态 Few-shot"和"动态画像"拼成 LLM 每次调用的指令基础。

```
┌──────────────────────────────────────────────────────────────────┐
│                    System Prompt 结构（Slot ①）                   │
│                                                                  │
│  [1] 角色定义（Role）                           静态              │
│      "你是一个专业的多工具 AI 助手..."                             │
│                                                                  │
│  [2] 能力边界（Capabilities）                   静态              │
│      "你能做：网页搜索、CSV分析、合同状态查询"                     │
│      "你不能做：执行危险操作、泄露隐私数据"                        │
│                                                                  │
│  [3] 行为约束（Constraints）                    静态              │
│      "调用工具前必须先推理说明原因"                                │
│      "最终答案用 Markdown 格式"                                   │
│                                                                  │
│  [4] Skill Registry 元数据（P1）                静态，初始化注入   │
│      告诉 LLM 当前有哪些 skill 可以激活，以及激活条件              │
│      不包含 skill 详细内容（详细内容在 Slot ②，按需动态加载）      │
│      示例：                                                       │
│        可用 Skills：                                              │
│        · contract-analyzer：分析合同条款风险，适用合同文本理解     │
│        · csv-reporter：生成数据统计报告，适用 CSV 数据分析         │
│        · legal-search：法律法规查询专家，适用合规问题              │
│        激活方式：当任务匹配 skill 描述时，调用 activate_skill()    │
│                                                                  │
│  [5] 静态 Few-shot 示例（P0/P1）               静态               │
│      2~3 个精心设计的示例对，告诉 LLM 如何推理和调用工具           │
│      E签宝场景示例：                                              │
│        用户：查合同123的签署状态                                   │
│        思考：需要工具 contract_status 查询指定合同 ID              │
│        操作：[contract_status(id="123")]                          │
│        结果：已完成签署，3方均已签字                               │
│                                                                  │
│  [6] 用户画像注入（Episodic）                   动态，Ephemeral   │
│      "[用户画像] domain: legal-tech, language: zh"                │
│      每次 LLM 调用前注入，不写入对话历史                           │
│                                                                  │
│  [7] 输出格式规范（Output Format）              静态/动态          │
└──────────────────────────────────────────────────────────────────┘
```

**关键设计**：

- Skill Registry 元数据（[4]）常驻 Slot ①，让 LLM 始终知道有哪些 skill 可用（约 50 Token）
- Skill 详细内容（Slot ②）按需动态加载，不激活时不占预算
- 用户画像（[6]）是 Ephemeral，每次 LLM 调用前重新注入，不写入对话历史
- 动态 Few-shot（Slot ③）是单独 Slot，通过语义检索获取，与静态 Few-shot 区分

#### ② Token Budget Manager

**职责**：管理 Context Window 的 Token 预算，决定每个 Slot 能用多少。

```
模型规格（以 Claude Sonnet 4.6 为例）
  Context Window（最大输入+输出）：200,000 Token
  Max Output Token：              8,192 Token（标准）/ 16,384 Token（扩展模式）
  ⚠️ 注意：200K 上限是模型硬上限，实际 Agent 应设置更小的工作预算

推荐 Agent 工作预算：32,768 Token / turn（兼顾成本与响应速度）
│
├── 预留给 LLM 输出 → 8,192 Token（ReAct 推理轨迹 + 最终答案，标准模式）
│
└── 可用于输入：24,576 Token
    │
    ├── Slot ①  System Prompt + Skill Registry 元数据 + 静态 Few-shot
    │           2,000 Token   P0（含 ~100 Token 的 skill 元数据 + 2~3 示例对）
    ├── Slot ②  活跃技能内容（Active Skill）
    │           1,500 Token   P1，默认 0（按需激活，同一时刻最多一个 skill）
    ├── Slot ③  动态 Few-shot
    │           800 Token    P1，默认 0
    ├── Slot ④  RAG 背景知识
    │           2,000 Token   P2，默认 0
    ├── Slot ⑤  用户画像（Episodic）
    │           500 Token    P0，来自 Long Memory
    ├── Slot ⑥  程序性记忆（Procedural）
    │           400 Token    P2，来自 Long Memory，默认 0
    ├── Slot ⑦  工具 Schema
    │           1,200 Token   P0，框架自动注入（工具越多越大）
    ├── Slot ⑧  会话历史（含推理轨迹）
    │           弹性           = 可用预算 - 所有已启用固定 Slot
    └── Slot ⑩  用户输入        实时，最高优先级保留

P0 固定占用：Slot① 2000 + Slot⑤ 500 + Slot⑦ 1200 = 3,700 Token
P0 弹性历史区：24,576 - 3,700 = 20,876 Token（大量历史轮次，几乎不需要压缩）

P1 固定占用（Skill + Few-shot 均激活）：3,700 + 1,500 + 800 = 6,000 Token
P1 弹性历史区：24,576 - 6,000 = 18,576 Token（仍非常充裕）

P2 固定占用（全开）：6,000 + 2,000 + 400 = 8,400 Token
P2 弹性历史区：24,576 - 8,400 = 16,176 Token（压缩触发频率极低）

复杂任务模式（如长篇合同分析）：可将工作预算调高至 100,000 Token
  可用输入：100,000 - 8,192 = 91,808 Token
  RAG 知识注入量可扩展至 10,000~20,000 Token
```

**关键设计**：

- Claude Sonnet 4.6 的 200K 上限 ≠ 每次 Agent 调用都用满，工作预算应按任务类型动态调整
- 32K 工作预算是大多数对话型 Agent 任务的合理默认值（历史压缩触发极少）
- Skill 激活是互斥的（同一时刻最多一个 skill），800→1500 Token 升级后依然远不会超限
- Slot ⑧（会话历史）弹性空间从旧版 `2696 Token` 扩展到 `20,876 Token`，Agent 可支持长达数十轮的连续对话而无需压缩

#### ③ Token Counter

**职责**：统计文本 Token 数量，驱动 Budget Manager 的超限判断。

```
为什么需要：不同模型的分词器不同，同样文字 Token 数不同
  "帮我查合同123的签署状态"
    OpenAI (cl100k)  → 约 12 Token
    Ollama glm4      → 约 16 Token（中文分词差异）

两种实现：
  精确计数：tiktoken 库（OpenAI 兼容模型）
  近似估算：字符数/1.5（中文）+ 字符数/4（英文）← P0 够用
```

#### ④ Compressor（消息压缩器）

**职责**：会话历史超出 Token 预算时，把旧消息压缩成摘要腾出空间。

```
压缩流程：
  原始消息：[msg1...msg15, msg16, msg17, msg18, msg19, msg20]
      │
      ├─ 保留区：msg16~msg20（最近 5 条，保持当前上下文）
      └─ 压缩区：msg1~msg15 → 发给 LLM 生成摘要（< 400 Token）
      │
  压缩后：[SystemMessage("摘要：用户在处理合同123审批流程..."), msg16~msg20]
  Token：400 + ~1500 = 1900（原来 6000 → 压缩至 32%）

压缩 Prompt 核心原则：
  必须保留：用户的核心任务目标
  必须保留：已确认的关键事实、工具调用结果
  必须保留：任务当前进度和未完成事项
  可以丢弃：闲聊、重复确认、格式说明
```

#### ⑤ Memory Injector（记忆注入器）

**职责**：在每次 LLM 调用前，把相关记忆动态注入到 Context Window。

```
Memory Injector 职责范围（仅管理 Long Memory → Context Window 的注入）：

  ✅ Memory Injector 负责：
     · Episodic（用户画像）：Long Memory → Slot ① System Prompt（Ephemeral）
     · Procedural（工具模式）：Long Memory → Slot ⑥（Ephemeral，P2）

  ❌ Memory Injector 不负责（由框架或其他模块处理）：
     · Slot ⑧ Short Memory 恢复 → checkpointer 自动完成，无需手写
     · Slot ① Skill Registry 元数据 → System Prompt Builder 静态写入
     · Slot ② Active Skill 内容 → activate_skill @tool + LangGraph 框架自动
     · Slot ③ 动态 Few-shot → Few-shot Retriever
     · Slot ④ RAG 背景知识 → RAG Retriever

──────────────────────────────────────────────────────────────

Slot ① 用户画像注入（Episodic，Ephemeral）
  来源：Long Memory  namespace=("profile", user_id)
  时机：turn 开始时从 DB 加载到 RAM（state["memory_ctx"].episodic）
        每次 LLM 调用前从 RAM 读取，拼入 SystemMessage
  特点：不写入 state["messages"] → 历史永远干净
  示例注入文本：
    [用户画像]
    · 领域: legal-tech（电子合同平台）
    · 语言: zh
    · 角色: 合同管理员
    · 交互次数: 15 次

Slot ⑥ 程序性记忆注入（Procedural，Ephemeral，P2）
  来源：Long Memory  namespace=("procedural", user_id)
  时机：同 Episodic，每次 LLM 调用前注入
  特点：不写入 state["messages"]
  示例注入文本：
    [历史成功模式]
    · 合同查询 → contract_status（成功率 95%）
    · 批量提醒 → query_contracts → send_email（成功率 88%）

Slot ⑧ 会话历史（Short Memory，持久化）
  来源：checkpointer 自动从 PostgreSQL 恢复到 state["messages"]
  内容分类：
    HumanMessage               → 用户输入
    AIMessage(tool_calls=[...])→ LLM 推理（Thought）+ 工具调用指令（Action）
    ToolMessage(普通工具)       → 工具执行结果（Observation）
    ToolMessage(activate_skill)→ skill.md 完整内容（与普通工具结果同类型，
                                  但内容是操作手册而非数据，LLM 用于指导后续行为）
  注意：
    · AIMessage 中的 Thought 文字就是 ReAct 推理轨迹，随历史持久化
    · activate_skill ToolMessage 也在此处，session 内后续 turn 持续可见
    · 若总 Token 超限，Compressor 会将此区域压缩为摘要 + 最近 N 条

──────────────────────────────────────────────────────────────

为什么 Ephemeral 内容需要每次 LLM 调用前重新注入（而非 turn 开始注入一次）：
  ReAct 循环每步后 state 变化：
  · 新 ToolMessage 追加 → Token 增加 → 压缩阈值可能被触发
  · turn 中用户画像实时更新（P2）→ 需要最新版本
  → AgentMiddleware.wrap_model_call 在每次 LLM 调用前执行，确保注入的是当前最新状态
```

#### ⑥ Tool Schema Formatter

**职责**：把工具函数定义转成 LLM 能理解的 JSON Schema（工具描述越好，LLM 选工具越准）。

```
开发者写的工具 docstring：
  def web_search(query: str) -> str:
      """
      搜索互联网获取实时信息。
      适用：最新法规、实时价格、新闻动态。
      不适用：静态知识、数学计算。
      """

LLM 看到的 JSON Schema（框架自动生成）：
  {
    "name": "web_search",
    "description": "搜索互联网获取实时信息。适用：最新法规...",
    "parameters": { "query": { "type": "string" } }
  }

核心原则：description 写得好 = LLM 选工具更准确
  差：description = "搜索工具"        → LLM 不知道何时调用
  好：description = "搜索获取实时信息，适用最新法规查询"  → LLM 精确判断
```

#### ⑦ RAG Retriever（P2，默认关闭）

**职责**：根据用户输入从知识库检索相关背景，Ephemeral 注入 Slot ④。

```
流程：
  用户输入 "电子签名法最新修订内容"
      ↓ Embedding 向量化
      ↓ 向量相似度检索（top-k）
      ↓ 相关性过滤（阈值）
      ↓ Ephemeral 注入 Slot ④（< 2,000 Token，不写入历史）
```

#### ⑧ Few-shot Builder（P0 静态 / P1 动态）

**职责**：提供 LLM 推理和工具调用的"示范样本"，让 LLM 理解期望的行为模式。

**为什么 Few-shot 属于 Prompt 设计，而不属于 Memory：**

```
Memory 解决的问题：把过去的事实和状态带入当前对话
Few-shot 解决的问题：告诉 LLM 如何推理、如何使用工具、输出什么格式

区别：
  Memory   → "你是谁、你之前做过什么"（事实性内容）
  Few-shot → "你应该怎么思考、怎么行动"（行为指导）

Few-shot 是 Prompt Engineering 的核心技术之一：
  零样本（Zero-shot）：只有角色定义，LLM 自行推断行为
  少样本（Few-shot） ：提供 2~5 个示例，LLM 模仿示例推断行为
  Agent 场景尤其需要 Few-shot，因为 ReAct 推理链比普通问答复杂得多
```

**静态 Few-shot（P0/P1）：**

```
硬编码在 System Prompt 里（Slot ①），不需要检索
适合：通用场景、固定任务模式（如合同查询流程）
E签宝场景示例 1：
  用户：查合同123的当前签署进度
  思考：用户需要了解特定合同的签署状态，应使用 contract_status 工具
  行动：[contract_status(contract_id="123")]
  观察：合同123已有2/3方签署，待：财务总监（ddl: 2026-03-20）
  结果：合同123已完成 2/3 签署，财务总监须在3月20日前完成

E签宝场景示例 2：
  用户：批量提醒所有逾期未签合同的签署方
  思考：需先查询所有逾期合同列表，再发送邮件，这是不可逆操作，需要 HIL
  行动：[query_overdue_contracts()]
  观察：发现 15 份逾期合同，涉及 23 位签署方
  HIL：这将向 23 位签署方发送提醒邮件，请确认
```

**动态 Few-shot（P1/P2）：**

```
根据当前用户输入，从 Few-shot 示例库中语义检索最相关的示例
适合：工具种类多、场景多样时，静态 Few-shot 不够覆盖
流程：
  用户输入 → Embedding 向量化 → 相似度检索（Few-shot 库）
  → 取 top-2 相关示例 → Ephemeral 注入 Slot ③（< 800 Token）
```

#### ⑨ Agent Skill Manager（P1）

**职责**：管理 Agent Skills 的注册与加载。初始化时将 Skill Registry 元数据写入 System Prompt（Slot ①），推理时 LLM 通过标准 Function Calling 触发 `activate_skill` @tool，完整 skill 内容以 ToolMessage 形式进入 `state["messages"]`（Slot ⑧ 历史区，持久化）。

**Agent Skill 的设计哲学：**

```
Tool Schema（Slot ⑦）回答的是：我能调用哪些工具，参数是什么？
Agent Skill（进入 Slot ⑧）回答的是：面对这类任务，我应该如何思考和行动？

两者互补，不互斥：
  web_search 工具 → 定义了 API 接口
  legal-search.md → 定义了如何用 web_search 做法律研究
    · 优先搜索官方法律数据库（court.gov.cn / npc.gov.cn）
    · 搜索词组合：法律名称 + "最新修订" + 年份
    · 结果验证：来源必须是官方网站，否则标注"非官方"
    · 引用格式：《法律名称》第X条，YYYY年修订版
```

**两阶段机制（初始化元数据 + 推理时动态加载）：**

```
阶段一：初始化注入（Slot ①，< 100 Token，P1 启用时）
  将 Skill Registry 元数据写入 System Prompt（硬编码，启动时固定）
  告诉 LLM 有哪些 skill、每个 skill 的适用场景、激活方式

  示例元数据格式（写入 Slot①）：
    [可用 Skills]
    · contract-analyzer（合同分析）：适用合同文本理解、风险评估
    · legal-search（法规查询）：适用法律法规、合规问题
    · csv-reporter（数据报告）：适用 CSV 数据统计与可视化
    激活方式：调用工具 activate_skill(name="skill-name")

阶段二：推理时动态加载（标准 Function Call，P1）

  ⚠️ 关键机制：activate_skill 是一个普通 @tool 函数，
  走标准 LangGraph Function Calling 流程，不需要 Middleware。

  完整调用链：
    ① LLM Thought：判断需要 legal-search skill
    ② LLM Action：输出 tool_call → activate_skill(name="legal-search")
    ③ Tool Executor：执行 activate_skill 函数
    ④ 函数内部：从文件系统/DB 读取 legal-search.md 内容
    ⑤ 返回：ToolMessage(content=<skill.md 完整内容>)
    ⑥ 框架追加：state["messages"].append(ToolMessage(...))
    ⑦ LLM 下一步读取 ToolMessage，按 skill 指南继续推理

  与普通工具调用的区别：
    普通工具（web_search）→ 返回查询结果数据
    activate_skill       → 返回操作指南文本（供 LLM 用来指导后续行为）
```

**持久化行为（重要）：**

```
skill 内容通过 ToolMessage 进入 state["messages"]
    ↓
checkpointer 自动将其写入 Short Memory（PostgreSQL checkpoint 表）
    ↓
同一 session 后续 turn 中，LLM 仍能看到已激活 skill 的 ToolMessage

实际效果：
  turn 3 激活了 legal-search → ToolMessage 进入历史
  turn 4 用户继续追问法律问题 → LLM 直接复用 skill 指南（无需重新激活）
  turn 5 话题切换为 CSV 分析 → LLM 可选择激活 csv-reporter skill

注意：skill ToolMessage 占用 Slot ⑧（历史区）的 Token 预算（~1,500 Token），
      非独立的 Slot ②；Slot ② 的预算描述是概念上的"为 skill 内容预留"
```

#### ⑩ 内部操作 Prompt（各节点系统级 LLM 调用）

**与 Few-shot 的本质区别：**

```
Few-shot      → 告诉 LLM"如何推理和使用工具"（行为示范，用户间接感知）
内部操作 Prompt → 驱动框架内部的 LLM 调用（系统运营级，用户完全不感知）

不占用 Context Window Slot，由各子系统独立管理
```

**节点一：Compressor 压缩 Prompt**（触发时机：Slot ⑦ 超出历史弹性预算）

```
调用方   🔧 自行开发 summarize_node（LangGraph 无内置压缩中间件）
LLM 调用 独立于 ReAct 主循环，仅压缩旧历史，不影响当前推理

Prompt 模板（内置默认版，可自定义覆写）：

  请将以下对话历史压缩成简洁摘要（控制在 400 Token 以内）。

  【必须保留】
  · 用户的核心任务目标和意图
  · 已确认的关键事实（合同编号、状态、签署人等）
  · 工具调用结果及其核心含义
  · 当前任务进度和尚未完成的事项

  【可以省略】
  · 闲聊、礼貌用语、重复确认
  · 格式排版相关的指令
  · 与当前任务无关的背景信息

  [对话历史]
  {messages}

  摘要：

输出示例：
  "用户在处理E签宝合同123审批流程。已通过 contract_status 确认：2/3方已签，
  财务总监尚未签署（截止 2026-03-20）。用户下一步计划发送提醒邮件给财务总监。"
```

**节点二：HIL 中断确认 Prompt**（触发时机：Agent 即将执行不可逆操作）

```
调用方   HumanInTheLoopMiddleware（自行开发）
类型     非 LLM 调用，是生成给用户的确认消息模板

消息模板：

  ⚠️ 即将执行以下操作，请确认：

  操作类型：{action_type}           （如：批量发送邮件）
  影响范围：{scope_description}     （如：23 位签署方 / 15 份合同）
  具体内容：{action_detail}         （如：合同签署提醒，模板 contract-reminder-v2）
  预期结果：{expected_result}       （如：签署方将在 24h 内收到邮件）

  [✅ 确认执行]   [❌ 取消操作]

触发条件（在 System Prompt 的 [3] 行为约束中定义）：
  · 发送邮件（影响外部用户）
  · 批量操作（影响 ≥ 5 条记录）
  · 数据删除（不可逆）
  · 外部 API 调用（涉及费用或权限）
```

**节点三：错误恢复 Prompt**（触发时机：工具调用返回错误或异常）

```
调用方   内嵌在 System Prompt 的 [3] 行为约束中，无需额外 LLM 调用

约束内容（写入 System Prompt）：

  工具调用失败时的处理规则：
  1. 分析错误类型，修改参数后重试（最多 2 次）
  2. 2 次重试后仍失败，切换备用方案或告知用户限制原因
  3. 禁止使用相同参数重复调用（防死循环）

  E签宝场景对应：
  · contract_status 返回 404  → 先用 contract_search 确认合同 ID，再调用 status
  · send_email 返回 403       → 告知用户权限不足，建议检查收件人地址
  · web_search 超时           → 最多重试 1 次，超时告知用户网络异常
```

**节点四：结构化输出 Prompt**（触发时机：需要 LLM 输出固定格式的最终答案）

```
调用方   内嵌在 System Prompt 的 [6] 输出格式规范中

输出格式约束（写入 System Prompt，P1）：

  最终答案必须使用以下结构：

  **结论**：一句话摘要（< 50 字）

  **详细说明**：
  {具体内容，Markdown 格式}

  **执行了哪些操作**：
  - 工具名 → 参数 → 关键结果

  **建议下一步**（可选）：
  {如有后续操作建议}
```

### 1.4 完整组装时序（含 Memory 读写节点）

> 标注说明：**DB→RAM** = 从持久化存储读到内存；**RAM→DB** = 从内存写回持久化存储；
> **RAM→LLM** = 组装后发给 LLM；**Ephemeral** = 只存在于当次 LLM 调用，用完即弃

**state 字段说明（AgentState 中的两个核心键）**


| 字段                    | 类型                  | 含义                                                     | 生命周期               | 持久化                                |
| --------------------- | ------------------- | ------------------------------------------------------ | ------------------ | ---------------------------------- |
| `state["messages"]`   | `list[BaseMessage]` | 当前 session 的完整对话历史（Human + AI + Tool 消息）               | session 级，turn 间保留 | ✅ 由 checkpointer 自动写入 checkpoint 表 |
| `state["memory_ctx"]` | `MemoryContext`     | 本次 turn 从 Long Memory 加载的用户画像缓存，供 ReAct 循环内多次 LLM 调用复用 | turn 级，turn 结束后丢弃  | ❌ 不写 checkpoint，仅存 RAM             |


```
用户发送："帮我看看E签宝合同平台今天的合规风险"
    │  FastAPI 收到 { session_id, user_id, message }
    │
═══ turn 开始（每个 turn 各触发一次）════════════════════════════════════

① [DB → RAM] Short Memory 恢复（自动，无需手写）
    PostgreSQL checkpoint 表 → state["messages"]
    SELECT * FROM checkpoints WHERE thread_id=session_id ORDER BY step DESC
    ┌─────────────────────────────────────────────────────────────┐
    │ state["messages"] = [                                       │
    │   HumanMessage("上轮：查合同123状态"),                       │
    │   AIMessage(tool_calls=[{contract_status}]),                │
    │   ToolMessage("已完成签署"),                                 │
    │   AIMessage("合同123已完成，3方均已签字")                     │
    │ ]                                                           │
    └─────────────────────────────────────────────────────────────┘

② [DB → RAM] Long Memory 加载（每 turn 一次，不重复访问 DB）
    PostgreSQL store 表 → state["memory_ctx"]
    store.aget(namespace=("profile", user_id), key="episodic")
    ┌─────────────────────────────────────────────────────────────┐
    │ state["memory_ctx"] = MemoryContext(                             │
    │   # turn 级缓存，before_agent 写入，供 ReAct 循环内复用，不持久化  │
    │                                                                  │
    │   episodic = EpisodicData(          # 用户画像（来自 Long Memory） │
    │     domain   = "legal-tech",        # 业务领域：E签宝电子合同平台  │
    │     language = "zh",               # 语言偏好：中文回复            │
    │     role     = "合同管理员",        # 职业角色：影响术语和详略程度   │
    │     interaction_count = 15         # 历史交互轮次：已用 15 次       │
    │   ),                                                             │
    │   procedural = [                   # 成功工具模式（P2，默认空列表） │
    │     {                                                            │
    │       task: "合同查询",             # 任务类型：匹配用户意图        │
    │       path: ["contract_status"],   # 最优工具路径：单步直接调用     │
    │       rate: 0.95                   # 历史成功率：95%               │
    │     }                                                            │
    │   ]                                                              │
    │ )                                                                │
    └─────────────────────────────────────────────────────────────┘

═══ ReAct 循环（每次 LLM 调用各触发一次）════════════════════════════════

③ [RAM → Ephemeral] 组装工作记忆（本质：把 RAM 中的数据序列化成文本）

    [System Prompt Builder]
    Slot ①  静态内容（角色定义 + 能力边界 + Skill Registry 元数据 + 静态 Few-shot） ~800 Token
            + 动态画像（从 state["memory_ctx"].episodic 读）                       ~100 Token
            → "[用户画像] domain: legal-tech, role: 合同管理员"
            Slot ① 合计 = 900 Token（< 900 上限）✓

    [Token Budget Manager]
    Slot ⑤  用户画像（已并入 Slot①）                              0 Token
    Slot ⑦  工具 Schema（框架自动注入估算）                    1,100 Token
    Slot ⑧  历史消息 Token 数计算：
            count_tokens(state["messages"]) = 2,400 Token
            历史弹性预算 = 24,576 - 2,000 - 1,100 - 8,192(输出) = 13,284 Token
            2,400 < 13,284 → 未超限，不触发压缩 ✓
            （Claude Sonnet 4.6，32K 工作预算）

    ⚪ P1 [Skill 加载] activate_skill 是普通 @tool，走标准 Function Calling
           LLM 输出 tool_call → activate_skill(name="legal-search")
           → Tool Executor 执行 → 读取 legal-search.md
           → 返回 ToolMessage(content=<skill 内容>)
           → 追加到 state["messages"]（持久化，非 Ephemeral）
           → LLM 下一步从 Slot ⑧（历史区）读取 skill 内容继续推理

    ⚪ P1 [DB → Ephemeral] 动态 Few-shot 检索（默认关闭）
    向量存储 → Embedding 相似度检索 → top-2 示例 → Ephemeral 注入 Slot ③

    ⚪ P2 [DB → Ephemeral] RAG 检索（默认关闭）
    向量存储 → 语义检索 → 相关 chunk → Ephemeral 注入 Slot ④

④ [RAM → LLM] Context Window 最终内容
    ┌───────────────────────────────────────────────────────────────────┐
    │ Slot ①  SystemMessage：角色定义 + Skill Registry 元数据           │
    │         + 静态 Few-shot + 用户画像                                 │
    │         （Ephemeral 部分：用户画像来自 state["memory_ctx"]）        │
    │ Slot ③  [P1] DynamicFewshotMessage（若开启，Ephemeral）            │
    │ Slot ④  [P2] RAGContextMessage（若开启，Ephemeral）                │
    │ Slot ⑦  [隐式] 工具定义 Schema（框架自动注入）                      │
    │ Slot ⑧  HumanMessage / AIMessage / ToolMessage × N                │
    │         （来自 state["messages"]，Short Memory 恢复的历史）         │
    │         ← 若已激活 skill，ToolMessage(legal-search.md) 在此处      │
    │ Slot ⑩  HumanMessage：本轮用户输入（最高优先级）                    │
    └───────────────────────────────────────────────────────────────────┘
    ※ Slot ② 概念（活跃 skill 内容）实际落在 Slot ⑧ 历史区，
      通过 activate_skill ToolMessage 自然出现，非独立注入位置
    → LLM 调用

⑤ [RAM 内部] LLM 输出写入对话历史
    ┌──────────────────────────────────────────────────────────────┐
    │ 触发方   框架自动处理，无需手写                                │
    │ 写入内容 AIMessage（含 tool_calls 或 final answer）           │
    │ 写入位置 state["messages"]（内存列表追加）                    │
    └──────────────────────────────────────────────────────────────┘

⑥ [RAM → DB] Short Memory 自动落盘（每个 ReAct 步骤后）
    ┌──────────────────────────────────────────────────────────────┐
    │ 触发方   checkpointer 全自动，无需手写                        │
    │ 写入内容 HumanMessage / AIMessage / ToolMessage              │
    │ 写入位置 PostgreSQL checkpoint 表（追加新 step，不覆盖旧数据）  │
    │ ⚠️ 不写入 用户画像文本（Ephemeral）→ 历史永远干净             │
    └──────────────────────────────────────────────────────────────┘

═══ turn 结束（每个 turn 各触发一次）════════════════════════════════════

⑦ [RAM → DB] Long Memory 写回用户画像
    ┌──────────────────────────────────────────────────────────────┐
    │ 触发方   MemoryMiddleware.after_agent（自行开发）              │
    │ 写入内容 state["memory_ctx"].episodic（更新后的用户画像）      │
    │ 写入位置 PostgreSQL store 表                                  │
    │          store.aput(namespace=("profile", user_id), ...)     │
    │ 🔴 P0   空操作，链路结构建好即可                               │
    │ ⚪ P2   写入规则提炼后的最新偏好（domain / language / role）   │
    └──────────────────────────────────────────────────────────────┘

⑧ [RAM → DB] 可观测性日志落盘（P1）
    ┌──────────────────────────────────────────────────────────────┐
    │ 触发方   TraceMiddleware.after_agent（自行开发）               │
    │ 写入内容 thought_chain / tool_calls / token_usage / latency  │
    │ 写入位置 PostgreSQL agent_traces 表                           │
    │ 用途     面试演示 + 调试 + 执行质量评估                        │
    └──────────────────────────────────────────────────────────────┘
```

### 1.5 Memory 数据结构设计（Context Window 注入视角）

> 记忆内容在注入 Context Window 时，必须序列化成文本。本节定义三层记忆的字段结构以及注入后的文本形态。

#### AgentState 完整结构（state 根节点）

```python
# ── 官方规范 ─────────────────────────────────────────────────────────────────
# AgentState 是 TypedDict（langchain v1 强制要求，不能用 Pydantic BaseModel）
# create_agent 通过 state_schema= 接受自定义扩展
# checkpointer 对所有字段持久化到 PostgreSQL checkpoint 表
# ──────────────────────────────────────────────────────────────────────────────

from langchain.agents import AgentState           # TypedDict，含 messages 字段
from typing_extensions import NotRequired
from typing import Any

class CustomAgentState(AgentState):
    # ── AgentState 基类已定义（不需要重复写）─────────────────────────────────
    # messages: Annotated[list[AnyMessage], add_messages]
    #   ↑ add_messages reducer：更新时"追加"而非"替换"（LangGraph 核心机制）
    #   ↑ 包含当前 session 全部消息历史（Human + AI + Tool），由 checkpointer 自动持久化

    # ── 扩展字段 ─────────────────────────────────────────────────────────────
    memory_ctx: NotRequired[dict | None]
    # turn 级记忆缓存（由 MemoryContext TypedDict 填充，见下方定义）
    # 生命周期：before_agent 写入 → ReAct 循环内复用 → after_agent 写回 DB
    # 持久化：✅ checkpointer 会写入 checkpoint 表，但每 turn 开始重新从 store 加载覆盖
    # P0：None（暂不使用，middleware 直接读 store）
    # P0+：dict 形态，便于 before_agent/after_agent 之间共享，避免 ReAct 循环内重复读 DB
```

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      CustomAgentState（完整字段视图）                        │
│                                                                            │
│  state["messages"]          list[AnyMessage]                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ HumanMessage(content="查合同123状态")              ← 用户输入          │  │
│  │ AIMessage(                                        ← LLM 推理 + 决策  │  │
│  │   content="需要查询合同，调用 contract_status",   ←   Thought 文字    │  │
│  │   tool_calls=[{name:"contract_status",id:"c1"}]  ←   Action 指令    │  │
│  │ )                                                                    │  │
│  │ ToolMessage(content="已完成，3方均已签字",          ← 工具执行结果     │  │
│  │   tool_call_id="c1")                              ←   Observation   │  │
│  │ AIMessage(content="合同123已完成签署...")           ← LLM 最终回答    │  │
│  │ ToolMessage(content="# Legal Search Skill\n...", ← activate_skill  │  │
│  │   tool_call_id="s1")                              ←   (持久化 P1)   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ✅ 由 checkpointer 自动持久化到 PostgreSQL checkpoint 表                   │
│  ✅ add_messages reducer：每次 turn 追加新消息，不覆盖旧消息                  │
│  ❌ SystemMessage 不在此处（Ephemeral，wrap_model_call 临时注入）             │
│                                                                            │
│  state["memory_ctx"]        dict（MemoryContext）                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ {                                                                    │  │
│  │   "episodic": {                  ← 用户画像（来自 Long Memory）       │  │
│  │     "user_id": "admin_001",                                          │  │
│  │     "preferences": {                                                 │  │
│  │       "domain": "legal-tech",                                        │  │
│  │       "language": "zh",                                              │  │
│  │       "role": "合同管理员"                                            │  │
│  │     },                                                               │  │
│  │     "interaction_count": 15,                                         │  │
│  │     "summary": "..."                                                 │  │
│  │   },                                                                 │  │
│  │   "procedural": [               ← 成功工具模式 top-k（P2，默认[]）   │  │
│  │     {                                                                │  │
│  │       "task_type": "合同状态查询",                                    │  │
│  │       "tool_path": ["contract_status"],                              │  │
│  │       "success_rate": 0.95,                                          │  │
│  │       "example": "用户提合同ID时直接调用..."                           │  │
│  │     }                                                                │  │
│  │   ]                                                                  │  │
│  │ }                                                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ✅ checkpointer 会写入（但每 turn 刷新，持久化无副作用）                     │
│  ❌ 不单独管理，由 before_agent / after_agent hook 自动维护                  │
└────────────────────────────────────────────────────────────────────────────┘
```

```python
# ── MemoryContext：memory_ctx 字段的内部结构（TypedDict，与 AgentState 兼容）─
from typing_extensions import TypedDict

class MemoryContext(TypedDict, total=False):
    episodic:    dict          # EpisodicData.model_dump() 的输出，用户画像
    procedural:  list[dict]    # list[ProceduralPattern.model_dump()]，top-k 成功模式（P2）

# ── state["messages"] 的消息类型说明 ─────────────────────────────────────────
from langchain_core.messages import (
    HumanMessage,    # 用户输入，每 turn 1 条
    AIMessage,       # LLM 输出：content=Thought文字 + tool_calls=[Action指令列表]
    ToolMessage,     # 工具执行结果：content=Observation（普通工具结果 or Skill内容）
    SystemMessage,   # 系统提示，⚠️ 不在 state["messages"] 中（Ephemeral，不持久化）
)
# add_messages reducer 规则：
#   · 新消息 append 到列表末尾（不覆盖）
#   · 更新同一 tool_call_id 的 ToolMessage 会覆盖（幂等更新）
#   · AIMessage 中 tool_calls=[] 表示 LLM 决定直接回答（Final Answer）

# ── 两种状态的持久化对比 ─────────────────────────────────────────────────────
"""
state["messages"]          → checkpointer 自动写 DB（session 级，跨 turn 保留）
state["memory_ctx"]        → checkpointer 自动写 DB（但每 turn 被 before_agent 覆盖刷新）
SystemMessage（Ephemeral）  → 不写 DB，仅存在于 LLM 调用的瞬间
"""
```

#### Episodic Memory（用户画像）→ Slot ⑤（注入 Slot ①）

```python
class EpisodicData(BaseModel):
    # ── 标识 ───────────────────────────────────────────────────────────
    user_id: str = ""
    # 用户唯一标识，对应 Long Memory 存储的 namespace 隔离键
    # 示例："admin_001"（E签宝合同管理员）

    # ── 用户偏好（核心字段，P2 自动提炼写入） ────────────────────────────
    preferences: dict[str, str] = {}
    # 键值对存储用户的动态偏好，Agent 推理和回复时参考
    # 当前支持的 key（可随业务扩展）：
    #   "domain"   → 业务领域
    #              示例："legal-tech"（E签宝电子合同）/ "finance"（金融投资）
    #              来源：对话中出现"合同""签署"等词时自动写入
    #
    #   "language" → 语言偏好，控制 Agent 回复语言
    #              示例："zh"（中文）/ "en"（英文）
    #              来源：检测用户输入语言自动写入
    #
    #   "role"     → 职业角色，影响术语选择和详略程度
    #              示例："合同管理员" / "法务专员" / "普通用户"
    #              来源：用户自我介绍或对话中推断
    #
    #   "style"    → 表达风格
    #              示例："professional"（专业简洁）/ "casual"（口语化）
    #              来源：P2 后期通过对话模式推断
    #
    #   "output"   → 偏好的输出格式
    #              示例："markdown_table"（表格）/ "bullet_list"（列表）/ "plain"（纯文字）
    #              来源：用户明确要求或多次点赞特定格式后写入

    # ── 统计与摘要 ───────────────────────────────────────────────────
    interaction_count: int = 0
    # 历史交互轮次计数，P2 第一步写入
    # 用途：统计用户活跃程度；达到阈值时触发偏好提炼逻辑
    # 示例：15（已与 Agent 交互 15 轮）

    summary: str = ""
    # 历史对话的压缩摘要，P2 后期写入
    # 用途：在 Long Memory 中保留跨 session 的核心上下文
    # 注意：不是 Short Memory 的会话摘要（那个存在 checkpoint 里）
    # 示例："用户主要处理E签宝平台的合同审批流程，常用合同状态查询和批量提醒功能"
```

注入 Slot ① 的文本形态（Ephemeral，不写入历史）：

```
[用户画像]
· 领域: legal-tech（电子合同平台）
· 语言: zh（中文回复）
· 角色: 合同管理员
· 交互次数: 15 次
```

#### Agent Skill（技能定义）→ Slot ① 元数据 + Slot ② 完整内容（P1）

```python
class SkillMetadata(BaseModel):
    # 注入 Slot ① 的轻量元数据（约 15~20 Token/条），LLM 用于决策是否激活

    skill_id:    str
    # 技能唯一标识，LLM 调用 activate_skill 时传入此值
    # 示例："legal-search" / "contract-analyzer" / "csv-reporter"

    name:        str
    # 技能展示名称（供日志、UI 展示使用）
    # 示例："法规查询专家"

    description: str
    # 功能描述（1~2 句），写入 System Prompt 让 LLM 判断是否激活
    # 示例："查询法律法规、合规要求、电子签名效力。适用：用户提问含法律/合规/条款"

    trigger:     str
    # 激活条件（一句话），补充 description 让 LLM 更准确判断触发时机
    # 示例："用户询问法律依据、合规要求、电子签名是否有法律效力时"

    path:        str
    # skill.md 文件路径，activate_skill @tool 调用 read() 时使用
    # 示例："skills/legal-search.md"
    # 由 SkillRegistry.load_all() 扫描目录后自动填充

    token_size:  int = 0
    # skill.md 内容的估算 Token 数，用于预算参考
    # load_all() 按文件字节数粗估（中英混合约 len/3）
    # 示例：450

```

#### Procedural Memory（程序性记忆）→ Slot ⑥（P2）

```python
class ProceduralPattern(BaseModel):
    # 一条"成功工具调用模式"的记录
    # ⚠️ 存储方式：每条 ProceduralPattern 作为独立 entry 存入 store
    #    store.put(("procedural", user_id), task_type_hash, pattern.model_dump())
    #    这样 store.asearch() 才能对每条模式做语义检索，找到最相关的几条

    task_type: str
    # 任务类型描述，作为语义检索的主要匹配字段（store 对此字段做 embedding）
    # 示例："合同状态查询" / "CSV 数据分析" / "批量发送通知邮件"

    tool_path: list[str]
    # 完成该任务的最优工具调用序列（按先后顺序）
    # 示例：["contract_status"]（单步）
    #        ["query_contracts", "send_email"]（多步）
    #        ["query_contracts", "HIL_confirm", "send_email"]（含人工确认）

    success_rate: float
    # 该调用路径的历史成功率，0.0~1.0
    # 成功 = Agent 完成任务且用户满意（无后续纠错）
    # 示例：0.95（100 次调用中 95 次直接成功）
    # 用途：注入 Prompt 时向 LLM 展示置信度，引导选择高成功率路径

    example: str
    # 一句话使用提示，注入 Prompt 后直接被 LLM 读取
    # 应简洁、具体，包含"何时调用"的条件
    # 示例："用户提到合同 ID 时直接调用 contract_status，无需先用 contract_search 搜索"

# ── 存取方式（无需 ProceduralData 包装类）─────────────────────────────────────
# 写入：每条模式独立存一个 entry（key 用 task_type hash 实现去重）
#   import hashlib
#   key = hashlib.md5(pattern.task_type.encode()).hexdigest()
#   store.put(("procedural", user_id), key, pattern.model_dump())
#
# 读取：语义检索当前意图最相关的模式（top-3）
#   items = store.asearch(("procedural", user_id), query=user_input, limit=3)
#   patterns = [ProceduralPattern(**item.value) for item in items]
#
# E签宝场景示例（3 条独立 entry）：
#   entry 1: key=hash("合同状态查询"),  value=ProceduralPattern(task_type="合同状态查询",
#            tool_path=["contract_status"], success_rate=0.95,
#            example="用户提到合同ID → 直接调用 contract_status，无需先搜索").model_dump()
#
#   entry 2: key=hash("批量发送提醒邮件"), value=ProceduralPattern(
#            task_type="批量发送提醒邮件",
#            tool_path=["query_contracts","HIL_confirm","send_email"], success_rate=0.88,
#            example="批量操作须先 HIL 确认影响范围，再执行发送").model_dump()
#
#   entry 3: key=hash("CSV合同数据分析"), value=ProceduralPattern(
#            task_type="CSV 合同数据分析",
#            tool_path=["csv_analyze"], success_rate=0.92,
#            example="上传 CSV 后直接调用 csv_analyze，无需预处理").model_dump()
```

注入 Slot ⑥ 的文本形态（Ephemeral，P2）：
来源：`store.asearch(("procedural", user_id), query=user_input, limit=3)` 语义检索 top-3 条

```
[成功经验]
· 合同查询: contract_status（成功率 95%）
  提示：用户提合同ID时直接调用，无需先搜索
· 批量提醒: query → HIL确认 → send_email（成功率 88%）
  提示：批量操作须先确认数量
```

#### Few-shot Example → Slot ① 静态 / Slot ③ 动态

```python
class FewShotExample(BaseModel):
    # 一个完整的"示范对话"，展示 Agent 期望的推理方式和工具使用方式
    # ⚠️ 存储方式：每条 FewShotExample 作为独立 entry 存入 store（全局共享命名空间）
    #    store.put(("fewshot", "global"), str(uuid.uuid4()), example.model_dump())
    #    store 配置 index={"embed": embeddings, "fields": ["user_input"]} 后自动索引
    #    store.asearch(("fewshot", "global"), query=user_input, limit=2) 语义检索

    user_input: str
    # 用户原始输入，作为语义检索的主匹配字段（store 自动对此做 embedding 索引）
    # 示例："查合同123的签署进度"

    thought: str
    # Agent 的推理过程（Thought），是 Few-shot 最核心的示范内容
    # 要点：说清楚"为什么选这个工具"，体现 ReAct 的推理逻辑
    # 示例："用户需要查询指定合同的状态，应使用 contract_status 工具，
    #        合同 ID 已在输入中明确提供，无需先调用 contract_search"

    tool_calls: list[str]
    # 工具调用序列（仅记录工具名+参数的文本描述，非代码）
    # 示例：["contract_status(contract_id='123')"]

    observation: str
    # 工具返回结果的简化版本（过长的返回需要截断）
    # 目的：让 LLM 理解工具的典型输出格式
    # 示例："合同123已有2/3方签署，待签：财务总监（截止 2026-03-20）"

    final_answer: str
    # 最终给用户的回复，体现期望的输出格式和详略程度
    # 示例："合同123进度：2/3 已签署，财务总监需在3月20日前完成签署。"

    tags: list[str]
    # 分类标签，用于人工管理和过滤（非检索主键）
    # 建议格式：[业务领域, 任务类型, 工具名]
    # 示例：["legal-tech", "contract-query", "contract_status"]

    # ⚠️ 移除 embedding 字段：LangGraph Store 配置 embedding 模型后自动管理向量
    #    index={"embed": init_embeddings("openai:text-embedding-3-small"), "dims": 1536}
    #    开发者无需在数据结构中手动维护 embedding，store.put() 时自动生成并存储

# ── 存取方式（无需 FewShotStore 包装类）──────────────────────────────────────
# P0：静态 Few-shot 直接硬编码到 System Prompt 模板，不需要 store
#
# P1：动态 Few-shot，每条示例独立存入 store
#   写入（初始化脚本，一次性导入）：
#     for example in STATIC_FEW_SHOTS:
#         store.put(("fewshot", "global"), str(uuid.uuid4()), example.model_dump())
#
#   读取（每次 LLM 调用前，wrap_model_call 内）：
#     items = store.asearch(("fewshot", "global"), query=user_input, limit=2)
#     few_shots = [FewShotExample(**item.value) for item in items]
#
#   建议总量：10~15 条，覆盖各主要工具场景
#   维护策略：定期人工审核，删除低质量条目，补充新场景

静态 Few-shot 注入 Slot ① 的文本形态：

```
## 示例对话（演示推理方式，非真实历史）

示例 1：
用户：查合同123的签署进度
思考：用户需要查询指定合同的状态，直接使用 contract_status 工具
操作：contract_status(contract_id="123")
观察：合同123已有2/3方签署，待签：财务总监（截止 2026-03-20）
回复：合同123进度：2/3 已签署，财务总监需在3月20日前完成签署。

示例 2：
用户：批量提醒所有逾期未签合同的签署方
思考：这是批量操作，需先确认范围再执行，必须触发人工确认
操作：query_overdue_contracts()
观察：15 份逾期合同，23 位签署方
HIL：此操作将向 23 位签署方发送提醒邮件，请确认是否继续？
```

#### Long Memory 数据存取规范（官方 API）

```python
# LangGraph AsyncPostgresStore 官方 API（基于官方文档）
# 导入路径
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# ── 存（Write）────────────────────────────────────────────────────────────
# store.aput(namespace, key, value)
# · namespace：tuple[str, ...]，用于隔离数据
# · key：       str，记录唯一标识
# · value：     dict（⚠️ 只接受 dict，Pydantic 需先 .model_dump()）
await runtime.store.aput(
    ("profile", user_id),    # namespace
    "profile",               # key（Episodic 单条，固定 key）
    episodic_data.model_dump()  # ⚠️ 必须 .model_dump()，不能直接传 Pydantic 对象
)
await runtime.store.aput(
    ("procedural", user_id),
    pattern_id,              # key（每条 Pattern 独立存储，uuid 或 task_type hash）
    pattern.model_dump()
)

# ── 取（Read）────────────────────────────────────────────────────────────
# store.aget(namespace, key) → Item | None，Item.value 是原始 dict
item = await runtime.store.aget(("profile", user_id), "profile")
if item:
    episodic = EpisodicData(**item.value)   # dict → Pydantic 重建

# store.asearch(namespace, query=..., limit=...) → list[Item]（语义搜索）
items = await runtime.store.asearch(
    ("procedural", user_id),
    query=current_user_input,  # 语义相似度匹配
    limit=3
)
patterns = [ProceduralPattern(**item.value) for item in items]

# ── 两种 store 访问方式 ──────────────────────────────────────────────────
# 方式 A：create_agent + AgentMiddleware（推荐，langchain v1 新 API）
#   context_schema：TypedDict
#   store 访问：request.runtime.store.aget/asearch（在 wrap_model_call 内）
#   context 访问：request.runtime.context.get("user_id")（dict 风格）
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from typing import TypedDict

class AgentContext(TypedDict):
    user_id: str

class MemoryMiddleware(AgentMiddleware):
    async def awrap_model_call(self, request: ModelRequest, handler):
        user_id = request.runtime.context.get("user_id", "")
        item = await request.runtime.store.aget(("profile", user_id), "profile")
        # ... 注入 episodic 到 system_message
        return await handler(request)

# 方式 B：自定义 StateGraph node（底层，灵活，适用于复杂图结构）
#   context_schema：@dataclass 或 TypedDict
#   store 访问：runtime.store.aget/asearch（通过 Runtime[Context] 参数）
#   context 访问：runtime.context.user_id（属性风格，@dataclass）
from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.graph import StateGraph, MessagesState

@dataclass
class Context:
    user_id: str

async def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id           # ← 属性访问
    item = await runtime.store.aget(("profile", user_id), "profile")

builder = StateGraph(MessagesState, context_schema=Context)
graph = builder.compile(checkpointer=checkpointer, store=store)
graph.invoke(
    {"messages": [...]},
    config={"configurable": {"thread_id": "t1"}},
    context=Context(user_id="admin_001"),
)
```

#### 三层记忆 Token 预算汇总

```
记忆类型               Slot          最大 Token   存储位置           持久化  注入时机            优先级
────────────────────────────────────────────────────────────────────────────────────────────────
Skill Registry 元数据  Slot ①        ~100 Token  代码硬编码            ❌    启动时写入模板，静态  P1
Static Few-shot        Slot ①        ~300 Token  代码硬编码            ❌    启动时写入模板，静态  P0/P1
用户画像 Episodic       Slot ①/⑤     500 Token   Long Memory(DB)      ❌    每次 LLM 调用前      P0
                       （Ephemeral：LLM 调用前注入 SystemMessage，不写入 state["messages"]）
Dynamic Few-shot       Slot ③        800 Token   向量存储(DB)          ❌    每次 LLM 调用前      P1
                       （Ephemeral：AgentMiddleware.wrap_model_call → request.override(system_message=...)）
RAG 背景知识            Slot ④        2,000 Token 向量存储(DB)          ❌    每次 LLM 调用前      P2
                       （Ephemeral：同 Dynamic Few-shot，wrap_model_call 追加 content_blocks）
Procedural             Slot ⑥        400 Token   Long Memory(DB)      ❌    每次 LLM 调用前      P2
                       （Ephemeral：同 Episodic，wrap_model_call 内 request.runtime.store.asearch 读取后追加）
Active Skill 完整内容   Slot ⑧ 历史区  ~1,500 Token 文件系统             ✅    LLM activate_skill  P1
                       （持久化：ToolMessage 进入 state["messages"]，随 checkpoint 写 DB）
Short Memory           Slot ⑧        弹性         Short Memory(DB)     ✅    turn 开始时恢复      P0
                       （持久化：所有 Human/AI/Tool Message）

Ephemeral 类：Skill Registry 元数据 / 静态 Few-shot / Episodic / RAG / Dynamic Few-shot / Procedural
              → 不进入 state["messages"]，历史永远干净
持久化类  ：Active Skill ToolMessage / 对话历史 HumanMessage / AIMessage / 普通 ToolMessage
              → 进入 state["messages"]，checkpointer 自动写 DB
Active Skill 同一时刻建议最多激活一个，避免 Slot ⑧ 中大量 skill 内容堆积
```

---

## 第二层：LangChain 实现映射

### 2.1 子模块 → LangChain API 对照


| 子模块                     | 功能                                          | LangChain 实现                                                                           | 归属          | 优先级       |
| ----------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------- | ----------- | --------- |
| System Prompt Builder   | 静态模板 + Skill Registry 元数据 + 静态 Few-shot     | `create_agent(system_prompt=build_system_prompt())`                                    | 🔧 自行开发（模板） | 🔴 P0     |
| System Prompt Builder   | Episodic 动态注入（Ephemeral）                    | `AgentMiddleware.wrap_model_call` → `request.override(system_message=...)`             | 🔧 自行开发     | 🔴 P0     |
| Token Budget Manager    | 预算常量定义                                      | `config.py` 手写常量（含 `SLOT_ACTIVE_SKILL` / `SLOT_FEW_SHOT` / `SLOT_PROCEDURAL`）          | 🔧 自行开发     | 🔴 P0     |
| Token Budget Manager    | 超限检测与历史压缩                                   | 🔧 自行开发：`before_model` hook 检测 Token 超限 → 触发 summarize LLM 调用                          | 🔧 自行开发     | 🔴 P0     |
| **Agent Skill Manager** | **Skill Registry 初始化（元数据写入 System Prompt）** | **`SkillRegistry.load_all()` + `SkillMiddleware.wrap_model_call` 注入到 system_message** | **🔧 自行开发** | **🟡 P1** |
| **Agent Skill Manager** | **activate_skill 工具注册**                     | **`@tool def activate_skill(name: str) -> str`，读取 skill.md 返回内容**                      | **🔧 自行开发** | **🟡 P1** |
| **Agent Skill Manager** | **skill 内容进入历史（ToolMessage）**               | **LangGraph 框架自动处理，无需额外开发**                                                            | **✅ 框架内置**  | **🟡 P1** |
| Token Counter           | 近似估算                                        | 手写字符估算函数                                                                               | 🔧 自行开发     | 🔴 P0     |
| Token Counter           | 精确计数                                        | `tiktoken` 库                                                                           | 🔧 自行开发     | ⚪ P2      |
| Compressor              | 历史压缩触发与执行                                   | `AgentMiddleware.before_model` hook：Token 超限时调 LLM 压缩旧历史，替换 state["messages"]         | 🔧 自行开发     | 🔴 P0     |
| Memory Injector         | Short Memory 恢复                              | `checkpointer` 自动恢复 `state["messages"]`                                               | ✅ 框架内置      | 🔴 P0     |
| Memory Injector         | Episodic 注入（Long Memory）                    | `AgentMiddleware.wrap_model_call`：`request.runtime.store.aget(("profile", user_id), "profile")` | 🔧 自行开发     | 🔴 P0     |
| Memory Injector         | Procedural 注入（Long Memory）                  | `AgentMiddleware.wrap_model_call`：`request.runtime.store.asearch(("procedural", user_id), ...)` | 🔧 自行开发     | ⚪ P2      |
| Tool Schema Formatter   | Schema 生成                                   | `@tool` 装饰器自动生成                                                                        | ✅ 框架内置      | 🔴 P0     |
| Tool Schema Formatter   | Schema 注入                                   | `create_agent(tools=[...])` 自动处理                                                      | ✅ 框架内置      | 🔴 P0     |
| Few-shot Builder        | 静态 Few-shot                                 | `prompt/templates.py` 硬编码到 `system_prompt`                                             | 🔧 自行开发     | 🔴 P0     |
| Few-shot Builder        | 动态 Few-shot 检索                              | `AsyncPostgresStore` + pgvector + `AgentMiddleware.wrap_model_call` 内语义检索注入            | 🔧 自行开发     | 🟡 P1     |
| RAG Retriever           | 向量存储                                        | `AsyncPostgresStore` + pgvector                                                        | ✅ 框架支持      | ⚪ P2      |
| RAG Retriever           | 检索 + Ephemeral 注入                           | `AgentMiddleware.wrap_model_call` 内检索后 `request.override(system_message=...)`         | 🔧 自行开发     | ⚪ P2      |


### 2.2 关键代码

#### System Prompt Builder（🔴 P0）

```python
# prompt/templates.py — 🔧 自行开发
ROLE_TEMPLATE = """你是一个专业的多工具 AI 助手，能够自主规划并执行复杂任务。

## 核心能力
- 实时信息搜索（web_search）
- 数据分析（csv_analyze，P0）
- 合同流程查询（E签宝场景示例）

## 行为准则
- 每次行动前先推理，说明为什么选择当前工具
- 遇到不确定信息，优先搜索而不是猜测
- 最终答案使用 Markdown 格式
"""

USER_PROFILE_TEMPLATE = """
## 用户画像
{preferences}
"""

# prompt/builder.py — 🔧 自行开发
def build_system_prompt(episodic: EpisodicData | None = None) -> str:
    parts = [ROLE_TEMPLATE]
    # 动态注入用户画像（P0 episodic 为空不影响运行，P2 后生效）
    if episodic and episodic.preferences:
        prefs_text = "\n".join(f"- {k}: {v}" for k, v in episodic.preferences.items())
        parts.append(USER_PROFILE_TEMPLATE.format(preferences=prefs_text))
    return "\n".join(parts)
```

#### Token Budget 常量（🔴 P0）

```python
# config.py — 🔧 自行开发
class TokenBudget:
    # 模型规格：Claude Sonnet 4.6
    MODEL_CONTEXT_WINDOW: int = 200_000   # 模型硬上限，200K
    MODEL_MAX_OUTPUT:     int = 8_192     # 标准输出上限；扩展模式可改为 16_384

    # Agent 工作预算：每次 turn 实际使用的 Token 上限
    # 设为 32K 而非 200K，兼顾成本与速度；复杂任务可动态调高至 100K
    WORKING_BUDGET: int = 32_768

    # 输出预留（固定值，对应 Model_MAX_OUTPUT）
    SLOT_OUTPUT: int = 8_192

    # ── 固定 Slot 上限 ────────────────────────────────────────────
    # Slot ①  System Prompt + Skill Registry 元数据 + 静态 Few-shot
    SLOT_SYSTEM:      int = 2_000

    # Slot ②（概念预算）活跃技能内容预估占用（P1）
    # 实际上 skill 内容以 ToolMessage 存在于 Slot ⑧（会话历史），而非独立 Slot
    # 此常量用于预算跟踪：估算 activate_skill ToolMessage 的 Token 占用
    # 方便 Token Budget Manager 计算 Slot ⑧ 的剩余弹性空间
    SLOT_ACTIVE_SKILL: int = 0    # P1 改为 1_500（当 session 内已激活 skill 时）

    # Slot ③  动态 Few-shot（P1，默认 0）
    SLOT_FEW_SHOT:    int = 0     # P1 改为 800

    # Slot ④  RAG 背景知识（P2，默认 0）
    SLOT_RAG:         int = 0     # P2 改为 2_000

    # Slot ⑤  用户画像 Episodic（P0）
    SLOT_EPISODIC:    int = 500

    # Slot ⑥  程序性记忆 Procedural（P2，默认 0）
    SLOT_PROCEDURAL:  int = 0     # P2 改为 400

    # Slot ⑦  工具 Schema（框架自动注入，按实际工具数量估算）
    SLOT_TOOLS:       int = 1_200

    @property
    def input_budget(self) -> int:
        """可用输入 Token 数 = 工作预算 - 输出预留"""
        return self.WORKING_BUDGET - self.SLOT_OUTPUT
        # 默认：32,768 - 8,192 = 24,576 Token

    @property
    def slot_history(self) -> int:
        """Slot ⑧ 会话历史弹性预算 = 可用输入 - 所有已启用固定 Slot"""
        fixed = (
            self.SLOT_SYSTEM + self.SLOT_ACTIVE_SKILL + self.SLOT_FEW_SHOT
            + self.SLOT_RAG + self.SLOT_EPISODIC + self.SLOT_PROCEDURAL
            + self.SLOT_TOOLS
        )
        return self.input_budget - fixed
        # P0（全关）：24,576 - (2000+0+0+0+500+0+1200) = 20,876 Token
        # P1（Skill+Few-shot 开）：24,576 - (2000+1500+800+0+500+0+1200) = 18,576 Token
        # P2（全开）：24,576 - (2000+1500+800+2000+500+400+1200) = 16,176 Token
```

#### Agent Skill Manager（🟡 P1）

```python
# skills/registry.py — 🔧 自行开发
import os
from pathlib import Path
from langchain_core.tools import tool

SKILLS_DIR = Path("skills/")  # skill .md 文件目录

class SkillRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, SkillMetadata] = {}  # skill_id → SkillMetadata（含 path）

    def load_all(self) -> None:
        """启动时扫描 skills/ 目录，将所有 .md 文件注册为 SkillMetadata"""
        for md_file in SKILLS_DIR.glob("*.md"):
            skill_id   = md_file.stem
            content    = md_file.read_text(encoding="utf-8")
            token_size = len(content) // 3
            self._registry[skill_id] = SkillMetadata(
                skill_id   = skill_id,
                name       = skill_id,
                description= "",          # P1：从 .md frontmatter 解析
                trigger    = "",          # P1：从 .md frontmatter 解析
                path       = str(md_file),
                token_size = token_size,
            )

    def get_metadata_summary(self) -> str:
        """生成注入 Slot ① 的元数据文本，LLM 用于判断是否激活 skill"""
        lines = ["[可用 Skills]"]
        for meta in self._registry.values():
            lines.append(f"· {meta.skill_id}：{meta.description}（触发：{meta.trigger}）")
        lines.append("激活方式：调用工具 activate_skill(name=\"skill-id\")")
        return "\n".join(lines)

    def read(self, skill_id: str) -> str:
        """读取 skill.md 完整内容，供 activate_skill @tool 返回给 LLM"""
        meta = self._registry.get(skill_id)
        if meta is None:
            return f"[错误] skill '{skill_id}' 不存在，可用：{list(self._registry.keys())}"
        return Path(meta.path).read_text(encoding="utf-8")


# 全局单例，应用启动时初始化
skill_registry = SkillRegistry()
skill_registry.load_all()


# tools/skill_tool.py — 🔧 自行开发
@tool
def activate_skill(name: str) -> str:
    """
    激活指定的 Agent Skill，获取该场景的完整操作指南。
    当任务需要专业知识（法律查询、合同分析、数据报告等）时调用。
    返回的内容是操作手册，阅读后按其指南继续执行任务。

    Args:
        name: skill 名称，如 "legal-search" / "contract-analyzer" / "csv-reporter"
    """
    content = skill_registry.read(name)
    return content
    # 返回值作为 ToolMessage 进入 state["messages"]
    # LLM 在下一个 ReAct 步骤中读取此 ToolMessage，按 skill 指南行动
    # ToolMessage 随 checkpointer 写入 Short Memory，同 session 后续 turn 持续可见
```

**实际 ReAct 执行轨迹（E签宝场景）：**

```
用户："这份电子合同的签名具有法律效力吗？"

Step 1 - LLM Thought：
  "用户询问法律效力，这是法律合规问题，需要激活 legal-search skill"
  LLM Action → activate_skill(name="legal-search")

Step 2 - Tool Executor：
  调用 activate_skill("legal-search")
  → 读取 skills/legal-search.md
  → 返回 ToolMessage(content="# Legal Search Skill\n## 适用场景\n...")

Step 3 - LLM Thought（读取 ToolMessage 后）：
  "已获取 legal-search skill 指南，按其策略搜索官方法律来源"
  LLM Action → web_search("电子签名法律效力 site:npc.gov.cn")

Step 4 - Tool Executor：
  调用 web_search → 返回搜索结果

Step 5 - LLM Final Answer：
  "根据《电子签名法》第十三条..."
```

#### Token Counter（🔴 P0 近似版）

```python
# utils/token_counter.py — 🔧 自行开发
def count_tokens_approx(text: str) -> int:
    """
    P0：字符数近似估算，Ollama 本地模型够用
    P2：替换为 tiktoken 精确计数（OpenAI / DeepSeek 等兼容模型）
    """
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars   = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
```

#### create_agent 启动 + MemoryMiddleware（🔴 P0）

```python
# agent/langchain_engine.py — ⚡ 胶水代码
# 迁移说明：create_react_agent（已废弃）→ create_agent（langchain v1 新 API）
from langchain.agents import create_agent                      # ✅ 新 API
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage
from typing import Callable, TypedDict
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

# context_schema 必须是 TypedDict（create_agent 规范）
class AgentContext(TypedDict):
    user_id: str


# ── MemoryMiddleware：Ephemeral 注入 Episodic（P0）+ Procedural（P2）──────────
class MemoryMiddleware(AgentMiddleware):
    """
    wrap_model_call：每次 LLM 调用前从 Long Memory 读取记忆，
    通过 request.override(system_message=...) 注入 SystemMessage。
    不写入 state["messages"] → 历史永远干净（Ephemeral）。
    """

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        user_id = request.runtime.context.get("user_id", "")

        # Episodic：取用户画像（P0，单条固定 key）
        item = await request.runtime.store.aget(("profile", user_id), "profile")
        episodic_text = format_episodic(item.value) if item else ""

        # Procedural：语义检索成功模式（P2，注释解开即启用）
        # patterns = await request.runtime.store.asearch(
        #     ("procedural", user_id), query=request.state["messages"][-1].content, limit=3
        # )

        if episodic_text:
            new_content = list(request.system_message.content_blocks) + [
                {"type": "text", "text": episodic_text}
            ]
            new_sys = SystemMessage(content=new_content)
            request = request.override(system_message=new_sys)  # Ephemeral

        return await handler(request)


# ── P0 版：静态 system_prompt（快速启动，无动态注入）───────────────────────────
agent = create_agent(
    model=llm_factory(),
    tools=tools,
    system_prompt=build_system_prompt(),   # str，启动时固定
    checkpointer=checkpointer,             # ✅ Short Memory 自动恢复
    store=store,                           # ✅ Long Memory 访问入口
)

# ── P0+ 版：加入 MemoryMiddleware 实现 Ephemeral 注入 ─────────────────────────
agent_with_memory = create_agent(
    model=llm_factory(),
    tools=tools,
    system_prompt=build_system_prompt(),   # 静态基础，动态增量由 middleware 追加
    middleware=[
        MemoryMiddleware(),                # 🔧 Episodic + Procedural Ephemeral 注入
        TraceMiddleware(),                 # 🔧 日志记录（P1）
    ],
    checkpointer=checkpointer,
    store=store,
    context_schema=AgentContext,           # TypedDict，调用时通过 context= 传入
)

# 调用示例
config = {"configurable": {"thread_id": "session-001"}}
result = await agent_with_memory.ainvoke(
    {"messages": [{"role": "user", "content": "查合同123的签署状态"}]},
    config=config,
    context=AgentContext(user_id="admin_001"),   # user_id 传入 middleware
)
```

### 2.3 一句话总结：LangChain 帮你省掉了什么

```
不用自己写的（✅ 框架内置）：
  工具 JSON Schema 生成          → @tool 装饰器
  工具 Schema 注入 Context       → create_agent(tools=[...]) 自动
  会话历史管理 + 断点恢复         → AsyncPostgresSaver + checkpointer 自动
  ToolMessage 进入历史            → LangGraph graph execution 自动（含 activate_skill）
  Long Memory 存储接口            → AsyncPostgresStore（store.aput/aget/asearch）
  Ephemeral 注入机制              → AgentMiddleware.wrap_model_call + request.override()

必须自己写的（🔧 自行开发）：
  System Prompt 模板内容         → templates.py（角色定义、能力边界）
  MemoryMiddleware               → wrap_model_call 读 store + override system_message
  会话历史压缩（Token 超限时）     → before_model hook：Token 计数 → LLM 压缩 → 替换旧历史
  SkillMiddleware                → wrap_model_call 注入 Skill Registry 元数据（P1）
  Token 近似计数                 → 简单工具函数（P0 够用）
  工具 docstring                 → 每个工具认真写（影响 LLM 选工具准确率）
```

