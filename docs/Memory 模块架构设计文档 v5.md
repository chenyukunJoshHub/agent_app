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
> 3. 架构修正：`middleware` + `state_schema` 互斥 → **方案 A**（Middleware 通过 `state_schema` 属性引入自定义 state）
> 4. 属性修正：`SystemMessage.content_blocks` → `SystemMessage.content`
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

工作记忆
  对话历史管理                    AsyncPostgresSaver 自动恢复         ✅ 全自动
  Token 超限压缩                  SummarizationMiddleware            ✅ 框架内置
  用户画像 Ephemeral 注入         MemoryMiddleware.wrap_model_call    🔧 自行开发
  RAG chunk Ephemeral 注入（P2） wrap_model_call + request.override  🔧 自行开发
```

> **官方参考**（验证日期 2026-03-20）
> - [AsyncPostgresSaver](https://pypi.org/project/langgraph-checkpoint-postgres/)：`langgraph-checkpoint-postgres` v3.0.5（2026-03-18），使用 Psycopg 3
> - [BaseStore / PostgresStore](https://langchain-ai.github.io/langgraphjs/reference/classes/langgraph-checkpoint-postgres.store.PostgresStore.html)：`put / get / search / delete`，namespace 隔离
> - [AgentMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware)：`langchain` v1.2.13，`before_agent / wrap_model_call / after_agent` 等钩子
> - [SummarizationMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware)：`trigger / keep / model` 参数

### 2.2 关键约束：middleware 与 state_schema 互斥

> ⚠️ 这是影响架构的框架限制，必须理解。
> 来源：[Issue #33217](https://github.com/langchain-ai/langchain/issues/33217)

```
问题：
  create_agent() 的 middleware 和 state_schema 参数不能同时使用
  → 如果传 middleware=[MemoryMiddleware(...)],
    就不能再传 state_schema=CustomAgentState

影响：
  v4 设计中 AgentState 包含 memory_ctx 字段 → 需要 state_schema
  同时又需要 SummarizationMiddleware → 需要 middleware
  两者冲突 ❌

方案 A（本文档采用）：通过 Middleware 的 state_schema 属性引入自定义 state
  AgentMiddleware 子类可以声明自己的 state_schema 属性
  框架会自动将 middleware 的 state_schema 合并到 Agent 的 state 中
  → 不需要在 create_agent() 传 state_schema
  → 与 SummarizationMiddleware 兼容 ✅
  → state 是 per-invocation 的，无线程安全问题 ✅

  官方推荐："subclass middleware to introduce state"
  来源：https://github.com/langchain-ai/langchain/pull/33263
```

### 2.3 存储层初始化

```python
# db/postgres.py — ⚡ 胶水代码

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver   # ✅ 短期记忆
from langgraph.store.postgres import AsyncPostgresStore             # ✅ 长期记忆
from psycopg.rows import dict_row                                   # ⚠️ 必须 psycopg，不是 asyncpg
import psycopg

DB_URI = "postgresql://user:pass@host:5432/dbname"

async def create_stores():
    # ── 短期记忆：checkpointer ──
    # ⚠️ 三个必填参数：autocommit / dict_row / prepare_threshold
    checkpointer = AsyncPostgresSaver.from_conn_string(
        DB_URI,
        connection_kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
    )
    await checkpointer.setup()  # ✅ 自动建 checkpoint 相关表

    # ── 长期记忆：store ──
    store = AsyncPostgresStore.from_conn_string(DB_URI)
    await store.setup()          # ✅ 自动建 store 表

    return checkpointer, store
```

> **为什么用 psycopg 而不是 asyncpg？**
> `langgraph-checkpoint-postgres` v3.0.x 内部依赖 Psycopg 3（非 asyncpg）。
> 必须配置 `autocommit=True`（`setup()` 需要 DDL 提交）、`dict_row`（行以 dict 格式访问）。
> 来源：[PyPI langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres/)

### 2.4 MemoryManager

```python
# memory/manager.py — 🔧 自行开发
# 对应第一层 §1.3 步骤① 和步骤⑧

from langgraph.store.base import BaseStore  # ✅ 框架内置接口

class MemoryManager:
    """长期记忆的读写封装"""

    def __init__(self, store: BaseStore):
        self.store = store

    async def load_episodic(self, user_id: str) -> EpisodicData:
        """
        读用户画像 — 对应 §1.3 步骤①
        namespace 对应 §1.5 存储粒度：("profile", user_id)
        """
        items = await self.store.aget(
            namespace=("profile", user_id),
            key="episodic",
        )
        return EpisodicData(**items.value) if items else EpisodicData()

    async def save_episodic(self, user_id: str, data: EpisodicData) -> None:
        """
        写回用户画像 — 对应 §1.3 步骤⑧
        🔴 P0：空操作   ⚪ P2：实装
        """
        await self.store.aput(
            namespace=("profile", user_id),
            key="episodic",
            value=data.model_dump(),
        )

    def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
        """
        构建 Ephemeral 注入文本 — 对应 §1.4
        返回空字符串则不注入
        """
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)
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
│  │    │  Ephemeral 注入：request.override(system_message=...)   │   │
│  │    ▼                                                         │   │
│  │  handler(request) → LLM 调用                                 │   │
│  │    │                                                         │   │
│  │    ▼  输出 A → 工具执行 → 回到循环顶部                         │   │
│  │    ▼  输出 B → 退出循环                                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  MemoryMiddleware.aafter_agent(state, runtime)      ← turn 结束    │
│    │  🔴 P0：空操作                                                 │
│    │  ⚪ P2：写回用户画像                                            │
│                                                                     │
│  checkpointer 自动保存 state（短期记忆） ← ✅ 框架全自动             │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# agent/middleware/memory.py — 🔧 自行开发

from __future__ import annotations
from typing import Any, TypedDict
from langchain.agents.middleware.types import (      # ← v5 修正后的 import 路径
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import SystemMessage

# ── 方案 A：通过 middleware 的 state_schema 引入 memory_ctx ──────────
# 解决 create_agent() 中 middleware + state_schema 互斥问题
# 框架会自动将此 schema 合并到 Agent 的 state 中

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
        # user_id 从调用配置 configurable 传入
        user_id = runtime.config["configurable"].get("user_id", "")
        episodic = await self.mm.load_episodic(user_id)
        # 写入 state，后续 wrap_model_call 从 request.state 读取
        return {"memory_ctx": MemoryContext(episodic=episodic)}

    # ─── wrap_model_call：每次 LLM 调用前，Ephemeral 注入 ─────────
    # 对应第一层 §1.3 步骤③ 和 §1.4 Ephemeral 策略
    # ⚠️ 通过 request.override() 注入，不写入 state → 对话历史保持干净

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Any,
    ) -> ModelResponse:
        ctx = request.state.get("memory_ctx") if request.state else None
        if not ctx:
            return handler(request)

        memory_text = self.mm.build_ephemeral_prompt(ctx)
        if not memory_text:
            return handler(request)

        # 在原有 System Prompt 末尾追加用户画像（Ephemeral，不进历史）
        existing = request.system_message
        new_content = (existing.content + memory_text) if existing else memory_text

        return handler(request.override(
            system_message=SystemMessage(content=new_content),
        ))

    # ─── aafter_agent：turn 结束，写回用户画像 ─────────────────────
    # 对应第一层 §1.3 步骤⑧

    async def aafter_agent(
        self,
        state: Any,
        runtime: Any,
    ) -> dict[str, Any] | None:
        # 🔴 P0：空操作，钩子结构建好即可
        return None
        # ⚪ P2 实装：
        # user_id = runtime.config["configurable"].get("user_id", "")
        # ctx = state.get("memory_ctx")
        # if ctx and ctx.episodic.preferences:
        #     await self.mm.save_episodic(user_id, ctx.episodic)
```

> **钩子签名来源**
> - `before_agent(state, runtime) -> dict | None`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/before_agent)
> - `wrap_model_call(request, handler) -> ModelResponse`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/wrap_model_call)
> - `after_agent(state, runtime) -> dict | None`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/after_agent)
> - `ModelRequest.override(system_message=..., state=...)`：[官方 Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelRequest/override)

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
# user_id    隔离长期记忆（MemoryMiddleware 从 configurable 读取）

config = {
    "configurable": {
        "thread_id": session_id,
        "user_id":   user_id,
    }
}

result = await agent.ainvoke(
    {"messages": [HumanMessage(content="帮我查合同123的签署状态")]},
    config,
)
```

### 2.8 完整执行时序（第二层，LangChain 视角）

```
─── FastAPI 收到请求 ─────────────────────────────────────────────────
│  session_id, user_id, message
│
├─ config = { "configurable": { "thread_id": session_id, "user_id": user_id } }
│
▼  agent.ainvoke(inputs, config)

─── checkpointer 自动恢复 ───────────────────────────────────────────
│  AsyncPostgresSaver 根据 thread_id 查 checkpoint 表
│  恢复上次保存的 state.messages（短期记忆 §1.3 步骤②）
│  新 session → messages 为空
│
▼

─── MemoryMiddleware.abefore_agent ──────────────────────────────────
│  从 runtime.config 获取 user_id
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
│  │     从 request.state["memory_ctx"] 读画像                     │
│  │     request.override(system_message=...) Ephemeral 注入       │
│  │     （§1.3 步骤③ 中组装 + §1.4 Ephemeral 策略）               │
│  │                                                               │
│  │  3. LLM 调用（§1.3 步骤④）                                    │
│  │     → 工具调用 → 执行 → 结果追加到 messages → 回到 1           │
│  │     → 最终回答 → 退出循环                                      │
│  └───────────────────────────────────────────────────────────────┘
│
▼

─── MemoryMiddleware.aafter_agent ───────────────────────────────────
│  🔴 P0：return None
│  ⚪ P2：store.aput(namespace=("profile", user_id), ...)
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

from pydantic import BaseModel


class EpisodicData(BaseModel):
    """
    长期记忆：用户跨会话画像
    对应第一层 §1.2 长期记忆
    存储位置：AsyncPostgresStore，namespace=("profile", user_id)
    """
    user_id:           str  = ""
    preferences:       dict = {}    # {"domain": "legal-tech", "language": "zh"}
    interaction_count: int  = 0
    summary:           str  = ""


class MemoryContext(BaseModel):
    """
    工作记忆的 turn 级缓存
    对应第一层 §1.3 步骤①
    生命周期：abefore_agent 创建 → wrap_model_call 读取 → aafter_agent 清理
    """
    episodic: EpisodicData = EpisodicData()
```

> **与 v4 的关键差异**
>
> v4 定义了 `AgentState(TypedDict)` 包含 `memory_ctx` 字段，通过 `state_schema` 传入 → 与 middleware 冲突。
> v5 不再自定义 `AgentState`，改为 `MemoryMiddleware.state_schema = MemoryState` 引入。
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
  MemoryManager            load_episodic / save_episodic / build_ephemeral_prompt
  EpisodicData / MemoryContext  数据结构定义
  db/postgres.py           存储层初始化胶水代码

⚡ 纯配置
  create_agent(checkpointer=..., middleware=[...])  组装接线
  config["configurable"]                           session_id / user_id 传入

TODO（⚪ P2）：
  MemoryMiddleware.aafter_agent 实装写回逻辑
  规则提炼偏好（关键词 → preferences）
  dirty flag 优化（对比快照，减少无意义写操作）
```

### 2.12 实现优先级

```
🔴 P0（面试前必须跑通）
  ✅ db/postgres.py：AsyncPostgresSaver + AsyncPostgresStore 初始化
  🔧 memory/schemas.py：EpisodicData / MemoryContext
  🔧 memory/manager.py：load_episodic（返回空 EpisodicData）/ build_ephemeral_prompt
  🔧 MemoryMiddleware：
      abefore_agent    → 加载空 EpisodicData 进 state
      wrap_model_call  → 暂时直接透传（无画像可注入）
      aafter_agent     → 空操作
  ✅ SummarizationMiddleware 配置
  ⚡ create_agent 组装

  验收标准：
    ✓ 第二轮对话能记住第一轮内容（短期记忆 → checkpointer）
    ✓ 长对话触发 Token 压缩（工作记忆 → SummarizationMiddleware）
    ✓ middleware 钩子正常触发（日志可见）

⚪ P2（面试后做）
  🔧 aafter_agent 实装写回逻辑（长期记忆读写链路跑通）
  🔧 规则提炼偏好（消息含"合同""签署" → domain: "legal-tech"）
  🔧 wrap_model_call 真正注入用户画像到 System Prompt
  🔧 dirty flag 优化（减少无意义写操作）
```

### 2.13 面试话术

**Q: 你的记忆模块是怎么设计的？**
> "记忆分三层。短期记忆覆盖一个 session 内的对话历史，关键设计是必须持久化到数据库而不是放内存——因为 Agent 执行中途会遇到 HIL 人工确认，等待期间服务可能重启，必须能从断点恢复。长期记忆覆盖跨 session 的用户画像，按 (user_id, 类型) 的粒度隔离，便于后续扩展技能库和知识库而不影响现有数据。工作记忆不是持久存储，是每次 LLM 调用前动态组装的 Context Window，核心设计是 Ephemeral 注入——用户画像每次注入请求但不写入对话历史，否则历史里会不断堆积重复的画像文本，影响 Token 效率和历史压缩质量。"

**Q: 在 LangChain 里怎么实现的？**
> "短期记忆用 `AsyncPostgresSaver` 作为 checkpointer，框架全自动管理对话历史和 HIL 断点。长期记忆用 `AsyncPostgresStore`，我自己实现了 `MemoryManager` 封装 namespace 级别的读写。关键扩展点是 `MemoryMiddleware`，继承 `AgentMiddleware`：`abefore_agent` 在 turn 开始时加载画像到 state；`wrap_model_call` 在每次 LLM 调用前通过 `request.override()` Ephemeral 注入；`aafter_agent` 在 turn 结束时写回。Token 超限压缩用内置的 `SummarizationMiddleware`，配置 `trigger` 和 `keep` 即可，不用自己写压缩逻辑。"

**Q: 为什么用户画像要 Ephemeral 注入？**
> "如果 Persistent 注入，第一轮写入历史一份画像，第二轮恢复历史时画像已经在里面，再注入又一份，N 轮后历史里有 N 份重复画像。这会影响 `SummarizationMiddleware` 的压缩质量——压缩时 LLM 看到的是大量重复文本而不是真实对话内容。Ephemeral 注入通过 `request.override()` 只在请求级别注入，不写入 state 里的 messages，对话历史永远干净。"

**Q: middleware 和 state_schema 冲突怎么解决的？**
> "LangChain 的 `create_agent()` 不允许同时传 middleware 和 state_schema。官方推荐的做法是通过 middleware 子类的 `state_schema` 属性引入自定义 state。我让 `MemoryMiddleware` 声明自己的 `state_schema`，框架自动合并到 Agent 的 state 里。这样既能用 `SummarizationMiddleware`，又能在 state 里存 `memory_ctx`。"

**Q: after_agent 每次无条件写回，性能问题？**
> "P0 阶段 `aafter_agent` 是空操作，不写回。P2 实装后，优化方向是 dirty flag：`abefore_agent` 加载时保存一份画像快照，`aafter_agent` 时对比快照和当前值，只有画像真正变化时才执行 `store.aput()`。大多数 turn 不会触发画像变更，实际写操作频率很低。"

---

## 附录：v4 → v5 变更日志

| 编号 | v4 内容 | v5 修正 | 原因 / 来源 |
|------|--------|---------|------------|
| 1 | `import asyncpg; asyncpg.create_pool()` | `import psycopg; AsyncPostgresSaver.from_conn_string()` | LangGraph 使用 Psycopg 3，非 asyncpg。[PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) |
| 2 | `from langchain.agents.middleware import AgentMiddleware` | `from langchain.agents.middleware.types import AgentMiddleware` | 对齐官方模块路径。[Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware) |
| 3 | `AgentState` 包含 `memory_ctx`，通过 `state_schema` 传入 | `MemoryMiddleware.state_schema = MemoryState` 引入 | `middleware` + `state_schema` 互斥。[Issue #33217](https://github.com/langchain-ai/langchain/issues/33217) |
| 4 | `request.system_message.content_blocks` | `request.system_message.content` | `SystemMessage` 的属性是 `.content`（str \| list），无 `.content_blocks`。[Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelRequest/override) |
| 5 | "Token 超限压缩用 SummarizationMiddleware" 未说明钩子位置 | 明确：`before_model`（每次 LLM 调用级别，非 `before_agent`） | [SummarizationMiddleware Reference](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware) |
| 6 | `PostgresStore(pool)` | `AsyncPostgresStore.from_conn_string()` | 异步场景应使用 `AsyncPostgresStore`。[Store API](https://langchain-ai.github.io/langgraphjs/reference/classes/langgraph-checkpoint-postgres.store.PostgresStore.html) |
