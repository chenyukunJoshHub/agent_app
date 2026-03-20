# CLAUDE.md · Multi-Tool AI Agent 项目约定

> Claude Code 每次启动自动读取本文件。
> **开始任何任务前，必须先完整阅读本文件。**
> 遇到本文件与其他文档冲突时，以本文件为准。

---

## 项目简介

一个基于 LangChain 1.0 + LangGraph 1.0 的多工具 AI Agent。
支持 ReAct 推理、工具调用、多轮对话（Short Memory）、SSE 流式输出、HIL 人工介入。

参考文档（按优先级）：
- 总架构设计：`docs/Multi-Tool AI Agent 完整架构设计文档 v13`
- agent skills 架构设计：`docs/agent skills.md`
- memory 架构设计：`docs/Memory 模块架构设计文档 v5.md`
- Prompt+context 架构设计：`docs/Prompt + Context 模块完整设计文档.md`
- 总计划：`docs/superpowers/specs/2026-03-20-multi-tool-agent-design.md`
- 后端实施：`docs/implementation/backend-implementation-plan.md`（⚠️ 部分代码模板有错误，见下方纠正）
- 数据库设计：`docs/implementation/database-implementation-plan.md`
- 测试策略：`docs/implementation/testing-strategy.md`
- 部署方案：`docs/implementation/2026-03-20-deployment-implementation-plan.md`
- 前端实施：`docs/implementation/frontend-implementation-plan.md`
- 产品方案：`docs/implementation/product-requirements.md`

---

## 技术栈（精确版本）

```
Python          3.11+
FastAPI         0.115+
langchain       1.x（最新稳定版）
langgraph       1.x（最新稳定版）
langgraph-checkpoint-postgres  最新稳定版
psycopg         3.x            ⚠️ 不是 psycopg2，不是 asyncpg
psycopg-pool    3.x
PostgreSQL      16+（Docker）
Node.js         20+
Next.js         14+
Zustand         4.x（前端状态管理）
```

---

## 当前阶段目标：🔴 P0 Only

**只实现 P0 范围，不超前实现 P1 / P2 功能。**

### P0 验收标准

```
1. 用户发消息 → Agent 调用 web_search → SSE 流式返回推理过程和结果
2. 第二轮对话能记住第一轮内容（Short Memory 跑通）
3. 前端能展示工具调用链路（工具名 / 入参 / 结果）
```

### P0 实现步骤（按顺序，不跳步）

```
Step 1   Docker + PostgreSQL 启动，数据库连接验证
Step 2   config.py + .env 配通一个 LLM Provider（优先 DeepSeek，其次 Ollama）
Step 3   db/postgres.py：AsyncPostgresSaver + AsyncPostgresStore 初始化
Step 4   llm/factory.py：单 Provider 版本，不实现 Fallback
Step 5   tools/search.py：web_search（Tavily）
Step 6   agent/middleware/memory.py：MemoryMiddleware（P0 版，after_agent 空操作）
Step 7   agent/middleware/trace.py：TraceMiddleware（after_model 推送 SSE）
Step 8   agent/langchain_engine.py：create_agent 组装
Step 9   agent/finish_handler.py：finish_reason 处理
Step 10  api/chat.py + main.py：POST /chat SSE 接口
Step 11  前端对话界面 + SSE 流式渲染 + 工具调用链路展示
```

每个 Step 完成后运行对应验收命令，通过后再进入下一步。

---

## ✅ 已验证可用的核心 API

以下 API 经过人工验证，直接使用，不要替换：

```python
# ── Agent 创建 ──────────────────────────────────────────────────
from langchain.agents import create_agent

# ── Middleware 基类和内置实现 ────────────────────────────────────
from langchain.agents.middleware import (
    AgentMiddleware,
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
)

# ── Middleware 钩子（AgentMiddleware 子类中重写的方法）──────────
# 正确签名如下，不要用其他签名：
#
#   async def abefore_agent(self, state: Any, runtime: Any) -> dict | None
#       turn 开始时触发，返回 dict 写入 state，返回 None 不改变 state
#
#   def wrap_model_call(self, request: ModelRequest, handler: Callable) -> ModelResponse
#       每次 LLM 调用前触发，用 request.override() 修改请求
#
#   async def aafter_model(self, state: Any, runtime: Any) -> dict | None
#       每次 LLM 调用后触发
#
#   async def aafter_agent(self, state: Any, runtime: Any) -> dict | None
#       turn 结束时触发

# ── 短期记忆（checkpointer）────────────────────────────────────
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# ⚠️ 连接必须用 psycopg3，三个参数缺一不可：
# connection_kwargs={
#     "autocommit": True,
#     "row_factory": dict_row,
#     "prepare_threshold": 0,
# }

# ── 长期记忆（store）───────────────────────────────────────────
from langgraph.store.postgres import AsyncPostgresStore   # ⚠️ Async 前缀

# ── 工具并行调度 ────────────────────────────────────────────────
from langgraph.prebuilt import ToolNode, InjectedState

# ── LLM Provider ────────────────────────────────────────────────
from langchain_ollama import ChatOllama
from langchain_community.chat_models import ChatZhipuAI
from langchain_openai import ChatOpenAI   # 兼容 DeepSeek

# ── 工具定义 ────────────────────────────────────────────────────
from langchain_core.tools import tool
```

---

## ❌ 禁止使用的 API 和写法

```python
# ❌ 已废弃
from langgraph.prebuilt import create_react_agent   # LangGraph 1.0 已废弃

# ❌ 错误的数据库连接库
import asyncpg      # LangGraph 不用 asyncpg，用 psycopg3
import psycopg2     # 用 psycopg（v3），不是 psycopg2

# ❌ 错误的 Store 类名（缺少 Async 前缀）
from langgraph.store.postgres import PostgresStore  # 错误

# ❌ interrupt_on 不是 create_agent 的参数
create_agent(..., interrupt_on={"send_email": True})  # 错误
# ✅ 正确：interrupt_on 是 HumanInTheLoopMiddleware 的参数
HumanInTheLoopMiddleware(interrupt_on={"send_email": True})  # 正确

# ❌ 错误的 Middleware 钩子签名（后端计划文档里写错了，不要照抄）
async def abefore_agent(self, request, handler):  # 错误签名
# ✅ 正确签名
async def abefore_agent(self, state: Any, runtime: Any) -> dict | None:  # 正确

# ❌ 不存在的属性
SystemMessage.content_blocks  # 不存在，用 SystemMessage.content
```

---

## ⚠️ 后端实施计划（docs/implementation/backend-implementation-plan.md）已知错误

以下代码模板有错误，**不要照抄**，以本文件为准：

```
错误 1（Phase 1.4 数据库初始化）：
  计划写的：from asyncpg import connect, Connection
  正确写法：用 psycopg3 + AsyncPostgresSaver.from_conn_string()

错误 2（Phase 1.4 数据库初始化）：
  计划写的：AsyncPostgresStore(conn)
  正确写法：AsyncPostgresStore.from_conn_string(DB_URI)

错误 3（Phase 2.3 Memory Middleware）：
  计划写的：async def abefore_agent(self, request, handler)
  正确写法：async def abefore_agent(self, state: Any, runtime: Any) -> dict | None
```

---

## 关键架构约定

### Short Memory（🔴 P0）

```
- AsyncPostgresSaver 全自动，不手写 save / restore 逻辑
- thread_id = session_id，通过 config={"configurable": {"thread_id": ...}} 传入
- checkpoint 表由 .setup() 自动创建，不手写建表 SQL
- 只保存 HumanMessage + AIMessage，不保存 RAG chunk
```

### Long Memory（⚪ P2，当前不实现）

```
- P0 阶段 MemoryMiddleware 钩子结构建好即可
- abefore_agent：P0 返回 None，不读 store
- aafter_agent：P0 返回 None，不写 store
- wrap_model_call：P0 直接透传 request，不注入用户画像
```

### SSE Event 协议

```json
// thought
{ "type": "thought", "content": "LLM 推理文本" }

// tool_start
{ "type": "tool_start", "tool_name": "web_search", "args": {"query": "..."} }

// tool_result
{ "type": "tool_result", "result": "工具返回内容" }

// done
{ "type": "done", "answer": "最终答案" }

// error
{ "type": "error", "message": "错误信息" }

// hil_interrupt（🟡 P1，当前不实现）
{ "type": "hil_interrupt", "interrupt_id": "uuid", "tool_name": "send_email", "tool_args": {} }
```

### user_id 来源

```
🔴 P0：从请求 body 直接传入，不做鉴权
  { "message": "...", "session_id": "...", "user_id": "dev_user" }

🟡 P1 之后：从 JWT token 解码获取
```

### 工具编写规范

```python
@tool
def web_search(query: str) -> str:
    """
    搜索互联网获取实时信息。
    适用：最新股价、新闻动态、法规变化等实时数据。
    不适用：静态知识、数学计算。
    """
    # description 必须写清楚"适用/不适用"，影响 LLM 选工具的准确率
    # 返回值必须是 str，复杂结果 json.dumps() 序列化
```

---

## 目录结构

```
agent_app/
├── CLAUDE.md                          # 本文件（项目根目录）
├── docs/                              # 设计文档
├── docker-compose.yml
├── .env.example
├── skills/                            # Claude Code 读取的 SKILL.md（根目录）
│   └── langchain-api/
│       └── SKILL.md
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口 + lifespan
│   │   ├── config.py                  # pydantic-settings
│   │   ├── agent/
│   │   │   ├── executor.py            # Agent 主入口
│   │   │   ├── langchain_engine.py    # create_agent 组装
│   │   │   ├── finish_handler.py      # finish_reason 全量处理
│   │   │   ├── error_recovery.py      # 降级兜底
│   │   │   └── middleware/            # ⚠️ 在 agent/ 内部，不在顶层
│   │   │       ├── memory.py          # MemoryMiddleware
│   │   │       └── trace.py           # TraceMiddleware（SSE 推送）
│   │   ├── api/
│   │   │   └── chat.py                # /chat + /chat/resume 路由
│   │   ├── core/
│   │   │   ├── config.py              # 配置读取
│   │   │   ├── logging.py             # 结构化日志
│   │   │   └── session.py             # session_id → thread_id 映射
│   │   ├── db/
│   │   │   ├── client.py              # 连接池单例
│   │   │   └── postgres.py            # AsyncPostgresSaver + AsyncPostgresStore 初始化
│   │   ├── llm/
│   │   │   ├── factory.py             # llm_factory()
│   │   │   ├── ollama_provider.py
│   │   │   ├── zhipu_provider.py
│   │   │   ├── deepseek_provider.py
│   │   │   └── openai_provider.py
│   │   ├── memory/                    # ⚪ P2，P0 建目录占位即可
│   │   │   ├── schemas.py             # EpisodicData / MemoryContext
│   │   │   ├── manager.py             # MemoryManager（P0 空实现）
│   │   │   └── long_term/
│   │   │       └── episodic.py        # P0 空实现；P2 写回逻辑
│   │   ├── prompt/
│   │   │   ├── builder.py             # build_system_prompt()
│   │   │   └── templates.py           # 角色定义 / 行为约束静态模板
│   │   ├── tools/
│   │   │   ├── registry.py            # 工具注册表
│   │   │   ├── base.py                # 工具基类
│   │   │   ├── search.py              # web_search（Tavily）🔴 P0
│   │   │   ├── file.py                # read_file（🟡 P1 Skills 用）
│   │   │   └── send_email.py          # mock 邮件（🟡 P1 HIL 演示）
│   │   ├── skills/                    # Skills Manager 代码（🟡 P1，P0 不建）
│   │   │   ├── manager.py             # SkillManager
│   │   │   ├── registry.py            # SkillRegistry
│   │   │   └── models.py              # SkillDefinition / SkillSnapshot
│   │   ├── observability/
│   │   │   ├── tracer.py              # AgentTrace 写入（🟡 P1）
│   │   │   └── events.py              # SSE Event 类型定义
│   │   └── utils/
│   │       ├── token.py               # Token 计数（tiktoken）
│   │       └── security.py            # 路径校验（read_file 安全）
│   ├── supabase/
│   │   └── migrations/
│   │       ├── 001_agent_traces.sql   # 🔴 P0 手写建表
│   │       ├── 002_users_sessions.sql # 🟡 P1
│   │       └── rollback/
│   ├── requirements.txt
│   └── Dockerfile.dev
│
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   ├── components/
│   │   │   ├── ChatInput.tsx          # 🔴 P0
│   │   │   ├── MessageList.tsx        # 🔴 P0
│   │   │   └── ToolCallTrace.tsx      # 🔴 P0 工具调用链路
│   │   ├── lib/
│   │   │   └── sse-manager.ts         # SSE 连接管理
│   │   ├── store/
│   │   │   └── use-session.ts         # Zustand 状态
│   │   └── types/
│   └── Dockerfile.dev
│
└── tests/
    ├── unit/                          # 🔴 P0 起建
    ├── integration/                   # 🟡 P1
    └── e2e/                           # 🟡 P1
```

---

## 数据库约定

### 建表策略

```
checkpoint 表   →  AsyncPostgresSaver.setup() 自动建，不手写
store 表        →  AsyncPostgresStore.setup() 自动建，不手写
agent_traces 表 →  手写 migration（001_agent_traces.sql）🔴 P0
users / sessions → 手写 migration（002_users_sessions.sql）🟡 P1
约束 / RLS / 复杂索引 → 🟡 P1 后按 database_plan.md 分批实施
```

### P0 最小 Schema

```sql
-- supabase/migrations/001_agent_traces.sql
CREATE TABLE IF NOT EXISTS agent_traces (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    text        NOT NULL,
    user_id       text        NOT NULL DEFAULT 'dev_user',
    user_input    text,
    final_answer  text,
    thought_chain jsonb       NOT NULL DEFAULT '[]',
    tool_calls    jsonb       NOT NULL DEFAULT '[]',
    token_usage   jsonb       NOT NULL DEFAULT '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_user    ON agent_traces(user_id);
```

---

## 每个 Step 的验收命令

```bash
# Step 1  Docker 启动
docker-compose up -d postgres
docker-compose exec postgres pg_isready -U postgres
# 期望：accepting connections

# Step 2-3  配置 + 数据库初始化
cd backend
python -c "
import asyncio
from app.db.postgres import init_db
asyncio.run(init_db())
"
# 期望：checkpointer ready / store ready，无报错

# Step 4  LLM Factory
python -c "
import asyncio
from app.llm.factory import llm_factory
llm = llm_factory()
resp = asyncio.run(llm.ainvoke('hi'))
print(resp.content)
"
# 期望：LLM 返回任意文本，无报错

# Step 5  web_search 工具
python -c "
from app.tools.search import web_search
result = web_search.invoke({'query': '茅台最新股价'})
print(result)
"
# 期望：返回搜索结果文本

# Step 6-9  Agent 主链路
python -c "
import asyncio
from app.agent.executor import run_once
asyncio.run(run_once(
    message='帮我查一下茅台今天的股价',
    session_id='test-001',
    user_id='dev_user'
))
"
# 期望：控制台输出 thought → tool_start → tool_result → done

# Step 10  HTTP 接口
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我查茅台股价","session_id":"s1","user_id":"dev_user"}' \
  --no-buffer
# 期望：SSE 事件流，包含 thought / tool_start / tool_result / done

# Step 11  前端验收（浏览器）
# http://localhost:3000
# 输入：帮我查一下茅台今天的股价 → 看到流式思考链 + 工具调用卡片
# 输入：和昨天比怎么样？         → Agent 记住上轮结果（Short Memory 验证）
```

---

## 优先级速查

```
🔴 P0（面试前，当前阶段）
  web_search 工具
  SSE 流式推送（thought / tool_start / tool_result / done）
  Short Memory（AsyncPostgresSaver，多轮对话历史）
  agent_traces 表建表
  前端对话界面 + 工具调用链路展示

🟡 P1（P0 跑通后，面试加分）
  HIL 完整流程（send_email mock + /chat/resume 接口 + 前端弹窗）
  Long Memory 基础（interaction_count +1，读写链路跑通）
  可观测性（tracer.py 写入 + Supabase Studio 展示）
  多 LLM Provider 完整版 + Fallback

⚪ P2（面试后）
  Long Memory 规则提炼（合同/签署 → domain=legal）
  Skills 插件系统（SkillManager + activate_skill 工具）
  数据库约束 + RLS + 复杂索引（按 database_plan.md）
  完整测试套件（集成 + E2E，按 test_plan.md）
  生产部署（Vercel + Railway + Supabase，按 deploy_plan.md）
```

---

## 项目管理约定

严格遵守用 planning-with-files skill 进行项目管理

每次 session 结束前更新：
```
task_plan.md  →  把本次完成的 Step 打 [x]
findings.md   →  记录 API 验证结论和踩坑
progress.md   →  记录本次 session 做了什么
```

每次新 session 开始，统一用这句话：
> "读取 CLAUDE.md 和 task_plan.md，告诉我当前完成到哪个 Step，然后继续下一个未完成的 Step。每个 Step 完成后更新 task_plan.md，遇到 API 验证结论写入 findings.md。"

---

## 禁止事项

```
❌ 不要一次实现多个 Step，每步跑通验收后再推进
❌ 不要超前实现 P1 / P2 功能
❌ 不要使用 ❌ 禁止 API 列表里的任何 API
❌ 不要直接复制 docs/implementation/backend-implementation-plan.md 里的代码模板（有已知错误）
❌ 不要跳过每 Step 的验收命令
❌ 不要自行发明文档里没有的模块或目录
❌ 不要在 P0 阶段碰 Skills / HIL / Long Memory / Fallback
```

---

## 遇到问题时

```
1. API 是否存在不确定
   → python -c "import module; help(module.ClassName)"  先验证再用

2. 架构决策有疑问
   → 查 总架构设计：`docs/Multi-Tool AI Agent 完整架构设计文档 v13` agent skills 架构设计：`docs/agent skills.md` memory 架构设计：`docs/Memory 模块架构设计文档 v5.md` Prompt+context 架构设计：`docs/Prompt + Context 模块完整设计文档.md` 等架构设计文档的对应章节
   → 不确定就停下来，不要自行决策

3. 运行报错
   → 读完整错误栈，定位到具体文件和行号
   → 将错误现象 + 修复方案写入 .planning/findings.md

4. 代码模板和本文件冲突
   → 以本文件（CLAUDE.md）为准
```