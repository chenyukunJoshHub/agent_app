# Memory 模块架构设计文档 v5

> **v5 更新说明**（基于 v4 全面修正）
>
> 所有 LangChain / LangGraph API 已通过官方 Reference 验证（2026-03-20）
>
> 当前依赖版本：
> - `langchain` v1.2.13 · `langgraph` v1.1.3 · `langgraph-checkpoint-postgres` v3.0.5（2026-03-18 发布）
>
> 关键变更：
> 1. 连接库修正：`asyncpg` → `psycopg`（LangGraph 使用 Psycopg 3）
> 2. Import 路径修正：对齐官方模块结构
> 3. 状态扩展策略：当前项目优先使用 `middleware.state_schema` 注入自定义 state（`create_agent(state_schema=...)` 仍可用）
> 4. 属性澄清：`SystemMessage.content` 与 `SystemMessage.content_blocks` 均可用（按中间件场景选择）
> 5. 明确 `SummarizationMiddleware` 触发位置：`before_model`（每次 LLM 调用级别）
>
> 文档分两层：
> - **第一层（框架无关）**：概念定义、设计决策、数据流时序 ← 面试先答这层
> - **第二层（LangChain 实现）**：API 映射、伪代码、存储表、优先级 ← 面试再答 / 指导开发

---

## 第一层：框架无关的 Memory 架构

> 本层不出现任何框架名词。用任何语言、任何框架都能实现这个设计。

### 1.1 为什么 Agent 需要三层记忆

LLM 本身无状态——每次 API 调用都是独立请求，没有天然"记忆"。这导致三个问题：

| 问题 | 场景举例 | 解决方案 |
|------|---------|---------|
| 多轮对话失忆 | 第一轮说"查合同123的签署状态"；第二轮说"发邮件提醒" → Agent 不知道提醒哪份合同 | 短期记忆 |
| 跨会话无个性化 | 每次都要重新说"我是合同管理员，请用法律术语" | 长期记忆 |
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
      ✅ 当前实现：aafter_agent 执行写回链路
         · interaction_count +1（有用户交互时）
         · 规则提炼偏好（rule 模式）
         · 可选 LLM 提炼（llm 模式，按 interval 触发）
         · dirty-flag 对比，只有变化时才 store.aput
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

  每次 LLM 调用前：把用户画像前置拼接到最后一条 HumanMessage（request 级）
  调用结束后：只把 Human + AI + Tool 消息写入历史，画像不单独写入
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
  场景举例：
    用户A审核合同的会话 ≠ 用户A管理模板的会话（两个独立 session）

长期记忆隔离单元：(user_id, memory_type)
  memory_type 按类型隔离，支持渐进扩展：
  ├── "profile"     用户画像（🔴 P0 建好结构，⚪ P2 实装内容）
  ├── "skills"      工具技能库（⚪ P2，Agent 执行成功案例）
  └── "knowledge"   领域知识库（⚪ P2，向量检索）

  不同 memory_type 完全独立：
  添加 "skills" 不影响 "profile" 的读写逻辑和数据
```

### 1.6 Workspace 人格记忆分层（IDENTITY / SOUL / USER）

> 本节用于兼容 OpenClaw 的 workspace 约定，将“人格与用户信息”纳入长期记忆设计。  
> 目标：避免把角色设定、行为边界、用户偏好混在一处导致冲突与漂移。

| 文件 | 角色定位 | 变更频率 | 是否写入短期历史 | 推荐持久化方式 |
|------|---------|---------|----------------|---------------|
| `IDENTITY.md` | 外显身份层（Name / Creature / Vibe / Emoji / Avatar） | 低 | ❌ 否 | 文件为主，结构化快照可选 |
| `SOUL.md` | 行为宪法层（Core Truths / Boundaries / Vibe） | 低 | ❌ 否 | 文件为主，规则摘要可选 |
| `USER.md` | 用户模型层（称呼、时区、偏好、当前 Context） | 中高 | ❌ 否（原文）/ ✅ 是（提炼结果） | 文件 + `profile` 命名空间 |

**设计约束（与 §1.4 Ephemeral 策略一致）**

- `IDENTITY.md` / `SOUL.md` / `USER.md` 原文默认按 Ephemeral 注入，不直接写入对话历史。
- 历史中只保留真实 Human/AI/Tool 交互，避免“每轮重复画像文本”污染压缩质量。
- 可持久化的是“提炼后的结构化结果”（如偏好字段、交互计数、规则版本），而非整段原文。

**运行时约束（OpenClaw 语义）**

- 首轮会话可将这些文件注入上下文；缺失文件应降级为“missing marker”，不能导致主链路失败。
- 文件过长会被截断（受 bootstrap/context 字符预算约束）；必须有截断标记与日志。
- 子代理默认不继承 `SOUL.md` / `IDENTITY.md` / `USER.md`：关键边界需镜像到 `AGENTS.md` 或显式写入 task。

**冲突优先级（建议）**

`安全/系统硬约束 > SOUL Boundaries > USER 偏好 > IDENTITY 风格`

> 例：`USER.md` 要求“直接自动发邮件”，若 `SOUL.md` 定义“对外动作需确认”，则必须先确认。

---

## 第二层：LangChain 实现映射

> 将第一层的每个概念映射到具体 LangChain / LangGraph API。
> 标注说明：✅ 框架内置 · 🔧 自行开发 · ⚡ 胶水代码 · 🔴P0 / ⚪P2
> 所有 API 引用附官方 Reference 链接。

### 2.1 三层记忆 → LangChain API 对照

```
框架无关概念                      LangChain 实现                     归属
──────────────────────────────────────────────────────────────────────
短期记忆
  持久化存储                      AsyncPostgresSaver（checkpointer）  ✅ 全自动
  断点恢复（HIL）                  checkpointer 版本链               ✅ 全自动
  session 隔离                   thread_id = session_id             ⚡ 胶水

长期记忆
  存储层                         AsyncPostgresStore（BaseStore 实现） ✅ 框架内置
  读写逻辑                        MemoryManager                     🔧 自行开发
  turn 开始加载（步骤①）          MemoryMiddleware.abefore_agent     🔧 自行开发
  turn 结束写回（步骤⑧）         MemoryMiddleware.aafter_agent      🔧 自行开发
  Workspace 人格文件（P1）         workspace/*.md + MemoryManager     🔧 自行开发

工作记忆
  对话历史管理                    AsyncPostgresSaver 自动恢复         ✅ 全自动
  Token 超限压缩                  SummarizationMiddleware            ✅ 框架内置
  用户画像 Ephemeral 注入         MemoryMiddleware.wrap_model_call    🔧 自行开发
  RAG chunk Ephemeral 注入（P2） wrap_model_call + request.override  🔧 自行开发
  人格/用户文件 Ephemeral 注入（P1）wrap_model_call + request.override 🔧 自行开发
```

> **官方参考**（验证日期 2026-03-20）
> - [AsyncPostgresSaver](https://pypi.org/project/langgraph-checkpoint-postgres/)：`langgraph-checkpoint-postgres` v3.0.5（2026-03-18），使用 Psycopg 3
> - [BaseStore / PostgresStore](https://langchain-ai.github.io/langgraphjs/reference/classes/langgraph-checkpoint-postgres.store.PostgresStore.html)：`put / get / search / delete`，namespace 隔离
> - [AgentMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware)：`langchain` v1.2.13，`before_agent / wrap_model_call / after_agent` 等钩子
> - [SummarizationMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware)：`trigger / keep / model` 参数

### 2.2 state_schema 使用建议（当前项目采用 middleware 方案）

> 现版本（`langchain` v1.2.13）中，`create_agent()` 可同时使用 `middleware` 与 `state_schema`。  
> 当前项目选择将自定义字段通过 `MemoryMiddleware.state_schema` 注入，这是工程约定而非框架硬限制。

```
当前项目方案（A）：
  MemoryMiddleware.state_schema = MemoryState
  create_agent(...) 仅传 context_schema（不再额外传 state_schema）

  优点：
  - state 扩展与中间件职责绑定，代码位置集中
  - 与 SummarizationMiddleware / PolicyHITLMiddleware 等并用时结构清晰

可选方案（B）：
  create_agent(state_schema=CustomAgentState, middleware=[...])
  也可工作；若采用此方案，需保证字段定义与 middleware 逻辑一致
```

### 2.3 存储层初始化

```python
# db/postgres.py — ⚡ 胶水代码

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver   # ✅ 短期记忆
from langgraph.store.postgres import AsyncPostgresStore             # ✅ 长期记忆

DB_URI = "postgresql://user:pass@host:5432/dbname"

async def create_stores():
    # ── 短期记忆：checkpointer ──
    # from_conn_string 返回 async context manager，需要保持生命周期
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(DB_URI)
    checkpointer = await checkpointer_cm.__aenter__()
    await checkpointer.setup()  # ✅ 自动建 checkpoint 相关表

    # ── 长期记忆：store ──
    store_cm = AsyncPostgresStore.from_conn_string(DB_URI)
    store = await store_cm.__aenter__()
    await store.setup()          # ✅ 自动建 store 表

    return checkpointer, store, checkpointer_cm, store_cm
```

> **为什么用 psycopg 而不是 asyncpg？**
> `langgraph-checkpoint-postgres` v3.0.x 内部依赖 Psycopg 3（非 asyncpg）。  
> 使用 `from_conn_string()` 时无需手动传 `autocommit/dict_row/prepare_threshold`；  
> 仅在你自行构造底层 psycopg 连接时才需要显式处理这些参数。
> 来源：[PyPI langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres/)

### 2.4 MemoryManager

```python
# memory/manager.py — 🔧 自行开发
# 对应第一层 §1.3 步骤① 和步骤⑧

from langgraph.store.base import BaseStore  # ✅ 框架内置接口
from app.memory.processors import EpisodicProcessor, ProceduralProcessor

class MemoryManager:
    """长期记忆的读写封装"""

    def __init__(self, store: BaseStore):
        self.store = store
        self.processors = [EpisodicProcessor(), ProceduralProcessor()]

    async def load_episodic(self, user_id: str) -> UserProfile:
        """
        读用户画像 — 对应 §1.3 步骤①
        namespace 对应 §1.5 存储粒度：("profile", user_id)
        """
        items = await self.store.aget(
            namespace=("profile", user_id),
            key="episodic",
        )
        return UserProfile(**items.value) if items else UserProfile()

    async def save_episodic(self, user_id: str, data: UserProfile) -> None:
        """
        写回用户画像 — 对应 §1.3 步骤⑧
        当前实现：由 aafter_agent 决定是否写回（dirty=true 时调用）
        """
        if not user_id:
            return
        payload = data.model_dump()
        if not payload.get("user_id"):
            payload["user_id"] = user_id
        await self.store.aput(
            namespace=("profile", user_id),
            key="episodic",
            value=payload,
        )

    def build_injection_parts(self, ctx: MemoryContext) -> dict[str, str]:
        """
        多 Slot 注入构建（当前主链路）
        返回：{slot_name: text}
        """
        return {p.slot_name: p.build_prompt(ctx) for p in self.processors}

    def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
        """
        兼容接口（已弱化）：仅返回 episodic 注入文本
        实际主链路使用 build_injection_parts()
        """
        return EpisodicProcessor().build_prompt(ctx)
```

> **Store API 说明**
> `BaseStore` 核心方法：`put(namespace, key, value)` / `get(namespace, key)` / `search(namespace, query)` / `delete(namespace, key)`
> 异步版前缀 `a`：`aput` / `aget` / `asearch` / `adelete`
> 来源：[BaseStore API](https://langchain-ai.github.io/langgraphjs/reference/classes/langgraph-checkpoint.BaseStore.html)

### 2.5 MemoryMiddleware（方案 A 实现）

```
执行时序（与 AgentMiddleware 钩子对应）：

┌─ create_agent() 启动 ──────────────────────────────────────────────┐
│                                                                     │
│  MemoryMiddleware.abefore_agent(state, runtime)     ← turn 开始    │
│    │  从 store 加载用户画像                                          │
│    │  return {"memory_ctx": MemoryContext(...)}      ← 写入 state   │
│    ▼                                                                │
│  ┌─ ReAct 循环 ────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  SummarizationMiddleware.abefore_model(state, runtime)       │   │
│  │    │  检查 Token 是否超限 → 超限则压缩历史消息                  │   │
│  │    ▼                                                         │   │
│  │  MemoryMiddleware.wrap_model_call(request, handler)          │   │
│  │    │  从 request.state 读 memory_ctx                         │   │
│  │    │  Ephemeral 注入：request.override(messages=...)         │   │
│  │    ▼                                                         │   │
│  │  handler(request) → LLM 调用                                 │   │
│  │    │                                                         │   │
│  │    ▼  输出 A → 工具执行 → 回到循环顶部                         │   │
│  │    ▼  输出 B → 退出循环                                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  MemoryMiddleware.aafter_agent(state, runtime)      ← turn 结束    │
│    │  ✅ 当前实现：interaction_count 更新 + 偏好提炼 + dirty-flag 写回 │
│    │  ⚪ P2 持续演进：策略细化（如更丰富提炼规则）                    │
│                                                                     │
│  checkpointer 自动保存 state（短期记忆） ← ✅ 框架全自动             │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# agent/middleware/memory.py — 🔧 自行开发

from __future__ import annotations
from typing import Any, TypedDict
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import HumanMessage
# ── 当前项目约定：通过 middleware.state_schema 引入 memory_ctx ─────────
# create_agent(state_schema=...) 仍可用，这里选择把扩展字段与 middleware 聚合管理

class MemoryState(TypedDict, total=False):
    """Middleware 引入的额外 state 字段（不影响框架内置字段）"""
    memory_ctx: MemoryContext   # turn 级缓存，abefore_agent 写入


class MemoryMiddleware(AgentMiddleware):

    state_schema = MemoryState  # ← 方案 A 核心：middleware 声明自己需要的 state 字段

    def __init__(self, memory_manager: MemoryManager):
        self.mm = memory_manager

    # ─── abefore_agent：turn 开始，加载用户画像 ────────────────────
    # 对应第一层 §1.3 步骤①
    # 整个 ReAct 循环只触发一次

    async def abefore_agent(
        self,
        state: Any,
        runtime: Any,
    ) -> dict[str, Any] | None:
        # user_id 从 runtime.context 传入（context_schema）
        user_id = runtime.context.user_id if getattr(runtime, "context", None) else ""
        episodic = await self.mm.load_episodic(user_id)
        # 写入 state，后续 wrap_model_call 从 request.state 读取
        return {"memory_ctx": MemoryContext(episodic=episodic)}

    # ─── wrap_model_call：每次 LLM 调用前，Ephemeral 注入 ─────────
    # 对应第一层 §1.3 步骤③ 和 §1.4 Ephemeral 策略
    # ⚠️ 通过 request.override(messages=...) 注入，不写入 state → 对话历史保持干净

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Any,
    ) -> ModelResponse:
        ctx = request.state.get("memory_ctx") if request.state else None
        if not ctx:
            return handler(request)

        # 统一处理注入片段（episodic / procedural），空片段返回空字符串
        parts = self.mm.build_injection_parts(ctx)
        memory_text = "".join(parts.values())
        if not memory_text:
            return handler(request)

        # 前置拼接到最后一条 HumanMessage（若不存在则追加一条）
        messages = list(request.messages)
        last_human_idx = next(
            (i for i in reversed(range(len(messages))) if isinstance(messages[i], HumanMessage)),
            None,
        )
        if last_human_idx is not None:
            original = messages[last_human_idx]
            original_content = original.content if isinstance(original.content, str) else str(original.content)
            messages[last_human_idx] = HumanMessage(content=memory_text + "\n\n---\n\n" + original_content)
        else:
            messages.append(HumanMessage(content=memory_text))

        return handler(request.override(messages=messages))

    # ─── aafter_agent：turn 结束，写回用户画像 ─────────────────────
    # 对应第一层 §1.3 步骤⑧

    async def aafter_agent(
        self,
        state: Any,
        runtime: Any,
    ) -> dict[str, Any] | None:
        user_id = runtime.context.user_id if getattr(runtime, "context", None) else ""
        ctx = state.get("memory_ctx")
        baseline = state.get("memory_ctx_baseline")
        if not user_id or not ctx:
            return None

        # 1) 更新交互计数
        updated = ctx.episodic.model_copy(deep=True)
        updated.interaction_count += 1

        # 2) 规则提炼（可扩展 llm 模式）
        # if contains("合同", state["messages"]): updated.preferences["domain"] = "legal-tech"

        # 3) dirty-flag：无变化不写库
        if baseline and updated.model_dump() == baseline.model_dump():
            return None

        await self.mm.save_episodic(user_id, updated)
        return None
```

#### OpenClaw Workspace 兼容补充（P1）

> 下列策略用于把 `IDENTITY.md` / `SOUL.md` / `USER.md` 纳入本架构，而不破坏现有 P0 主链路。

```python
# memory/manager.py（扩展建议，P1）

class MemoryManager:
    async def load_workspace_profile(self, workspace_root: str) -> WorkspaceProfile:
        """
        读取 workspace 文件：
        - IDENTITY.md（身份壳）
        - SOUL.md（边界与价值观）
        - USER.md（用户偏好与上下文）
        缺失文件返回 missing marker，不抛异常中断主流程
        """

    def build_workspace_injection(self, profile: WorkspaceProfile) -> dict[str, str]:
        """
        输出可注入片段：
        - persona_identity
        - behavior_boundaries
        - user_context
        所有片段走 Ephemeral 注入，不写入 messages 历史
        """
```

**建议落点**

- `abefore_agent`：加载/缓存 `WorkspaceProfile`（与 episodic 同一 turn 缓存）。
- `wrap_model_call`：将 `WorkspaceProfile` 片段与 `build_injection_parts()` 一并注入。
- `aafter_agent`：仅写回“结构化提炼结果”（如 preference diff / interaction_count），不回写原文。

**子代理兼容**

- 主代理下发子任务时，显式附带最小边界集合（来自 `SOUL.md`）。
- 对必须遵守的硬规则，在 `AGENTS.md` 维持镜像版本，避免子代理上下文缺失。

> **钩子签名来源**
> - `before_agent(state, runtime) -> dict | None`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/before_agent)
> - `wrap_model_call(request, handler) -> ModelResponse`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/wrap_model_call)
> - `after_agent(state, runtime) -> dict | None`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/after_agent)
> - `ModelRequest.override(messages=..., state=...)`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelRequest/override)

### 2.6 SummarizationMiddleware 集成

> 完全替代 v1 的自建 `_maybe_compress()` + `tiktoken` 方案，零自研代码。

```python
# agent/middleware/summarization.py — ✅ 框架内置，仅需配置

from langchain.agents.middleware.summarization import SummarizationMiddleware

summarization = SummarizationMiddleware(
    model="openai:gpt-4o-mini",         # 用小模型做压缩，降低成本

    trigger=("fraction", 0.75),          # Token 超过上下文窗口 75% 时触发
    # 也可多条件 OR：[("fraction", 0.75), ("messages", 50)]

    keep=("messages", 5),                # 压缩后保留最近 5 条消息
    # 也可按 Token：("tokens", 3000)
    # 也可按比例：("fraction", 0.3)
)
```

```
SummarizationMiddleware 工作原理：

  钩子位置：before_model（每次 LLM 调用前）
  ─────────────────────────────────────────────
  检查当前 messages 的 Token 数
        │
        ▼
  超过 trigger 阈值？
        │
    No ─┤─→ 直接放行，不压缩
        │
    Yes ▼
  分离：保留最近 keep 条 + 压缩其余
        │
        ▼
  调用 model 生成摘要（替换旧消息）
        │
        ▼
  返回更新后的 state（messages 已压缩）
```

> **参数对照**（v1 自建 → v5 SummarizationMiddleware）
>
> | v1 自建参数 | v5 SummarizationMiddleware | 说明 |
> |------------|---------------------------|------|
> | `COMPRESSION_THRESHOLD = 0.75` | `trigger=("fraction", 0.75)` | 触发阈值 |
> | `KEEP_RECENT_COUNT = 5` | `keep=("messages", 5)` | 保留条数 |
> | `tiktoken` 手动计数 | `token_counter`（内置近似计数） | Token 统计 |
> | `build_compression_prompt()` | `summary_prompt`（内置默认） | 压缩提示词 |

### 2.7 create_agent 组装

```python
# agent/factory.py — ⚡ 胶水代码（串联全部组件）

from langchain.agents import create_agent

async def build_agent():
    checkpointer, store = await create_stores()

    memory_manager = MemoryManager(store)

    agent = create_agent(
        model="openai:gpt-4o",
        tools=[...],
        prompt="你是一个多工具 AI 助手...",

        # ── 短期记忆 ──
        checkpointer=checkpointer,     # ✅ 对话历史自动持久化 + HIL 断点恢复

        # ── 长期记忆 + 工作记忆 ──
        middleware=[
            MemoryMiddleware(memory_manager),    # 🔧 自建：画像加载 + Ephemeral 注入
            SummarizationMiddleware(             # ✅ 内置：Token 超限自动压缩
                model="openai:gpt-4o-mini",
                trigger=("fraction", 0.75),
                keep=("messages", 5),
            ),
        ],

        # store 不需要传给 create_agent
        # MemoryManager 直接持有 store 引用，middleware 内部调用
    )

    return agent
```

```
调用方式：

# session_id 隔离短期记忆（checkpointer 自动使用 thread_id）
# user_id    通过 context_schema 注入（MemoryMiddleware 从 runtime.context 读取）

config = {"configurable": {"thread_id": session_id}}
context = AgentContext(user_id=user_id, sse_queue=queue)

result = await agent.ainvoke(
    {"messages": [HumanMessage(content="帮我查合同123的签署状态")]},
    config=config,
    context=context,
)
```

### 2.8 完整执行时序（第二层，LangChain 视角）

```
─── FastAPI 收到请求 ─────────────────────────────────────────────────
│  session_id, user_id, message
│
├─ config = { "configurable": { "thread_id": session_id } }
│  context = AgentContext(user_id=..., sse_queue=...)
│
▼  agent.ainvoke(inputs, config)

─── checkpointer 自动恢复 ───────────────────────────────────────────
│  AsyncPostgresSaver 根据 thread_id 查 checkpoint 表
│  恢复上次保存的 state.messages（短期记忆 §1.3 步骤②）
│  新 session → messages 为空
│
▼

─── MemoryMiddleware.abefore_agent ──────────────────────────────────
│  从 runtime.context 获取 user_id
│  调用 store.aget(namespace=("profile", user_id), key="episodic")
│  return {"memory_ctx": MemoryContext(episodic=...)}
│  → 写入 state（长期记忆 §1.3 步骤①）
│
▼

─── ReAct 循环开始 ──────────────────────────────────────────────────
│
│  ┌─ 每次 LLM 调用 ──────────────────────────────────────────────┐
│  │                                                               │
│  │  1. SummarizationMiddleware.abefore_model                     │
│  │     检查 messages Token → 超 75% 则压缩（§1.3 步骤③ 中压缩）  │
│  │                                                               │
│  │  2. MemoryMiddleware.wrap_model_call                          │
│  │     从 request.state["memory_ctx"] 读画像/流程记忆            │
│  │     request.override(messages=...) Ephemeral 注入             │
│  │     （§1.3 步骤③ 中组装 + §1.4 Ephemeral 策略）               │
│  │                                                               │
│  │  3. LLM 调用（§1.3 步骤④）                                    │
│  │     → 工具调用 → 执行 → 结果追加到 messages → 回到 1           │
│  │     → 最终回答 → 退出循环                                      │
│  └───────────────────────────────────────────────────────────────┘
│
▼

─── MemoryMiddleware.aafter_agent ───────────────────────────────────
│  1) 从 state["memory_ctx"] + baseline 计算 updated UserProfile
│  2) 有用户交互时 interaction_count +1
│  3) 规则提炼（domain/language），按 mode/interval 可选 LLM 提炼
│  4) dirty=true 且 user_id 有效时写回：
│       store.aput(namespace=("profile", user_id), key="episodic", ...)
│  5) dirty=false / user_id 缺失时跳过写回（save_skip）
│  （§1.3 步骤⑧）
│
▼

─── checkpointer 自动保存 ──────────────────────────────────────────
│  AsyncPostgresSaver 将 state（含 messages）写入 checkpoint 表
│  ⚠️ memory_ctx 也会随 state 保存，但 abefore_agent 每次 turn 覆盖写入
│  （§1.3 步骤⑦）
│
▼  返回最终回答给 FastAPI
```

### 2.9 数据结构

```python
# memory/schemas.py — 🔧 自行开发

from typing import Any
from pydantic import BaseModel
from pydantic import Field


class UserProfile(BaseModel):
    """
    长期记忆：用户跨会话画像
    对应第一层 §1.2 长期记忆
    存储位置：AsyncPostgresStore，namespace=("profile", user_id)
    """
    user_id: str = ""
    preferences: dict[str, Any] = Field(default_factory=dict)
    interaction_count: int = 0
    summary: str = ""
    content: str = ""


class ProceduralMemory(BaseModel):
    """
    长期记忆：工作流 SOP（当前默认空）
    存储位置：AsyncPostgresStore，namespace=("profile", user_id), key="procedural"
    """
    workflows: dict[str, str] = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """
    工作记忆的 turn 级缓存
    对应第一层 §1.3 步骤①
    生命周期：abefore_agent 创建 → wrap_model_call 读取 → aafter_agent 更新并条件写回
    """
    episodic: UserProfile = Field(default_factory=UserProfile)
    procedural: ProceduralMemory = Field(default_factory=ProceduralMemory)
```

> 说明：`EpisodicData` 在当前代码中仍保留，但定位是“单条情景记忆记录（P2 预留）”，不参与 P0 的用户画像写回链路。

> **与 v4 的关键差异**
>
> v4 主要通过外部 `state_schema` 扩展 `memory_ctx` 字段。  
> v5 在当前项目中改为 `MemoryMiddleware.state_schema = MemoryState`，将扩展字段与中间件实现放在同一处管理。  
> `create_agent(state_schema=...)` 仍可用，这里是工程约定选择，不是框架硬限制。
> 框架内置的 `AgentState` 已包含 `messages` 等字段，middleware 只需声明额外字段。

### 2.10 存储表设计

```sql
-- ✅ checkpoint 表：AsyncPostgresSaver.setup() 自动创建，无需手写
--    包含：checkpoints / checkpoint_blobs / checkpoint_writes / checkpoint_migrations

-- ✅ store 表：AsyncPostgresStore.setup() 自动创建，无需手写
--    包含：store 主表（namespace + key + value JSONB）

-- 🔧 唯一需要手建的业务表（可观测性模块，🟡 P1）
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

### 2.11 自开发 vs 框架内置 总结

```
✅ 框架内置，配置即用
  AsyncPostgresSaver       短期记忆自动持久化与恢复（含 HIL 断点恢复）
  AsyncPostgresStore       长期记忆存储层，namespace 隔离
  SummarizationMiddleware  工作记忆 Token 超限自动压缩
  AgentMiddleware          Middleware 协议基类（继承即可）

🔧 自行开发
  MemoryMiddleware         abefore_agent / wrap_model_call / aafter_agent
  MemoryManager            load_episodic / save_episodic / build_injection_parts
  UserProfile / ProceduralMemory / MemoryContext  数据结构定义
  EpisodicData（单条记录）      P2 预留结构，当前不参与画像写回
  db/postgres.py           存储层初始化胶水代码

⚡ 纯配置
  create_agent(checkpointer=..., middleware=[...])  组装接线
  config["configurable"]                           仅传 thread_id（session 维度）
  context_schema                                   传 user_id / sse_queue 等请求上下文

TODO（⚪ 后续演进）：
  LLM 提炼策略精细化（触发条件、输出约束、回退策略）
  Procedural Memory 自动写回策略（当前以读取/注入为主）
  更细粒度冲突合并策略（多来源偏好覆盖规则）
```

### 2.12 实现优先级

```
🔴 P0（面试前必须跑通）
  ✅ db/postgres.py：AsyncPostgresSaver + AsyncPostgresStore 初始化
  🔧 memory/schemas.py：UserProfile / ProceduralMemory / MemoryContext
  🔧 memory/manager.py：load_episodic（返回空 UserProfile）/ save_episodic / build_injection_parts
  🔧 MemoryMiddleware：
      abefore_agent    → 加载 episodic + procedural + baseline 进 state
      wrap_model_call  → 通过 request.override(messages=...) 做 Ephemeral 注入（无内容时透传）
      aafter_agent     → interaction_count 更新 + 规则/LLM 提炼 + dirty-flag 写回
  ✅ SummarizationMiddleware 配置
  ⚡ create_agent 组装

  验收标准：
    ✓ 第二轮对话能记住第一轮内容（短期记忆 → checkpointer）
    ✓ 长对话触发 Token 压缩（工作记忆 → SummarizationMiddleware）
    ✓ middleware 钩子正常触发（日志可见）

⚪ 后续阶段（面试后持续演进）
  🔧 LLM 提炼策略增强（结构化输出质量、低置信度过滤）
  🔧 Procedural 自动沉淀策略（workflow 发现与回写）
  🔧 跨来源偏好冲突合并策略（规则提炼 vs LLM 提炼）
```

### 2.13 面试话术

**Q: 你的记忆模块是怎么设计的？**
> "记忆分三层。短期记忆覆盖一个 session 内的对话历史，关键设计是必须持久化到数据库而不是放内存——因为 Agent 执行中途会遇到 HIL 人工确认，等待期间服务可能重启，必须能从断点恢复。长期记忆覆盖跨 session 的用户画像，按 (user_id, 类型) 的粒度隔离，便于后续扩展技能库和知识库而不影响现有数据。工作记忆不是持久存储，是每次 LLM 调用前动态组装的 Context Window，核心设计是 Ephemeral 注入——用户画像每次注入请求但不写入对话历史，否则历史里会不断堆积重复的画像文本，影响 Token 效率和历史压缩质量。"

**Q: 在 LangChain 里怎么实现的？**
> "短期记忆用 `AsyncPostgresSaver` 作为 checkpointer，框架全自动管理对话历史和 HIL 断点。长期记忆用 `AsyncPostgresStore`，我自己实现了 `MemoryManager` 封装 namespace 级别的读写。关键扩展点是 `MemoryMiddleware`，继承 `AgentMiddleware`：`abefore_agent` 在 turn 开始时加载画像；`wrap_model_call` 在每次 LLM 调用前通过 `request.override(messages=...)` 做 Ephemeral 注入；`aafter_agent` 在 turn 结束时执行 interaction_count 更新、规则/LLM 提炼，并用 dirty-flag 控制写回。Token 超限压缩用内置的 `SummarizationMiddleware`。"

**Q: 为什么用户画像要 Ephemeral 注入？**
> "如果 Persistent 注入，第一轮写入历史一份画像，第二轮恢复历史时画像已经在里面，再注入又一份，N 轮后历史里有 N 份重复画像。这会影响 `SummarizationMiddleware` 的压缩质量——压缩时 LLM 看到的是大量重复文本而不是真实对话内容。Ephemeral 注入通过 `request.override()` 只在请求级别注入，不写入 state 里的 messages，对话历史永远干净。"

**Q: 为什么这里用 middleware.state_schema，而不是 create_agent(state_schema=...)?**
> "两种方式都可行。我们当前项目选 `MemoryMiddleware.state_schema`，把 `memory_ctx` 字段定义和内存注入逻辑放在同一个中间件里，维护成本更低。这个是工程约定，不是框架强制。"

**Q: after_agent 每次无条件写回，性能问题？**
> "当前实现不是无条件写回。`abefore_agent` 会保存 baseline，`aafter_agent` 对比 baseline 与更新后画像，只有 dirty=true 才 `store.aput()`。再加上 mode/interval 控制，实际写库频率是可控的。"

---

## 附录：v4 → v5 变更日志

| 编号 | v4 内容 | v5 修正 | 原因 / 来源 |
|------|--------|---------|------------|
| 1 | `import asyncpg; asyncpg.create_pool()` | `import psycopg; AsyncPostgresSaver.from_conn_string()` | LangGraph 使用 Psycopg 3，非 asyncpg。[PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) |
| 2 | middleware 导入路径混用 | 当前项目统一：`from langchain.agents.middleware import AgentMiddleware`（`ModelRequest/ModelResponse` 同处导入） | 与仓库实现保持一致，减少样例与代码差异。 |
| 3 | `AgentState` 包含 `memory_ctx`，通过 `state_schema` 传入 | 当前项目采用 `MemoryMiddleware.state_schema = MemoryState` 引入 | 工程约定：字段定义与中间件逻辑聚合；`create_agent(state_schema=...)` 仍可用。 |
| 4 | `request.system_message.content_blocks` | `SystemMessage.content` / `SystemMessage.content_blocks` 均可按场景使用 | 当前实现选择 `request.override(messages=...)` 做 Ephemeral 注入，避免对 system 指令层重复堆叠。 |
| 5 | "Token 超限压缩用 SummarizationMiddleware" 未说明钩子位置 | 明确：`before_model`（每次 LLM 调用级别，非 `before_agent`） | [SummarizationMiddleware Reference](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware) |
| 6 | `PostgresStore(pool)` | `AsyncPostgresStore.from_conn_string()` | 异步场景应使用 `AsyncPostgresStore`。[Store API](https://langchain-ai.github.io/langgraphjs/reference/classes/langgraph-checkpoint-postgres.store.PostgresStore.html) |
