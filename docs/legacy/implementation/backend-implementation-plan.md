# Multi-Tool AI Agent - 后端实施计划

**文档版本**: v1.0
**创建日期**: 2026-03-20
**预计工期**: 1-2个月（分阶段实施）
**技术栈**: FastAPI + LangGraph + PostgreSQL + Ollama

---

## 目录

1. [项目结构设计](#项目结构设计)
2. [Phase 1: 基础设施](#phase-1-基础设施)
3. [Phase 2: Memory 系统](#phase-2-memory-系统)
4. [Phase 3: Skills 系统](#phase-3-skills-系统)
5. [Phase 4: HIL 机制](#phase-4-hil-机制)
6. [Phase 5: SSE 流式推送](#phase-5-sse-流式推送)
7. [安全加固要求](#安全加固要求)
8. [验收标准汇总](#验收标准汇总)

---

## 项目结构设计

### 最终目录结构

```
backend/
├── main.py                          # FastAPI 入口
├── config.py                        # 配置管理
├── requirements.txt                 # 依赖列表
├── pyproject.toml                   # 项目配置
├── .env.example                     # 环境变量模板
│
├── agent/                           # Agent 核心逻辑
│   ├── __init__.py
│   ├── graph.py                     # LangGraph 定义
│   ├── nodes.py                     # ReAct 节点
│   ├── executor.py                  # Agent 执行器
│   ├── langchain_engine.py          # LangChain 引擎组装
│   ├── finish_handler.py            # finish_reason 处理
│   └── middleware/                  # 中间件
│       ├── __init__.py
│       ├── base.py                  # 中间件基类
│       ├── memory.py                # Memory 中间件
│       ├── trace.py                 # Trace 中间件
│       └── hil.py                   # HIL 中间件
│
├── llm/                             # LLM Factory
│   ├── __init__.py
│   ├── factory.py                   # LLM 工厂
│   ├── ollama_provider.py           # Ollama Provider
│   ├── zhipu_provider.py            # 智谱 Provider
│   ├── deepseek_provider.py         # DeepSeek Provider
│   └── openai_provider.py           # OpenAI Provider
│
├── memory/                          # Memory 管理
│   ├── __init__.py
│   ├── manager.py                   # Memory Manager
│   ├── schemas.py                   # 数据模型
│   └── long_term/
│       ├── __init__.py
│       ├── episodic.py              # 情景记忆
│       ├── procedural.py            # 程序记忆（预留）
│       └── semantic.py              # 语义记忆（预留）
│
├── skills/                          # Skill Manager
│   ├── __init__.py
│   ├── manager.py                   # Skill Manager
│   ├── registry.py                  # Skill 注册表
│   └── models.py                    # Skill 数据模型
│
├── tools/                           # 工具实现
│   ├── __init__.py
│   ├── registry.py                  # 工具注册表
│   ├── base.py                      # 工具基类
│   ├── file.py                      # read_file
│   ├── web.py                       # fetch_url
│   ├── search.py                    # web_search
│   ├── csv_analyze.py               # CSV 分析
│   └── send_email.py                # 邮件发送（HIL 演示）
│
├── prompt/                          # Prompt 管理
│   ├── __init__.py
│   ├── builder.py                   # Prompt 构建器
│   └── templates.py                 # 静态模板
│
├── db/                              # 数据库
│   ├── __init__.py
│   ├── client.py                    # 数据库客户端
│   ├── postgres.py                  # PostgreSQL 连接
│   └── schema.sql                   # 数据库 Schema
│
├── observability/                   # 可观测性
│   ├── __init__.py
│   ├── tracer.py                    # 执行追踪
│   └── store.py                     # 追踪存储
│
├── session/                         # 会话管理
│   ├── __init__.py
│   └── manager.py                   # Session Manager
│
├── utils/                           # 工具函数
│   ├── __init__.py
│   ├── token.py                     # Token 计数
│   ├── logging.py                   # 日志配置
│   └── security.py                  # 安全工具
│
└── tests/                           # 测试
    ├── __init__.py
    ├── conftest.py                  # Pytest 配置
    ├── test_agent.py                # Agent 测试
    ├── test_memory.py               # Memory 测试
    ├── test_tools.py                # 工具测试
    └── test_api.py                  # API 测试
```

---

## Phase 1: 基础设施

**优先级**: 🔴 P0（面试必须）
**预计工期**: 1-2 周
**工作量**: 40-60 小时

### 1.1 项目脚手架搭建

**任务描述**: 创建项目基础结构、配置文件和依赖管理

**涉及文件**:
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `backend/.env.example`
- `backend/config.py`

**工作量**: 4 小时

**依赖**: 无

**验收标准**:
- [ ] 依赖可正常安装
- [ ] 环境变量可正确加载
- [ ] 配置类可访问所有必需项

**代码模板**:

```python
# backend/requirements.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
langchain>=0.1.0
langgraph>=0.0.40
langchain-ollama>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.1.0
psycopg[binary]>=3.1.0
asyncpg>=0.29.0
tiktoken>=0.5.0
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.25.0
aiofiles>=23.0.0

# 测试
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

```python
# backend/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # LLM 配置
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "glm-4"
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-flash"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_fallback_provider: str = "zhipu"

    # 工具配置
    tavily_api_key: str = ""

    # 数据库配置
    database_url: str = "postgresql://postgres:postgres@localhost:54322/agent_db"

    # Memory 配置
    enable_long_term_memory: bool = True
    enable_episodic_memory: bool = True
    enable_semantic_memory: bool = False

    # Agent 安全
    max_iterations: int = 10
    max_execution_time: int = 60
    enable_checkpoint: bool = True
    enable_human_in_loop: bool = False

    # 可观测性
    enable_trace: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

---

### 1.2 FastAPI 入口文件

**任务描述**: 创建 FastAPI 应用入口，包含 CORS、中间件配置

**涉及文件**:
- `backend/main.py`

**工作量**: 6 小时

**依赖**: 1.1

**验收标准**:
- [ ] 服务器可正常启动
- [ ] 健康检查接口可访问
- [ ] CORS 配置正确
- [ ] SSE 端点框架就绪

**代码模板**:

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import get_settings
from db.postgres import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    await init_db()
    yield
    # 关闭时清理

app = FastAPI(
    title="Multi-Tool AI Agent",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 路由将在后续阶段添加
# app.include_router(chat.router, prefix="/api")
```

---

### 1.3 LLM Factory 实现

**任务描述**: 实现多 Provider 支持的 LLM 工厂

**涉及文件**:
- `backend/llm/factory.py`
- `backend/llm/ollama_provider.py`
- `backend/llm/zhipu_provider.py`

**工作量**: 12 小时

**依赖**: 1.1, 1.2

**验收标准**:
- [ ] 支持至少 2 个 Provider
- [ ] Fallback 机制工作正常
- [ ] 模型切换无需重启

**代码模板**:

```python
# backend/llm/factory.py
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatZhipuAI
from config import Settings
from typing import Literal

ProviderType = Literal["ollama", "zhipu", "deepseek", "openai"]

class LLMFactory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._current_provider: ProviderType = settings.llm_provider

    def create_llm(self, provider: ProviderType | None = None):
        provider = provider or self._current_provider

        if provider == "ollama":
            return ChatOllama(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                temperature=0.7
            )
        elif provider == "zhipu":
            return ChatZhipuAI(
                model=self.settings.zhipu_model,
                api_key=self.settings.zhipu_api_key,
                temperature=0.7
            )
        elif provider == "deepseek":
            return ChatOpenAI(
                model=self.settings.deepseek_model,
                api_key=self.settings.deepseek_api_key,
                base_url="https://api.deepseek.com/v1",
                temperature=0.7
            )
        elif provider == "openai":
            return ChatOpenAI(
                model=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                temperature=0.7
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def create_with_fallback(self):
        """创建带 Fallback 的 LLM"""
        primary = self.create_llm(self._current_provider)
        fallback = self.create_llm(self.settings.llm_fallback_provider)
        return primary.with_fallbacks([fallback])

def get_llm_factory(settings: Settings | None = None) -> LLMFactory:
    from config import get_settings
    settings = settings or get_settings()
    return LLMFactory(settings)
```

---

### 1.4 数据库初始化

**任务描述**: 配置 PostgreSQL 连接，创建必要的表

**涉及文件**:
- `backend/db/postgres.py`
- `backend/db/schema.sql`

**工作量**: 8 小时

**依赖**: 1.1

**验收标准**:
- [ ] AsyncPostgresSaver 初始化成功
- [ ] PostgresStore 初始化成功
- [ ] agent_traces 表创建成功

**代码模板**:

```python
# backend/db/postgres.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import PostgresStore
from asyncpg import connect, Connection
from config import get_settings

_checkpointer: AsyncPostgresSaver | None = None
_store: PostgresStore | None = None

async def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        settings = get_settings()
        conn = await connect(settings.database_url)
        _checkpointer = AsyncPostgresSaver(conn)
        await _checkpointer.setup()  # 自动创建 checkpoint 表
    return _checkpointer

async def get_store() -> PostgresStore:
    global _store
    if _store is None:
        settings = get_settings()
        _store = PostgresStore(conn)
        await _store.setup()  # 自动创建 store 表
    return _store

async def init_db():
    """初始化数据库"""
    await get_checkpointer()
    await get_store()
    # 创建 agent_traces 表（手动 migration）
    await _create_agent_traces_table()

async def _create_agent_traces_table():
    """创建 agent_traces 表"""
    conn = await connect(get_settings().database_url)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_traces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            user_input TEXT,
            final_answer TEXT,
            thought_chain JSONB NOT NULL DEFAULT '[]',
            tool_calls JSONB NOT NULL DEFAULT '[]',
            token_usage JSONB NOT NULL DEFAULT '{}',
            latency_ms INTEGER NOT NULL,
            finish_reason TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    # 创建索引...
```

---

### 1.5 基础工具实现

**任务描述**: 实现 read_file, fetch_url, token_counter 三个核心工具

**涉及文件**:
- `backend/tools/registry.py`
- `backend/tools/base.py`
- `backend/tools/file.py`
- `backend/tools/web.py`
- `backend/utils/token.py`

**工作量**: 10 小时

**依赖**: 1.1

**验收标准**:
- [ ] read_file 只能访问 skills 目录
- [ ] fetch_url 支持超时控制
- [ ] token_counter 使用 tiktoken 精确计数

**代码模板**:

```python
# backend/tools/base.py
from langchain_core.tools import BaseTool
from typing import Any, Type
from pydantic import BaseModel

class InjectedState:
    """工具可访问的 AgentState"""
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id

class AgentTool(BaseTool):
    """所有工具的基类"""
    state: InjectedState | None = None

    def set_state(self, state: InjectedState):
        self.state = state

# backend/tools/file.py
from pathlib import Path
from .base import AgentTool

ALLOWED_DIRS = [
    Path.cwd() / "skills",
    Path.home() / ".agents" / "skills"
]

def read_file(path: str) -> str:
    """读取文件内容（仅限 skills 目录）"""
    full_path = Path(path).expanduser().resolve()

    # 安全检查
    if not any(full_path.is_relative_to(d.resolve()) for d in ALLOWED_DIRS):
        raise PermissionError(f"路径不在允许范围内: {path}")

    return full_path.read_text(encoding='utf-8')
```

---

## Phase 2: Memory 系统

**优先级**: 🔴 P0（面试必须）
**预计工期**: 1 周
**工作量**: 30-40 小时

### 2.1 Memory 数据模型

**任务描述**: 定义 Memory 相关的数据结构

**涉及文件**:
- `backend/memory/schemas.py`

**工作量**: 6 小时

**依赖**: 1.4

**验收标准**:
- [ ] AgentState 定义完整
- [ ] EpisodicData 支持序列化
- [ ] MemoryContext 包含所有必需字段

**代码模板**:

```python
# backend/memory/schemas.py
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class EpisodicData(TypedDict):
    """情景记忆：用户画像"""
    preferences: dict[str, str]  # domain, language, style
    interaction_count: int
    summary: str
    created_at: str

class MemoryContext(TypedDict):
    """Memory 上下文"""
    episodic: EpisodicData | None

class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[list, add_messages]
    session_id: str
    user_id: str
    memory_ctx: MemoryContext
```

---

### 2.2 Memory Manager

**任务描述**: 实现 Memory 读写逻辑

**涉及文件**:
- `backend/memory/manager.py`

**工作量**: 8 小时

**依赖**: 2.1

**验收标准**:
- [ ] load_episodic 从 PostgresStore 读取
- [ ] save_episodic 写回 PostgresStore
- [ ] build_working_memory 组装完整 Context

**代码模板**:

```python
# backend/memory/manager.py
from langgraph.store.base import BaseStore
from .schemas import EpisodicData, MemoryContext

class MemoryManager:
    def __init__(self, store: BaseStore):
        self.store = store

    async def load_episodic(self, user_id: str) -> EpisodicData:
        """加载用户画像"""
        item = await self.store.aget(
            namespace=("episodic", user_id),
            key="profile"
        )
        return item.value if item else {
            "preferences": {},
            "interaction_count": 0,
            "summary": "",
            "created_at": ""
        }

    async def save_episodic(self, user_id: str, data: EpisodicData):
        """保存用户画像"""
        await self.store.aput(
            namespace=("episodic", user_id),
            key="profile",
            value=data
        )

    def build_working_memory(
        self,
        episodic: EpisodicData,
        messages: list,
        system_prompt: str
    ) -> str:
        """组装 Working Memory"""
        # 简化版，完整版需考虑 Token 预算
        parts = [system_prompt]
        if episodic.get("summary"):
            parts.append(f"用户画像: {episodic['summary']}")
        parts.extend([msg.content for msg in messages[-10:]])
        return "\n\n".join(parts)
```

---

### 2.3 Memory Middleware

**任务描述**: 实现 Memory 中间件钩子

**涉及文件**:
- `backend/agent/middleware/memory.py`

**工作量**: 12 小时

**依赖**: 2.2

**验收标准**:
- [ ] before_agent 加载用户画像
- [ ] wrap_model_call 注入用户画像
- [ ] after_agent 写回用户画像

**代码模板**:

```python
# backend/agent/middleware/memory.py
from langchain_core.messages import SystemMessage
from langchain.agents.middleware import AgentMiddleware
from ..memory.manager import MemoryManager
from ..memory.schemas import MemoryContext

class MemoryMiddleware(AgentMiddleware):
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    async def abefore_agent(self, request, handler):
        """Turn 开始，加载用户画像"""
        user_id = request.runtime.context.get("user_id", "")

        episodic = await self.memory_manager.load_episodic(user_id)
        request.state["memory_ctx"] = MemoryContext(
            episodic=episodic
        )

        return await handler(request)

    async def awrap_model_call(self, request, handler):
        """LLM 调用前，注入用户画像"""
        memory_ctx: MemoryContext = request.state.get("memory_ctx", {})
        episodic = memory_ctx.get("episodic", {})

        if episodic.get("summary"):
            original_sys = request.system_message.content
            new_sys = original_sys + "\n\n用户画像:\n" + episodic["summary"]
            request = request.override(
                system_message=SystemMessage(content=new_sys)
            )

        return await handler(request)

    async def aafter_agent(self, request, handler):
        """Turn 结束，写回用户画像"""
        memory_ctx: MemoryContext = request.state.get("memory_ctx", {})
        episodic = memory_ctx.get("episodic", {})

        # 🔴 P0: 空操作，仅验证钩子结构
        # ⚪ P2: interaction_count += 1
        user_id = request.runtime.context.get("user_id", "")
        # await self.memory_manager.save_episodic(user_id, episodic)

        return await handler(request)
```

---

### 2.4 LangGraph 集成

**任务描述**: 创建 Agent Graph，集成 Middleware

**涉及文件**:
- `backend/agent/graph.py`
- `backend/agent/nodes.py`
- `backend/agent/langchain_engine.py`

**工作量**: 14 小时

**依赖**: 2.3, 1.3

**验收标准**:
- [ ] create_agent 成功创建 ReAct 循环
- [ ] SummarizationMiddleware 自动压缩
- [ ] invoke 和 astream 方法可用

**代码模板**:

```python
# backend/agent/langchain_engine.py
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.prebuilt import ToolNode
from .middleware.memory import MemoryMiddleware
from .middleware.trace import TraceMiddleware
from ..tools.registry import get_all_tools
from ..llm.factory import get_llm_factory

def create_agent_engine():
    """创建 Agent 引擎"""
    llm_factory = get_llm_factory()
    llm = llm_factory.create_with_fallback()

    tools = get_all_tools()
    tool_node = ToolNode(tools)

    # Middleware
    memory_middleware = MemoryMiddleware(...)
    trace_middleware = TraceMiddleware(...)
    summarization = SummarizationMiddleware(
        max_token_limit=8000,
        llm=llm
    )

    agent = create_agent(
        llm=llm,
        tools=tools,
        middleware=[
            memory_middleware,
            trace_middleware,
            summarization
        ],
        checkpointer=get_checkpointer(),
        store=get_store(),
        max_iterations=10
    )

    return agent
```

---

## Phase 3: Skills 系统

**优先级**: 🟡 P1（加分项）
**预计工期**: 1 周
**工作量**: 25-35 小时

### 3.1 Skill 数据模型

**任务描述**: 定义 Skill 元数据结构

**涉及文件**:
- `backend/skills/models.py`

**工作量**: 4 小时

**依赖**: 无

**验收标准**:
- [ ] SkillMetadata 支持所有必需字段
- [ ] SKILL.md 解析器正确工作

**代码模板**:

```python
# backend/skills/models.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class SkillMetadata:
    """Skill 元数据"""
    id: str
    name: str
    description: str
    version: str
    file_path: Path
    instructions: str
    examples: Optional[str] = None
    tools: Optional[list[str]] = None

@dataclass
class SkillSnapshot:
    """Skill 快照"""
    skills: dict[str, SkillMetadata]
    version: int
    loaded_at: float
```

---

### 3.2 Skill Manager

**任务描述**: 实现 Skill 扫描和加载逻辑

**涉及文件**:
- `backend/skills/manager.py`

**工作量**: 10 小时

**依赖**: 3.1

**验收标准**:
- [ ] scan_all 扫描多层目录
- [ ] 高优先级覆盖低优先级
- [ ] 热重载不影响运行中请求

**代码模板**:

```python
# backend/skills/manager.py
import asyncio
from pathlib import Path
from .models import SkillMetadata, SkillSnapshot

class SkillManager:
    def __init__(self):
        self.skill_dirs = [
            Path.home() / ".agents" / "skills",  # 用户全局
            Path.cwd() / "skills",                # 项目
        ]
        self._snapshot = SkillSnapshot({}, 0, 0)
        self._lock = asyncio.Lock()

    async def scan_all(self) -> SkillSnapshot:
        """扫描所有 Skills"""
        async with self._lock:
            all_skills = {}
            for skill_dir in self.skill_dirs:
                for skill_md in skill_dir.glob("**/SKILL.md"):
                    skill_def = self._parse_skill_md(skill_md)
                    if skill_def.id in all_skills:
                        # 高优先级覆盖
                        all_skills[skill_def.id] = skill_def

            self._snapshot = SkillSnapshot(
                skills=all_skills,
                version=self._snapshot.version + 1,
                loaded_at=asyncio.get_event_loop().time()
            )
            return self._snapshot

    def _parse_skill_md(self, path: Path) -> SkillMetadata:
        """解析 SKILL.md"""
        content = path.read_text()
        # 解析 frontmatter 和内容
        # 返回 SkillMetadata
        ...
```

---

### 3.3 Skill Registry

**任务描述**: 管理 Skill 注册和激活

**涉及文件**:
- `backend/skills/registry.py`

**工作量**: 8 小时

**依赖**: 3.2

**验收标准**:
- [ ] 通过 description 触发 Skill
- [ ] read_file 激活机制工作
- [ ] 指令注入 System Prompt

**代码模板**:

```python
# backend/skills/registry.py
from typing import dict
from .manager import SkillManager
from .models import SkillMetadata

class SkillRegistry:
    def __init__(self, manager: SkillManager):
        self.manager = manager
        self._active_skills: dict[str, SkillMetadata] = {}

    async def activate_skill(self, skill_id: str) -> SkillMetadata:
        """激活 Skill"""
        snapshot = await self.manager.scan_all()
        skill = snapshot.skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        self._active_skills[skill_id] = skill
        return skill

    def get_active_instructions(self) -> str:
        """获取所有激活 Skill 的指令"""
        instructions = []
        for skill in self._active_skills.values():
            instructions.append(skill.instructions)
        return "\n\n".join(instructions)
```

---

### 3.4 read_file 安全加固

**任务描述**: 实现 read_file 的安全限制

**涉及文件**:
- `backend/tools/file.py`

**工作量**: 6 小时

**依赖**: 3.3

**验收标准**:
- [ ] 只能访问 skills 目录
- [ ] 路径遍历攻击被拦截
- [ ] 支持并发安全

**代码模板**:

```python
# backend/tools/file.py
from pathlib import Path
from langchain_core.tools import tool
import asyncio

ALLOWED_DIRS = [
    Path.cwd() / "skills",
    Path.home() / ".agents" / "skills"
]
_lock = asyncio.Lock()

@tool
async def read_file(path: str) -> str:
    """读取文件内容（仅限 skills 目录）"""
    async with _lock:
        full_path = Path(path).expanduser().resolve()

        # 安全检查
        if not any(full_path.is_relative_to(d.resolve()) for d in ALLOWED_DIRS):
            raise PermissionError(f"路径不在允许范围内: {path}")

        # 路径遍历检查
        try:
            full_path.relative_to(Path.cwd().resolve())
        except ValueError:
            raise PermissionError(f"检测到路径遍历攻击: {path}")

        return full_path.read_text(encoding='utf-8')
```

---

## Phase 4: HIL 机制

**优先级**: 🟡 P1（加分项）
**预计工期**: 1 周
**工作量**: 20-30 小时

### 4.1 HIL Middleware

**任务描述**: 实现人工介入中间件

**涉及文件**:
- `backend/agent/middleware/hil.py`

**工作量**: 8 小时

**依赖**: 2.4

**验收标准**:
- [ ] interrupt_on 配置工作
- [ ] 暂停点正确保存
- [ ] resume 可恢复执行

**代码模板**:

```python
# backend/agent/middleware/hil.py
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import interrupt

class HILMiddleware(HumanInTheLoopMiddleware):
    def __init__(self, interrupt_on: dict[str, bool]):
        super().__init__(interrupt_on=interrupt_on)

    async def awrap_tool_call(self, request, handler):
        """工具调用前检查是否需要中断"""
        tool_name = request.tool_name

        if self.interrupt_on.get(tool_name, False):
            # 触发中断
            config = interrupt({
                "tool": tool_name,
                "args": request.tool_args,
                "risk": self._assess_risk(tool_name)
            })

            if not config.get("confirmed"):
                return {"result": "用户取消操作"}

        return await handler(request)

    def _assess_risk(self, tool_name: str) -> str:
        """评估操作风险"""
        high_risk = ["send_email", "delete_file", "place_order"]
        medium_risk = ["post_to_social_media"]

        if tool_name in high_risk:
            return "high"
        elif tool_name in medium_risk:
            return "medium"
        return "low"
```

---

### 4.2 Resume 接口

**任务描述**: 实现 HIL 恢复接口

**涉及文件**:
- `backend/main.py` (添加路由)

**工作量**: 6 小时

**依赖**: 4.1

**验收标准**:
- [ ] POST /chat/resume 可用
- [ ] approve/reject 分支正确
- [ ] SSE 继续推送事件

**代码模板**:

```python
# backend/main.py (添加)
from fastapi import APIRouter, Request
from pydantic import BaseModel

class ResumeRequest(BaseModel):
    interrupt_id: str
    action: Literal["approve", "reject"]

@router.post("/chat/resume")
async def resume_chat(req: ResumeRequest):
    """恢复 HIL 暂停的对话"""
    # 从 interrupt_id 恢复 checkpoint
    # 根据 action 决定继续或取消
    # 返回 SSE 流
    ...
```

---

### 4.3 send_email 工具（演示用）

**任务描述**: 实现 mock 邮件发送工具

**涉及文件**:
- `backend/tools/send_email.py`

**工作量**: 4 小时

**依赖**: 4.1

**验收标准**:
- [ ] 工具可被调用
- [ ] 不真实发送邮件
- [ ] 返回模拟结果

**代码模板**:

```python
# backend/tools/send_email.py
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

@tool
async def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件（mock 实现，用于 HIL 演示）"""
    logger.info(f"[MOCK] 发送邮件: to={to}, subject={subject}")
    # 不真实发送，仅记录日志
    return f"邮件已发送（模拟）: {to}"
```

---

## Phase 5: SSE 流式推送

**优先级**: 🔴 P0（面试必须）
**预计工期**: 1 周
**工作量**: 25-35 小时

### 5.1 Trace Middleware

**任务描述**: 实现执行追踪中间件

**涉及文件**:
- `backend/agent/middleware/trace.py`

**工作量**: 8 小时

**依赖**: 2.4

**验收标准**:
- [ ] after_model 记录 LLM 输出
- [ ] thought_chain 正确序列化
- [ ] token_usage 准确记录

**代码模板**:

```python
# backend/agent/middleware/trace.py
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from ..observability.tracer import Tracer

class TraceMiddleware(AgentMiddleware):
    def __init__(self, tracer: Tracer):
        self.tracer = tracer

    async def aafter_model(self, request, handler):
        """LLM 调用后，记录追踪"""
        state = request.state
        last_msg = state["messages"][-1]

        if isinstance(last_msg, AIMessage):
            await self.tracer.record(
                session_id=state.get("session_id"),
                content_blocks=last_msg.content_blocks,
                token_usage=last_msg.usage_metadata
            )

        return await handler(request)
```

---

### 5.2 SSE 端点实现

**任务描述**: 实现 /chat SSE 接口

**涉及文件**:
- `backend/main.py`

**工作量**: 12 小时

**依赖**: 5.1

**验收标准**:
- [ ] thought 事件正确推送
- [ ] tool_start 事件包含入参
- [ ] tool_result 事件包含结果
- [ ] done 事件标志结束

**代码模板**:

```python
# backend/main.py (添加)
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

@router.post("/chat")
async def chat(req: ChatRequest):
    async def event_generator():
        agent = create_agent_engine()

        async for stream_mode, data in agent.astream(
            {"messages": [HumanMessage(content=req.message)]},
            config={"configurable": {
                "thread_id": req.session_id,
                "user_id": req.user_id,
            }},
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

---

### 5.3 事件类型定义

**任务描述**: 定义 SSE 事件类型

**涉及文件**:
- `backend/observability/events.py`

**工作量**: 4 小时

**依赖**: 无

**验收标准**:
- [ ] 所有事件类型有明确 Schema
- [ ] 事件可通过 Python 类型检查

**代码模板**:

```python
# backend/observability/events.py
from enum import Enum
from pydantic import BaseModel

class SSEEventType(str, Enum):
    THOUGHT = "thought"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    HIL_INTERRUPT = "hil_interrupt"
    TOKEN_UPDATE = "token_update"
    ERROR = "error"
    DONE = "done"

class ThoughtEvent(BaseModel):
    type: SSEEventType = SSEEventType.THOUGHT
    content: str

class ToolStartEvent(BaseModel):
    type: SSEEventType = SSEEventType.TOOL_START
    tool_name: str
    args: dict

class ToolResultEvent(BaseModel):
    type: SSEEventType = SSEEventType.TOOL_RESULT
    result: str

class HILInterruptEvent(BaseModel):
    type: SSEEventType = SSEEventType.HIL_INTERRUPT
    interrupt_id: str
    tool_name: str
    args: dict
    risk: str
```

---

## 安全加固要求

### 路径安全限制

```python
# backend/utils/security.py
from pathlib import Path

class PathValidator:
    ALLOWED_DIRS = [
        Path.cwd() / "skills",
        Path.home() / ".agents" / "skills"
    ]

    @classmethod
    def validate(cls, path: str) -> Path:
        full_path = Path(path).expanduser().resolve()

        # 白名单检查
        if not any(full_path.is_relative_to(d.resolve()) for d in cls.ALLOWED_DIRS):
            raise PermissionError(f"路径不在允许范围内: {path}")

        # 路径遍历检查
        try:
            full_path.relative_to(Path.cwd().resolve())
        except ValueError:
            raise PermissionError(f"检测到路径遍历攻击: {path}")

        return full_path
```

### 并发安全保护

```python
# backend/skills/manager.py
import asyncio

class SkillRegistry:
    def __init__(self):
        self._registry = {}
        self._version = 0
        self._lock = asyncio.Lock()

    async def load_all(self) -> None:
        """原子性地重新加载所有 Skills"""
        async with self._lock:
            new_registry = {}
            # 先构建新版本
            for skill_dir in self.skill_dirs:
                for skill_md in skill_dir.glob("**/SKILL.md"):
                    skill_def = self._parse_skill_md(skill_md)
                    new_registry[skill_def.id] = skill_def
            # 原子替换
            self._registry = new_registry
            self._version += 1
```

### Token 精确计数

```python
# backend/utils/token.py
import tiktoken

def get_token_encoder(model: str = "gpt-4o"):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoder = get_token_encoder(model)
    return len(encoder.encode(text))
```

### Row Level Security

```sql
-- backend/db/schema.sql
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT USING (user_id = current_setting('app.user_id', true));

CREATE POLICY agent_traces_insert_own ON agent_traces
FOR INSERT WITH CHECK (user_id = current_setting('app.user_id', true));
```

---

## 验收标准汇总

### Phase 1: 基础设施
- [ ] 服务器启动成功
- [ ] 健康检查返回 200
- [ ] LLM 可正常调用
- [ ] 数据库表创建成功
- [ ] 基础工具可执行

### Phase 2: Memory 系统
- [ ] 用户画像可保存
- [ ] 用户画像可加载
- [ ] 用户画像注入 System Prompt
- [ ] 短期记忆自动持久化
- [ ] 消息超限自动压缩

### Phase 3: Skills 系统
- [ ] Skills 可被扫描
- [ ] Skills 可被激活
- [ ] read_file 安全限制生效
- [ ] Skill 指令注入工作

### Phase 4: HIL 机制
- [ ] send_email 触发中断
- [ ] 前端收到 hil_interrupt 事件
- [ ] approve 后继续执行
- [ ] reject 后正确处理

### Phase 5: SSE 流式推送
- [ ] thought 事件实时推送
- [ ] tool_start 事件包含入参
- [ ] tool_result 事件包含结果
- [ ] done 事件标志结束

---

## 依赖关系图

```
Phase 1 (基础设施)
    ├─ 1.1 项目脚手架
    ├─ 1.2 FastAPI 入口 ─依赖→ 1.1
    ├─ 1.3 LLM Factory ─依赖→ 1.1, 1.2
    ├─ 1.4 数据库初始化 ─依赖→ 1.1
    └─ 1.5 基础工具 ─依赖→ 1.1

Phase 2 (Memory 系统)
    ├─ 2.1 Memory 数据模型 ─依赖→ 1.4
    ├─ 2.2 Memory Manager ─依赖→ 2.1
    ├─ 2.3 Memory Middleware ─依赖→ 2.2
    └─ 2.4 LangGraph 集成 ─依赖→ 2.3, 1.3

Phase 3 (Skills 系统)
    ├─ 3.1 Skill 数据模型
    ├─ 3.2 Skill Manager ─依赖→ 3.1
    ├─ 3.3 Skill Registry ─依赖→ 3.2
    └─ 3.4 read_file 安全 ─依赖→ 3.3

Phase 4 (HIL 机制)
    ├─ 4.1 HIL Middleware ─依赖→ 2.4
    ├─ 4.2 Resume 接口 ─依赖→ 4.1
    └─ 4.3 send_email 工具 ─依赖→ 4.1

Phase 5 (SSE 流式推送)
    ├─ 5.1 Trace Middleware ─依赖→ 2.4
    ├─ 5.2 SSE 端点 ─依赖→ 5.1
    └─ 5.3 事件类型 ─依赖→ 5.2
```

---

## 文件创建顺序

### 第一批（Day 1-2）
1. `backend/requirements.txt`
2. `backend/config.py`
3. `backend/.env.example`
4. `backend/main.py` (基础版)

### 第二批（Day 3-5）
5. `backend/llm/factory.py`
6. `backend/db/postgres.py`
7. `backend/tools/base.py`
8. `backend/tools/file.py`
9. `backend/utils/token.py`

### 第三批（Day 6-10）
10. `backend/memory/schemas.py`
11. `backend/memory/manager.py`
12. `backend/agent/middleware/memory.py`
13. `backend/agent/graph.py`
14. `backend/agent/langchain_engine.py`

### 第四批（Day 11-15）
15. `backend/skills/models.py`
16. `backend/skills/manager.py`
17. `backend/skills/registry.py`
18. `backend/tools/send_email.py`
19. `backend/agent/middleware/hil.py`

### 第五批（Day 16-20）
20. `backend/agent/middleware/trace.py`
21. `backend/observability/events.py`
22. `backend/main.py` (完整版)
23. `backend/tests/test_agent.py`
24. `backend/tests/test_api.py`

---

**文档结束**
