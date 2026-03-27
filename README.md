# Multi-Tool AI Agent

> 企业级 Multi-Tool AI Agent 系统，具备 Memory、Skills 和可观测性能力

## 🚀 快速开始

### 前置要求

- Docker 和 Docker Compose
- Python 3.11+
- Node.js 20+

### 本地开发

1. **克隆仓库**
   ```bash
   git clone <repo-url>
   cd agent_app
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入必要的 API Keys
   ```

3. **启动所有服务**
   ```bash
   docker-compose up -d
   ```

4. **访问应用**
   - 前端: http://localhost:3000
   - 后端 API: http://localhost:8000
   - API 文档: http://localhost:8000/api/docs

### 手动启动（不使用 Docker）

**后端**
```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --log-level info
```

启动后日志输出示例：
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Starting Multi-Tool AI Agent backend...
INFO:     Environment: development
INFO:     LLM Provider: ollama
INFO:     Database initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**前端**
```bash
cd frontend
npm install
npm run dev
```

## 📁 项目结构

```
agent_app/
├── backend/              # Python 后端
│   ├── app/
│   │   ├── agent/       # Agent 核心逻辑
│   │   ├── api/         # FastAPI 路由
│   │   ├── core/        # 配置和工具
│   │   ├── db/          # 数据库连接
│   │   ├── llm/         # LLM Factory
│   │   ├── skills/      # Skills Manager
│   │   ├── tools/       # 工具注册表
│   │   └── middleware/  # LangGraph 中间件
│   └── tests/           # 测试
├── frontend/            # Next.js 前端
│   └── src/
│       ├── app/        # App Router 页面
│       ├── components/ # React 组件
│       ├── lib/        # 工具函数
│       ├── store/      # Zustand 状态
│       └── types/      # TypeScript 类型
├── supabase/           # 数据库迁移
├── docs/               # 架构和实施文档
└── docker-compose.yml  # Docker 编排
```

## 🔧 核心功能

### 1. 三层 Memory 架构

- **Short Memory**: 会话级上下文（24h TTL）
- **Long Memory**: 用户画像持久化
- **Working Memory**: Token 预算管理（32K）

### 2. Skills 插件系统

```
~/.agents/skills/          # 全局 Skills
    ├── web_search/
    ├── analyzer/
    └── ...
project/skills/             # 项目 Skills（优先级更高）
    ├── custom_skill/
    └── ...
```

### 3. 内置工具

| 工具 | 描述 | 确认 |
|-----|------|-----|
| `read_file` | 读取文件内容 | ❌ |
| `fetch_url` | HTTP 请求 | ❌ |
| `token_counter` | Token 计数 | ❌ |
| `tavily_search` | 网络搜索 | ❌ |
| `browser_use` | 浏览器自动化 | ✅ |
| `python_repl` | Python 代码执行 | ✅ |

### 4. HIL 人工介入

敏感操作会触发用户确认：
- 浏览器自动化
- Python 代码执行
- 删除/发送操作

### 5. SSE 实时推送

Agent 推理过程实时推送到前端时间轴可视化

## 🧪 测试

```bash
# 后端单元测试
cd backend
pytest

# 前端测试
cd frontend
npm test

# E2E 测试
npm run test:e2e
```

## 📚 文档

- [架构设计](docs/superpowers/specs/2026-03-20-multi-tool-agent-design.md)
- [产品需求](docs/implementation/product-requirements.md)
- [后端实施计划](docs/implementation/backend-implementation-plan.md)
- [前端实施计划](docs/implementation/frontend-implementation-plan.md)
- [数据库设计](docs/superpowers/database-implementation-plan.md)
- [部署指南](docs/superpowers/deployment/2026-03-20-deployment-implementation-plan.md)
- [测试策略](docs/testing-strategy.md)

## 🛠️ 开发状态

当前处于 **Phase 1: 基础设施** 阶段

- [x] 项目脚手架
- [x] Docker Compose 配置
- [ ] 数据库初始化
- [ ] LLM Factory
- [ ] 核心 Tools
- [ ] Memory 系统
- [ ] Skills 系统

## 📄 License

MIT
# -RAG_App
