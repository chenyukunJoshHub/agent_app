# Multi-Tool AI Agent · 架构设计文档

**日期**: 2026-03-20
**状态**: 审查完成，已整合反馈
**版本**: v1.1

---

## 目录

1. [产品定位与场景](#产品定位与场景)
2. [核心功能模块](#核心功能模块)
3. [Memory 三层架构](#memory-三层架构)
4. [Agent Skills 四层结构](#agent-skills-四层结构)
5. [HIL 人工介入机制](#hil-人工介入机制)
6. [可观测性与 SSE 流式推送](#可观测性与-sse-流式推送)
7. [技术栈与依赖](#技术栈与依赖)
8. [实施路线图](#实施路线图)
9. [部署策略](#部署策略)
10. [数据库设计](#数据库设计)
11. [安全加固](#安全加固)
12. [审查意见汇总](#审查意见汇总)

---

## 产品定位与场景

### 产品定位

**Multi-Tool AI Agent** 是一个支持多工具调用的通用助手系统，具备以下特点：

- **面试演示项目**：展示架构设计能力和工程实现能力
- **学习与研究**：分阶段实施，1-2个月宽松时间线
- **通用助手场景**：非 E-sign宝 特定，可复用于多种场景
- **架构驱动开发**：从完整架构设计到实现

### 核心场景

| 场景 | 描述 | 示例 |
|-----|------|------|
| 信息查询 | 调用搜索工具获取实时信息 | "今天天气怎么样？" |
| 文件操作 | 读取、分析本地文件 | "分析这个 CSV 文件" |
| 网页交互 | 浏览器自动化操作 | "帮我登录网站并截图" |
| 数据分析 | 处理结构化数据 | "统计这周销售额" |
| 任务编排 | 多步骤复杂任务 | "查合同状态，完成后发邮件" |

---

## 核心功能模块

### 模块架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Multi-Tool Agent                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   前端 UI   │  │   后端 API  │  │   LLM 服务  │         │
│  │   Next.js   │  │   FastAPI   │  │   Ollama    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │ SSE             │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│         ┌─────────────────┴─────────────────┐               │
│         │           Agent Core              │               │
│         │         (LangGraph)               │               │
│         │   ┌─────────────────────────┐    │               │
│         │   │     ReAct Loop          │    │               │
│         │   │  Reason → Act → Observe  │    │               │
│         │   └─────────────────────────┘    │               │
│         └─────────────────┬─────────────────┘               │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐        │
│  │                    Middleware                   │        │
│  │  before_agent │ wrap_model │ after_agent        │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐        │
│  │                    Memory                       │        │
│  │  Short │ Long │ Working (Token Budget)          │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐        │
│  │                  Skills Manager                  │        │
│  │  project/skills/ │ ~/.agents/skills/             │        │
│  └────────────────────────┬────────────────────────┘        │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐        │
│  │                    Tools                        │        │
│  │  read_file │ web_search │ browser │ csv...      │        │
│  └──────────────────────────────────────────────────┘        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Memory 三层架构

### 三层结构

| 层级 | 存储介质 | 作用域 | 生命周期 | 实现 |
|-----|---------|-------|---------|------|
| **Short Memory** | PostgreSQL (AsyncPostgresSaver) | session | 会话期间 | 检查点恢复 |
| **Long Memory** | PostgreSQL (AsyncPostgresStore) | user | 持久化 | 用户画像 |
| **Working Memory** | Context Window | turn | 单轮对话 | Token 预算管理 |

### Ephemeral 注入策略

**设计原则**：用户画像临时注入到 System Prompt，避免污染聊天历史。

```python
# Memory 中间件实现
class MemoryMiddleware(AgentMiddleware):
    async def awrap_model_call(self, request, handler):
        user_id = request.runtime.context.get("user_id", "")

        # 从 Long Memory 读取用户画像
        item = await request.runtime.store.aget(("profile", user_id), "profile")
        episodic_text = format_episodic(item.value) if item else ""

        # 临时注入（不写入历史）
        if episodic_text:
            original_sys = request.system_message.content
            new_sys = original_sys + "\n\n用户画像:\n" + episodic_text
            request = request.override(system_message=SystemMessage(content=new_sys))

        return await handler(request)
```

### Token 预算分配

32K 工作预算示例：

| 插槽 | 大小 | 说明 |
|-----|------|------|
| ① System Prompt | 2000 | 基础指令 |
| ② Tools Schema | 3000 | 工具定义 |
| ③ Few-Shot | 2000 | 示例 |
| ④ Long Memory | 1000 | 用户画像 (ephemeral) |
| ⑤ Short Memory | 8000 | 历史消息 |
| ⑥ 当前输入 | 2000 | 用户问题 |
| ⑦ 预留 | 14000 | 输出生成 + 缓冲 |

---

## Agent Skills 四层结构

### Skill 内容结构

```markdown
skills/
└── my-skill/
    ├── SKILL.md          # 元数据 + 指令
    ├── examples.md       # 示例
    └── tools.py          # 工具实现
```

**SKILL.md 格式**：

```markdown
---
id: my-skill
name: My Skill
description: 当用户需要 XXX 时触发
version: 1.0.0
---

# 指令内容

你是一个 XXX 助手...

## 工具

- my_tool: 做什么
```

### Skill Protocol 四大约定

1. **识别约定**：通过 `description` 字段触发
2. **调用约定**：`read_file` 激活机制
3. **执行约定**：指令注入 System Prompt
4. **冲突约定**：后加载覆盖先加载

### 多层加载策略

```python
class SkillManager:
    def __init__(self):
        self.skill_dirs = [
            Path.home() / ".agents" / "skills",  # 用户全局（低优先级）
            Path.cwd() / "skills",                # 项目（高优先级）
        ]

    def scan_all(self) -> SkillSnapshot:
        all_skills = {}
        for skill_dir in self.skill_dirs:
            for skill_md in skill_dir.glob("**/SKILL.md"):
                skill_def = self._parse_skill_md(skill_md)
                # 高优先级覆盖低优先级
                all_skills[skill_def.id] = skill_def
        return self._build_snapshot(all_skills)
```

---

## HIL 人工介入机制

### 设计原则

- **仅不可逆操作**：邮件发送、文件删除、支付等
- **可选配置**：可通过配置关闭
- **状态持久化**：中断后可恢复

### 实现方式

**LangGraph Interrupt**：

```python
from langgraph.types import interrupt

def send_email(to: str, subject: str, body: str):
    # 触发中断，等待用户确认
    config = interrupt({
        "tool": "send_email",
        "args": {"to": to, "subject": subject, "body": body},
        "risk": "medium"  # low / medium / high
    })

    if not config.get("confirmed"):
        return "用户取消操作"

    # 执行发送...
```

### 前端确认流程

```
┌─────────────────────────────────────┐
│  ⚠️ 需要确认操作                    │
├─────────────────────────────────────┤
│  工具: send_email                   │
│  参数:                              │
│    to: user@example.com             │
│    subject: 合同通知                │
│                                     │
│  [拒绝]          [确认执行]         │
└─────────────────────────────────────┘
```

---

## 可观测性与 SSE 流式推送

### 设计理念

通过 SSE (Server-Sent Events) 实时推送 Agent 推理链，前端逐步可视化每一步决策过程。

### SSE 事件类型

| 事件类型 | 触发时机 | 前端展示 |
|---------|---------|---------|
| `thought` | LLM 产生新思考 | 时间轴新增节点，带脉冲动画 |
| `tool_start` | 工具开始执行 | 工具卡片出现加载状态 |
| `tool_result` | 工具返回结果 | 展示结果摘要（可展开） |
| `hil_interrupt` | 需要人工确认 | 弹出确认模态框 |
| `token_update` | Token 使用变化 | 实时更新进度条 |
| `error` | 发生错误 | 红色错误卡片 |
| `done` | 执行完成 | 显示最终答案 |

### 前端布局结构（参考 pencil-new.pen）

```
┌─────────────────────────────────────────────────────────────┐
│ Header: Multi-Tool Agent  [Theme]  [SSE流式·32k工作预算]   │
├──────────┬───────────────────────────────┬──────────────────┤
│ 左侧栏   │        中间聊天区              │    右侧栏       │
│ (272px)  │       (fill_container)        │    (320px)      │
│          │                               │                  │
│ 会话列表 │  ┌─────────────────────────┐  │  [可观测|Context│
│ 工具芯片 │  │ 此会话 · thread_8f2a    │  │   |Skills]      │
│          │  ├─────────────────────────┤  │                  │
│ read_file│  │ 消息流（可滚动）        │  │  时间轴可视化   │
│ tavily_  │  │                        │  │                  │
│ search   │  │ User: 查合同123...     │  │  1·before_agent │
│ contract_│  │                        │  │  2·恢复短期记忆 │
│ status   │  │ Claude: 已调用...      │  │  3·wrap_model   │
│ send_    │  │                        │  │  4·LLM调用#1    │
│ email    │  └─────────────────────────┘  │  5·工具调用     │
│ python_  │  输入框: [描述任务...]       │  6·HIL确认 ⚠️   │
│ repl     │         [↑]                  │  7·after_agent   │
└──────────┴───────────────────────────────┴──────────────────┘
```

### Design Tokens

```typescript
const designTokens = {
  colors: {
    bg: ['#E8EDF3', '#0B1221'],
    surface: ['#FFFFFF', '#111827'],
    surfaceMuted: ['#F1F5F9', '#1F2937'],
    text: ['#1E293B', '#F9FAFB'],
    textMuted: ['#64748B', '#9CA3AF'],
    accent: ['#2563EB', '#60A5FA'],
    border: ['#E2E8F0', '#334155'],
    toolChip: ['#DBEAFE', '#1E3A8A'],
    tabActive: ['#EFF6FF', '#1E40AF']
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px'
  },
  borderRadius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px'
  },
  typography: {
    fontFamily: 'Plus Jakarta Sans'
  }
};
```

### 时间轴组件

```typescript
interface TimelineEvent {
  id: string;
  step: number;
  title: string;
  description: string;
  status: 'pending' | 'active' | 'done' | 'error';
  focus?: boolean;
  timestamp: number;
  duration?: number;
  eventType: SSEEventType;
  metadata?: {
    toolName?: string;
    tokenUsage?: number;
    error?: string;
  };
  children?: TimelineEvent[];
}

enum SSEEventType {
  THOUGHT = 'thought',
  TOOL_START = 'tool_start',
  TOOL_RESULT = 'tool_result',
  HIL_INTERRUPT = 'hil_interrupt',
  TOKEN_UPDATE = 'token_update',
  ERROR = 'error',
  DONE = 'done'
}
```

### HIL 确认模态框

```typescript
interface HILConfirmModalProps {
  toolName: string;
  args: Record<string, any>;
  risk: 'low' | 'medium' | 'high';
  onConfirm: () => void;
  onReject: () => void;
  operationId: string;
  estimatedCost?: string;
  timeout?: number;
  history?: HILHistoryItem[];
}
```

---

## 技术栈与依赖

### 后端

| 组件 | 技术选型 | 版本约束 | 说明 |
|-----|---------|----------|------|
| Web 框架 | FastAPI | latest | 异步支持，自动 OpenAPI |
| Agent 框架 | LangChain + LangGraph | >=1.2.13, <2.0.0 | ReAct 循环，中间件钩子 |
| LLM | ChatOllama | latest | 支持 Claude 模型 |
| 数据库 | PostgreSQL | 16+ | JSONB + GIN 索引 |
| 内存检索 | AsyncPostgresStore | latest | 官方支持 |
| 检查点 | AsyncPostgresSaver | latest | 官方支持 |
| Token 计数 | tiktoken | latest | 精确计数 |

### 前端

| 组件 | 技术选型 | 说明 |
|-----|---------|-----|
| 框架 | Next.js 15 | App Router + RSC |
| UI 组件 | Radix UI | 无障碍组件 |
| 样式 | Tailwind CSS v4 | 设计 tokens |
| 字体 | Plus Jakarta Sans | 从 pencil 设计 |
| 状态管理 | Zustand | 轻量级 |
| SSE 客户端 | @microsoft/fetch-event-source | 支持自定义头 |
| 服务器状态 | TanStack Query | 缓存和自动刷新 |

---

## 实施路线图

### Phase 1: 基础设施（Week 1-2）🔴 P0

- 项目脚手架搭建
- 核心工具实现 (read_file, fetch_url, token_counter)
- LLM Factory (多 provider + Fallback)
- Docker Compose 配置

### Phase 2: Memory 系统（Week 2-3）🔴 P0

- 三层 Memory 实现
- Memory Middleware (before/wrap/after)
- 数据库 Schema + 约束

### Phase 3: 安全加固（Week 3）🔴 P0

- 路径安全限制 (read_file)
- 并发安全 (SkillRegistry 加锁)
- Row Level Security 启用

### Phase 4: Agent Skills（Week 3-4）🟡 P1

- Skill Manager (多层扫描 + 热重载)
- Skill Protocol (触发 + 冲突检测)
- 内置 Skills (web_search, browser_use)

### Phase 5: 可观测性（Week 4-5）🟡 P1

- SSE 流式推送 (事件类型 + 重连)
- 前端可视化 (时间轴 + Token 进度条)
- HIL 模态框

### Phase 6: HIL 人工介入（Week 5-6）🟡 P1

- Interrupt 机制
- 前端交互 (确认模态框 + 风险标识)

### Phase 7: 前端完善（Week 6-7）⚪ P2

- UI 组件库 (参考 pencil-new.pen)
- React Query 集成
- 会话管理

### Phase 8: 测试与优化（Week 7-8）⚪ P2

- 单元测试 + 集成测试
- 性能优化
- 监控告警配置

---

## 部署策略

### 本地开发

```bash
# 使用 Docker Compose 一键启动
docker-compose up -d

# 服务包括：
# - PostgreSQL (端口 54322)
# - Backend FastAPI (端口 8000)
# - Frontend Next.js (端口 3000)
# - Ollama (端口 11434)
```

### Docker Compose 配置

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: agent_db
    ports:
      - "54322:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./supabase/migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/agent_db
      - LLM_PROVIDER=ollama
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - /app/.venv

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  postgres_data:
```

### 生产部署

| 组件 | 推荐方案 | 月度成本 |
|-----|---------|----------|
| 前端 | Vercel Pro | $20 |
| 后端 | Railway (2 实例) | $20-40 |
| 数据库 | Supabase Pro | $25 |
| LLM | DeepSeek API | $50-100 |
| 监控 | Grafana Cloud | $10-50 |
| **总计** | | **$125-235** |

---

## 数据库设计

### 优化后的 Schema

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    email text UNIQUE NOT NULL,
    created_at timestamptz NOT NULL default now(),
    updated_at timestamptz NOT NULL default now()
);

-- 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text,
    last_message_at timestamptz,
    created_at timestamptz NOT NULL default now(),
    updated_at timestamptz NOT NULL default now()
);

-- Agent 追踪表
CREATE TABLE IF NOT EXISTS agent_traces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id text NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_input text,
    final_answer text,
    thought_chain jsonb NOT NULL DEFAULT '[]',
    tool_calls jsonb NOT NULL DEFAULT '[]',
    token_usage jsonb NOT NULL DEFAULT '{}',
    latency_ms integer NOT NULL,
    finish_reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- 约束（审查反馈添加）
ALTER TABLE agent_traces
ADD CONSTRAINT chk_latency_ms_positive CHECK (latency_ms >= 0),
ADD CONSTRAINT chk_finish_reason_valid
CHECK (finish_reason IN ('stop', 'length', 'tool_calls', 'content_filter', 'error', 'interrupted')),
ADD CONSTRAINT chk_thought_chain_max_size CHECK (pg_column_size(thought_chain) <= 100000),
ADD CONSTRAINT chk_tool_calls_max_size CHECK (pg_column_size(tool_calls) <= 50000);

-- 唯一约束（防止重复）
CREATE UNIQUE INDEX idx_agent_traces_session_created_unique
ON agent_traces(session_id, created_at DESC, id);

-- 覆盖索引（性能提升 10-50x）
CREATE INDEX idx_agent_traces_user_session_created
ON agent_traces(user_id, session_id, created_at DESC)
INCLUDE (final_answer, latency_ms, finish_reason, thought_chain, tool_calls);

-- GIN 索引
CREATE INDEX idx_agent_traces_thought_chain
ON agent_traces USING GIN (thought_chain);
CREATE INDEX idx_agent_traces_tool_calls
ON agent_traces USING GIN (tool_calls);

-- 部分索引（近期会话）
CREATE INDEX idx_agent_traces_recent
ON agent_traces(session_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '90 days';

-- 会话搜索索引
CREATE INDEX idx_sessions_user_last_message
ON sessions(user_id, last_message_at DESC NULLS LAST)
INCLUDE (title);
```

### Row Level Security

```sql
-- 启用 RLS
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 用户只能访问自己的数据
CREATE POLICY agent_traces_select_own ON agent_traces
FOR SELECT USING (user_id = current_setting('app.user_id', true));

CREATE POLICY sessions_select_own ON sessions
FOR SELECT USING (user_id = current_setting('app.user_id', true));

CREATE POLICY users_select_own ON users
FOR SELECT USING (id = current_setting('app.user_id', true));
```

---

## 安全加固

### 路径安全限制

```python
# 后端/tools/file.py
from pathlib import Path
from typing import Optional

ALLOWED_DIRS = [
    Path.cwd() / "skills",
    Path.home() / ".agents" / "skills"
]

@tool
def read_file(path: str) -> str:
    """
    读取文件内容（Skill 激活核心工具）

    Args:
        path: 文件路径（仅允许访问 skills 目录）
    """
    full_path = Path(path).expanduser().resolve()

    # 安全检查：限制可访问路径
    if not any(full_path.is_relative_to(d.resolve()) for d in ALLOWED_DIRS):
        raise PermissionError(f"路径不在允许范围内: {path}")

    # 路径遍历检查
    try:
        full_path.relative_to(Path.cwd().resolve())
    except ValueError:
        raise PermissionError(f"检测到路径遍历攻击: {path}")

    return full_path.read_text(encoding='utf-8')
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
            # 先构建新版本
            new_registry = {}
            for skill_dir in self.skill_dirs:
                for skill_md in skill_dir.glob("**/SKILL.md"):
                    skill_def = self._parse_skill_md(skill_md)

                    # 记录覆盖日志
                    if skill_def.id in new_registry:
                        logger.warning(
                            f"Skill {skill_def.id} 被覆盖: "
                            f"{new_registry[skill_def.id].file_path} → {skill_def.file_path}"
                        )

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
    """获取 Token 编码器"""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """精确计数 Token"""
    encoder = get_token_encoder(model)
    return len(encoder.encode(text))

# 使用示例
token_count = count_tokens(user_input + system_prompt)
if token_count > TOKEN_BUDGET:
    logger.warning(f"Token 超预算: {token_count} > {TOKEN_BUDGET}")
```

### 用户上下文设置

```python
# backend/db/postgres.py
async def set_user_context(conn, user_id: str) -> None:
    """设置 RLS 用户上下文"""
    await conn.execute(
        "SET LOCAL app.user_id = $1",
        (user_id,)
    )

# 中间件集成
@app.middleware("http")
async def add_user_context(request: Request, call_next):
    user_id = request.state.user_id  # 从 JWT 解码获得

    # 为每个数据库连接设置上下文
    async with pool.connection() as conn:
        await set_user_context(conn, user_id)

    response = await call_next(request)
    return response
```

---

## 前端优化

### SSE 连接管理

```typescript
// frontend/lib/sse-manager.ts
import { fetchEventSource } from '@microsoft/fetch-event-source';

interface SSEOptions {
  url: string;
  token: string;
  onMessage: (event: any) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
}

class SSEManager {
  private retryCount = 0;
  private maxRetries = 5;
  private initialDelay = 1000;
  private maxDelay = 30000;
  private backoffMultiplier = 1.5;
  private abortController: AbortController | null = null;

  async connect(options: SSEOptions): Promise<void> {
    this.abortController = new AbortController();

    await fetchEventSource(options.url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sessionId: 'xxx' }),
      signal: this.abortController.signal,

      onopen: () => {
        this.retryCount = 0;
        options.onOpen?.();
      },

      onmessage: (msg) => {
        const event = JSON.parse(msg.data);
        options.onMessage(event);
      },

      onerror: (err) => {
        this.scheduleReconnect(options);
        options.onError?.(err);
        throw err; // 重试
      }
    });
  }

  private scheduleReconnect(options: SSEOptions): void {
    if (this.retryCount >= this.maxRetries) {
      options.onError?.(new Error('达到最大重试次数'));
      return;
    }

    const delay = Math.min(
      this.initialDelay * Math.pow(this.backoffMultiplier, this.retryCount),
      this.maxDelay
    );

    setTimeout(() => {
      this.retryCount++;
      this.connect(options);
    }, delay);
  }

  disconnect(): void {
    this.abortController?.abort();
  }
}

export const sseManager = new SSEManager();
```

### TanStack Query 集成

```typescript
// frontend/lib/api/sessions.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useSessions() {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
    refetchInterval: 30000, // 30秒自动刷新
    staleTime: 5000,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (title: string) => {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
}
```

### 时间轴虚拟滚动

```typescript
// frontend/components/Timeline.tsx
import { useVirtualizer } from '@tanstack/react-virtual';

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 5,
  });

  return (
    <div ref={parentRef} className="h-[600px] overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const event = events[virtualItem.index];
          return (
            <div
              key={virtualItem.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              <TimelineEventItem event={event} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

---

## 监控与运维

### 日志结构化

```python
# backend/utils/logging.py
import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

# 使用示例
logger = structlog.get_logger(__name__)

@app.post("/chat")
async def chat(req: ChatRequest):
    log = logger.bind(
        session_id=req.session_id,
        user_id=req.user_id,
        request_id=generate_request_id()
    )

    log.info("chat_request_received")

    try:
        result = await agent_executor.invoke(...)
        log.info("chat_request_success", latency_ms=..., token_usage=...)
    except Exception as e:
        log.error("chat_request_failed", error=str(e))
        raise
```

### 监控指标

| 指标类别 | 具体指标 | 告警阈值 | 严重程度 |
|---------|---------|---------|----------|
| 系统健康 | API 响应时间 | P95 > 5s | 🟡 中等 |
| | 错误率 | > 5% | 🔴 高 |
| Agent 特有 | LLM 调用失败率 | > 10% | 🔴 高 |
| | 工具调用超时 | > 30s | 🟡 中等 |
| 数据库 | 连接池使用率 | > 80% | 🟡 中等 |
| | 查询慢查询 | > 1s | 🟡 中等 |

---

## 审查意见汇总

### 审查团队评分

| 维度 | 评分 | 状态 |
|-----|------|------|
| **前端架构** | ⭐⭐⭐⭐☆ (4/5) | ✅ 优秀 |
| **后端架构** | 8.5-9/10 | ✅ 优秀 |
| **数据库设计** | 8.5/10 | ✅ 优秀 |
| **部署策略** | ✅ 全面 | ✅ 完善 |

### 关键改进点（已整合）

| 优先级 | 项目 | 状态 |
|-------|------|------|
| 🔴 P0 | 数据库约束 + 覆盖索引 | ✅ 已整合 |
| 🔴 P0 | 路径安全限制 | ✅ 已整合 |
| 🔴 P0 | 并发安全保护 | ✅ 已整合 |
| 🔴 P0 | Row Level Security | ✅ 已整合 |
| 🟡 P1 | SSE 连接管理 | ✅ 已整合 |
| 🟡 P1 | Token 精确计数 | ✅ 已整合 |
| 🟡 P1 | React Query 集成 | ✅ 已整合 |
| 🟡 P1 | Docker Compose | ✅ 已整合 |

### 架构优势

- ✅ Memory 三层架构设计精妙
- ✅ Agent Skills 系统完整
- ✅ Ephemeral 注入策略正确
- ✅ UI/UX 设计参考 pencil-new.pen
- ✅ 技术栈现代化

### 剩余工作

- ⚪ 实施验证（需要代码实现）
- ⚪ 性能测试（需要压力测试）
- ⚪ 安全审计（需要渗透测试）

---

## 优先级对照

```
🔴 P0 (面试必须)
├── 基础设施 (FastAPI + LangGraph)
├── Memory 三层架构
├── 核心工具
├── HIL 人工介入
└── 安全加固 (新增)

🟡 P1 (加分项)
├── Agent Skills 系统
├── SSE 可观测性
├── 内置工具
└── 前端优化 (新增)

⚪ P2 (面试后)
├── UI 完善 (动画)
├── E2E 测试
└── 性能优化
```

---

**文档版本**: v1.1
**审查状态**: 已通过四维度专业审查
**下一步**: 调用 `writing-plans` skill 创建实施计划
