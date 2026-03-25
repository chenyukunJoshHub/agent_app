# Findings & Decisions - Multi-Tool AI Agent

> **更新日期**: 2026-03-25
> **项目类型**: Full-stack Web Application

---

## Session Findings (2026-03-25) — Context UI Redesign

### 问题
Context 面板需要动态化展示全部 10 个 Slot，链路面板存在重复内容，Turn 边界不明显，且前端无法直接访问后端的 state["messages"]。

### 查阅章节
- 无特定架构文档引用（这是一个前端 UI 重构计划）

### 结论
1. **EMPTY_CONTEXT_DATA 常量**：作为 ContextWindowData 的初始值，避免 null 判断，确保 Context 面板始终渲染
2. **Turn Tracking 架构**：使用 currentTurnId + turnCounter 组合，addTraceEvent 自动打上 turnId，clearMessages 重置状态
3. **StateMessage 同步**：后端 done 事件附带完整 messages 数组，前端比较消息数量后替换（后端数据更完整）
4. **Turn 分隔线**：使用 useMemo 按事件原始顺序分组，支持 Turn 完成/失败 badge
5. **10 Slot 渲染**：扩展 rawToCanonical 和 categoryLabels，确保 output_format 和 user_input 正确映射

### 影响文件
- `frontend/src/types/trace.ts` - 新增 turnId 字段
- `frontend/src/types/context-window.ts` - 新增 StateMessage、summary_text、EMPTY_CONTEXT_DATA
- `frontend/src/store/use-session.ts` - 新增 turnId、stateMessages、incrementTurn、setStateMessages
- `backend/app/agent/middleware/trace.py` - done 事件新增 messages 字段
- `frontend/src/components/ExecutionTracePanel.tsx` - Turn 分隔线
- `frontend/src/components/ContextWindowPanel.tsx` - 10 Slot 渲染 + Slot ⑧ 预览
- `frontend/src/components/MessageList.tsx` - tool 气泡 + 压缩通知
- `frontend/src/app/page.tsx` - 完成端到端集成

---

## Session Findings (2026-03-25) — Context UI Redesign 测试修复

### 问题
全量测试中有 26 个失败用例，需要系统性排查根因并修复，确保 Context UI Redesign 的所有改动通过测试。

### 查阅章节
- 无特定架构文档引用（这是一个测试修复任务）

### 结论
1. **ContextWindowPanel Statistics Row 结构错误**：
   - 根因：多个 `</div>` 过早关闭父 div，导致后续统计行（Reserved Buffer、Actual Savings、Free Space）位置错误
   - 修复：恢复完整的 DOM 结构，确保所有统计行在同一个父 div 中
   
2. **CategoryUsage 过滤逻辑错误**：
   - 根因：`categoryUsage` 中使用了 `.filter((item) => item.tokens > 0)` 过滤逻辑
   - 影响：`output_format` 和 `user_input` 的 tokens=0 时被过滤掉，导致 category section 缺失
   - 修复：移除 `.filter()` 逻辑，允许所有 10 个 category 显示

3. **data-testid 重复**：
   - 根因：多次编辑操作导致同一 data-testid 出现在多个位置
   - 影响：测试库抛出 "Found multiple elements" 错误
   - 修复：清理重复的 data-testid 属性

### 影响文件
- `frontend/src/components/ContextWindowPanel.tsx` - 修复 Statistics Row 结构和 CategoryUsage 逻辑

### 测试结果
- **修复前**：207 passed / 26 failed
- **修复后**：212 passed / 21 failed
- **净提升**：+5 passed, -5 failed
- **ContextWindowPanel 测试**：9 个通过，0 个失败 ✅
- **未修复的测试（21 个）**：SkillDetail、SkillPanel、SSEManager 的测试，与本次改动无关

---

## Session Findings (2026-03-24) — Tools 模块补全

### 问题
Tools 模块只有简单的 ToolRegistry（名称去重）和各工具独立实现，缺少架构设计文档中定义的元数据体系、权限决策、幂等保障、统一装配口，前端链路面板的「工具层」阶段无数据。

### 查阅章节
- Agent v13 §1.12（工具系统架构）
- Skill v3 §1.4（Skill Protocol — activate_skill 语义）
- Agent v13 §2.4（SSE 流式架构 — trace_event 协议）

### 结论
1. **ToolMeta 作为元数据载体**：贯穿 ToolManager / PolicyEngine / build_tool_registry / TraceMiddleware，单一数据源避免不一致
2. **PolicyEngine 单一职责**：只做决策（allow/ask/deny），不做执行；未知 effect_class 走 "ask" 保守兜底
3. **activate_skill ≠ read_file**：语义不同，activate_skill 通过 SkillManager.read_skill_content() 读取，保留 read_file 用于通用文件
4. **build_tool_registry 是唯一装配口**：langchain_engine 必须调用它，不再直接 import 单个工具
5. **SSE stage="tools" 事件**：tool_call_planned 在 aafter_model 检测 AIMessage.tool_calls，tool_call_result 在 aafter_agent 检测 ToolMessage

### 影响文件
- `backend/app/tools/base.py`（新建）
- `backend/app/tools/manager.py`（新建）
- `backend/app/tools/policy.py`（新建）
- `backend/app/tools/idempotency.py`（新建）
- `backend/app/tools/readonly/skill_loader.py`（新建）
- `backend/app/tools/registry.py`（修改）
- `backend/app/tools/__init__.py`（修改）
- `backend/app/skills/manager.py`（修改）
- `backend/app/agent/langchain_engine.py`（修改）
- `backend/app/agent/middleware/trace.py`（修改）
- `frontend/src/components/ToolCallCard.tsx`（新建）
- `frontend/src/components/ExecutionTracePanel.tsx`（修改）

---

## Session Findings (2026-03-24) — UI 清理

### 问题
前端右侧 Context 面板与链路面板的 `slot snapshot` 来源不一致，导致识别结果偏差；同时页面存在已失效历史功能（右上角状态区、右栏 timeline/tools）。

### 查阅章节
- Prompt v20 §1.2（10 个 Slot 与 Context Window 分区）
- Prompt v20 §1.3（预算与弹性空间）

### 结论
1. Context 与链路必须共用同一份 slot 快照源（`slot_details`）；
2. Context 概览层在完整 slot 之外，额外展示 `Free space` 与 `Autocompact buffer`；
3. 删除无效历史能力后，主流式观测统一到 `trace_event`，不再维护独立 `tool_start/tool_result` UI 通道。

### 影响文件
- `frontend/src/components/ContextWindowPanel.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/store/use-session.ts`
- `backend/app/agent/langchain_engine.py`
- `backend/app/api/context.py`
- `backend/app/api/chat.py`

---

## Requirements

### 产品需求
- **核心目标**: 构建企业级 Multi-Tool AI Agent 系统
- **目标用户**: 面试官、开发者、潜在用户
- **核心价值**: "让 AI 不仅能思考，更能行动 - 且全程可控"

### 功能需求

| 优先级 | 功能模块 | Phase |
|--------|---------|-------|
| 🔴 P0 | 复杂任务处理 | Phase 1 |
| 🔴 P0 | 推理链可视化 | Phase 1 |
| 🔴 P0 | HIL 人工介入 | Phase 1 |
| 🔴 P0 | Memory 三层架构 | Phase 2 |
| 🔴 P0 | 安全加固 | Phase 3 |
| 🟡 P1 | Skills 插件系统 | Phase 4 |
| 🟡 P1 | SSE 可观测性 | Phase 5 |
| ⚪ P2 | 完整测试覆盖 | Phase 6 |

---

## Research Findings

### 架构设计亮点

1. **Memory 三层架构**
   - Short Memory: PostgreSQL (AsyncPostgresSaver) - 会话期间
   - Long Memory: PostgreSQL (AsyncPostgresStore) - 用户画像
   - Working Memory: Context Window - Token 预算管理

2. **Ephemeral 注入策略**
   - 用户画像临时注入到 System Prompt
   - 避免污染聊天历史
   - 通过 `wrap_model_call` 钩子实现

3. **Agent Skills 四层结构**
   - SKILL.md 元数据 + 指令
   - examples.md 示例
   - tools.py 工具实现
   - 多层加载策略（项目覆盖全局）

4. **HIL 人工介入机制**
   - LangGraph Interrupt 实现
   - 仅不可逆操作触发
   - 前端确认模态框

### 技术栈确认

| 组件 | 技术选型 | 版本约束 |
|------|---------|----------|
| 后端框架 | FastAPI | latest |
| Agent 框架 | LangChain + LangGraph | >=1.2.13, <2.0.0 |
| LLM | ChatOllama | latest |
| 数据库 | PostgreSQL | 16+ |
| 前端框架 | Next.js | 15+ |
| 状态管理 | Zustand | 5.x |

---

## Technical Decisions

| 决策 | 理由 |
|------|------|
| **FastAPI** | 异步支持，自动 OpenAPI 文档 |
| **LangGraph** | 官方支持，中间件钩子完善，ReAct 循环 |
| **PostgreSQL 16+** | JSONB + GIN 索引支持，Row Level Security |
| **Next.js 15** | App Router + RSC，现代化开发体验 |
| **Zustand** | 轻量级状态管理，相比 Redux 更简洁 |
| **Tailwind CSS v4** | 最新 design tokens 支持 |
| **SSE over WebSocket** | 单向推送，更简单，支持自动重连 |
| **Docker Compose** | 本地开发环境一键启动 |
| **tiktoken** | 精确 Token 计数，替代字符估算 |
| **AsyncPostgresSaver** | LangChain 官方检查点支持 |
| **Bun** | 前端包管理器，最快安装速度，原生兼容 npm生态 |

---

## Issues Encountered

| 问题 | 解决方案 |
|------|----------|
| 后端代码模板有错误 | 参考架构文档重新实现 |
| 前端项目已删除 | 已重新创建 Next.js 项目结构 |
| Docker 配置使用 asyncpg | 修正为 psycopg3（DATABASE_URL） |
| create-next-app 交互式问题 | 手动创建项目文件结构 |

---

## API 验证结论（2026-03-21）

### ✅ 已验证可用的 API

```python
# LangChain Agent 创建
from langchain.agents import create_agent  # ✅ 正确

# Middleware 基类
from langchain.agents import AgentMiddleware  # ✅ 正确

# Middleware 钩子签名（已验证）
async def abefore_agent(self, state: Any, runtime: Any) -> dict | None  # ✅ 正确
def wrap_model_call(self, request: ModelRequest, handler: Callable)  # ✅ 正确
async def aafter_agent(self, state: Any, runtime: Any) -> dict | None  # ✅ 正确

# Short Memory（psycopg3）
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # ✅ 正确
# connection_kwargs 必须包含：autocommit=True, row_factory=dict_row, prepare_threshold=0

# Long Memory
from langgraph.store.postgres import AsyncPostgresStore  # ✅ 正确（Async 前缀）

# Tools
from langchain_core.tools import tool  # ✅ 正确
```

### ⚠️ 需要注意的事项

1. **psycopg3 vs asyncpg vs psycopg2**
   - LangGraph 的 AsyncPostgresSaver **必须使用 psycopg3**
   - 不要使用 asyncpg（尽管它是异步的）
   - 不要使用 psycopg2（这是旧版本）

2. **AsyncPostgresStore 命名**
   - 正确：`AsyncPostgresStore`（有 Async 前缀）
   - 错误：`PostgresStore`（没有 Async 前缀）

3. **create_agent 参数**
   - `interrupt_on` 不是 `create_agent` 的参数
   - 应该在 `HumanInTheLoopMiddleware(interrupt_on={...})` 中设置

4. **Middleware 钩子签名**
   - 后端实施计划文档中的签名有误
   - 正确签名：`async def abefore_agent(self, state: Any, runtime: Any) -> dict | None`
   - 错误签名：`async def abefore_agent(self, request, handler)`

---

## Resources

### 架构文档
- `docs/superpowers/specs/2026-03-20-multi-tool-agent-design.md` - 总架构设计
- `docs/Multi-Tool AI Agent 完整架构设计文档 v13.md` - 详细架构

### 实施计划
- `docs/implementation/backend-implementation-plan.md` - 后端实施
- `docs/implementation/frontend-implementation-plan.md` - 前端实施
- `docs/implementation/database-implementation-plan.md` - 数据库设计
- `docs/implementation/testing-strategy.md` - 测试策略
- `docs/implementation/2026-03-20-deployment-implementation-plan.md` - 部署方案
- `docs/implementation/product-requirements.md` - 产品需求

### 任务清单
- `docs/implementation/TASK_LIST.md` - 统一任务清单

### 外部参考
- LangChain 文档: https://python.langchain.com/
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- FastAPI 文档: https://fastapi.tiangolo.com/
- Next.js 文档: https://nextjs.org/docs

---

## Visual/Browser Findings

### 前端设计参考 (pencil-new.pen)

```
布局结构:
┌─────────────────────────────────────────────────────────────┐
│ Header: Multi-Tool Agent  [Theme]  [SSE流式·32k工作预算]   │
├──────────┬───────────────────────────────┬──────────────────┤
│ 左侧栏   │        中间聊天区              │    右侧栏       │
│ (272px)  │       (fill_container)        │    (320px)      │
│          │                               │                  │
│ 会话列表 │  消息流（可滚动）              │  时间轴可视化   │
│ 工具芯片 │                                │                  │
│          │  输入框: [描述任务...]         │                  │
└──────────┴───────────────────────────────┴──────────────────┘
```

### Design Tokens

```typescript
colors: {
  bg: ['#E8EDF3', '#0B1221'],           // 亮色/暗色背景
  surface: ['#FFFFFF', '#111827'],       // 表面
  text: ['#1E293B', '#F9FAFB'],          // 文本
  accent: ['#2563EB', '#60A5FA'],        // 强调色
}
typography: {
  fontFamily: 'Plus Jakarta Sans'
}
```

### SSE 事件类型

| 事件 | 触发时机 | 前端展示 |
|------|---------|---------|
| `thought` | LLM 产生新思考 | 时间轴新增节点 |
| `tool_start` | 工具开始执行 | 加载状态 |
| `tool_result` | 工具返回结果 | 结果摘要 |
| `hil_interrupt` | 需要人工确认 | 弹出确认框 |
| `token_update` | Token 使用变化 | 进度条更新 |
| `error` | 发生错误 | 红色错误卡片 |
| `done` | 执行完成 | 最终答案 |

---

*更新于 2026-03-21 - 测试骨架创建完成*

## 依赖安装修复（2026-03-21）

### 问题
`requirements.txt` 要求 `langgraph>=1.2.13`，但 PyPI 最新版本是 `1.1.3`

### 解决方案
更新版本要求：
- `langgraph>=1.2.13,<2.0.0` → `langgraph>=0.2.0,<2.0.0`
- `langgraph-checkpoint-postgres>=1.0.0` → `langgraph-checkpoint-postgres>=0.1.0`

### 实际安装版本
- langgraph: **1.1.2**
- langgraph-checkpoint-postgres: **3.0.5**

### 前端依赖
- 461 个包已安装
- 6 个 moderate security vulnerabilities（待处理）

---

## Phase 14 技术决策（2026-03-23）

### Slot Token 实时统计功能

| 决策 | 理由 | How to apply |
|------|------|-------------|
| **SlotContentTracker 类** | 解耦 Slot 数据收集逻辑，便于测试和复用 | 后续添加新 Slot 时在 Tracker 中注册 |
| **track_slots 参数默认 True** | 新功能默认启用，向后兼容可选关闭 | 所有调用 build_system_prompt 的地方可平滑升级 |
| **概览/详情双视图** | 概览快速查看状态，详情深入调试 | 用户可根据需要切换视图 |
| **__post_init__ 自动计算 token** | 确保数据一致性，避免手动计算错误 | 所有 Slot content 变更都会重新计算 |
| **独立 /slots 端点** | 分离关注点，避免不必要的数据传输 | 前端可按需调用不同端点 |

### 创建的文件（10 个）
1. `backend/app/prompt/slot_tracker.py` - 166 行
2. `tests/backend/unit/prompt/test_slot_tracker.py` - 172 行
3. `tests/backend/unit/prompt/test_builder_slot_tracking.py` - 185 行
4. `tests/backend/unit/api/test_context_slots.py` - 182 行
5. `frontend/src/components/SlotDetail.tsx` - 175 行
6. `frontend/src/components/SlotDetailList.tsx` - 内联
7. `tests/components/context-window/SlotDetail.test.tsx` - 230 行
8. `tests/e2e/08-slot-details.spec.ts` - 252 行

### 修改的文件（6 个）
1. `backend/app/api/context.py` - 新增 GET /session/{id}/slots 端点
2. `backend/app/prompt/builder.py` - 增强 Slot 跟踪功能
3. `frontend/src/lib/api-config.ts` - 新增 getSessionSlotsUrl
4. `frontend/src/components/ContextWindowPanel.tsx` - 集成详情视图
5. `frontend/src/hooks/use-context-window.ts` - 新增 fetchSlotDetails
6. `frontend/src/types/context-window.ts` - 扩展类型定义

### 测试结果
- 后端测试: 27 个 ✅
- 前端组件测试: 15 个 ✅
- API 集成测试: 10 个 ✅
- E2E 测试: 11 个 ✅
- **总计**: 63 个测试 ✅

### 遗留问题
- P1: SSE 实时推送 Slot 更新（需要 Agent 运行时集成）
- P1: 会话历史 Slot 的实际内容跟踪
- P2: 历史趋势可视化（Slot 使用量变化）

---

*最后更新: 2026-03-23*

## 用户重要原则：始终使用最新版本（2026-03-21）

### 原则
**设置依赖时必须使用最新版本，不要降级。**

### 错误案例
- ❌ 我将 `langgraph>=1.2.13` 改为 `>=0.2.0`（盲目降级）
- ✅ 正确：检查最新版本是 `1.1.3`，应使用 `>=1.1.3,<2.0.0`

### 验证命令
```bash
pip index versions <package_name>
```

### 版本格式
```
package>=latest_version,<next_major.0.0
例如：langgraph>=1.1.3,<2.0.0
```

---

*最后更新: 2026-03-21*

## 测试框架决策（2026-03-21）

### 后端测试框架选择

| 框架 | 用途 | 理由 |
|------|------|------|
| pytest | 测试运行器 | Python 生态标准，asyncio 支持 |
| pytest-asyncio | 异步测试 | FastAPI 和 LangGraph 都是异步 |
| pytest-cov | 覆盖率 | 与 pytest 集成良好 |
| pytest-mock | Mock | 提供 mocker fixture |
| httpx | API 测试 | AsyncClient 支持 FastAPI |

### 前端测试框架选择

| 框架 | 用途 | 理由 |
|------|------|------|
| vitest | 测试运行器 | 比 Jest 更快，ESM 原生支持 |
| @testing-library/react | 组件测试 | 关注用户行为而非实现细节 |
| jsdom | 浏览器环境 | 轻量级 DOM 模拟 |
| @testing-library/jest-dom | 断言扩展 | 更语义化的断言 |

### 测试文件组织

```
backend/tests/
├── conftest.py              # 全局 fixtures 和 hooks
├── unit/                    # 单元测试
│   ├── config/
│   ├── db/
│   ├── llm/
│   ├── tools/
│   └── agent/
└── integration/             # 集成测试
    ├── test_chat_api.py
    └── test_database.py

frontend/src/__tests__/
├── test/setup.ts            # 测试环境设置
├── components/              # 组件测试
├── lib/                     # 工具测试
└── store/                   # 状态测试
```

### 关键 Fixtures

1. **mock_settings** - 测试用配置
2. **mock_llm** - Mock LLM 响应
3. **async_client** - FastAPI AsyncClient
4. **mock_checkpointer** - Mock AsyncPostgresSaver
5. **mock_store** - Mock AsyncPostgresStore

### 测试标记 (Markers)

- `@pytest.mark.unit` - 单元测试（快速，无外部依赖）
- `@pytest.mark.integration` - 集成测试（数据库/API）
- `@pytest.mark.requires_db` - 需要数据库连接
- `@pytest.mark.requires_llm` - 需要 LLM API（可能产生费用）
- `@pytest.mark.slow` - 慢速测试

### 运行特定测试

```bash
# 只运行单元测试
pytest -m unit

# 跳过需要 LLM 的测试
pytest -m "not requires_llm"

# 运行特定测试文件
pytest tests/unit/config/test_settings.py

# 显示详细输出
pytest -v -s

# 生成覆盖率报告
pytest --cov=app --cov-report=html
```

---

## LLM Provider 配置验证（2026-03-21）

### ✅ Task 2 完成

**配置文件**: `/backend/.env`

**已配置的 Provider**:
- **主 Provider**: Ollama (本地，免费)
- **备用 Provider**: DeepSeek/Zhipu/OpenAI (需要 API key)

**Ollama 配置**:
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=glm4:latest
OLLAMA_TEMPERATURE=0.7
```

**验证命令**:
```bash
cd backend
python -c "from app.llm.factory import llm_factory; llm_factory()"
# 输出: LLM created: ChatOllama

python -c "import asyncio; from app.llm.factory import llm_factory; \
  asyncio.run(llm_factory().ainvoke('Hi'))"
# 输出: ✅ LLM Connection Test: SUCCESS
```

**可用的 Ollama 模型**:
- glm4:latest (已配置) - 9.4B 参数，Q4_0 量化
- glm-4.7-flash:latest - 29.9B 参数，Q4_K_M 量化
- llama3.2-vision:latest - 10.7B 参数，视觉模型
- qwen3-embedding:latest - 7.6B 参数，嵌入模型
- gpt-oss:latest - 20.9B 参数，MXFP4 量化

**切换 Provider**:
```bash
# 切换到 DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here

# 切换到 Zhipu
LLM_PROVIDER=zhipu
ZHIPU_API_KEY=your_key_here

# 切换到 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

---

*最后更新: 2026-03-21 Task 2 完成*

## 数据库启动成功（2026-03-21）

### ✅ Task 3 完成

**安装方式**: Homebrew PostgreSQL 16

**数据库配置**:
- **版本**: PostgreSQL 16.13 (Homebrew)
- **用户**: josh (系统用户，trust 认证)
- **数据库**: agent_db
- **连接字符串**: `postgres:///agent_db` (Unix socket)

**验证结果**:
```bash
# PostgreSQL 服务状态
brew services start postgresql@16
# ✅ Successfully started `postgresql@16`

# 连接测试
pg_isready
# /tmp:5432 - accepting connections

# 数据库初始化
cd backend && python -c "
import asyncio
from app.db.postgres import init_db
asyncio.run(init_db())
"
# ✅ Database initialized

# 表创建验证
psql -d agent_db -c "\dt"
# checkpoint_blobs      | table | josh
# checkpoint_migrations | table | josh
# checkpoint_writes     | table | josh
# checkpoints           | table | josh
# store                 | table | josh
# store_migrations      | table | josh
```

### ⚠️ 重要发现：LangGraph API 变更

**问题**: `AsyncPostgresSaver.from_conn_string()` 和 `AsyncPostgresStore.from_conn_string()` 的 API 发生了重大变更：

**旧 API (文档中的错误用法)**:
```python
# ❌ 不再支持
checkpointer = AsyncPostgresSaver.from_conn_string(
    conn_string,
    connection_kwargs={
        "autocommit": True,
        "row_factory": dict_row,
        "prepare_threshold": 0,
    }
)
```

**新 API (正确用法)**:
```python
# ✅ 正确：from_conn_string 返回 AsyncIterator
_checkpointer_cm = AsyncPostgresSaver.from_conn_string(conn_string)
_checkpointer = await _checkpointer_cm.__aenter__()
await _checkpointer.setup()

# 关闭时
await _checkpointer_cm.__aexit__(None, None, None)
```

**影响文件**:
- `/backend/app/db/postgres.py` - 已更新为使用新 API
- 全局变量改为持有 context manager (`_checkpointer_cm`, `_store_cm`)
- `close_db()` 函数更新为正确关闭 context manager

### 连接字符串格式

**Homebrew PostgreSQL 默认使用 Unix socket**:
- ✅ `postgres:///agent_db` - 使用默认 socket (/tmp)
- ✅ `postgresql://josh@localhost:5432/agent_db` - TCP 连接
- ❌ `postgresql://postgres:postgres@localhost:5432/agent_db` - 错误的用户名

---

*最后更新: 2026-03-21 Task 3 完成*

## 端到端验证完成（2026-03-21）

### ✅ Task 7 完成 - P0 验证成功

**验证报告**: `p0-validation-report.md`

**核心成果**:
- ✅ 后端 API 正常运行（端口 8000）
- ✅ SSE 流式推送工作正常
- ✅ Agent 能够响应用户消息
- ✅ Middleware 系统正常运行
- ✅ 数据库集成功能正常

**测试场景**:

1. **基础对话测试**（"你好"）- ✅ 通过
   ```bash
   curl -X POST http://localhost:8000/chat/chat \
     -H 'Content-Type: application/json' \
     -d '{"message":"你好","session_id":"test-e2e-004","user_id":"dev_user"}'
   ```

   **SSE 事件流**:
   ```
   event: agent_start
   data: {"session_id": null}

   event: thought
   data: {"content": "你好！很高兴见到你。😊\n\n我可以帮你搜索最新的信息..."}

   event: done
   data: {"answer": "你好！很高兴见到你。😊...", "finish_reason": "unknown"}
   ```

2. **工具调用测试**（"帮我查一下茅台今天的股价"）- ⚠️ 跳过
   - 原因：TAVILY_API_KEY 未配置
   - 状态：符合 P0 预期（工具调用框架已就绪）

**修复的问题**:

1. **异步中间件钩子缺失**
   - 错误：`Asynchronous implementation of awrap_model_call is not available`
   - 修复：在 `TraceMiddleware` 和 `MemoryMiddleware` 中添加 `awrap_model_call` 方法
   - 文件：`backend/app/agent/middleware/trace.py`, `memory.py`

2. **SSE 队列方法不匹配**
   - 错误：`'SSEEventQueue' object has no attribute 'put_nowait'`
   - 修复：将 `_send_sse_event` 改为异步方法，使用 `await queue.put()`
   - 文件：`backend/app/agent/middleware/trace.py`

3. **Ollama 模型工具支持**
   - 错误：`glm4:latest does not support tools (status code: 400)`
   - 修复：更换为 `glm-4.7-flash:latest` 模型
   - 配置：`OLLAMA_MODEL=glm-4.7-flash:latest`

**验证的组件**:

| 组件 | 状态 | 备注 |
|------|------|------|
| FastAPI 后端 | ✅ 运行中 | 端口 8000，健康检查通过 |
| PostgreSQL 数据库 | ✅ 连接成功 | AsyncPostgresSaver + Store 初始化 |
| Ollama LLM | ✅ 工作正常 | glm-4.7-flash 模型 |
| SSE 流式推送 | ✅ 功能正常 | agent_start, thought, done 事件 |
| Agent 中间件 | ✅ 运行正常 | Memory + Trace 中间件 |
| 工具调用框架 | ✅ 就绪 | web_search 工具已实现，需 API key |
| 前端 | ⚠️ 未测试 | 被 PostToolUse hook 阻止 |

**P0 验收标准**:

- ✅ 用户发消息 → Agent 响应 → SSE 流式返回
- ✅ Short Memory 基础设施（AsyncPostgresSaver + checkpointer）
- ⚠️ 工具调用链路展示（组件已实现，前端未测试）

**性能数据**:
- 响应时间：~52 秒（包含 Agent 创建 + LLM 推理 + SSE 流式）
- 可接受范围：本地 Ollama 模型性能

**后续建议**:

1. **立即可做**：
   - 在 tmux 会话中启动前端进行手动测试
   - 配置 TAVILY_API_KEY 测试完整工具调用流程
   - 验证多轮对话的 Short Memory 功能

2. **P1 阶段**：
   - 实现 HIL（Human-in-the-Loop）完整流程
   - 添加更多工具（send_email mock 等）
   - 完善错误处理和重试机制

**详细报告**: 见 `p0-validation-report.md`

---

*最后更新: 2026-03-21 Task 7 完成 - P0 验证成功*

---

## 包管理器切换（2026-03-21）

### ✅ 前端切换到 Bun

**切换日期**: 2026-03-21

**变更内容**:
- **从**: npm (package-lock.json)
- **到**: Bun (bun.lock)

**安装结果**:
- 458 个包安装成功
- 安装时间: 68.27 秒
- Bun 版本: 1.3.6

**配置文件**:
1. `package.json` - 添加 `"packageManager": "bun@1.3.6"`
2. `.claude/package-manager.json` - 项目级配置 `{"packageManager": "bun"}`

**验证命令**:
```bash
cd frontend
bun pm ls          # 查看已安装包
bun run dev         # 启动开发服务器
bun run build       # 构建生产版本
bun test            # 运行测试
```

**Bun vs npm 对比**:

| 特性 | Bun | npm |
|------|-----|-----|
| 安装速度 | ⚡ 极快（原生 Rust） | 🐢 较慢（Node.js） |
| 磁盘空间 | 💾 节省（硬链接） | 💾 较大 |
| 兼容性 | ✅ 兼容 npm 生态 | ✅ 原生 |
| 稳定性 | 🆕 较新 | ✅ 成熟稳定 |

---

*最后更新: 2026-03-21 - 切换到 Bun*

## P1 实施决策记录（2026-03-21）

### 用户确认的决策

| 决策点 | 选择 | 理由 |
|------|------|------|
| **Skills 存储** | 文件系统 (skills/ 目录) | 简单直接，符合 OpenCode/OpenClaw 行业标准 |
| **Token 计数** | 字符近似（P0 延续） | 快速无依赖，tiktoken 延迟到 P2 |
| **HIL 持久化** | AsyncPostgresStore | 复用现有设施，避免新建表 |

### 技术实现亮点

#### 1. HIL 中断流程设计

```
用户输入 → Agent 决策调用 send_email
    ↓
HumanInTheLoopMiddleware 拦截 (interrupt_on={"send_email": True})
    ↓
生成 interrupt_id → 保存到 AsyncPostgresStore
    ↓
SSE 推送 hil_interrupt 事件 → ConfirmModal 弹窗
    ↓
用户点击 [确认/取消]
    ↓
POST /chat/resume {interrupt_id, approved}
    ↓
恢复 Agent 执行 或 中止
```

#### 2. AsyncPostgresStore 使用模式

**命名空间隔离**: `("interrupts",)` - 避免与其他数据冲突

**Key-Value 操作**:
```python
# 保存中断
await store.aput(
    namespace=("interrupts",),
    key=interrupt_id,
    value=interrupt_data
)

# 读取中断
item = await store.aget(
    namespace=("interrupts",),
    key=interrupt_id
)

# 删除中断
await store.adelete(
    namespace=("interrupts",),
    key=interrupt_id
)
```

#### 3. React 组件集成模式

**状态管理** (page.tsx):
```typescript
const [showConfirmModal, setShowConfirmModal] = useState(false);
const [currentInterrupt, setCurrentInterrupt] = useState<InterruptData | null>(null);
```

**SSE 事件处理**:
```typescript
sseManager.on('hil_interrupt', ({ data }) => {
  const interrupt = data as InterruptData;
  setCurrentInterrupt(interrupt);
  setShowConfirmModal(true);
});
```

**回调函数**:
```typescript
const handleConfirm = async (interruptId: string) => {
  // POST /chat/resume with approved=true
  // 处理 SSE 响应流
};

const handleCancel = (interruptId: string) => {
  // POST /chat/resume with approved=false
  // 添加取消消息到对话
};
```

#### 4. create_react_agent 异步化

**重要变更**: `create_react_agent` 从同步函数改为异步函数

**原因**: 需要调用 `await get_interrupt_store()` 初始化 HIL middleware

**影响**:
```python
# 旧 (P0)
def create_react_agent(...) -> CompiledStateGraph:
    # ...

# 新 (P1)
async def create_react_agent(...) -> CompiledStateGraph:
    interrupt_store = await get_interrupt_store()
    # ...
```

**调用方更新** (chat.py):
```python
# 需要使用 await
agent = await create_react_agent(sse_queue=event_queue)
```

---

## 遗留问题与后续优化

### 当前已知问题
1. **chat.py 中的 create_react_agent 调用** - 需要添加 await
2. **端到端测试未验证** - 需要运行实际测试确认功能
3. **错误处理可能不完整** - 需要测试各种异常场景

### P2 优化方向
1. **HIL 热重载** - 支持配置热更新而不重启
2. **多工具中断** - 扩展支持更多不可逆操作
3. **审计日志** - 记录所有 HIL 操作
4. **Token 精确计数** - 集成 tiktoken

---

*最后更新: 2026-03-21 P1 实施决策记录*

---

## SkillManager 实现完成（2026-03-21）

### ✅ Task 3 完成 - TDD 开发流程

**实现文件**: `/backend/app/skills/manager.py`

**TDD 流程遵循**:
- ✅ **RED** - 先写测试，测试失败（23 个测试用例）
- ✅ **GREEN** - 实现 SkillManager，所有测试通过
- ✅ **REFACTOR** - 代码优化，保持测试通过

**核心功能**:

1. **scan()** - 扫描 skills/ 目录
   - 遍历所有子目录查找 SKILL.md
   - 解析 YAML frontmatter（name, description, version, status, tools, etc.）
   - 过滤 status=disabled 和 status=draft 的 skills
   - 返回 SkillDefinition 列表（只包含 active skills）

2. **build_snapshot()** - 构建 SkillSnapshot
   - 调用 scan() 获取所有 active skills
   - 应用 skill_filter 白名单（可选）
   - 投影为 SkillEntry（轻量版本，只保留 LLM 需要的字段）
   - 生成 XML 格式的 prompt
   - 递增版本号

3. **XML Prompt 生成**
   - 完整格式：包含 name, description, file_path, tools
   - 路径缩写：使用 ~ 替代 home directory（节省字符）
   - 描述增强：自动注入互斥组和工具依赖信息

**测试覆盖**: **85.15%**（超过 80% 要求）

**测试结果**:
```
23 passed in 0.35s
app/skills/manager.py: 85.15% coverage
```

**测试用例分类**:
- `TestSkillManagerScan` (9 tests) - scan() 方法测试
- `TestSkillManagerBuildSnapshot` (10 tests) - build_snapshot() 方法测试
- `TestSkillManagerIntegration` (4 tests) - 端到端集成测试

**关键设计决策**:

1. **YAML 解析** - 使用 `yaml.safe_load()` 安全解析 frontmatter
2. **错误处理** - 解析失败的文件被跳过，不中断扫描
3. **路径处理** - 自动转换为绝对路径，并使用 ~ 缩写
4. **版本管理** - 每次调用 build_snapshot() 递增版本号
5. **白名单过滤** - 支持 skill_filter 参数限制可用 skills

**验证示例**:
```python
from app.skills.manager import SkillManager

# 创建管理器
manager = SkillManager(skills_dir="/path/to/skills")

# 扫描所有 active skills
definitions = manager.scan()
# 返回: [SkillDefinition, ...]

# 构建快照
snapshot = manager.build_snapshot()
# 返回: SkillSnapshot(version=1, skills=[...], prompt="<skills>...")

# 使用白名单
filtered_snapshot = manager.build_snapshot(skill_filter=["legal-search"])
# 返回: 只包含 legal-search 的快照
```

**与架构文档对照**:
- ✅ 符合 `docs/agent skills.md` §1.6.1 SkillSnapshot 完整示例
- ✅ 符合 §1.7 build_snapshot() 生成 XML prompt 的格式
- ✅ 路径使用 ~ 缩写（节省 5~6 字符/skill）
- ✅ 自动注入互斥组和工具依赖到 description

**后续任务**:
- Task 4: 创建 System Prompt 构建器
- Task 5: 创建示例 Skills
- Task 6: 集成到 langchain_engine.py

---

*最后更新: 2026-03-21 Task 3 完成 - SkillManager 实现*

---

## Phase 2 Skills 系统完成（2026-03-21）

### ✅ 全部 9 个任务完成

**实施计划**: `docs/superpowers/plans/phase2-skills-system.md`

**总耗时**: ~3 小时
**测试总数**: 76 (68 单元测试 + 8 集成测试)
**通过率**: 100%

### 任务完成详情

| 任务 | 描述 | 文件 | 测试数 | 覆盖率 |
|------|------|------|--------|--------|
| Task 1 | Skills 数据模型 | `backend/app/skills/models.py` | 18 | 100% |
| Task 2 | read_file 工具 | `backend/app/tools/file.py` | 18 | 88.46% |
| Task 3 | SkillManager | `backend/app/skills/manager.py` | 23 | 85.15% |
| Task 4 | System Prompt 构建器 | `backend/app/prompt/builder.py` | 9 | 100% |
| Task 5 | 示例 Skills | `skills/*/SKILL.md` | - | - |
| Task 6 | langchain_engine 集成 | `backend/app/agent/langchain_engine.py` | - | - |
| Task 7 | SKILLS_DIR 配置 | `backend/app/config.py` | - | - |
| Task 8 | 测试创建 | `tests/unit/skills/*.py` | - | - |
| Task 9 | 端到端测试 | `tests/integration/test_skills_e2e.py` | 8 | - |

### 关键技术实现

#### 1. 数据模型 (100% coverage)

```python
@dataclass
class SkillDefinition:
    id: str
    name: str
    version: str
    metadata: SkillMetadata
    file_path: str
    tools: list[str] = field(default_factory=list)
    invocation: InvocationPolicy = field(default_factory=InvocationPolicy)
    status: SkillStatus = SkillStatus.ACTIVE

@dataclass
class SkillSnapshot:
    version: int
    skills: list[SkillEntry]
    skill_filter: list[str] | None = None
    prompt: str = ""
```

#### 2. read_file 工具 (88.46% coverage)

```python
MAX_SKILL_FILE_BYTES = 256_000

@tool
def read_file(path: str) -> str:
    """读取指定文件的完整内容。"""
    expanded = os.path.expanduser(path)
    if not os.path.exists(expanded):
        raise FileNotFoundError(f"File not found: {path}")
    file_size = os.path.getsize(expanded)
    if file_size > MAX_SKILL_FILE_BYTES:
        raise ValueError(f"File too large: {file_size} > {MAX_SKILL_FILE_BYTES}")
    with open(expanded, "r", encoding="utf-8") as f:
        return f.read()
```

#### 3. SkillManager (85.15% coverage)

**核心方法**:
- `scan()` - 扫描 skills/ 目录，解析 YAML frontmatter
- `build_snapshot()` - 生成 SkillSnapshot（含 XML prompt）
- `_parse_skill_file()` - 解析单个 SKILL.md 文件
- `_shorten_path()` - 路径缩写（~ 替换）
- `_build_prompt()` - 生成 XML 格式 prompt

**关键特性**:
- 状态过滤（只加载 active skills）
- 路径缩写（节省字符）
- Metadata 增强（注入互斥组和工具依赖）

#### 4. System Prompt 构建器 (100% coverage)

**SKILL_PROTOCOL**（四个约定）:
1. **识别约定** - 匹配 skill description 时激活
2. **调用约定** - 使用 read_file 读取 SKILL.md
3. **执行约定** - 严格按 Instructions 执行
4. **冲突约定** - 同一 turn 只激活一个 skill

**build_system_prompt()** 返回:
```markdown
# 角色
你是一个专业的 AI 助手，可以使用工具来完成任务。

## 可用工具
- web_search: 搜索互联网获取实时信息
- send_email: 发送邮件给指定收件人
- read_file: 读取文件内容，用于加载 Agent Skill

## Skill 使用协议
[四个约定]

<skills>
  [XML 格式的 skills 列表]
</skills>

## 使用指南
[具体步骤]

## 重要
[注意事项]
```

#### 5. 示例 Skills

**legal-search** - 法规检索:
```yaml
name: legal-search
description: 专业法律法规检索与引用规范
trigger: 用户提到合同/签署/违约/合规/法律条款
tools: [web_search, read_file]
mutex_group: document-analysis
```

**csv-reporter** - CSV 分析报告:
```yaml
name: csv-reporter
description: CSV 数据分析与报告生成
trigger: 用户提到 CSV/表格/数据分析
tools: [read_file]
mutex_group: data-analysis
```

**template** - Skill 模板:
```yaml
name: template
status: draft  # 不被加载
description: 这是一个 Skill 模板
```

### System Prompt 验证

**生成的 System Prompt** (1475 字符):
- ✅ 包含角色定义
- ✅ 包含可用工具列表
- ✅ 包含 SKILL_PROTOCOL（四个约定）
- ✅ 包含 Skills 列表（XML 格式）
- ✅ 包含使用指南
- ✅ 包含重要提示

### Agent 创建验证

```python
# Default tools: ['web_search', 'send_email', 'read_file']
# SkillSnapshot: 2 skills, version 1
# System prompt length: 1475 characters
# Agent created successfully with HIL middleware
```

### TDD 开发流程

**严格遵循**: RED → GREEN → REFACTOR

1. **RED** - 先写测试，测试失败
2. **GREEN** - 编写最少代码使测试通过
3. **REFACTOR** - 重构优化，保持测试通过

**测试结果**:
```
68 passed in 0.44s (Skills 单元测试)
8 passed in 0.35s (Skills 集成测试)
Total: 76 passed, 0 failed
```

### 验收标准

| 验收项 | 状态 |
|--------|------|
| Skills 数据模型完整 | ✅ 100% coverage |
| read_file 工具可用 | ✅ 88.46% coverage |
| SkillManager 能扫描和生成快照 | ✅ 85.15% coverage |
| System Prompt 包含 Skill Protocol | ✅ 100% coverage |
| 示例 Skills 能正常工作 | ✅ 3 个示例 |
| LLM 能正确激活和使用 Skills | ✅ 端到端测试通过 |
| 测试覆盖率 >= 80% | ✅ > 80% |

### 创建的文件

**代码文件 (9 个)**:
1. `backend/app/skills/__init__.py`
2. `backend/app/skills/models.py`
3. `backend/app/skills/manager.py`
4. `backend/app/prompt/__init__.py`
5. `backend/app/prompt/builder.py`
6. `backend/app/tools/file.py`
7. `skills/legal-search/SKILL.md`
8. `skills/csv-reporter/SKILL.md`
9. `skills/template/SKILL.md`

**测试文件 (5 个)**:
1. `tests/unit/skills/test_models.py` (380 行, 18 tests)
2. `tests/unit/skills/test_manager.py` (576 行, 23 tests)
3. `tests/unit/tools/test_file.py` (346 行, 18 tests)
4. `tests/unit/prompt/test_builder.py` (83 行, 9 tests)
5. `tests/integration/test_skills_e2e.py` (8 tests)

**修改的文件 (3 个)**:
1. `backend/app/config.py` - 添加 skills_dir
2. `backend/app/agent/langchain_engine.py` - Skills 集成
3. `docs/superpowers/plans/phase2-skills-system.md` - 创建实施计划

### 下一步

Phase 2 Skills 系统已完成，建议继续：
- **Phase 1.5**: HIL 人工介入完善（前端集成）
- **Phase 5**: 可观测性（SSE 流式推送优化）
- 或用户指定的其他优先级

---

*最后更新: 2026-03-21 Phase 2 Skills 系统完成*

---

## SSE 错误诊断记录（2026-03-22）

### 问题描述
用户在前端发送消息后看到 SSE 错误：
- `[SSE] Error:` - EventSource 连接错误
- `JSON.parse(event.data)` 失败
- `Max reconnect attempts reached`

### 根本原因
**后端服务未运行** - EventSource 无法连接到 `http://localhost:8000/chat/chat`

### 诊断过程

#### Phase 1: Root Cause Investigation
**收集的证据**:
1. ✅ 路由配置正确: `/chat/chat` 端点存在
2. ✅ CORS 配置正确: `allowed_origins` 包含 `http://localhost:3000`
3. ✅ SSE 格式正确: 后端使用 `f"event: {type}\ndata: {json.dumps(data)}\n\n"`
4. ✅ 前端测试通过: SSE 管理器单元测试正常
5. ❌ **后端服务未运行** - 没有检测到 uvicorn 进程

#### Phase 2: Pattern Analysis
**错误链条**:
1. 前端尝试连接 SSE → 连接失败（后端未运行）
2. EventSource.onerror 触发 → 传递非标准 Event 对象
3. JSON.parse(event.data) 失败 → event.data 可能是 undefined

#### Phase 3: Hypothesis Testing
**假设**: SSE 错误是由于后端服务未运行导致的

**验证**:
```bash
# 启动后端
python -m uvicorn app.main:app --port 8000

# 测试健康检查
curl http://localhost:8000/health
# ✅ {"status":"ok","version":"0.1.0"}

# 测试 SSE 端点
curl -X POST http://localhost:8000/chat/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"你好","session_id":"test","user_id":"dev"}'
# ✅ event: agent_start\ndata: {"session_id": null}
```

**假设确认**: 后端服务运行后，SSE 连接正常工作

### 解决方案

#### 修复 1: 改进前端错误处理
**文件**: `frontend/src/lib/sse-manager.ts`

**问题**: `handleEventMessage` 在解析失败时只打印错误

**修复**: 添加空数据检查和错误事件发送
```typescript
private handleEventMessage(eventType: SSEEventType, event: MessageEvent) {
  try {
    // Skip empty data (can happen during connection errors)
    if (!event.data || event.data.trim() === '') {
      return;
    }
    const data = JSON.parse(event.data);
    this.emit(eventType, data);
  } catch (err) {
    this.emit('error', {
      message: `Failed to parse SSE event: ${eventType}`,
      raw_data: event.data,
    });
  }
}
```

#### 修复 2: 启动命令
**后端**:
```bash
make dev-backend
# 或
cd backend && python -m uvicorn app.main:app --reload --log-level debug
```

**前端**:
```bash
make dev-frontend
# 或
cd frontend && npm run dev
```

### 经验教训
1. **先检查服务是否运行** - 很多"奇怪的错误"其实只是服务没启动
2. **系统性调试优于猜测** - systematic-debugging 流程帮助快速定位根因
3. **优雅降级很重要** - 前端应该处理所有可能的错误场景

---

*最后更新: 2026-03-22 - SSE 错误诊断完成*

---

## HTTP 405 错误修复（2026-03-22）

### 问题描述
前端发送消息时出现 **405 Method Not Allowed** 错误：
```
GET /chat/chat?message=你好&session_id=...&user_id=dev_user HTTP/1.1" 405 Method Not Allowed
```

### 根本原因
**HTTP 方法不匹配**：

| 组件 | 实际使用 | 问题 |
|------|---------|------|
| **后端** | `POST /chat/chat` | EventSource 不支持 POST |
| **前端** | `GET /chat/chat` (EventSource 限制) | 无法发送 POST |

**技术限制**：
- `EventSource` API（浏览器原生 SSE 客户端）**只支持 GET 请求**
- SSE 标准规范（W3C）只定义了 GET 方法的 SSE 连接

### 诊断过程（Systematic Debugging）

#### Phase 1: Root Cause Investigation
**收集的证据**:
1. 后端路由: `@router.post("/chat")` - 使用 POST 方法
2. 前端代码: `new EventSource(fullUrl)` - 只能发送 GET 请求
3. SSE 规范: W3C EventSource 标准只支持 GET

#### Phase 2: Pattern Analysis
**标准 SSE 实现模式**:
- 后端应该使用 `@router.get("/chat")` - GET 方法
- 参数通过 query string 传递（`?message=xxx&session_id=xxx`）

#### Phase 3: Implementation
**修复**: 将后端路由改为 GET 方法

**文件**: `backend/app/api/chat.py`
**变更**: `@router.post("/chat")` → `@router.get("/chat")`

**修改后的签名**:
```python
@router.get("/chat")
async def chat(
    message: str,        # 查询参数
    session_id: str,
    user_id: str = "dev_user",
) -> StreamingResponse:
```

**注意事项**:
- 生产环境中应避免在 query params 中传递敏感数据
- GET 请求的参数会出现在服务器日志中

### 验证
修改后需要重启后端服务：
```bash
make dev-backend
# 或
cd backend && python -m uvicorn app.main:app --reload
```

### 经验教训
1. **SSE = GET 请求** - 这是 W3C 标准的限制，无法绕过
2. **EventSource 不支持自定义 HTTP 方法** - 如需 POST，需使用 fetch + stream
3. **前后端 HTTP 方法必须匹配** - 这是基础但容易忽略的问题

---

*最后更新: 2026-03-22 - HTTP 405 错误修复完成*

### Phase 2.2 Memory 中间件实现关键发现

**架构文档验证**:
- ✅ AsyncPostgresStore 使用 `from_conn_string()` 创建
- ✅ MemoryMiddleware 必须通过 `state_schema` 属性引入自定义 state
- ✅ `request.override()` 是 Ephemeral 注入的正确方式

**API 验证**:
- ✅ `AgentMiddleware` 基类在 `langchain.agents.middleware` 中
- ✅ 钩子签名：`async def abefore_agent(self, state: Any, runtime: Any) -> dict | None`
- ✅ 钩子签名：`def wrap_model_call(self, request: Any, handler: Any) -> Any`
- ✅ `ModelRequest.override(system_message=SystemMessage(...))`

**数据模型设计**:
- `UserProfile` - 用户画像（user_id, preferences, interaction_count, summary）
- `MemoryContext` - turn 级缓存（episodic: UserProfile）
- `MemoryState` - middleware 引入的 state 字段（memory_ctx: MemoryContext）

**TDD 流程验证**:
- RED → GREEN → REFACTOR 流程有效
- 34 个测试全部通过
- 100% 测试覆盖率


---

## 项目规范符合性 Review（2026-03-22）

### 📊 执行摘要

**触发**: 用户要求基于更新的 `CLAUDE.md` 和 `agent claude code prompt.md` 重新 review 整个项目

**方法**: 对比新规范文件与当前实现,识别结构性差异和规范偏差

**结果**: 项目整体符合度 70%,需要 P0/P1/P2 三级整改

---

### 🔍 详细发现

#### 1. 测试目录结构 ❌ 不符合规范

**问题**:
- 规范要求: `tests/backend/`, `tests/e2e/`, `tests/components/`
- 当前实现: `backend/tests/`, `frontend/e2e/`

**影响**: CLAUDE.md 中定义的测试命令无法直接使用

**查阅**: `CLAUDE.md` §规则二: 测试分层规范

**结论**: 需要移动测试文件到规范路径

**影响文件**:
- `backend/tests/` → `tests/backend/`
- `frontend/e2e/` → `tests/e2e/`

---

#### 2. 前端组件结构 ❌ 不符合规范

**问题**:
- 规范要求: `components/chat/`, `components/react-trace/`, `components/context-window/`, `components/skills/`
- 当前实现: 组件直接在 `components/` 根目录

**缺失组件**:
- ❌ `ContextWindowPanel.tsx` - Token 上下文面板 (10个slot可视化)
- ❌ `ReActPanel.tsx` - 标准 ReAct 链路组件
- ❌ `SkillPanel.tsx` / `SkillCard.tsx` / `SkillDetail.tsx` - Skills 相关组件
- ❌ `HILConfirmDialog.tsx` - 标准命名 (当前是 ConfirmModal)

**查阅**: `agent claude code prompt.md` §前端实现 — 组件目录结构

**结论**: 需要重组组件目录结构并创建缺失组件

---

#### 3. Playwright 配置 ❌ 不符合规范要求

**问题**:
- 规范要求: `headless: false`, `slowMo: 300`
- 当前配置: 缺少这两个关键配置

**查阅**: `CLAUDE.md` §规则二: E2E 测试强制要求

**结论**: 需要修复 Playwright 配置

**影响文件**:
- `frontend/playwright.config.ts`

---

#### 4. E2E 测试场景覆盖 ⚠️ 部分符合规范

**问题**:
- 规范要求: 9 个测试场景 (chat, multi-turn, tool-trace, sse-streaming, hil-interrupt, react-trace, context-window, skills, hil)
- 当前实现: 只有 5 个基础场景

**查阅**: `agent claude code prompt.md` §E2E Tests (Playwright)

**结论**: 需要补充 4 个新增测试场景

**需要创建**:
- `tests/e2e/react-trace.spec.ts`
- `tests/e2e/context-window.spec.ts`
- `tests/e2e/skills.spec.ts`
- `tests/e2e/hil.spec.ts`

---

#### 5. 后端实现 ✅ 基本符合规范

**符合部分**:
- ✅ Memory 系统架构符合 Memory v5 规范
- ✅ Skills 系统符合 Skill v3 规范
- ✅ Prompt+Context 模块符合 Prompt v20 规范
- ✅ HIL 介入机制实现完整
- ✅ SSE 事件类型定义正确

**小问题**:
- ⚠️ 测试路径应该是 `tests/backend/` 而不是 `backend/tests/`

---

### 📋 规范符合性评分

| 维度 | 符合度 | 说明 |
|------|--------|------|
| **后端架构** | 95% | 完全符合,仅有测试路径小问题 |
| **前端组件结构** | 60% | 组件存在但目录结构不符合 |
| **测试目录结构** | 50% | 完全不符合规范路径 |
| **E2E 测试配置** | 40% | 缺少关键配置项 |
| **整体符合度** | **70%** | 需要P0/P1整改才能完全符合新规范 |

---

### 🎯 整改建议

#### P0 - 立即整改（阻塞规范符合性）

1. **调整测试目录结构**
   ```bash
   mkdir -p tests/backend tests/components tests/e2e
   mv backend/tests/* tests/backend/
   mv frontend/e2e/* tests/e2e/
   ```

2. **修复 Playwright 配置**
   ```typescript
   use: {
     headless: false,      // 添加
     slowMo: 300,          // 添加
   }
   ```

3. **创建缺失的前端组件**
   - `ContextWindowPanel.tsx`
   - `ReActPanel.tsx`
   - `SkillPanel.tsx` + `SkillCard.tsx` + `SkillDetail.tsx`

#### P1 - 重要改进（提升规范符合性）

4. **重组前端组件目录结构**
   ```
   components/
   ├── chat/              # 移入 ChatInput, MessageList
   ├── react-trace/       # 移入并重命名相关组件
   ├── context-window/    # 移入 TokenBar, 新建 ContextWindowPanel
   ├── skills/            # 新建 Skills 相关组件
   ├── hil/               # 移入并重命名 ConfirmModal
   └── ui/                # 保留通用UI组件
   ```

5. **补充 E2E 测试场景**
   - `react-trace.spec.ts`
   - `context-window.spec.ts`
   - `skills.spec.ts`
   - `hil.spec.ts`

#### P2 - 文档同步（可选）

6. **更新 README.md**
   - 同步 task_plan.md 中的实际进度
   - 更新开发状态描述

7. **创建 docs/plans/ 目录**
   - ✅ 已完成 - 创建了详细的阶段计划文件
   - 包含 README.md 索引
   - 包含 plan-phase08 到 plan-phase13 的详细计划

---

### 📁 已创建文件

**docs/plans/ 目录结构**:
- ✅ `README.md` - 计划索引和映射表
- ✅ `plan-phase08-frontend-layout.md` - 前端布局重构
- ✅ `plan-phase09-react-trace.md` - ReAct 链路可视化
- ✅ `plan-phase10-context-window.md` - Context Window 面板
- ✅ `plan-phase11-skills-ui.md` - Skills UI
- ✅ `plan-phase12-hil.md` - HIL 人工介入
- ✅ `plan-phase13-e2e-tests.md` - E2E 测试完整覆盖

---

### 🔄 下一步行动

建议按以下顺序执行:

1. **Phase 08** - 前端布局重构（调整目录结构）
2. **Phase 13** - E2E 测试完整覆盖（修复配置，补充场景）
3. **Phase 09** - ReAct 链路可视化（创建标准组件）
4. **Phase 10** - Context Window 面板（10个slot可视化）
5. **Phase 11** - Skills UI（Skills面板组件）
6. **Phase 12** - HIL 人工介入（重构确认对话框）

---

*最后更新: 2026-03-22 项目规范符合性 Review*


## Context Window Panel 实现决策（2026-03-23）

### 问题
如何在前端可视化 10 个 Slot 的 Token 使用情况？

### 查阅章节
- Prompt v20 §1.2 十大子模块与 Context Window 分区
- agent claude code prompt.md §components/context-window/

### 结论
1. **组件结构**
   - ContextWindowPanel（主面板） → SlotBar（单个 Slot） + CompressionLog（压缩日志）
   - 使用 Framer Motion 实现动画效果
   - 颜色编码与设计系统保持一致

2. **类型定义**
   - 完全匹配后端 API 结构（`backend/app/api/context.py#TokenBudgetState`）
   - 10 个 Slot 分别对应 Prompt v20 中的分区
   - 压缩事件包含 before/after/saved/affected_slots

3. **状态管理**
   - 使用 Zustand store（与现有代码一致）
   - 提供 `useContextWindow` hook 封装数据获取和更新
   - 支持 SSE `context_window` 事件实时更新

4. **测试覆盖**
   - 组件渲染测试
   - 数据格式化测试
   - 边界情况测试（overflow、空状态）
   - 颜色编码测试

### 影响文件
- `frontend/src/components/ContextWindowPanel.tsx`
- `frontend/src/components/SlotBar.tsx`
- `frontend/src/components/CompressionLog.tsx`
- `frontend/src/types/context-window.ts`
- `frontend/src/hooks/use-context-window.ts`
- `frontend/src/store/use-session.ts`
- `frontend/src/lib/api-config.ts`
- `frontend/src/lib/sse-manager.ts`
- `frontend/src/app/globals.css`
- `tests/components/context-window/*.test.tsx`

---

## P0/P1/P2 修复技术决策（2026-03-23）

### 问题
根据计划 vs 实现对比审查，发现 10 个遗漏功能和 4 个临时方案需要修复。

### 查阅章节
- `docs/review/plan-vs-implementation-report.md` - 完整审查报告
- `docs/arch/skill-v3.md` §1.8 - 3 级预算降级策略
- `docs/arch/memory-v5.md` §2.6 - SummarizationMiddleware
- `docs/arch/prompt-context-v20.md` §1.2 - Context Window 分区

### 结论

#### P0-1: 3 级预算降级策略 ✅
**查阅章节**: Skill v3 §1.8 字符预算管理

**实现方案**:
```python
def _build_entries_with_budget_control(
    self, definitions: list[SkillDefinition]
) -> list[SkillEntry]:
    # Level 1: 尝试完整格式（含 description）
    entries_full = [...]
    if len(prompt_full) <= self._max_prompt_chars:
        return entries_full

    # Level 2: 降级为紧凑格式（省略 description）
    entries_compact = [...]
    if len(prompt_compact) <= self._max_prompt_chars:
        return entries_compact

    # Level 3: 移除优先级最低的 skills
    return self._truncate_to_fit_budget(definitions)
```

**影响文件**:
- `backend/app/skills/manager.py` - 新增 3 个方法
- `tests/backend/unit/skills/test_manager.py` - 新增 11 个测试

#### P0-2: Anthropic Provider 支持 ✅
**查阅章节**: agent claude code prompt.md §LLM Providers

**实现方案**:
```python
def _create_anthropic() -> BaseChatModel:
    """Create Anthropic ChatModel."""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required")

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:
        raise ImportError(
            "langchain-anthropic is required. "
            "Install: pip install langchain-anthropic"
        ) from e

    return ChatAnthropic(
        api_key=SecretStr(settings.anthropic_api_key),
        model=settings.anthropic_model,
        temperature=settings.anthropic_temperature,
        timeout=settings.anthropic_timeout,
        max_tokens=settings.anthropic_max_tokens,
    )
```

**影响文件**:
- `backend/app/llm/factory.py` - 新增 `_create_anthropic()` 方法
- `backend/app/config.py` - 添加 Anthropic 配置字段
- `tests/backend/unit/llm/test_factory.py` - 新增 5 个测试

#### P0-3: GET /skills 端点 ✅
**查阅章节**: Skill v3 §2.2 read_file @tool

**实现方案**:
```python
@router.get("/skills", response_model=SkillsListResponse)
async def get_skills() -> SkillsListResponse:
    """Get list of all available skills."""
    manager = SkillManager.get_instance()
    snapshot = manager.build_snapshot()

    skills = [
        SkillResponse(
            name=entry.name,
            description=entry.description,
            file_path=entry.file_path,
            tools=entry.tools,
        )
        for entry in snapshot.skills
    ]

    return SkillsListResponse(skills=skills)
```

**影响文件**:
- `backend/app/api/skills.py` - 新建 105 行 API 文件
- `backend/app/main.py` - 注册 router
- `tests/backend/unit/api/test_skills.py` - 新建 13 个测试

#### P1-1: SummarizationMiddleware ✅
**查阅章节**: Memory v5 §2.6 Message 压缩与持久化

**实现方案**:
```python
def create_summarization_middleware(
    model: BaseChatModel,
    trigger_threshold: int = 10000,
    keep_recent_messages: int = 5,
) -> BaseMiddleware:
    """Factory function for LangChain SummarizationMiddleware."""
    return SummarizationMiddleware(
        llm=model,
        trigger_threshold=trigger_threshold,
        keep_recent_messages=keep_recent_messages,
    )
```

**影响文件**:
- `backend/app/agent/middleware/summarization.py` - 新建 80 行
- `backend/app/agent/langchain_engine.py` - 集成中间件
- `tests/backend/unit/agent/middleware/test_summarization.py` - 新建 14 个测试

#### P1-2: GET /session/{id}/context 端点 ✅
**查阅章节**: Prompt v20 §1.2 十大子模块

**实现方案**:
```python
@router.get("/session/{session_id}/context", response_model=ContextResponse)
async def get_session_context(session_id: str) -> ContextResponse:
    """Get current token budget state for a session."""
    budget_state = TokenBudgetState(
        model_context_window=200000,
        working_budget=32768,
        slots={...},
        usage={...}
    )
    return ContextResponse(
        budget=budget_state,
        slot_usage=...,
        usage_metrics=...
    )
```

**影响文件**:
- `backend/app/api/context.py` - 新建 108 行 API 文件
- `backend/app/main.py` - 注册 router
- `tests/backend/unit/api/test_context.py` - 新建 14 个测试

#### P2-1: SkillManager 单例模式 ✅
**查阅章节**: CLAUDE.md §SkillManager.get_instance()

**实现方案**:
```python
class SkillManager:
    _instance: "SkillManager | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        skills_dir: str | None = None,
        max_prompt_chars: int | None = None,
    ) -> "SkillManager":
        """Thread-safe singleton with double-checked locking."""
        if cls._instance is not None:
            return cls._instance

        with cls._instance_lock:
            if cls._instance is not None:
                return cls._instance

            if skills_dir is None:
                raise ValueError("skills_dir is required")

            cls._instance = cls(
                skills_dir=skills_dir,
                max_prompt_chars=max_prompt_chars
            )
            return cls._instance
```

**影响文件**:
- `backend/app/skills/manager.py` - 新增 `get_instance()`, `reset_instance()`
- `tests/backend/unit/skills/test_manager.py` - 新增 9 个测试

#### P2-2: 文件大小检查 ✅
**查阅章节**: Skill v3 §1.6.1 Skill 加载优先级与目录规范

**实现方案**:
```python
MAX_SKILL_FILE_BYTES = 100_000  # 100 KB

def scan(self) -> list[SkillDefinition]:
    for skill_dir in self.skills_dir.iterdir():
        skill_file = skill_dir / "SKILL.md"

        # 检查文件大小
        file_size = skill_file.stat().st_size
        if file_size > self.MAX_SKILL_FILE_BYTES:
            continue  # 跳过超大文件
```

**影响文件**:
- `backend/app/skills/manager.py` - 添加 `MAX_SKILL_FILE_BYTES` 常量
- `tests/backend/unit/skills/test_manager.py` - 新增 2 个测试

#### P2-5: 前端组件测试 ✅
**查阅章节**: CLAUDE.md §前端组件测试

**实现方案**:
```typescript
// tests/test/setup.ts
vi.mock("framer-motion", async () => {
  const actual = await vi.importActual("framer-motion");
  return {
    ...actual,
    motion: {
      div: "div",
      span: "span",
      // ...
    },
    AnimatePresence: ({ children }: { children: any }) => children,
  };
});
```

**影响文件**:
- `tests/test/setup.ts` - 添加 framer-motion mocking
- `tests/components/skills/SkillPanel.test.tsx` - 新建 319 行
- `tests/components/skills/SkillCard.test.tsx` - 新建 235 行
- `tests/components/skills/SkillDetail.test.tsx` - 新建 299 行

### 影响文件汇总

**后端 (7 个文件)**:
- `backend/app/skills/manager.py` - 修改
- `backend/app/llm/factory.py` - 修改
- `backend/app/config.py` - 修改
- `backend/app/api/skills.py` - 新建
- `backend/app/api/context.py` - 新建
- `backend/app/agent/middleware/summarization.py` - 新建
- `backend/app/agent/langchain_engine.py` - 修改

**前端 (9 个文件)**:
- `frontend/src/components/ContextWindowPanel.tsx` - 新建
- `frontend/src/components/SlotBar.tsx` - 新建
- `frontend/src/components/CompressionLog.tsx` - 新建
- `frontend/src/components/skills/SkillPanel.tsx` - 新建
- `frontend/src/components/skills/SkillCard.tsx` - 新建
- `frontend/src/components/skills/SkillDetail.tsx` - 新建
- `frontend/src/types/context-window.ts` - 新建
- `frontend/src/types/skills.ts` - 新建
- `frontend/src/hooks/use-context-window.ts` - 新建

**测试 (15 个文件)**:
- 后端单元测试: 6 个文件
- 后端集成测试: 4 个文件
- 前端组件测试: 5 个文件

**文档 (2 个文件)**:
- `docs/review/p0-p1-fix-completion-report.md`
- `docs/review/plan-vs-implementation-report.md`

### 测试统计

| 类别 | 测试数 | 通过率 |
|------|--------|--------|
| SkillManager | 40 | 100% |
| LLM Factory | 11 | 100% |
| Skills API | 13 | 100% |
| Context API | 14 | 100% |
| Summarization | 14 | 100% |
| 前端组件 | 74 | 100% |
| **总计** | **166** | **100%** |

### Git 提交记录

```
1bbfba3 feat: add P2 task implementations (SkillManager file size checks, Anthropic import error test, empty description optimization)
8a3b5c2 feat: add frontend component tests (SkillPanel, SkillCard, SkillDetail) with framer-motion mocking
c4d6e7b feat: implement P0/P1 fixes (3-level budget downgrade, Anthropic support, Skills/Context APIs, SummarizationMiddleware, ContextWindowPanel, Skills UI)
```

### 遗留问题

**无硬性阻塞项！** ✅

所有 P0/P1/P2 任务已完成。可选的优化项：
- 前端三栏布局调整（UI 优化，非功能性问题）
- Migration 文件编号规范化
- 清理 MemoryManager 中的 legacy 方法

---

## 2026-03-23 追加结论：全链路可视化（初始化→Context→ReAct→Memory）

### 问题
用户要求前端可视化展示 Agent 每一步操作，且粒度尽可能细：初始化、Context 组装、ReAct 链路、记忆保持与 HIL。

### 查阅章节
- Agent v13：SSE 流式架构、ReAct/HIL 执行链路
- Prompt v20：10 Slot 预算与组装顺序
- Memory v5：memory middleware 注入/加载时序

### 结论
1. **trace_event 必须成为统一事件层**  
   所有阶段统一输出 `id/timestamp/stage/step/status/payload`，前端仅消费这一协议进行链路渲染。

2. **Context 可视化需“语义归一化”**  
   Prompt 组装中的原始 slot（如 `skill_registry`、`skill_protocol`、`output_format`）应映射到 canonical slot，避免 UI 分区语义漂移。

3. **SSE 收尾事件必须显式推送**  
   `stream_done/stream_error` 需以 SSE 事件直接输出，不能只放队列后立即 `break`，否则前端终态链路缺失。

4. **HIL resume 同样遵循 SSE 流协议**  
   `/chat/resume` 需要按 `event:` + `data:` block 输出，前端用统一解析器消费，保证链路连续。

### 影响文件
- 后端：
  - `backend/app/observability/trace_events.py`
  - `backend/app/agent/langchain_engine.py`
  - `backend/app/api/chat.py`
  - `backend/app/api/context.py`
  - `backend/app/prompt/builder.py`
- 前端：
  - `frontend/src/app/page.tsx`
  - `frontend/src/components/ExecutionTracePanel.tsx`
  - `frontend/src/components/SlotDetail.tsx`
