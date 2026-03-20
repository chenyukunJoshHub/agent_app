# Multi-Tool AI Agent 测试策略规划

**版本**: v1.0
**日期**: 2026-03-20
**状态**: 初稿完成

---

## 目录

1. [测试金字塔](#测试金字塔)
2. [单元测试策略](#单元测试策略)
3. [集成测试策略](#集成测试策略)
4. [E2E 测试策略](#e2e-测试策略)
5. [测试数据管理](#测试数据管理)
6. [覆盖率目标](#覆盖率目标)
7. [CI/CD 集成](#cicd-集成)
8. [Mock 策略](#mock-策略)
9. [测试环境管理](#测试环境管理)
10. [实施路线图](#实施路线图)

---

## 测试金字塔

```
        /\
       /E2E\        ← 端到端测试（关键用户流程）~10%
      /------\
     / 集成测试 \     ← API 测试、组件集成测试 ~30%
    /----------\
   /  单元测试    \    ← 函数/类/组件单元测试 ~60%
  /--------------\
```

### 测试分层原则

| 层级 | 覆盖范围 | 执行速度 | 隔离性 | 维护成本 | 数量占比 |
|-----|---------|---------|--------|----------|----------|
| **单元测试** | 单个函数/类/组件 | ⚡ 最快 | 🔒 完全隔离 | 💰 低 | 60% |
| **集成测试** | 模块间交互、API 端点 | 🚗 中等 | ⚠️ 部分隔离 | 💎💎 中 | 30% |
| **E2E 测试** | 完整用户流程 | 🐢 最慢 | 🌐 真实环境 | 💎💎💎 高 | 10% |

### 为什么是 60-30-10？

```
成本/收益比分析：

单元测试（60%）
├── 成本：低（Mock 外部依赖，执行快）
├── 收益：高（快速反馈，精确定位问题）
└── ROI：💎💎💎💎💎 最高

集成测试（30%）
├── 成本：中（需要真实数据库、网络）
├── 收益：中高（验证模块协作）
└── ROI：💎💎💎 中高

E2E 测试（10%）
├── 成本：高（完整环境，执行慢，脆弱）
├── 收益：中（验证端到端流程，但问题定位难）
└── ROI：💎💎 较低
```

---

## 单元测试策略

### 后端单元测试（pytest）

#### 1. Memory 中间件测试

**测试目标**：验证 `MemoryMiddleware` 的钩子正确执行

```python
# backend/tests/middleware/test_memory_middleware.py

import pytest
from unittest.mock import AsyncMock, Mock, patch
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from agent.middleware.memory import MemoryMiddleware, MemoryContext, EpisodicData

class TestMemoryMiddleware:
    """MemoryMiddleware 单元测试套件"""

    @pytest.fixture
    def memory_manager(self):
        """创建 Mock MemoryManager"""
        manager = Mock()
        manager.load_episodic = AsyncMock(return_value=EpisodicData(
            user_id="test_user",
            preferences={"domain": "legal-tech", "language": "zh"},
            interaction_count=5
        ))
        manager.save_episodic = AsyncMock()
        manager.build_ephemeral_prompt = Mock(return_value="[用户画像]\ndomain: legal-tech")
        return manager

    @pytest.fixture
    def middleware(self, memory_manager):
        """创建 MemoryMiddleware 实例"""
        return MemoryMiddleware(memory_manager)

    @pytest.mark.asyncio
    async def test_abefore_agent_loads_episodic_memory(self, middleware, memory_manager):
        """测试：abefore_agent 正确加载用户画像"""
        # Given
        state = {}
        runtime = Mock(config={"configurable": {"user_id": "test_user"}})

        # When
        result = await middleware.abefore_agent(state, runtime)

        # Then
        memory_manager.load_episodic.assert_called_once_with("test_user")
        assert "memory_ctx" in result
        assert result["memory_ctx"]["episodic"].preferences["domain"] == "legal-tech"

    @pytest.mark.asyncio
    async def test_abefore_agent_handles_new_user(self, middleware, memory_manager):
        """测试：新用户返回空 EpisodicData"""
        # Given
        memory_manager.load_episodic.return_value = EpisodicData()
        runtime = Mock(config={"configurable": {"user_id": "new_user"}})

        # When
        result = await middleware.abefore_agent({}, runtime)

        # Then
        assert result["memory_ctx"]["episodic"].interaction_count == 0

    def test_wrap_model_call_injects_ephemeral_prompt(self, middleware, memory_manager):
        """测试：wrap_model_call 临时注入用户画像"""
        # Given
        request = Mock(
            state={"memory_ctx": MemoryContext(episodic=EpisodicData(
                preferences={"domain": "legal-tech"}
            ))},
            system_message=Mock(content="原始 System Prompt")
        )
        handler = Mock(return_value=ModelResponse(content="AI 回复"))

        # When
        response = middleware.wrap_model_call(request, handler)

        # Then
        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert "legal-tech" in call_args.system_message.content

    def test_wrap_model_call_skips_when_no_memory_ctx(self, middleware, memory_manager):
        """测试：无 memory_ctx 时直接透传"""
        # Given
        request = Mock(state=None, system_message=Mock(content="原始"))
        handler = Mock(return_value=ModelResponse(content="回复"))

        # When
        response = middleware.wrap_model_call(request, handler)

        # Then
        handler.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_aafter_agent_saves_episodic_memory(self, middleware, memory_manager):
        """测试：aafter_agent 写回用户画像（P2 功能）"""
        # Given
        state = {
            "memory_ctx": MemoryContext(episodic=EpisodicData(
                interaction_count=6  # +1
            ))
        }
        runtime = Mock(config={"configurable": {"user_id": "test_user"}})

        # When
        await middleware.aafter_agent(state, runtime)

        # Then
        memory_manager.save_episodic.assert_called_once()
```

#### 2. Skill Manager 测试

```python
# backend/tests/skills/test_skill_manager.py

import pytest
from pathlib import Path
from skills.manager import SkillManager, SkillDefinition

class TestSkillManager:
    """SkillManager 单元测试套件"""

    @pytest.fixture
    def temp_skills_dir(self, tmp_path):
        """创建临时 skills 目录结构"""
        # 低优先级（全局）
        global_dir = tmp_path / ".agents" / "skills"
        global_dir.mkdir(parents=True)
        (global_dir / "global_skill.md").write_text("""
---
id: global-skill
name: Global Skill
description: 全局技能
---
指令内容
        """)

        # 高优先级（项目）
        project_dir = tmp_path / "project" / "skills"
        project_dir.mkdir(parents=True)
        (project_dir / "project_skill.md").write_text("""
---
id: project-skill
name: Project Skill
description: 项目技能
---
指令内容
        """)

        # 覆盖场景
        (project_dir / "global_skill.md").write_text("""
---
id: global-skill
name: Global Skill (Override)
description: 项目覆盖全局技能
---
覆盖后的指令
        """)

        return tmp_path

    def test_scan_all_loads_skills_from_both_dirs(self, temp_skills_dir):
        """测试：扫描加载所有 skills"""
        # Given
        manager = SkillManager(skill_dirs=[
            temp_skills_dir / ".agents" / "skills",
            temp_skills_dir / "project" / "skills"
        ])

        # When
        snapshot = manager.scan_all()

        # Then
        assert "global-skill" in snapshot.skills
        assert "project-skill" in snapshot.skills
        # 项目优先级覆盖全局
        assert snapshot.skills["global-skill"].description == "项目覆盖全局技能"

    def test_skill_conflict_resolution(self, temp_skills_dir):
        """测试：技能冲突解决（高优先级覆盖低优先级）"""
        # 验证覆盖日志
        pass

    def test_hot_reload_detects_changes(self, temp_skills_dir):
        """测试：热重载检测文件变化"""
        # Given
        manager = SkillManager(skill_dirs=[temp_skills_dir / "project" / "skills"])
        initial_snapshot = manager.scan_all()

        # When：修改文件
        skill_file = temp_skills_dir / "project" / "skills" / "project_skill.md"
        skill_file.write_text("""
---
id: project-skill
name: Updated Skill
---
更新后的指令
        """)

        # Then
        new_snapshot = manager.scan_all()
        assert new_snapshot.version > initial_snapshot.version
```

#### 3. 工具函数测试

```python
# backend/tests/utils/test_token_counter.py

import pytest
from utils.token import count_tokens, get_token_encoder

class TestTokenCounter:
    """Token 计数工具测试"""

    def test_count_tokens_for_known_model(self):
        """测试：精确计数已知模型的 Token"""
        text = "Hello, world!"
        count = count_tokens(text, model="gpt-4o")
        assert count > 0

    def test_count_tokens_fallback_to_cl100k_base(self):
        """测试：未知模型回退到 cl100k_base"""
        text = "测试文本"
        count = count_tokens(text, model="unknown-model")
        assert count > 0

    def test_count_chinese_tokens(self):
        """测试：中文字符 Token 计数"""
        chinese_text = "这是一个测试"
        count = count_tokens(chinese_text)
        # 中文字符通常占用更多 Token
        assert count >= len(chinese_text)

    @pytest.mark.parametrize("text,expected_min", [
        ("", 0),
        ("a", 1),
        ("Hello world!", 2),
    ])
    def test_token_count_edge_cases(self, text, expected_min):
        """测试：边界情况"""
        assert count_tokens(text) >= expected_min
```

#### 4. LLM Factory 测试

```python
# backend/tests/llm/test_factory.py

import pytest
from unittest.mock import Mock, patch
from llm.factory import llm_factory, LLMProvider
from langchain_core.language_models.chat_models import BaseChatModel

class TestLLMFactory:
    """LLM Factory 单元测试"""

    @patch('llm.factory.ChatOllama')
    def test_create_ollama_llm(self, mock_chatollama):
        """测试：创建 Ollama LLM"""
        # Given
        mock_model = Mock(spec=BaseChatModel)
        mock_chatollama.return_value = mock_model

        # When
        llm = llm_factory(provider="ollama", model="claude-opus-4-6")

        # Then
        mock_chatollama.assert_called_once()
        assert llm == mock_model

    @patch('llm.factory.ChatOpenAI')
    def test_create_deepseek_llm(self, mock_chatopenai):
        """测试：创建 DeepSeek LLM"""
        mock_model = Mock(spec=BaseChatModel)
        mock_chatopenai.return_value = mock_model

        llm = llm_factory(provider="deepseek", model="deepseek-chat")

        mock_chatopenai.assert_called_once_with(
            model="deepseek-chat",
            api_key=pytest.os.getenv("DEEPSEEK_API_KEY")
        )

    def test_fallback_mechanism(self):
        """测试：主 LLM 失败时自动回退"""
        # 模拟主 LLM 抛出异常
        with patch('llm.factory.ChatOllama', side_effect=Exception("Connection failed")):
            with patch('llm.factory.ChatZhipuAI') as mock_fallback:
                llm = llm_factory(
                    provider="ollama",
                    fallback_provider="zhipu"
                )
                # 验证回退到备用 LLM
                mock_fallback.assert_called_once()
```

### 前端单元测试（vitest）

#### 1. 组件测试

```typescript
// frontend/components/__tests__/Timeline.test.tsx

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Timeline } from '../Timeline'

describe('Timeline Component', () => {
  const mockEvents = [
    {
      id: '1',
      step: 1,
      title: 'before_agent',
      description: '加载长期记忆',
      status: 'done' as const,
      timestamp: Date.now(),
      eventType: 'thought' as const
    },
    {
      id: '2',
      step: 2,
      title: 'LLM 调用',
      description: '调用 web_search 工具',
      status: 'active' as const,
      timestamp: Date.now(),
      eventType: 'tool_start' as const,
      metadata: { toolName: 'web_search' }
    }
  ]

  it('renders timeline events correctly', () => {
    render(<Timeline events={mockEvents} />)

    expect(screen.getByText('before_agent')).toBeInTheDocument()
    expect(screen.getByText('LLM 调用')).toBeInTheDocument()
  })

  it('applies correct status styles', () => {
    const { container } = render(<Timeline events={mockEvents} />)

    const doneEvent = container.querySelector('[data-status="done"]')
    const activeEvent = container.querySelector('[data-status="active"]')

    expect(doneEvent).toHaveClass('opacity-100')
    expect(activeEvent).toHaveClass('animate-pulse')
  })

  it('renders tool metadata when available', () => {
    render(<Timeline events={mockEvents} />)

    expect(screen.getByText('web_search')).toBeInTheDocument()
  })
})
```

#### 2. SSE Manager 测试

```typescript
// frontend/lib/__tests__/sse-manager.test.ts

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SSEManager } from '../sse-manager'
import { fetchEventSource } from '@microsoft/fetch-event-source'

vi.mock('@microsoft/fetch-event-source')

describe('SSEManager', () => {
  let sseManager: SSEManager

  beforeEach(() => {
    sseManager = new SSEManager()
    vi.clearAllMocks()
  })

  afterEach(() => {
    sseManager.disconnect()
  })

  it('connects to SSE endpoint with correct headers', async () => {
    const mockFetchEventSource = vi.mocked(fetchEventSource)
    mockFetchEventSource.mockResolvedValue(undefined as any)

    await sseManager.connect({
      url: 'http://localhost:8000/chat',
      token: 'test-token',
      onMessage: vi.fn()
    })

    expect(mockFetchEventSource).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer test-token'
        })
      })
    )
  })

  it('implements exponential backoff on retry', async () => {
    vi.useFakeTimers()
    const onMessage = vi.fn()
    let connectAttempts = 0

    vi.mocked(fetchEventSource).mockImplementation((url, options) => {
      connectAttempts++
      options?.onerror?.(new Error('Connection failed'))
      return Promise.resolve() as any
    })

    await sseManager.connect({
      url: 'http://localhost:8000/chat',
      token: 'test-token',
      onMessage,
      onError: vi.fn()
    })

    // 验证重试延迟指数增长
    vi.advanceTimersByTime(1000)
    expect(connectAttempts).toBe(2)

    vi.advanceTimersByTime(1500)  // 1.5x delay
    expect(connectAttempts).toBe(3)

    vi.useRealTimers()
  })

  it('resets retry count on successful connection', async () => {
    // 测试成功连接后重置重试计数
  })

  it('stops reconnecting after max retries', async () => {
    // 测试达到最大重试次数后停止
  })
})
```

#### 3. Zustand Store 测试

```typescript
// frontend/store/__tests__/use-session.test.ts

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSessionStore } from '../use-session'

describe('useSessionStore', () => {
  beforeEach(() => {
    // 重置 store 状态
    useSessionStore.setState({
      sessions: [],
      currentSessionId: null
    })
  })

  it('creates a new session', () => {
    const { result } = renderHook(() => useSessionStore())

    act(() => {
      result.current.createSession('Test Session')
    })

    expect(result.current.sessions).toHaveLength(1)
    expect(result.current.sessions[0].title).toBe('Test Session')
  })

  it('switches current session', () => {
    const { result } = renderHook(() => useSessionStore())

    act(() => {
      result.current.createSession('Session 1')
      result.current.createSession('Session 2')
      result.current.setCurrentSession(result.current.sessions[1].id)
    })

    expect(result.current.currentSessionId).toBe(result.current.sessions[1].id)
  })

  it('adds message to current session', () => {
    const { result } = renderHook(() => useSessionStore())

    act(() => {
      result.current.createSession('Test')
      result.current.addMessage({
        role: 'user',
        content: 'Hello'
      })
    })

    const currentSession = result.current.sessions.find(
      s => s.id === result.current.currentSessionId
    )

    expect(currentSession?.messages).toHaveLength(1)
    expect(currentSession?.messages[0].content).toBe('Hello')
  })
})
```

#### 4. React Query Hooks 测试

```typescript
// frontend/hooks/__tests__/use-sessions.test.ts

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useSessions, useCreateSession } from '../use-sessions'
import { fetchSessions, createSession } from '@/lib/api/sessions'

// Mock API 函数
vi.mock('@/lib/api/sessions', () => ({
  fetchSessions: vi.fn(),
  createSession: vi.fn()
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useSessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches sessions successfully', async () => {
    const mockSessions = [
      { id: '1', title: 'Session 1', messages: [] },
      { id: '2', title: 'Session 2', messages: [] }
    ]
    vi.mocked(fetchSessions).mockResolvedValue(mockSessions)

    const { result } = renderHook(() => useSessions(), {
      wrapper: createWrapper()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockSessions)
  })

  it('creates a new session', async () => {
    const newSession = { id: '3', title: 'New Session', messages: [] }
    vi.mocked(createSession).mockResolvedValue(newSession)

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: createWrapper()
    })

    await result.current.mutateAsync('New Session')

    expect(createSession).toHaveBeenCalledWith('New Session')
  })
})
```

---

## 集成测试策略

### API 端点测试

```python
# backend/tests/api/test_chat_endpoint.py

import pytest
from httpx import AsyncClient
from main import app

class TestChatEndpoint:
    """聊天 API 集成测试"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def test_db(self, postgres_url):
        """创建测试数据库连接"""
        # 使用 pytest-asyncio 的 postgres fixture
        # 返回已初始化的数据库连接
        pass

    @pytest.mark.asyncio
    async def test_chat_simple_question(self, client):
        """场景1：简单问答（无工具调用）"""
        response = await client.post(
            "/chat",
            json={
                "message": "你好",
                "session_id": "test-session-1",
                "user_id": "test-user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_chat_with_tool_call(self, client, mock_llm_response):
        """场景2：单工具调用（read_file）"""
        # Mock LLM 返回工具调用指令
        mock_llm_response.return_value = AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {"path": "/skills/test.md"}}]
        )

        response = await client.post(
            "/chat",
            json={
                "message": "读取 test.md 文件",
                "session_id": "test-session-2",
                "user_id": "test-user"
            }
        )

        assert response.status_code == 200
        # 验证 SSE 事件流包含 tool_start 和 tool_result

    @pytest.mark.asyncio
    async def test_chat_multi_tool_serial(self, client):
        """场景3：多工具串行调用"""
        pass

    @pytest.mark.asyncio
    async def test_chat_session_continuity(self, client):
        """场景4：会话连续性（第二轮对话记住第一轮内容）"""
        # 第一轮
        await client.post("/chat", json={
            "message": "我叫张三",
            "session_id": "test-session-3",
            "user_id": "test-user"
        })

        # 第二轮
        response = await client.post("/chat", json={
            "message": "我叫什么名字？",
            "session_id": "test-session-3",
            "user_id": "test-user"
        })

        data = response.json()
        assert "张三" in data["answer"]

    @pytest.mark.asyncio
    async def test_sse_stream_events(self, client):
        """测试：SSE 事件流正确推送"""
        response = await client.post(
            "/chat",
            json={
                "message": "测试消息",
                "session_id": "test-sse",
                "user_id": "test-user"
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))

        # 验证事件类型
        event_types = [e["type"] for e in events]
        assert "thought" in event_types
        assert "done" in event_types
```

### 数据库集成测试

```python
# backend/tests/db/test_memory_integration.py

import pytest
from agent.middleware.memory import MemoryMiddleware, MemoryManager
from db.postgres import create_stores

class TestMemoryIntegration:
    """Memory 模块数据库集成测试"""

    @pytest.fixture
    async def stores(self):
        """创建真实的测试数据库 stores"""
        checkpointer, store = await create_stores(
            db_url="postgresql://postgres:postgres@localhost:5432/test_db"
        )
        yield checkpointer, store
        # 清理
        await store.delete(namespace=("profile", "test_user"), key="episodic")

    @pytest.mark.asyncio
    async def test_episodic_memory_round_trip(self, stores):
        """测试：长期记忆读写往返"""
        checkpointer, store = stores
        manager = MemoryManager(store)
        middleware = MemoryMiddleware(manager)

        # 写入
        await manager.save_episodic("test_user", EpisodicData(
            user_id="test_user",
            preferences={"domain": "legal-tech"},
            interaction_count=1
        ))

        # 读取
        loaded = await manager.load_episodic("test_user")

        assert loaded.preferences["domain"] == "legal-tech"
        assert loaded.interaction_count == 1

    @pytest.mark.asyncio
    async def test_checkpoint_version_chain(self, stores):
        """测试：检查点版本链（HIL 断点恢复）"""
        checkpointer, _ = stores

        config = {"configurable": {"thread_id": "test-thread"}}

        # 创建多个检查点
        for step in range(3):
            await checkpointer.aput(
                config,
                {"messages": [f"step_{step}"]},
                {"step": step}
            )

        # 恢复最新检查点
        latest = await checkpointer.aget(config)
        assert latest.config["step"] == 2

        # 恢复特定版本的检查点（HIL resume 场景）
        checkpoint_1 = await checkpointer.aget_tuple(config, 1)
        assert checkpoint_1.config["step"] == 1
```

### Agent 执行流程测试

```python
# backend/tests/agent/test_executor_integration.py

import pytest
from agent.executor import AgentExecutor
from langchain.schema import HumanMessage, AIMessage, ToolMessage

class TestAgentExecutorIntegration:
    """Agent 执行流程集成测试"""

    @pytest.fixture
    async def executor(self, test_stores, mock_llm):
        """创建已初始化的 Agent Executor"""
        return AgentExecutor(
            llm=mock_llm,
            tools=[read_file, web_search],
            checkpointer=test_stores[0],
            store=test_stores[1]
        )

    @pytest.mark.asyncio
    async def test_react_loop_single_tool(self, executor):
        """测试：ReAct 循环 - 单工具调用"""
        result = await executor.ainvoke(
            HumanMessage(content="读取 skills/readme.md"),
            config={"configurable": {"thread_id": "test-1"}}
        )

        # 验证执行流程
        messages = result["messages"]
        assert len(messages) >= 3  # Human -> AI(tool_call) -> Tool(result)
        assert isinstance(messages[1], AIMessage)
        assert messages[1].tool_calls[0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_react_loop_parallel_tools(self, executor):
        """测试：ReAct 循环 - 并行工具调用"""
        # Mock LLM 返回多个工具调用
        result = await executor.ainvoke(
            HumanMessage(content="查询天气和股价"),
            config={"configurable": {"thread_id": "test-2"}}
        )

        # 验证工具并行执行
        tool_calls = result["messages"][1].tool_calls
        assert len(tool_calls) == 2

    @pytest.mark.asyncio
    async def test_summarization_trigger(self, executor):
        """测试：Token 超限触发压缩"""
        # 创建超长历史
        long_history = [HumanMessage(content=f"消息 {i}") for i in range(100)]

        result = await executor.ainvoke(
            {"messages": long_history + [HumanMessage(content="最新消息")]},
            config={"configurable": {"thread_id": "test-3"}}
        )

        # 验证历史被压缩
        assert len(result["messages"]) < 50
```

---

## E2E 测试策略

### Playwright 测试场景

```typescript
// e2e/scenarios/chat.spec.ts

import { test, expect } from '@playwright/test'

test.describe('Multi-Tool Agent E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000')
  })

  test('场景1：简单问答（无工具调用）', async ({ page }) => {
    // Given
    await page.fill('[data-testid="chat-input"]', '你好，请介绍一下你自己')

    // When
    await page.click('[data-testid="send-button"]')

    // Then
    await expect(page.locator('[data-testid="message-ai"]')).toBeVisible()
    const aiMessage = page.locator('[data-testid="message-ai"]').last()
    await expect(aiMessage).toContainText('AI 助手', { timeout: 10000 })
  })

  test('场景2：单工具调用（read_file）', async ({ page }) => {
    // Given
    await page.fill('[data-testid="chat-input"]', '读取 skills/readme.md 文件')

    // When
    await page.click('[data-testid="send-button"]')

    // Then
    // 验证时间轴显示工具调用
    await expect(page.locator('[data-event-type="tool_start"]')).toBeVisible()
    await expect(page.locator('[data-tool-name="read_file"]')).toBeVisible()

    // 验证最终答案
    await expect(page.locator('[data-testid="message-ai"]')).last()
      .toContainText('readme.md', { timeout: 15000 })
  })

  test('场景3：多工具串行调用', async ({ page }) => {
    // Given
    await page.fill('[data-testid="chat-input"]',
      '搜索今天的天气，然后把结果保存到 weather.txt 文件')

    // When
    await page.click('[data-testid="send-button"]')

    // Then
    // 验证时间轴显示两个工具调用
    await expect(page.locator('[data-event-type="tool_start"]')).toHaveCount(2, {
      timeout: 20000
    })

    // 验证工具顺序（先搜索，后写文件）
    const toolNames = await page.locator('[data-tool-name]').allTextContents()
    expect(toolNames[0]).toContain('web_search')
    expect(toolNames[1]).toContain('write_file')
  })

  test('场景4：HIL 确认流程', async ({ page }) => {
    // Given
    await page.fill('[data-testid="chat-input"]',
      '发邮件给 boss@example.com 告知股价')

    // When
    await page.click('[data-testid="send-button"]')

    // Then：验证 HIL 弹窗出现
    await expect(page.locator('[data-testid="hil-modal"]')).toBeVisible()
    await expect(page.locator('[data-hil-tool="send_email"]')).toBeVisible()
    await expect(page.locator('[data-hil-arg="to"]')).toContainText('boss@example.com')

    // 用户确认
    await page.click('[data-testid="hil-confirm-button"]')

    // 验证邮件发送
    await expect(page.locator('[data-event-type="tool_result"]')).toBeVisible()
  })

  test('场景5：会话恢复（Memory 中间件）', async ({ page }) => {
    // 第一轮对话
    await page.fill('[data-testid="chat-input"]', '我叫张三')
    await page.click('[data-testid="send-button"]')
    await expect(page.locator('[data-testid="message-ai"]')).toBeVisible()

    // 刷新页面（模拟会话恢复）
    await page.reload()

    // 第二轮对话
    await page.fill('[data-testid="chat-input"]', '我叫什么名字？')
    await page.click('[data-testid="send-button"]')

    // 验证 Agent 记住了名字
    await expect(page.locator('[data-testid="message-ai"]')).last()
      .toContainText('张三', { timeout: 10000 })
  })

  test('场景6：Token 预算管理', async ({ page }) => {
    // 创建超长会话历史
    for (let i = 0; i < 50; i++) {
      await page.fill('[data-testid="chat-input"]', `测试消息 ${i}`)
      await page.click('[data-testid="send-button"]')
      await page.waitForTimeout(500)
    }

    // 发送新消息
    await page.fill('[data-testid="chat-input"]', '总结我们的对话')
    await page.click('[data-testid="send-button"]')

    // 验证 Token 进度条显示（不超预算）
    await expect(page.locator('[data-testid="token-progress"]')).toBeVisible()
    const progressValue = await page.locator('[data-testid="token-progress"]')
      .getAttribute('aria-valuenow')
    expect(parseInt(progressValue || '0')).toBeLessThan(100)
  })
})
```

---

## 测试数据管理

### Fixture 设计

```python
# backend/tests/fixtures/data.py

import pytest
from pathlib import Path
from agent.middleware.memory import EpisodicData

@pytest.fixture
def sample_skill_file(tmp_path):
    """创建示例 Skill 文件"""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text("""
---
id: test-skill
name: Test Skill
description: 测试技能
---
# 指令内容

你是一个测试助手。

## 工具

- test_tool: 测试工具
    """)

    (skill_dir / "examples.md").write_text("""
# 示例

用户: 测试输入
助手: 测试输出
    """)

    return skill_dir

@pytest.fixture
def sample_episodic_data():
    """创建示例用户画像数据"""
    return EpisodicData(
        user_id="test_user",
        preferences={
            "domain": "legal-tech",
            "language": "zh"
        },
        interaction_count=10,
        summary="用户关注电子签名和合同管理"
    )

@pytest.fixture
def mock_llm_response():
    """Mock LLM 响应库"""
    return {
        "simple_answer": AIMessage(content="这是我的回答"),
        "tool_call_read_file": AIMessage(
            content="",
            tool_calls=[{
                "name": "read_file",
                "args": {"path": "/skills/test.md"},
                "id": "call_001"
            }]
        ),
        "parallel_tools": AIMessage(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "天气"}, "id": "call_001"},
                {"name": "get_time", "args": {}, "id": "call_002"}
            ]
        )
    }
```

### 测试数据库

```python
# backend/tests/fixtures/database.py

import pytest
from psycopg import AsyncConnection
from db.postgres import create_stores

@pytest.fixture(scope="session")
async def test_database():
    """创建测试数据库（会话级别）"""
    conn = await AsyncConnection.connect(
        "postgresql://postgres:postgres@localhost:5432"
    )
    async with conn.cursor() as cur:
        await cur.execute("CREATE DATABASE test_db")
    await conn.close()
    yield
    # 清理
    conn = await AsyncConnection.connect(
        "postgresql://postgres:postgres@localhost:5432"
    )
    async with conn.cursor() as cur:
        await cur.execute("DROP DATABASE test_db")
    await conn.close()

@pytest.fixture
async def test_stores(test_database):
    """创建测试用的 stores"""
    checkpointer, store = await create_stores(
        db_url="postgresql://postgres:postgres@localhost:5432/test_db"
    )
    yield checkpointer, store

    # 每个测试后清理数据
    await store.aput(namespace=("test",), key="cleanup", value={})
```

### Mock LLM 响应库

```python
# backend/tests/fixtures/llm.py

import pytest
from unittest.mock import AsyncMock, Mock
from langchain.schema import AIMessage, HumanMessage

@pytest.fixture
def mock_llm():
    """创建 Mock LLM，支持预设响应序列"""
    class MockLLM:
        def __init__(self):
            self.responses = []
            self.call_count = 0

        def set_responses(self, responses):
            """设置响应序列"""
            self.responses = responses

        async def ainvoke(self, messages, **kwargs):
            """模拟 LLM 调用"""
            if self.call_count < len(self.responses):
                response = self.responses[self.call_count]
            else:
                response = AIMessage(content="默认回复")
            self.call_count += 1
            return response

    return MockLLM()

@pytest.fixture
def mock_llm_factory():
    """Mock LLM Factory"""
    with patch('llm.factory.llm_factory') as mock:
        mock_llm_instance = Mock()
        mock.return_value = mock_llm_instance
        yield mock_llm_instance
```

---

## 覆盖率目标

### 后端覆盖率

| 模块 | 目标覆盖率 | 优先级 |
|-----|----------|--------|
| **agent/middleware/** | 85% | 🔴 P0 |
| **memory/** | 90% | 🔴 P0 |
| **skills/manager.py** | 85% | 🔴 P0 |
| **llm/factory.py** | 80% | 🔴 P0 |
| **tools/** | 75% | 🟡 P1 |
| **utils/token.py** | 90% | 🟡 P1 |
| **api/endpoints/** | 70% | 🟡 P1 |
| **db/** | 60% | ⚪ P2 |

### 前端覆盖率

| 模块 | 目标覆盖率 | 优先级 |
|-----|----------|--------|
| **components/Timeline.tsx** | 85% | 🔴 P0 |
| **lib/sse-manager.ts** | 90% | 🔴 P0 |
| **store/use-session.ts** | 85% | 🔴 P0 |
| **components/HILModal.tsx** | 80% | 🟡 P1 |
| **hooks/use-sessions.ts** | 75% | 🟡 P1 |
| **components/ChatInput.tsx** | 70% | ⚪ P2 |

### 覆盖率配置

```ini
# backend/pyproject.toml

[tool.pytest.ini_options]
addopts = [
    "--cov=agent",
    "--cov=memory",
    "--cov=skills",
    "--cov=llm",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=75"
]

[tool.coverage.run]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*"
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

```typescript
// frontend/vitest.config.ts

export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      include: ['**/*.{ts,tsx}'],
      exclude: [
        'node_modules/',
        '**/*.test.{ts,tsx}',
        '**/*.spec.{ts,tsx}',
        '**/types/',
        '**/dist/'
      ],
      thresholds: {
        lines: 75,
        functions: 75,
        branches: 70,
        statements: 75
      }
    }
  }
})
```

---

## CI/CD 集成

### GitHub Actions 配置

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop, 'feature/**']
  pull_request:
    branches: [main, develop]

jobs:
  # ========================================
  # 单元测试（快速反馈）
  # ========================================
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10

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
          pip install pytest pytest-cov pytest-asyncio pytest-mock

      - name: Run unit tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        run: |
          pytest tests/unit/ \
            --cov=agent \
            --cov=memory \
            --cov=skills \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=75

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
          flags: unit-tests

  # ========================================
  # 前端单元测试
  # ========================================
  frontend-unit-tests:
    name: Frontend Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10

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

      - name: Run unit tests
        working-directory: ./frontend
        run: npm run test:unit -- --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./frontend/coverage/coverage-final.json
          flags: frontend-unit

  # ========================================
  # 集成测试
  # ========================================
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 20
    needs: [unit-tests, frontend-unit-tests]

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
          pip install pytest pytest-asyncio httpx

      - name: Run integration tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          LLM_PROVIDER: mock  # 使用 Mock LLM
        run: |
          pytest tests/integration/ -v

  # ========================================
  # E2E 测试
  # ========================================
  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: [integration-tests]

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: e2e_db
        ports:
          - 5432:5432

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

      - name: Install Playwright
        working-directory: ./frontend
        run: npx playwright install --with-deps

      - name: Start services
        run: |
          docker-compose up -d postgres backend
          npm run dev &

      - name: Wait for services
        run: |
          npx wait-on http://localhost:8000/health -t 30000
          npx wait-on http://localhost:3000 -t 30000

      - name: Run E2E tests
        working-directory: ./frontend
        run: npm run test:e2e

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: frontend/playwright-report/
          retention-days: 7
```

### 测试触发条件

| 事件 | 触发条件 | 执行测试套件 |
|-----|---------|------------|
| **Push to main** | 自动 | 全部（单元 + 集成 + E2E） |
| **Push to develop** | 自动 | 全部（单元 + 集成 + E2E） |
| **Push to feature/** | 自动 | 单元 + 集成 |
| **PR to main** | 自动 | 全部 |
| **PR to develop** | 自动 | 全部 |
| **Comment `/test`** | 手动触发 | 全部 |
| **Comment `/test unit`** | 手动触发 | 仅单元 |

---

## Mock 策略

### Mock 层级决策

```
决策树：何时使用 Mock？

需要外部依赖？
├── 是 → 可控？
│   ├── 是 → 使用 Mock（更快、更稳定）
│   └── 否 → 使用真实依赖（集成测试）
└── 否 → 不需要 Mock

示例：
├── LLM 调用 → ✅ Mock（不可控、慢、有成本）
├── 文件系统 → ✅ Mock（隔离性）
├── HTTP API → ✅ Mock（外部依赖）
├── PostgreSQL → ⚠️ 部分场景用真实数据库（集成测试）
└── Redis → ✅ Mock（可选依赖）
```

### Mock 实现

```python
# backend/tests/mocks/mock_llm.py

from unittest.mock import AsyncMock
from langchain.schema import AIMessage, HumanMessage, ToolMessage
from typing import List, Optional

class MockLLM:
    """
    可配置的 Mock LLM

    支持预设响应序列，模拟真实 LLM 行为
    """

    def __init__(self, responses: Optional[List] = None):
        self.responses = responses or []
        self.call_count = 0
        self.call_history = []

    async def ainvoke(self, messages, **kwargs):
        """模拟 LLM 调用"""
        self.call_count += 1
        self.call_history.append({
            "messages": messages,
            "kwargs": kwargs
        })

        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        else:
            # 默认响应
            return AIMessage(content="Mock LLM 默认回复")

    def reset(self):
        """重置调用状态"""
        self.call_count = 0
        self.call_history = []

# 使用示例
@pytest.fixture
def mock_llm_for_react():
    """为 ReAct 循环预设响应序列"""
    return MockLLM(responses=[
        # 第一次调用：决定调用工具
        AIMessage(
            content="我需要搜索信息",
            tool_calls=[{
                "name": "web_search",
                "args": {"query": "测试查询"},
                "id": "call_001"
            }]
        ),
        # 第二次调用：基于工具结果生成答案
        AIMessage(content="根据搜索结果，答案是...")
    ])
```

### Mock 工具

```python
# backend/tests/mocks/mock_tools.py

from unittest.mock import Mock
from langchain.tools import tool

@tool
def mock_read_file(path: str) -> str:
    """Mock read_file 工具"""
    return f"文件 {path} 的内容"

@tool
def mock_web_search(query: str) -> str:
    """Mock web_search 工具"""
    return f"搜索结果：{query}"

@tool
def mock_send_email(to: str, subject: str, body: str) -> str:
    """Mock send_email 工具"""
    return f"邮件已发送至 {to}"

class MockTools:
    """Mock 工具集合"""

    @staticmethod
    def get_all():
        """获取所有 Mock 工具"""
        return [mock_read_file, mock_web_search, mock_send_email]
```

---

## 测试环境管理

### 环境分层

```
┌─────────────────────────────────────────────┐
│              测试环境金字塔                   │
├─────────────────────────────────────────────┤
│  Local 开发环境（单元测试 + 快速集成）       │
│  - Docker Compose                           │
│  - Mock LLM                                 │
│  - 内存数据库（可选）                        │
├─────────────────────────────────────────────┤
│  CI/CD 环境（全量测试）                      │
│  - GitHub Actions                           │
│  - 真实 PostgreSQL                          │
│  - Mock LLM（成本控制）                      │
├─────────────────────────────────────────────┤
│  Staging 环境（E2E + 性能测试）              │
│  - Railway 部署                             │
│  - 真实 LLM API                             │
│  - 完整监控                                 │
└─────────────────────────────────────────────┘
```

### Docker Compose 测试配置

```yaml
# docker-compose.test.yml

version: '3.8'

services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test_db
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend-test:
    build:
      context: ./backend
      dockerfile: Dockerfile.test
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres-test:5432/test_db
      LLM_PROVIDER: mock
      LOG_LEVEL: DEBUG
    depends_on:
      postgres-test:
        condition: service_healthy
    command: pytest tests/ -v

  frontend-test:
    build:
      context: ./frontend
      dockerfile: Dockerfile.test
    environment:
      - CI=true
    command: npm run test:ci
```

---

## 实施路线图

### Phase 1: 测试基础设施（Week 1）🔴 P0

**目标**：建立测试基础设施

- [x] 配置 pytest + vitest
- [ ] 创建测试目录结构
- [ ] 编写 Fixture 库
- [ ] 配置 Mock LLM
- [ ] 设置 Docker Compose 测试环境
- [ ] 配置 CI/CD 测试工作流

**验收**：
- `pytest tests/unit/` 能运行
- `npm run test:unit` 能运行
- GitHub Actions 测试任务通过

### Phase 2: 后端单元测试（Week 2）🔴 P0

**目标**：核心模块单元测试覆盖率 75%+

- [ ] Memory Middleware 测试
- [ ] Skill Manager 测试
- [ ] LLM Factory 测试
- [ ] Token Counter 测试
- [ ] 工具函数测试

**验收**：
- `pytest --cov` 覆盖率 ≥ 75%
- 所有测试通过

### Phase 3: 前端单元测试（Week 2-3）🔴 P0

**目标**：核心组件单元测试覆盖率 75%+

- [ ] Timeline 组件测试
- [ ] SSE Manager 测试
- [ ] Zustand Store 测试
- [ ] React Query Hooks 测试

**验收**：
- `npm run test:unit -- --coverage` 覆盖率 ≥ 75%
- 所有测试通过

### Phase 4: 集成测试（Week 3-4）🟡 P1

**目标**：关键路径集成测试

- [ ] API 端点测试（/chat, /chat/resume）
- [ ] 数据库集成测试
- [ ] Agent 执行流程测试
- [ ] SSE 事件流测试

**验收**：
- 集成测试套件全部通过
- 覆盖关键用户路径

### Phase 5: E2E 测试（Week 4-5）🟡 P1

**目标**：核心场景端到端测试

- [ ] Playwright 环境搭建
- [ ] 场景1：简单问答
- [ ] 场景2：单工具调用
- [ ] 场景3：多工具串行调用
- [ ] 场景4：HIL 确认流程
- [ ] 场景5：会话恢复

**验收**：
- E2E 测试套件全部通过
- Playwright 报告生成

### Phase 6: 测试优化（Week 5-6）⚪ P2

**目标**：测试性能和稳定性优化

- [ ] 测试并行化
- [ ] 测试数据隔离
- [ ] Mock 策略优化
- [ ] 测试报告增强

**验收**：
- 测试执行时间 < 10 分钟
- 测试稳定性 ≥ 95%

---

## 附录

### 测试命名约定

```
文件命名：
├── backend/tests/
│   ├── unit/test_<module>.py
│   ├── integration/test_<feature>.py
│   └── e2e/test_<scenario>.py
└── frontend/
    ├── unit/<module>.test.ts
    ├── integration/<feature>.test.ts
    └── e2e/<scenario>.spec.ts

测试命名：
├── 类名：Test<ClassName>
├── 方法名：test_<scenario>_<expected_outcome>
└── 描述："""测试：<场景描述>"""
```

### 常用断言

```python
# Python pytest
assert actual == expected
assert actual in expected_list
assertRaises(ValueError, func, *args)
assertAsyncRaises(async_func, *args)
```

```typescript
// TypeScript vitest
expect(actual).toBe(expected)
expect(actual).toEqual(expected)
expect(actual).toContain(substring)
expect(element).toBeVisible()
await waitFor(() => expect(element).toBeInTheDocument())
```

---

**文档版本**: v1.0
**创建日期**: 2026-03-20
**状态**: 待审查
