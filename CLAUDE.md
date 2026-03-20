# Multi-Tool AI Agent - Claude 开发指南

> **项目**: Multi-Tool AI Agent 系统
> **目标**: 企业级 Agent 系统用于面试演示
> **最后更新**: 2026-03-20

---

## 🔴 关键开发原则

### TDD (测试驱动开发) - 强制要求

**所有功能开发必须遵循 TDD 流程：**

1. **RED** - 先编写失败的测试
   - 为新功能编写测试用例
   - 确认测试失败（预期失败）
   - 测试覆盖功能的核心行为

2. **GREEN** - 实现最少代码使测试通过
   - 编写刚好足够的代码让测试通过
   - 不添加额外功能
   - 快速迭代

3. **REFACTOR** - 重构优化
   - 在测试保护下优化代码
   - 改进设计但保持功能不变
   - 测试仍然通过

### TDD 检查清单

每个功能开发前必须：
- [ ] 编写测试用例（pytest/vitest）
- [ ] 确认测试失败
- [ ] 实现功能代码
- [ ] 确认测试通过
- [ ] 检查测试覆盖率（目标 ≥ 80%）

### 测试优先级

```
测试金字塔:
       /\
      /  \     E2E 测试 (10%) - 关键用户流程
     /____\
    /      \   集成测试 (30%) - API、数据库交互
   /________\
  /          \ 单元测试 (60%) - 核心逻辑
```

---

## 📁 项目架构

### 技术栈

**后端**:
- FastAPI + Python 3.11+
- SQLAlchemy (异步)
- LangChain/LangGraph
- PostgreSQL

**前端**:
- Next.js 15 (App Router)
- React 19
- Tailwind CSS v4
- Zustand (状态管理)

### 目录结构

```
agent_app/
├── backend/app/
│   ├── agent/          # Agent 核心逻辑
│   ├── api/            # FastAPI 路由
│   ├── core/           # 配置、日志
│   ├── db/             # 数据库
│   ├── llm/            # LLM Factory
│   ├── skills/         # Skills Manager
│   ├── tools/          # 工具注册表
│   └── middleware/     # LangGraph 中间件
├── frontend/src/
│   ├── app/            # Next.js 页面
│   ├── components/     # React 组件
│   ├── lib/            # 工具函数
│   ├── store/          # Zustand 状态
│   └── types/          # TypeScript 类型
├── skills/             # Skills 目录
└── tests/              # 测试文件
```

---

## 🧪 测试规范

### 后端测试 (pytest)

```python
# 测试文件命名: tests/test_<module>.py
# 测试类命名: Test<ClassName>
# 测试函数命名: test_<function_name>_<scenario>

import pytest
from app.core.config import settings

class TestConfig:
    def test_load_settings(self):
        """Test settings loading from environment"""
        assert settings.app_name == "Multi-Tool AI Agent"
        assert settings.app_version == "0.1.0"
```

### 前端测试 (vitest)

```typescript
// 测试文件命名: <module>.test.ts
// 测试函数命名: describe + test

import { describe, it, expect } from 'vitest';
import { cn } from '@/lib/utils';

describe('cn utility', () => {
  it('merges class names correctly', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1');
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });
});
```

### 集成测试

```python
# tests/integration/test_agent_flow.py

async def test_agent_execution_flow():
    """Test complete agent execution with tool calls"""
    executor = AgentExecutor()
    result = await executor.execute("What's 2+2?")
    assert result["response"]
    assert result["session_id"]
```

---

## 📝 代码规范

### Python

- 使用 **类型注解**
- Docstring 遵循 Google 风格
- 异步函数使用 `async/await`
- 错误处理要具体

```python
async def execute_tool(tool_name: str, params: dict) -> ToolResult:
    """Execute a tool with given parameters.

    Args:
        tool_name: Name of the tool to execute
        params: Parameters for the tool

    Returns:
        ToolResult with execution status and data

    Raises:
        ToolNotFoundError: If tool doesn't exist
        ToolExecutionError: If tool execution fails
    """
    ...
```

### TypeScript

- 使用 **严格模式**
- 接口定义清晰
- 避免使用 `any`

```typescript
interface ToolExecution {
  toolName: string;
  parameters: Record<string, unknown>;
  result?: unknown;
  error?: string;
}
```

---

## 🔄 Git 工作流

### Commit 规范

```
<type>: <description>

[optional body]

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**Type**:
- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 重构
- `test`: 测试
- `docs`: 文档
- `chore`: 杂项

### 示例

```
feat: implement memory middleware for LangGraph

Add before_agent, wrap_model_call, after_agent hooks:
- Load user profile before agent execution
- Inject ephemeral context into model calls
- Write back profile after completion

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 🎯 当前阶段

### Phase 1: 基础设施 ✅
- [x] 项目脚手架
- [x] Docker Compose 配置
- [x] 数据库模型
- [x] LLM Factory
- [x] 核心工具
- [x] 前端基础组件

### Phase 2: Memory 系统 (下一步)
- [ ] **TDD: Memory 中间件**
- [ ] Token 预算管理
- [ ] Ephemeral 注入
- [ ] 用户画像 CRUD

### Phase 3: Skills 系统
- [ ] **TDD: Skill Manager**
- [ ] SKILL.md 解析器
- [ ] 热重载机制
- [ ] 优先级覆盖

### Phase 4: 可观测性
- [ ] **TDD: SSE 流式推送**
- [ ] 时间轴可视化
- [ ] HIL 人工介入
- [ ] 前端状态管理

---

## ⚡ 快速参考

### 运行测试

```bash
# 后端单元测试
cd backend
pytest

# 前端测试
cd frontend
npm test

# 测试覆盖率
pytest --cov=backend --cov-report=html
```

### TDD 开发流程

```bash
# 1. 编写测试 (失败)
vim tests/test_feature.py

# 2. 运行测试 (确认失败)
pytest tests/test_feature.py

# 3. 实现功能
vim app/feature.py

# 4. 运行测试 (确认通过)
pytest tests/test_feature.py

# 5. 重构 (可选)
# 在测试保护下优化代码
```

---

## 📚 参考文档

- [架构设计](docs/superpowers/specs/2026-03-20-multi-tool-agent-design.md)
- [产品需求](docs/implementation/product-requirements.md)
- [后端实施计划](docs/implementation/backend-implementation-plan.md)
- [前端实施计划](docs/implementation/frontend-implementation-plan.md)
- [测试策略](docs/testing-strategy.md)
- [任务清单](docs/implementation/TASK_LIST.md)

---

**记住**: TDD 不是可选项，而是**强制要求**。每个功能开发前必须先写测试！
