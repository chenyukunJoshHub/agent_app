# Multi-Tool AI Agent

企业级多工具 AI Agent：支持 ReAct 推理、Memory、Skills、工具编排、HIL 人工确认和 SSE 可观测性。

## Core Capabilities

- ReAct Agent Loop（LangGraph）
- 三层记忆能力（用户画像 + 程序记忆 + 上下文预算）
- Skills 管理与 `activate_skill` 动态加载
- Tool 执行层（策略、幂等、超时、并行控制）
- HIL（Human-in-the-Loop）敏感操作确认
- SSE 实时事件流（推理链路、工具调用、上下文状态）
- 前后端联动的 Context Window / Execution Trace 可视化

## Tech Stack

- Backend: FastAPI, LangChain, LangGraph, psycopg3
- Frontend: Next.js 15, React 19, Zustand, Vitest, Playwright
- Database: PostgreSQL 16
- Optional local model runtime: Ollama

## Repository Structure

```text
agent_app/
├── backend/                  # FastAPI + Agent runtime
│   ├── app/
│   │   ├── agent/            # Agent 核心与 middleware
│   │   ├── api/              # HTTP/SSE 路由
│   │   ├── memory/           # Episodic/Procedural memory
│   │   ├── prompt/           # Context window & prompt builder
│   │   ├── skills/           # SkillManager
│   │   ├── tools/            # Tools registry/manager/policy
│   │   └── observability/    # 事件与 trace block
├── frontend/                 # Next.js UI
├── tests/                    # backend unit/integration + frontend/e2e
├── docs/                     # architecture / plans / reviews
├── skills/                   # project skills
└── docker-compose.yml        # Postgres/Ollama + app services definition
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (recommended for local Postgres/Ollama)

## Quick Start (Recommended)

推荐模式：依赖服务用 Docker，应用进程本地运行。

1. Clone

```bash
git clone <your-repo-url>
cd agent_app
```

2. Configure env

```bash
cp .env.example .env
```

3. Start dependency services

```bash
docker compose up -d postgres ollama
```

4. Start backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Start frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

6. Open

- Frontend: <http://localhost:3000>
- Backend health: <http://localhost:8000/health>
- Backend docs: <http://localhost:8000/docs>

## Key API Endpoints

- `POST /chat/chat` - 发起会话并流式返回 SSE
- `POST /chat/resume` - HIL 审批后恢复执行
- `GET /skills/` - 获取可用技能列表
- `GET /session/{session_id}/context` - Token 预算状态
- `GET /session/{session_id}/slots` - Slot 详情
- `GET /api/user/preferences` / `POST /api/user/preferences`
- `GET /api/user/procedural` / `POST /api/user/procedural`

## Development Commands

From project root:

```bash
# lint
make lint

# backend tests
make test-backend

# frontend unit/component tests
make test-frontend

# frontend e2e
make test-frontend-e2e
```

Direct commands:

```bash
cd backend && pytest ../tests/backend -v --cov=app --cov-report=term-missing
cd frontend && npm run lint && npm run test
```

## Documentation Index

Architecture:

- [Agent v13](docs/arch/agent-v13.md)
- [Memory v5](docs/arch/memory-v5.md)
- [Prompt + Context v20](docs/arch/prompt-context-v20.md)
- [Skill v3](docs/arch/skill-v3.md)
- [Tools v12](docs/arch/tools-v12.md)

Implementation plans:

- [Plans Index](docs/plans/README.md)
- [Latest task orchestration plan](docs/plans/plan-phase23-task-orchestration.md)

Reviews:

- [Tool system implementation review](docs/reviews/tool-system-implementation-review.md)

## Branching

当前默认发布分支为 `master`。

## License

MIT
