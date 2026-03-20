# Memory 模块架构设计文档 v4

> v4 重大更新：双层架构拆分
> - **第一层（框架无关）**：概念定义、设计决策、数据流时序 ← 面试先答这层
> - **第二层（LangChain 实现）**：API 映射、代码接口、存储表、优先级 ← 面试再答这层

---

## 第一层：框架无关的 Memory 架构

> 本层不出现任何框架名词。用任何语言、任何框架都能实现这个设计。

### 1.1 为什么 Agent 需要三层记忆

LLM 本身无状态——每次 API 调用都是独立请求，没有天然"记忆"。这导致三个问题：

| 问题 | E签宝场景举例 | 解决方案 |
|------|-------------|---------|
| 多轮对话失忆 | 第一轮说"查合同123的签署状态"；第二轮说"发邮件提醒" → Agent 不知道提醒哪份合同 | 短期记忆 |
| 跨会话无个性化 | 每次都要重新说"我是电子合同平台的合同管理员，请用法律术语" | 长期记忆 |
| 每次 LLM 调用缺完整上下文 | 短期记忆有历史，长期记忆有画像，但 LLM 每次只接受一个输入 | 工作记忆（连接两者） |

### 1.2 三层记忆模型

```
┌──────────────────────────────────────────────────────────────────────┐
│                     三层记忆模型（框架无关）                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              工作记忆（Working Memory）                       │    │
│  │                                                             │    │
│  │  单次 LLM 调用的 Context Window（Token 上限内）               │    │
│  │  System Prompt + 用户画像 + 会话历史 + 工具定义 + 当前输入    │    │
│  │                                                             │    │
│  │  ⚡ 不是存储，是每次 LLM 调用前动态组装的内容                  │    │
│  │  ⚡ Ephemeral：用完即弃，本身不持久化                          │    │
│  └────────────────────────┬────────────────────────────────────┘    │
│                从这里取材   ↑↑↑   从这里取材                         │
│  ┌─────────────────────┐         ┌──────────────────────────────┐   │
│  │   短期记忆（Short）  │         │    长期记忆（Long）            │   │
│  │   session 内有效     │         │    跨 session 永久有效         │   │
│  │                     │         │                              │   │
│  │  · 会话历史          │         │  · 用户画像（偏好/领域/语言）   │   │
│  │  · 工具调用记录       │         │  · 技能库（P2）               │   │
│  │  · 中间推理状态       │         │  · 知识库（P2）               │   │
│  │                     │         │                              │   │
│  │  隔离粒度：session_id│         │  隔离粒度：(user_id, 类型)     │   │
│  └─────────────────────┘         └──────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

**短期记忆（within-session）**

- 范围：一个对话 session，session 结束后废弃
- 内容：Human 消息、AI 回复、工具执行结果、中间推理状态
- 关键要求：**跨 HTTP 请求存活**（Agent 分多次请求执行完成）；**支持断点恢复**（HIL 场景：Agent 等待人工确认期间不能丢失状态）
- 不存放：用户画像（归长期记忆）；RAG chunk（Ephemeral，不污染历史）

**长期记忆（cross-session）**

- 范围：一个用户的全部历史
- 内容：领域偏好（如 "legal-tech"）、语言偏好（"zh"）、交互风格、历史摘要
- 关键要求：**按类型隔离**，未来扩展技能库、知识库不影响现有画像
- 读写时机：每次 turn 开始读一次，结束后写一次

**工作记忆（per LLM call）**

- 不是存储介质，是一次 LLM API 调用的完整输入
- 组成：静态 System Prompt + 用户画像 + 对话历史（压缩后）+ 工具定义 + 当前输入
- 关键要求：**Token 预算管理**（必须在模型 Context Window 上限内）；**Ephemeral 注入**（用户画像注入请求但不写入历史）

### 1.3 读写时序（框架无关）

```
─── turn N 开始 ──────────────────────────────────────────────────────
用户发送："帮我检查合同123的签署进度，已完成的话发邮件通知对方"
      │
      ▼
① 加载长期记忆（每次 turn 触发一次，不是每次 LLM 调用）
      从持久存储读用户画像：
      { domain: "legal-tech", language: "zh", role: "合同管理员" }
      缓存到本次 turn 的内存（后续 LLM 调用直接读缓存，不重复访问存储）
      │
      ▼
② 恢复短期记忆
      加载上次 session 保存的对话历史（新 session 则为空）

─── ReAct 循环（可能多轮 LLM 调用）─────────────────────────────────
      │
      ▼  ← 每次 LLM 调用前
③ 组装工作记忆（Ephemeral，不持久化）
      静态 System Prompt
      + 用户画像 ← 从①的缓存读（不重复访问存储）
      + 对话历史 ← 从②的恢复结果读（超 Token 限制时先压缩）
      + 工具定义 Schema
      + 当前用户输入

      ▼
④ LLM 调用
      输出 A：推理文字（Thought）+ 工具调用指令（Action）→ 进入 ⑤
      输出 B：最终答案 → 进入 ⑥

      ▼ （输出 A 时）
⑤ 工具执行
      并行执行所有工具调用
      工具结果作为 ToolMessage 追加到对话历史（Persistent）
      保存检查点（支持 HIL 断点恢复）
      → 回到 ③ 继续循环

      ▼ （输出 B 时）
⑥ 退出 ReAct 循环

─── turn N 结束 ──────────────────────────────────────────────────────
      │
      ▼
⑦ 保存短期记忆（自动）
      将本轮完整对话（Human + AI + Tool 消息）保存到检查点
      ⚠️ 不含用户画像文本（Ephemeral，不写入）

      ▼
⑧ 写回长期记忆（每次 turn 触发一次）
      🔴 P0：空操作（钩子结构建好即可）
      ⚪ P2 第一步：interaction_count +1
      ⚪ P2 第二步：规则提炼偏好
```

### 1.4 Ephemeral vs Persistent 注入策略

**核心问题：用户画像注入进工作记忆后，该不该写入对话历史？**

```
❌ Persistent 注入（错误做法）

  第 1 轮：System Prompt 包含 "[用户画像] domain: legal-tech"
           → 这条 System Prompt 写入对话历史
  第 2 轮：恢复历史 → 历史里已有 "[用户画像] domain: legal-tech"
           + 本轮再注入一次 → 历史里出现 2 份
  第 N 轮：历史里有 N 份重复的用户画像
           → Token 严重浪费
           → 历史压缩质量下降（LLM 看到大量重复画像而非真实对话）

✅ Ephemeral 注入（正确做法）

  每次 LLM 调用前：把用户画像注入"请求级 System Prompt"
  调用结束后：只把 Human + AI + Tool 消息写入历史，画像不写入
  → 对话历史永远干净
  → 用户画像每轮基于最新数据注入
  → Token 可控，压缩质量好
```

| 内容类型 | 注入方式 | 是否写入历史 | 原因 |
|----------|----------|-------------|------|
| 用户画像 | Ephemeral | ❌ 否 | 避免重复堆积；每轮保持最新 |
| RAG chunk（P2） | Ephemeral | ❌ 否 | 每轮基于当前问题重新检索 |
| Human 消息 | Persistent | ✅ 是 | 核心对话内容 |
| AI 回复 | Persistent | ✅ 是 | 核心对话内容 |
| 工具结果 | Persistent | ✅ 是 | 后续推理依赖工具结果 |

### 1.5 存储粒度设计

```
短期记忆隔离单元：session_id
  同一 session 的所有请求共享同一份历史
  不同 session 完全隔离
  E签宝场景：
    用户A审核合同的会话 ≠ 用户A管理模板的会话（两个独立 session）

长期记忆隔离单元：(user_id, memory_type)
  memory_type 按类型隔离，支持渐进扩展：
  ├── "profile"     用户画像（🔴 P0 建好结构，⚪ P2 实装内容）
  ├── "skills"      工具技能库（⚪ P2，Agent 执行成功案例）
  └── "knowledge"   领域知识库（⚪ P2，向量检索）

  不同 memory_type 完全独立：
  添加 "skills" 不影响 "profile" 的读写逻辑和数据
```

---

## 第二层：LangChain 实现映射

> 将第一层的每个概念映射到具体 LangChain API。
> 标注：✅ 框架内置 · 🔧 自行开发 · ⚡ 胶水代码 · 🔴P0 / ⚪P2

### 2.1 三层记忆 → LangChain API 对照

```
框架无关概念                      LangChain 实现                    归属
──────────────────────────────────────────────────────────────────────
短期记忆
  持久化存储                      AsyncPostgresSaver（checkpointer） ✅ 全自动
  断点恢复（HIL）                  checkpointer 版本链设计           ✅ 全自动
  session 隔离                   thread_id = session_id            ⚡ 胶水

长期记忆
  存储层                         PostgresStore（BaseStore 实现）    ✅ 框架内置存储
  读写逻辑                        MemoryManager                    🔧 自行开发
  turn 开始加载（步骤①）          MemoryMiddleware.before_agent     🔧 自行开发
  每次 LLM 调用前注入（步骤③）    MemoryMiddleware.wrap_model_call  🔧 自行开发
  turn 结束写回（步骤⑧）         MemoryMiddleware.after_agent      🔧 自行开发

工作记忆
  对话历史管理                    AsyncPostgresSaver 自动恢复        ✅ 全自动
  Token 超限压缩                  SummarizationMiddleware           ✅ 全自动
  用户画像 Ephemeral 注入          wrap_model_call + request.override() 🔧 自行开发
  RAG chunk Ephemeral 注入（P2） wrap_model_call + request.override() 🔧 自行开发
```

### 2.2 存储层初始化

```python
# db/postgres.py — ⚡ 胶水代码
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # ✅ 框架内置
from langgraph.store.postgres import PostgresStore                 # ✅ 框架内置
import asyncpg

async def create_stores(db_url: str):
    pool = await asyncpg.create_pool(db_url)
    checkpointer = AsyncPostgresSaver(pool)  # ✅ 短期记忆，全自动
    store        = PostgresStore(pool)       # ✅ 长期记忆存储层
    await checkpointer.setup()              # ✅ 自动建 checkpoint 表
    await store.setup()                     # ✅ 自动建 store 表
    return checkpointer, store
```

### 2.3 MemoryManager

```python
# memory/manager.py — 🔧 自行开发
# 对应框架无关层 §1.3 步骤① 和 步骤⑧ 的具体实现
from langgraph.store.base import BaseStore  # ✅ 框架内置接口

class MemoryManager:
    def __init__(self, store: BaseStore):
        self.store = store

    async def load_episodic(self, user_id: str) -> EpisodicData:
        """读用户画像 — 对应 §1.3 步骤①"""
        item = await self.store.aget(
            namespace=("profile", user_id),  # 对应 §1.5 存储粒度：(user_id, "profile")
            key="episodic",
        )
        return EpisodicData(**item.value) if item else EpisodicData()

    async def save_episodic(self, user_id: str, data: EpisodicData) -> None:
        """写回用户画像 — 对应 §1.3 步骤⑧"""
        await self.store.aput(
            namespace=("profile", user_id),
            key="episodic",
            value=data.model_dump(),
        )

    def build_working_memory(self, ctx: MemoryContext) -> str:
        """构建注入 System Prompt 的记忆文本 — 对应 §1.4 Ephemeral 注入"""
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)
```

### 2.4 MemoryMiddleware（v3.1 修正版）

> v3.1 三处签名修正（已通过 LangChain 官方文档验证）：
> - 修正 A：`before_agent` / `after_agent` 增加 `runtime: Runtime`，返回 `dict | None`
> - 修正 B：`wrap_model_call` 从 `(call_model, state)` 改为 `(request, handler)`，用 `request.override()` 注入
> - 修正 C：`before_agent` 返回 dict 更新 state（Node-style 钩子的正确模式）

```python
# agent/middleware/memory.py — 🔧 自行开发
from __future__ import annotations
from typing import Any, Callable
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage
from langgraph.runtime import Runtime

class MemoryMiddleware(AgentMiddleware):

    def __init__(self, memory_manager: MemoryManager):
        self.mm = memory_manager

    # ─── Node-style 钩子（操作 AgentState）────────────────────────────────
    # 签名：async def hook(self, state, runtime) -> dict | None
    # 对应框架无关层：§1.3 步骤①（before_agent）和步骤⑧（after_agent）

    async def before_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """
        turn 开始时触发一次（整个 ReAct 循环只触发一次）
        加载用户画像到 state["memory_ctx"]
        后续 wrap_model_call 从 state 读缓存，不重复访问数据库
        🔴 P0：load_episodic 返回空 EpisodicData，钩子结构建好即可
        """
        episodic = await self.mm.load_episodic(state["user_id"])
        return {"memory_ctx": MemoryContext(episodic=episodic)}

    async def after_agent(
        self,
        state: AgentState,
        runtime: Runtime,
    ) -> dict[str, Any] | None:
        """
        turn 结束时触发一次

        🔴 P0：空操作（钩子结构建好即可）
        ⚪ P2 第一步：interaction_count +1，验证读写链路
        ⚪ P2 第二步：关键词规则提炼偏好（E签宝场景举例）：
            消息含"合同""签署" → preferences.domain = "legal-tech"
            消息含"A股""茅台"  → preferences.domain = "finance"
            用户使用中文        → preferences.language = "zh"

        TODO Phase 2：引入 dirty flag，对比 before_agent 加载的快照
                     只在画像实际发生变化时才执行 store.aput()，减少无效 IO
        """
        # 🔴 P0：空操作
        return None
        # ⚪ P2：
        # await self.mm.save_episodic(state["user_id"], state["memory_ctx"].episodic)

    # ─── Wrap-style 钩子（包裹 LLM 请求/响应）────────────────────────────
    # 签名：def hook(self, request: ModelRequest, handler) -> ModelResponse
    # ⚠️ 同步方法，不操作 AgentState，通过 request.override() 修改请求
    # 对应框架无关层：§1.3 步骤③ 和 §1.4 Ephemeral 注入策略

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """
        每次 LLM 调用前，Ephemeral 注入用户画像到请求级 System Prompt
        ⚠️ 通过 request.override() 注入，不写入 AgentState
           → 对话历史保持干净（对应 §1.4 的核心原则）
        ⚪ P2：同时注入 RAG chunk（同样 Ephemeral）
        """
        memory_ctx: MemoryContext = request.state.get("memory_ctx", MemoryContext())
        memory_text = self.mm.build_working_memory(memory_ctx)

        if not memory_text:
            return handler(request)

        # 在原有 System Prompt 末尾追加用户画像块
        existing_blocks = list(request.system_message.content_blocks)
        existing_blocks.append({"type": "text", "text": memory_text})

        return handler(request.override(
            system_message=SystemMessage(content=existing_blocks)
        ))
```

### 2.5 数据结构

```python
# memory/schemas.py — 🔧 自行开发

class EpisodicData(BaseModel):
    """
    长期记忆：用户跨会话画像
    对应框架无关层 §1.2 长期记忆
    存储位置：PostgresStore，namespace=("profile", user_id)
    """
    user_id:           str  = ""
    preferences:       dict = {}    # {"domain": "legal-tech", "language": "zh"}
    interaction_count: int  = 0
    summary:           str  = ""


class MemoryContext(BaseModel):
    """
    工作记忆的 turn 级缓存
    对应框架无关层 §1.3 步骤①（before_agent 写入，不持久化到 checkpointer）
    """
    episodic: EpisodicData = EpisodicData()


class AgentState(TypedDict):
    """
    短期记忆的载体：由 checkpointer 自动持久化
    对应框架无关层 §1.2 短期记忆 + §1.5 存储粒度
    """
    messages:     Annotated[list, add_messages]  # ✅ checkpointer 全自动管理
    session_id:   str                            # 短期记忆隔离粒度
    user_id:      str                            # 长期记忆隔离粒度
    memory_ctx:   MemoryContext                  # 请求级缓存，before_agent 注入，不写 checkpointer
    token_usage:  dict
```

### 2.6 存储表设计

```sql
-- ✅ checkpoint 表：AsyncPostgresSaver.setup() 自动建，无需手写
-- ✅ store 表：     PostgresStore.setup() 自动建，无需手写

-- 🔧 唯一需要手建的业务表（对应可观测性模块）
-- 🟡 P1：面试加分项——Supabase Studio 里展示执行日志
create table if not exists agent_traces (
    id            uuid        primary key default gen_random_uuid(),
    session_id    text        not null,
    user_id       text        not null default 'dev_user',
    user_input    text,
    final_answer  text,
    thought_chain jsonb       not null default '[]',
    tool_calls    jsonb       not null default '[]',
    token_usage   jsonb       not null default '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_agent_traces_session on agent_traces(session_id);
create index if not exists idx_agent_traces_user    on agent_traces(user_id);
```

### 2.7 自开发 vs 框架内置

```
✅ 框架内置，配置即用
  AsyncPostgresSaver      短期记忆自动持久化与恢复（含 HIL 断点恢复）
  PostgresStore           长期记忆存储层，namespace 隔离开箱即用
  SummarizationMiddleware 工作记忆 Token 超限时自动压缩历史消息
  AgentMiddleware         Middleware 协议基类（继承即可）

🔧 自行开发
  MemoryMiddleware        before_agent / wrap_model_call / after_agent
  MemoryManager           load_episodic / save_episodic / build_working_memory
  EpisodicData / MemoryContext / AgentState  数据结构定义

TODO（⚪ P2）：
  MemoryMiddleware.after_agent 引入 dirty flag
  对比 before_agent 快照 vs after_agent 时的当前值
  只在画像实际变化时才执行 store.aput()
```

### 2.8 实现优先级

```
🔴 P0（面试前必须跑通）
  ✅ AsyncPostgresSaver + PostgresStore 初始化（db/postgres.py）
  🔧 memory/schemas.py：EpisodicData / MemoryContext / AgentState
  🔧 memory/manager.py：load_episodic（返回空 EpisodicData）/ build_working_memory
  🔧 MemoryMiddleware：
      before_agent   → 加载空 EpisodicData 进 state
      wrap_model_call → 暂时直接透传（无画像可注入）
      after_agent    → 空操作
  验收：第二轮对话能记住第一轮内容（短期记忆跑通）

⚪ P2（面试后做）
  🔧 after_agent 实装写回逻辑（长期记忆读写链路跑通）
  🔧 规则提炼偏好（E签宝场景：法律/金融/语言偏好）
  🔧 wrap_model_call 真正注入用户画像到 System Prompt
  🔧 dirty flag 优化（减少无意义写操作）
```

### 2.9 面试话术

**Q: 你的记忆模块是怎么设计的？**
> "记忆分三层。短期记忆覆盖一个 session 内的对话历史，关键设计是必须持久化到数据库而不是放内存——因为 Agent 执行中途会遇到 HIL 人工确认，等待期间服务可能重启，必须能从断点恢复。长期记忆覆盖跨 session 的用户画像，按 (user_id, 类型) 的粒度隔离，便于后续扩展技能库和知识库而不影响现有数据。工作记忆不是持久存储，是每次 LLM 调用前动态组装的 Context Window，核心设计是 Ephemeral 注入——用户画像每次注入请求但不写入对话历史，否则历史里会不断堆积重复的画像文本，影响 Token 效率和历史压缩质量。"

**Q: 在 LangChain 里怎么实现的？**
> "短期记忆用 `AsyncPostgresSaver` 作为 checkpointer，框架全自动。长期记忆用 `PostgresStore`，我自己实现了 `MemoryManager` 的读写逻辑。关键扩展点是 `MemoryMiddleware`，继承 LangChain 的 `AgentMiddleware`：`before_agent` 在 turn 开始时加载画像缓存进 state；`wrap_model_call` 在每次 LLM 调用前 Ephemeral 注入；`after_agent` 在 turn 结束时写回。Token 超限压缩用 `SummarizationMiddleware` 零配置搞定。"

**Q: 为什么用户画像要 Ephemeral 注入？**
> "如果持久化注入，第一轮写入历史一份画像，第二轮恢复历史时画像已经在里面，再注入又一份，N 轮后历史里有 N 份重复画像。这会严重影响 `SummarizationMiddleware` 的压缩质量，因为压缩时 LLM 看到的是大量重复文本而不是真实对话内容。Ephemeral 注入让对话历史永远只有干净的对话内容。"

**Q: after_agent 每次无条件写回 PostgresStore，性能问题？**
> "P0 阶段无条件写回，实现最简单。优化方向是 dirty flag：before_agent 加载时保存一份画像快照，after_agent 时对比快照和当前值，只有画像真正变化时才执行 store.aput()。大多数 turn 不会触发画像变更，实际写操作频率很低。"
