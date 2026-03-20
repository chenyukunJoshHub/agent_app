# Multi-Tool AI Agent · 部署实施计划

**日期**: 2026-03-20
**状态**: 初稿
**版本**: v1.0
**负责人**: DevOps Team

---

## 目录

1. [部署架构概览](#部署架构概览)
2. [本地开发环境](#本地开发环境)
3. [生产部署架构](#生产部署架构)
4. [环境变量管理](#环境变量管理)
5. [CI/CD 配置](#cicd-配置)
6. [监控和日志](#监控和日志)
7. [备份和恢复](#备份和恢复)
8. [成本估算](#成本估算)
9. [分阶段实施计划](#分阶段实施计划)

---

## 部署架构概览

### 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        部署架构总览                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    本地开发环境                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │   │
│  │  │ Frontend│  │ Backend │  │   DB    │  │ Ollama  │         │   │
│  │  │ :3000   │  │ :8000   │  │ :54322  │  │ :11434  │         │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │   │
│  │                    Docker Compose                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    生产环境                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │   Vercel     │  │   Railway    │  │   Supabase   │       │   │
│  │  │              │  │              │  │              │       │   │
│  │  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │       │   │
│  │  │  │ Next.js│  │  │  │FastAPI │  │  │  │Postgres│  │       │   │
│  │  │  │ 2x CDN │  │  │  │ 2x 实例 │  │  │  │Pro 计划│  │       │   │
│  │  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │       │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │   │
│  │         │                    │                    │           │   │
│  │         └────────────────────┼────────────────────┘           │   │
│  │                              │                                │   │
│  │  ┌───────────────────────────┼───────────────────────┐       │   │
│  │  │  External Services                             │       │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐          │       │   │
│  │  │  │DeepSeek │  │Ollama   │  │Grafana  │          │       │   │
│  │  │  │  API    │  │ (可选)  │  │  Cloud  │          │       │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘          │       │   │
│  │  └─────────────────────────────────────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 技术选型对比

| 组件 | 本地开发 | 生产环境 | 说明 |
|-----|---------|---------|------|
| 前端 | Docker + Next.js Dev | Vercel Pro | 自动 CDN + 边缘部署 |
| 后端 | Docker + Uvicorn | Railway (2x) | 自动扩缩容 |
| 数据库 | Docker PostgreSQL | Supabase Pro | 托管 + 备份 |
| LLM | Ollama Local | DeepSeek API | 按需计费 |
| 监控 | 本地日志 | Grafana Cloud | SLO 追踪 |

---

## 本地开发环境

### Docker Compose 配置

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:16-alpine
    container_name: agent_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-agent_db}
      POSTGRES_INITDB_ARGS: "-E UTF8 --locale=C"
    ports:
      - "${POSTGRES_PORT:-54322}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./supabase/migrations:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-agent_db}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - agent_network

  # Backend FastAPI
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: agent_backend
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    environment:
      # 数据库
      DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-agent_db}
      DATABASE_POOL_SIZE: ${DATABASE_POOL_SIZE:-20}
      DATABASE_MAX_OVERFLOW: ${DATABASE_MAX_OVERFLOW:-10}

      # LLM 配置
      LLM_PROVIDER: ${LLM_PROVIDER:-ollama}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      OLLAMA_MODEL: ${OLLAMA_MODEL:-claude-opus-4-6}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}

      # 应用配置
      APP_ENV: development
      LOG_LEVEL: ${LOG_LEVEL:-DEBUG}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}
      SECRET_KEY: ${SECRET_KEY:-dev-secret-change-in-production}

      # Redis (可选，用于缓存)
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - /app/.venv
      - /app/__pycache__
    networks:
      - agent_network
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Frontend Next.js
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: agent_frontend
    ports:
      - "${FRONTEND_PORT:-3000:3000}"
    environment:
      NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
      NEXT_PUBLIC_APP_ENV: development
      NODE_ENV: development
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    networks:
      - agent_network

  # Redis (可选，用于缓存和会话)
  redis:
    image: redis:7-alpine
    container_name: agent_redis
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    networks:
      - agent_network
    command: redis-server --appendonly yes

  # Ollama (可选，本地 LLM)
  ollama:
    image: ollama/ollama:latest
    container_name: agent_ollama
    ports:
      - "${OLLAMA_PORT:-11434}:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_ORIGINS=*
    networks:
      - agent_network
    # GPU 支持 (需要 nvidia-docker)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # PgAdmin (可选，数据库管理)
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: agent_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@local.dev}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin}
    ports:
      - "${PGADMIN_PORT:-5050}:80"
    depends_on:
      - postgres
    networks:
      - agent_network
    profiles:
      - tools

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  ollama_data:
    driver: local

networks:
  agent_network:
    driver: bridge
```

### Backend Dockerfile (开发模式)

`backend/Dockerfile.dev`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 开发模式挂载点
VOLUME ["/app"]

# 暴露端口
EXPOSE 8000

# 默认命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Frontend Dockerfile (开发模式)

`frontend/Dockerfile.dev`:

```dockerfile
FROM node:20-alpine

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 开发模式挂载点
VOLUME ["/app"]

# 暴露端口
EXPOSE 3000

# 默认命令
CMD ["npm", "run", "dev"]
```

### Backend Dockerfile (生产模式)

`backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 从 builder 复制依赖
COPY --from=builder /root/.local /root/.local

# 复制应用代码
COPY ./app ./app

# 确保本地 Python 包在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 运行应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Frontend Dockerfile (生产模式)

`frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine as base

WORKDIR /app

# 依赖安装阶段
FROM base as deps
COPY package*.json ./
RUN npm ci

# 构建阶段
FROM base as build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# 运行阶段
FROM base as runner
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
```

### 健康检查配置

`backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Multi-Tool Agent API")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    # 检查数据库连接
    db_status = await check_database()

    # 检查 LLM 连接
    llm_status = await check_llm()

    return JSONResponse({
        "status": "healthy" if all([db_status, llm_status]) else "degraded",
        "checks": {
            "database": db_status,
            "llm": llm_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    })
```

### 热重载支持

开发模式下使用以下配置实现热重载：

**Backend (Uvicorn)**:
```bash
uvicorn app.main:app --reload --log-level debug
```

**Frontend (Next.js)**:
```javascript
// next.config.js
module.exports = {
  webpack: (config) => {
    config.watchOptions = {
      poll: 1000,
      aggregateTimeout: 300,
    };
    return config;
  },
};
```

### 本地开发启动脚本

创建 `scripts/dev.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 启动本地开发环境..."

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    exit 1
fi

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  未找到 .env 文件，使用默认配置"
fi

# 启动服务
docker-compose up -d postgres redis backend frontend

# 等待服务就绪
echo "⏳ 等待服务启动..."
sleep 10

# 运行数据库迁移
docker-compose exec backend alembic upgrade head

echo "✅ 开发环境启动完成！"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   PgAdmin:  http://localhost:5050 (需要 --profile tools)"
```

---

## 生产部署架构

### 服务提供商选择

| 服务 | 推荐方案 | 备选方案 | 选择理由 |
|-----|---------|---------|---------|
| 前端 | **Vercel Pro** | Netlify, Cloudflare Pages | 最佳 Next.js 支持，自动 CDN |
| 后端 | **Railway** | Fly.io, Render | 简单部署，自动 HTTPS |
| 数据库 | **Supabase Pro** | Neon, PlanetScale | 内置 RLS，备份友好 |
| LLM | **DeepSeek API** | OpenAI, Anthropic | 成本效益高 |
| 监控 | **Grafana Cloud** | Datadog, New Relic | 免费层 generous |

### Vercel 前端部署

**vercel.json**:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "framework": "nextjs",
  "regions": ["sin1"],
  "env": {
    "NEXT_PUBLIC_API_URL": "@api-url",
    "NEXT_PUBLIC_APP_ENV": "production"
  },
  "build": {
    "env": {
      "NEXT_PUBLIC_API_URL": "@api-url"
    }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.yourdomain.com/:path*"
    }
  ]
}
```

**Next.config.js 生产配置**:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  swcMinify: true,

  // 图片优化
  images: {
    domains: ['cdn.yourdomain.com'],
    formats: ['image/avif', 'image/webp'],
  },

  // 压缩
  compress: true,

  // 生产环境优化
  poweredByHeader: false,
  generateEtags: true,

  // 实验性功能
  experimental: {
    optimizeCss: true,
  },
};

module.exports = nextConfig;
```

### Railway 后端部署

**railway.json**:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "services": {
    "backend": {
      "environment": {
        "APP_ENV": "production",
        "LOG_LEVEL": "INFO",
        "WORKERS": "4"
      }
    }
  }
}
```

**nixpacks.toml** (Railway 构建配置):

```toml
[phases.build]
cmds = ["pip install --no-cache-dir -r requirements.txt"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4"

[phases.install]
cmds = ["pip install --no-cache-dir -r requirements.txt"]
```

### Supabase 数据库配置

**Supabase 项目设置**:

1. **启用 RLS (Row Level Security)**:
```sql
-- 为所有用户表启用 RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_traces ENABLE ROW LEVEL SECURITY;

-- 用户只能访问自己的数据
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can view own sessions" ON sessions
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own traces" ON agent_traces
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own traces" ON agent_traces
  FOR INSERT WITH CHECK (auth.uid() = user_id);
```

2. **自动备份配置**:
- 每日自动备份: 凌晨 2:00 UTC
- 保留期: 30 天
- 点时间恢复 (PITR): 启用

3. **连接池设置**:
- Pool Mode: Transaction
- Max Connections: 60
- Statement Timeout: 30s

### Grafana Cloud 监控

**grafana-agent.yaml**:

```yaml
metrics:
  configs:
  - name: integrations
    scrape_configs:
    # FastAPI 指标
    - job_name: 'fastapi'
      static_configs:
        - targets: ['localhost:8000']
      metrics_path: '/metrics'

    # PostgreSQL 指标
    - job_name: 'postgres'
      static_configs:
        - targets: ['localhost:9187']

    # 系统指标
    - job_name: 'node'
      static_configs:
        - targets: ['localhost:9100']

  wal:
    directory: /tmp/wal

integrations:
  agent:
    enabled: true
  prometheus_remote_write:
  - url: https://prometheus-prod-01-prod-us-central-0.grafana.net/api/prom/push
    basic_auth:
      username: ${GRAFANA_CLOUD_PROMETHEUS_USERNAME}
      password: ${GRAFANA_CLOUD_PROMETHEUS_PASSWORD}

logs:
  configs:
  - name: default
    clients:
    - url: https://logs-prod-01.grafana.net/loki/api/v1/push
      basic_auth:
        username: ${GRAFANA_CLOUD_LOKI_USERNAME}
        password: ${GRAFANA_CLOUD_LOKI_PASSWORD}
    positions:
      filename: /tmp/positions.yaml
    scrape_configs:
    - job_name: fastapi-logs
      static_configs:
        - targets:
          - localhost
          labels:
            job: fastapi
            __path__: /var/log/fastapi/*.log
```

---

## 环境变量管理

### 环境变量结构

```
.env.example              # 提交到 Git，模板文件
.env.development          # 本地开发（不提交）
.env.staging              # 预发布环境（不提交）
.env.production           # 生产环境（不提交）
.env.test                 # 测试环境（不提交）
```

### .env.example (提交到 Git)

```bash
# ========================================
# 应用配置
# ========================================
APP_ENV=development
LOG_LEVEL=DEBUG
SECRET_KEY=your-secret-key-here-change-this

# ========================================
# 数据库配置
# ========================================
DATABASE_URL=postgresql://user:password@localhost:5432/agent_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ========================================
# LLM 配置
# ========================================
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=claude-opus-4-6
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# ========================================
# Redis (可选)
# ========================================
REDIS_URL=redis://localhost:6379/0

# ========================================
# CORS 配置
# ========================================
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# ========================================
# 安全配置
# ========================================
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# ========================================
# 限流配置
# ========================================
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=100

# ========================================
# 监控配置
# ========================================
GRAFANA_CLOUD_PROMETHEUS_USERNAME=
GRAFANA_CLOUD_PROMETHEUS_PASSWORD=
GRAFANA_CLOUD_LOKI_USERNAME=
GRAFANA_CLOUD_LOKI_PASSWORD=

# ========================================
# 前端环境变量 (NEXT_PUBLIC_*)
# ========================================
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_ENV=development
NEXT_PUBLIC_SENTRY_DSN=

# ========================================
# Docker 配置
# ========================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=agent_db
POSTGRES_PORT=54322

BACKEND_PORT=8000
FRONTEND_PORT=3000
REDIS_PORT=6379
OLLAMA_PORT=11434
PGADMIN_PORT=5050
```

### 环境变量验证

创建 `backend/app/config.py`:

```python
from pydantic import BaseSettings, Field, validator
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_ENV: str = Field(default="development", regex="^(development|staging|production)$")
    LOG_LEVEL: str = Field(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR)$")
    SECRET_KEY: str = Field(default=secrets.token_urlsafe(32))

    # 数据库
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)

    # LLM
    LLM_PROVIDER: str = Field(default="ollama", regex="^(ollama|deepseek|openai)$")
    OLLAMA_BASE_URL: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None

    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # 安全
    JWT_SECRET_KEY: str = Field(default=secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = Field(default=60, ge=1)

    # 限流
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)
    RATE_LIMIT_BURST: int = Field(default=100, ge=1)

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

### 敏感信息保护策略

1. **永不提交敏感信息**:
```bash
# .gitignore
.env
.env.*
!.env.example
*.key
*.pem
secrets/
```

2. **使用密钥管理服务**:
- Railway: 环境变量自动加密
- Vercel: 使用 Environment Variables
- Supabase: 使用 Vault

3. **密钥轮换**:
- JWT 密钥: 每 90 天轮换
- API 密钥: 每 180 天轮换
- 数据库密码: 每 180 天轮换

4. **审计日志**:
```python
# 记录敏感操作
logger.info("secret_access", resource="database", user_id=user_id)
```

---

## CI/CD 配置

### GitHub Actions 工作流

创建 `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ========================================
  # 代码质量检查
  # ========================================
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install ruff mypy pylint

      - name: Run Ruff
        run: ruff check ./backend

      - name: Run MyPy
        run: mypy ./backend/app

  # ========================================
  # 前端检查
  # ========================================
  lint-frontend:
    name: Lint Frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Run ESLint
        working-directory: ./frontend
        run: npm run lint

      - name: Run TypeScript check
        working-directory: ./frontend
        run: npm run type-check

  # ========================================
  # 单元测试
  # ========================================
  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        run: |
          pytest --cov=app --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml

  # ========================================
  # 构建和推送镜像
  # ========================================
  build:
    name: Build & Push Image
    needs: [lint, test, lint-frontend]
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=sha,prefix={{branch}}-

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ========================================
  # 前端部署到 Vercel
  # ========================================
  deploy-frontend:
    name: Deploy Frontend
    needs: [lint-frontend, test]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          working-directory: ./frontend
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'

  # ========================================
  # 后端部署到 Railway
  # ========================================
  deploy-backend:
    name: Deploy Backend
    needs: [build]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: Deploy to Railway
        uses: railwayapp/cli-action@v2
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
          command: "up --detach"
```

### 自动化测试配置

`pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --asyncio-mode=auto
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### 数据库迁移自动化

创建 `.github/workflows/migrate.yml`:

```yaml
name: Database Migration

on:
  push:
    paths:
      - 'alembic/versions/**'
    branches: [main]

jobs:
  migrate:
    name: Run Migrations
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install alembic psycopg2-binary

      - name: Run migrations
        env:
          DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
        run: |
          alembic upgrade head
```

---

## 监控和日志

### 结构化日志配置

`backend/app/logging_config.py`:

```python
import structlog
import logging
from typing import Any

def configure_logging(log_level: str = "INFO") -> None:
    """配置结构化日志"""

    # 设置标准库日志级别
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    # 配置 structlog
    structlog.configure(
        processors=[
            # 过滤日志级别
            structlog.stdlib.filter_by_level,

            # 添加日志名称
            structlog.stdlib.add_logger_name,

            # 添加日志级别
            structlog.stdlib.add_log_level,

            # 添加时间戳
            structlog.processors.TimeStamper(fmt="iso"),

            # 添加调用信息
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),

            # 异常处理
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),

            # JSON 格式输出 (生产环境)
            structlog.processors.JSONRenderer() if log_level != "DEBUG"
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# 使用示例
logger = structlog.get_logger(__name__)

def log_request(
    session_id: str,
    user_id: str,
    request_id: str,
    **kwargs: Any
) -> structlog.BoundLogger:
    """创建绑定了请求上下文的 logger"""
    return logger.bind(
        session_id=session_id,
        user_id=user_id,
        request_id=request_id,
        **kwargs
    )
```

### 核心指标监控

**Prometheus 指标定义**:

`backend/app/metrics.py`:

```python
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client.fastapi import PrometheusMiddleware
from functools import lru_cache

# ========================================
# HTTP 指标
# ========================================
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# ========================================
# Agent 指标
# ========================================
agent_invocations_total = Counter(
    "agent_invocations_total",
    "Total agent invocations",
    ["session_id", "status"]
)

agent_duration_seconds = Histogram(
    "agent_duration_seconds",
    "Agent execution duration",
    ["session_id"]
)

# ========================================
# LLM 指标
# ========================================
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["provider", "model", "status"]
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "model", "type"]  # type: input/output
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM API latency",
    ["provider", "model"]
)

# ========================================
# 工具调用指标
# ========================================
tool_invocations_total = Counter(
    "tool_invocations_total",
    "Total tool invocations",
    ["tool_name", "status"]
)

tool_duration_seconds = Histogram(
    "tool_duration_seconds",
    "Tool execution duration",
    ["tool_name"]
)

# ========================================
# 数据库指标
# ========================================
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["operation", "table"]
)

db_pool_size = Gauge(
    "db_pool_size",
    "Database connection pool size"
)

db_pool_available = Gauge(
    "db_pool_available",
    "Available database connections"
)

# ========================================
# Memory 指标
# ========================================
memory_short_size = Gauge(
    "memory_short_size",
    "Short memory size in tokens"
)

memory_long_size = Gauge(
    "memory_long_size",
    "Long memory size in tokens"
)

# ========================================
# 系统信息
# ========================================
app_info = Info(
    "app",
    "Application information"
)

@lru_cache
def set_app_info(
    version: str,
    environment: str,
    git_commit: str
) -> None:
    """设置应用信息"""
    app_info.info({
        "version": version,
        "environment": environment,
        "git_commit": git_commit
    })
```

### 告警配置

**Grafana Alert Rules**:

```yaml
groups:
  - name: api_alerts
    interval: 30s
    rules:
      # API 错误率告警
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m]) /
          rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API 错误率过高"
          description: "错误率 {{ $value | humanizePercentage }} 超过 5%"

      # API 延迟告警
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "API P95 延迟过高"
          description: "P95 延迟 {{ $value }}s 超过 5s"

  - name: agent_alerts
    interval: 30s
    rules:
      # LLM 调用失败率
      - alert: HighLLMFailureRate
        expr: |
          rate(llm_requests_total{status="error"}[5m]) /
          rate(llm_requests_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "LLM 调用失败率过高"
          description: "失败率 {{ $value | humanizePercentage }} 超过 10%"

      # 工具调用超时
      - alert: ToolTimeout
        expr: |
          rate(tool_invocations_total{status="timeout"}[5m]) >
          rate(tool_invocations_total{status="success"}[5m]) * 0.2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "工具调用超时过多"
          description: "超时率超过 20%"

  - name: database_alerts
    interval: 30s
    rules:
      # 连接池使用率
      - alert: HighPoolUsage
        expr: |
          (db_pool_size - db_pool_available) / db_pool_size > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "数据库连接池使用率过高"
          description: "使用率 {{ $value | humanizePercentage }} 超过 80%"

      # 慢查询
      - alert: SlowQueries
        expr: |
          histogram_quantile(0.95,
            rate(db_query_duration_seconds_bucket[5m])
          ) > 1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "数据库慢查询过多"
          description: "P95 查询时间 {{ $value }}s 超过 1s"
```

### 仪表盘配置

**Grafana Dashboard JSON** (关键面板):

```json
{
  "title": "Multi-Tool Agent Dashboard",
  "panels": [
    {
      "title": "请求速率",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total[5m])) by (status)"
        }
      ],
      "type": "graph"
    },
    {
      "title": "P95 延迟",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
        }
      ],
      "type": "graph"
    },
    {
      "title": "LLM Token 消耗",
      "targets": [
        {
          "expr": "sum(rate(llm_tokens_total[1h])) by (type)"
        }
      ],
      "type": "graph"
    },
    {
      "title": "工具调用统计",
      "targets": [
        {
          "expr": "sum(rate(tool_invocations_total[5m])) by (tool_name, status)"
        }
      ],
      "type": "graph"
    },
    {
      "title": "数据库连接池",
      "targets": [
        {
          "expr": "db_pool_size - db_pool_available"
        }
      ],
      "type": "gauge"
    }
  ]
}
```

---

## 备份和恢复

### 数据库备份策略

**自动备份配置** (Supabase):

| 备份类型 | 频率 | 保留期 | 大小限制 |
|---------|------|--------|---------|
| 增量备份 | 每 5 分钟 | 24 小时 | - |
| 全量备份 | 每日 | 30 天 | 10 GB |
| PITR | 连续 | 30 天 | - |

**手动备份脚本**:

`scripts/backup-db.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/agent_db_${DATE}.sql"

mkdir -p ${BACKUP_DIR}

echo "🗄️  开始数据库备份..."

# 从环境变量读取
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-agent_db}"
PGUSER="${PGUSER:-postgres}"

# 执行备份
pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} \
    --format=plain \
    --no-owner \
    --no-acl \
    > ${BACKUP_FILE}

# 压缩
gzip ${BACKUP_FILE}
BACKUP_FILE="${BACKUP_FILE}.gz"

echo "✅ 备份完成: ${BACKUP_FILE}"

# 清理旧备份 (保留最近 30 天)
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +30 -delete

# 上传到 S3 (可选)
if [ -n "${S3_BUCKET}" ]; then
    aws s3 cp ${BACKUP_FILE} s3://${S3_BUCKET}/backups/
    echo "☁️  已上传到 S3"
fi
```

### 恢复流程

**从备份恢复**:

`scripts/restore-db.sh`:

```bash
#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE=$1

echo "🔄 开始恢复数据库..."

# 解压
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c ${BACKUP_FILE} > /tmp/restore.sql
    RESTORE_FILE="/tmp/restore.sql"
else
    RESTORE_FILE=${BACKUP_FILE}
fi

# 确认
echo "⚠️  这将覆盖当前数据库!"
read -p "确认继续? (yes/no): " confirm

if [ "${confirm}" != "yes" ]; then
    echo "❌ 已取消"
    exit 1
fi

# 执行恢复
psql -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} < ${RESTORE_FILE}

echo "✅ 恢复完成"

# 清理
rm -f /tmp/restore.sql
```

### 灾难恢复计划

**RTO/RPO 目标**:

| 指标 | 目标 | 实现方式 |
|-----|------|---------|
| RPO (数据丢失) | < 5 分钟 | PITR + 连续归档 |
| RTO (恢复时间) | < 1 小时 | 自动化恢复脚本 |

**灾难恢复步骤**:

1. **检测故障** (自动告警)
2. **切换到备用区域** (DNS 更新)
3. **从备份恢复** (PITR)
4. **验证数据完整性**
5. **切换回主区域**

**备用区域配置**:

```yaml
# 多区域部署
regions:
  primary: ap-southeast-1
  secondary: ap-northeast-1

failover:
  enabled: true
  dns_ttl: 60
  health_check_interval: 30
  unhealthy_threshold: 3
```

---

## 成本估算

### 月度成本明细

| 服务 | 规格 | 月度成本 (USD) | 说明 |
|-----|------|---------------|------|
| **Vercel Pro** | - | $20 | 前端托管 + CDN |
| **Railway** | 2x 实例 (512MB) | $20-40 | 后端 API |
| **Supabase Pro** | 8GB RAM, 50GB 存储 | $25 | 数据库 + 认证 |
| **DeepSeek API** | - | $50-100 | LLM 调用 |
| **Grafana Cloud** | 免费层 | $0 | 监控 (50GB logs) |
| **总计** | | **$115-185** | - |

### 成本优化建议

1. **LLM 成本优化**:
   - 使用本地 Ollama (开发环境)
   - 实现请求缓存
   - 使用更小的模型处理简单任务

2. **数据库优化**:
   - 启用连接池
   - 定期清理历史数据
   - 使用压缩

3. **前端优化**:
   - 启用 Vercel Edge Functions
   - 图片优化 (WebP)
   - 代码分割

### 成本监控

**预算告警**:

```python
# 每日成本检查
DAILY_BUDGET = {
    "llm_tokens": 1_000_000,  # 100万 tokens/天
    "api_requests": 100_000,   # 10万请求/天
}

def check_budget():
    """检查预算使用情况"""
    today_tokens = get_today_token_usage()
    if today_tokens > DAILY_BUDGET["llm_tokens"]:
        alert_admin("LLM token 超预算!")
```

---

## 分阶段实施计划

### Phase 1: 基础设施搭建 (Week 1)

- [ ] 创建 Docker Compose 配置
- [ ] 配置本地开发环境
- [ ] 设置数据库 Schema
- [ ] 配置 GitHub Actions 基础 CI

### Phase 2: 部署管道 (Week 2)

- [ ] 配置 Vercel 部署
- [ ] 配置 Railway 部署
- [ ] 设置 Supabase 项目
- [ ] 配置环境变量管理

### Phase 3: 监控告警 (Week 3)

- [ ] 集成结构化日志
- [ ] 配置 Prometheus 指标
- [ ] 设置 Grafana 仪表盘
- [ ] 配置告警规则

### Phase 4: 备份恢复 (Week 4)

- [ ] 配置自动备份
- [ ] 编写恢复脚本
- [ ] 测试灾难恢复
- [ ] 文档化运维流程

### Phase 5: 优化调优 (Week 5-6)

- [ ] 性能基准测试
- [ ] 成本优化
- [ ] 安全加固
- [ ] 文档完善

---

## 附录

### A. 快速参考

```bash
# 本地开发启动
docker-compose up -d

# 查看日志
docker-compose logs -f backend

# 运行迁移
docker-compose exec backend alembic upgrade head

# 备份数据库
./scripts/backup-db.sh

# 部署到生产
git push origin main
```

### B. 端口映射

| 服务 | 本地端口 | 容器端口 |
|-----|---------|---------|
| Frontend | 3000 | 3000 |
| Backend | 8000 | 8000 |
| PostgreSQL | 54322 | 5432 |
| Redis | 6379 | 6379 |
| Ollama | 11434 | 11434 |
| PgAdmin | 5050 | 80 |

### C. 相关文档

- [架构设计文档](../specs/2026-03-20-multi-tool-agent-design.md)
- [数据库设计](../database/README.md)
- [安全指南](../security/README.md)

---

**文档版本**: v1.0
**最后更新**: 2026-03-20
**维护者**: DevOps Team
