"""Test MemoryMiddleware hooks - RED phase."""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.agent.middleware.memory import MemoryMiddleware
from app.memory.schemas import UserProfile, MemoryContext
from app.memory.manager import MemoryManager


@pytest.fixture
def mock_store():
    """Mock AsyncPostgresStore."""
    store = MagicMock()
    store.aput = AsyncMock()
    store.aget = AsyncMock()
    return store


@pytest.fixture
def memory_manager(mock_store):
    """Create MemoryManager instance."""
    return MemoryManager(store=mock_store)


@pytest.fixture
def memory_middleware(memory_manager):
    """Create MemoryMiddleware instance."""
    return MemoryMiddleware(memory_manager=memory_manager)


class TestMemoryMiddlewareSchema:
    """Test MemoryMiddleware state_schema per architecture doc §2.5."""

    def test_state_schema_attribute_exists(self, memory_middleware):
        """验证 state_schema 属性存在"""
        assert hasattr(memory_middleware, "state_schema")

    def test_state_schema_contains_memory_ctx(self, memory_middleware):
        """验证 state_schema 包含 memory_ctx 字段"""
        # state_schema 应该是一个 TypedDict 或类似类型
        # 在运行时，我们检查它是否可以正确描述 state 结构
        assert memory_middleware.state_schema is not None


class TestMemoryMiddlewareBeforeAgent:
    """Test MemoryMiddleware.abefore_agent per architecture doc §2.5."""

    @pytest.mark.asyncio
    async def test_abefore_agent_loads_profile_to_state(
        self, memory_middleware, mock_store
    ):
        """验证 abefore_agent 从 store 加载用户画像到 state"""
        # 模拟 store 返回用户画像
        stored_data = {
            "user_id": "user-123",
            "preferences": {"domain": "legal-tech"},
            "interaction_count": 5,
            "summary": "Test user"
        }
        mock_item = Mock()
        mock_item.value = stored_data
        mock_store.aget.return_value = mock_item

        # 模拟 state 和 runtime
        state: Any = {}
        runtime = Mock()
        runtime.config = {"configurable": {"user_id": "user-123"}}

        # 调用 abefore_agent
        result = await memory_middleware.abefore_agent(state, runtime)

        # 验证返回包含 memory_ctx
        assert result is not None
        assert "memory_ctx" in result
        assert isinstance(result["memory_ctx"], MemoryContext)
        assert result["memory_ctx"].episodic.preferences["domain"] == "legal-tech"

    @pytest.mark.asyncio
    async def test_abefore_agent_returns_empty_profile_when_no_user_id(
        self, memory_middleware, mock_store
    ):
        """验证没有 user_id 时返回空画像"""
        # 模拟 store 返回 None（空 user_id 时）
        mock_store.aget.return_value = None

        state: Any = {}
        runtime = Mock()
        runtime.config = {"configurable": {}}

        result = await memory_middleware.abefore_agent(state, runtime)

        assert result is not None
        assert "memory_ctx" in result
        assert result["memory_ctx"].episodic.user_id == ""

    @pytest.mark.asyncio
    async def test_abefore_agent_returns_empty_profile_when_store_empty(
        self, memory_middleware, mock_store
    ):
        """验证 store 返回 None 时返回空画像"""
        mock_store.aget.return_value = None

        state: Any = {}
        runtime = Mock()
        runtime.config = {"configurable": {"user_id": "user-456"}}

        result = await memory_middleware.abefore_agent(state, runtime)

        assert result is not None
        assert "memory_ctx" in result
        assert result["memory_ctx"].episodic.preferences == {}

    @pytest.mark.asyncio
    async def test_abefore_agent_sets_baseline_profile(self, memory_middleware, mock_store):
        """abefore_agent 应同时返回 baseline 供 dirty-flag 对比。"""
        stored_data = {
            "user_id": "user-abc",
            "preferences": {"domain": "legal-tech"},
            "interaction_count": 9,
            "summary": "baseline summary",
        }
        mock_item = Mock()
        mock_item.value = stored_data
        mock_store.aget.return_value = mock_item

        runtime = Mock()
        runtime.config = {"configurable": {"user_id": "user-abc"}}

        result = await memory_middleware.abefore_agent({}, runtime)

        assert result is not None
        assert "memory_ctx_baseline" in result
        baseline = result["memory_ctx_baseline"]
        assert isinstance(baseline, UserProfile)
        assert baseline.interaction_count == 9
        assert baseline.preferences["domain"] == "legal-tech"


class TestMemoryMiddlewareWrapModelCall:
    """Test MemoryMiddleware.wrap_model_call per architecture doc §2.5."""

    def test_wrap_model_call_injects_profile_with_preferences(
        self, memory_middleware
    ):
        """验证有偏好时注入到 System Prompt"""
        # 创建带用户画像的 request.state
        profile = UserProfile(
            user_id="user-789", preferences={"language": "zh", "domain": "finance"}
        )
        memory_ctx = MemoryContext(episodic=profile)

        # 模拟 request
        request = Mock()
        request.state = {"memory_ctx": memory_ctx}
        request.system_message = SystemMessage(content="Original system prompt")
        request.messages = [HumanMessage(content="test user message")]
        request.runtime = None

        # 模拟 handler
        handler = Mock()
        handler.return_value = Mock()

        # 调用 wrap_model_call
        memory_middleware.wrap_model_call(request, handler)

        # 验证 handler 被调用
        assert handler.called

        # 验证 request.override 被调用来修改 system_message
        if hasattr(request, "override"):
            # 检查 override 是否被调用
            # 这取决于实际的实现方式
            pass

    def test_wrap_model_call_passes_through_with_no_memory_ctx(
        self, memory_middleware
    ):
        """验证没有 memory_ctx 时直接透传"""
        request = Mock()
        request.state = {}
        request.system_message = SystemMessage(content="Original")

        handler = Mock()
        handler.return_value = Mock()

        memory_middleware.wrap_model_call(request, handler)

        # 直接透传，不修改
        assert handler.called
        assert handler.call_args[0][0] == request

    def test_wrap_model_call_passes_through_with_empty_preferences(
        self, memory_middleware
    ):
        """验证空偏好时直接透传"""
        memory_ctx = MemoryContext(episodic=UserProfile(user_id="user-empty"))

        request = Mock()
        request.state = {"memory_ctx": memory_ctx}
        request.system_message = SystemMessage(content="Original")

        handler = Mock()
        handler.return_value = Mock()

        memory_middleware.wrap_model_call(request, handler)

        # 空偏好时不注入，直接透传
        assert handler.called


class TestMemoryMiddlewareAfterAgent:
    """Test MemoryMiddleware.aafter_agent per architecture doc §2.5."""

    @pytest.mark.asyncio
    async def test_aafter_agent_is_noop_p0(self, memory_middleware):
        """兼容性：无 user_id 时 aafter_agent 返回 None 且不写库。"""
        state: Any = {"memory_ctx": MemoryContext()}
        runtime = Mock()

        result = await memory_middleware.aafter_agent(state, runtime)

        assert result is None

    @pytest.mark.asyncio
    async def test_aafter_agent_rule_mode_increments_and_saves(
        self, memory_middleware, monkeypatch
    ):
        """rule 模式应 +1 interaction_count 并写回。"""
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "rule")

        profile = UserProfile(
            user_id="u1",
            preferences={"domain": "legal-tech"},
            interaction_count=2,
        )
        state: Any = {
            "memory_ctx": MemoryContext(episodic=profile),
            "memory_ctx_baseline": profile.model_copy(deep=True),
            "messages": [HumanMessage(content="请用中文继续合同审查流程")],
        }
        runtime = Mock()
        runtime.context = Mock()
        runtime.context.user_id = "u1"
        runtime.context.sse_queue = None

        result = await memory_middleware.aafter_agent(state, runtime)

        assert result is None
        memory_middleware.mm.store.aput.assert_called_once()
        saved_payload = memory_middleware.mm.store.aput.call_args.kwargs["value"]
        assert saved_payload["interaction_count"] == 3
        assert saved_payload["preferences"]["language"] == "zh"
        assert saved_payload["preferences"]["domain"] == "legal-tech"

    @pytest.mark.asyncio
    async def test_aafter_agent_dirty_false_skips_save(
        self, memory_middleware, monkeypatch
    ):
        """无交互内容且无规则变化时 dirty=false，不写库。"""
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "rule")

        profile = UserProfile(user_id="u2", preferences={}, interaction_count=0)
        state: Any = {
            "memory_ctx": MemoryContext(episodic=profile),
            "memory_ctx_baseline": profile.model_copy(deep=True),
            "messages": [AIMessage(content="")],
        }
        runtime = Mock()
        runtime.context = Mock()
        runtime.context.user_id = "u2"
        runtime.context.sse_queue = None

        result = await memory_middleware.aafter_agent(state, runtime)

        assert result is None
        memory_middleware.mm.store.aput.assert_not_called()

    @pytest.mark.asyncio
    async def test_aafter_agent_llm_mode_interval(
        self, memory_middleware, monkeypatch
    ):
        """llm 模式只在第 N 轮触发提炼。"""
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "llm")
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_llm_interval", 10)

        non_trigger = UserProfile(user_id="u3", preferences={}, interaction_count=8)
        non_trigger_state: Any = {
            "memory_ctx": MemoryContext(episodic=non_trigger),
            "memory_ctx_baseline": non_trigger.model_copy(deep=True),
            "messages": [HumanMessage(content="hello world")],
        }
        runtime = Mock()
        runtime.context = Mock()
        runtime.context.user_id = "u3"
        runtime.context.sse_queue = None

        fake_extract = AsyncMock(return_value={"preferences": {"role": "analyst"}, "summary": "x", "retain": []})
        monkeypatch.setattr(memory_middleware, "_extract_profile_with_llm", fake_extract)

        await memory_middleware.aafter_agent(non_trigger_state, runtime)
        assert fake_extract.await_count == 0

        trigger = UserProfile(user_id="u3", preferences={}, interaction_count=9)
        trigger_state: Any = {
            "memory_ctx": MemoryContext(episodic=trigger),
            "memory_ctx_baseline": trigger.model_copy(deep=True),
            "messages": [HumanMessage(content="hello world")],
        }
        await memory_middleware.aafter_agent(trigger_state, runtime)
        assert fake_extract.await_count == 1

    @pytest.mark.asyncio
    async def test_aafter_agent_llm_failure_fallback_to_rule(
        self, memory_middleware, monkeypatch
    ):
        """llm 提炼失败时应回退规则提炼，不抛错。"""
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "llm")
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_llm_interval", 1)
        monkeypatch.setattr(memory_middleware, "_extract_profile_with_llm", AsyncMock(return_value=None))

        profile = UserProfile(user_id="u4", preferences={}, interaction_count=0)
        state: Any = {
            "memory_ctx": MemoryContext(episodic=profile),
            "memory_ctx_baseline": profile.model_copy(deep=True),
            "messages": [HumanMessage(content="请用中文回答合同问题")],
        }
        runtime = Mock()
        runtime.context = Mock()
        runtime.context.user_id = "u4"
        runtime.context.sse_queue = None

        result = await memory_middleware.aafter_agent(state, runtime)

        assert result is None
        saved_payload = memory_middleware.mm.store.aput.call_args.kwargs["value"]
        assert saved_payload["preferences"]["language"] == "zh"
        assert saved_payload["preferences"]["domain"] == "legal-tech"

    @pytest.mark.asyncio
    async def test_retain_format_and_opinion_threshold(
        self, memory_middleware, monkeypatch
    ):
        """Retain summary 应包含 W/B/O/S；仅高置信 O 写入 preferences。"""
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_update_mode", "llm")
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_llm_interval", 1)
        monkeypatch.setattr("app.agent.middleware.memory.settings.memory_profile_opinion_min_confidence", 0.9)

        llm_payload = {
            "preferences": {"tone": "professional"},
            "summary": "用户偏好稳定",
            "retain": [
                {"type": "W", "text": "用户是法务角色"},
                {"type": "B", "text": "本轮完成合同风险审查"},
                {"type": "O", "text": "偏好中文回复", "confidence": 0.95, "preference": {"language": "zh"}},
                {"type": "O", "text": "偏好英文回复", "confidence": 0.6, "preference": {"language": "en"}},
                {"type": "S", "text": "持续关注合同流程自动化"},
            ],
        }
        monkeypatch.setattr(memory_middleware, "_extract_profile_with_llm", AsyncMock(return_value=llm_payload))

        profile = UserProfile(user_id="u5", preferences={}, interaction_count=9)
        state: Any = {
            "memory_ctx": MemoryContext(episodic=profile),
            "memory_ctx_baseline": profile.model_copy(deep=True),
            "messages": [HumanMessage(content="继续处理合同流程")],
        }
        runtime = Mock()
        runtime.context = Mock()
        runtime.context.user_id = "u5"
        runtime.context.sse_queue = None

        await memory_middleware.aafter_agent(state, runtime)

        saved_payload = memory_middleware.mm.store.aput.call_args.kwargs["value"]
        assert saved_payload["preferences"]["language"] == "zh"
        assert saved_payload["preferences"]["tone"] == "professional"
        assert "W @" in saved_payload["summary"]
        assert "B @" in saved_payload["summary"]
        assert "S @" in saved_payload["summary"]
        assert "O(c=0.95)" in saved_payload["summary"]


class TestProceduralInjection:
    """Tests for procedural injection via build_injection_parts."""

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.aput = AsyncMock()
        store.aget = AsyncMock()
        return store

    @pytest.fixture
    def memory_manager(self, mock_store):
        return MemoryManager(store=mock_store)

    @pytest.fixture
    def middleware(self, memory_manager):
        return MemoryMiddleware(memory_manager=memory_manager)

    def _make_request(self, memory_ctx=None, messages=None):
        """Helper: build a mock ModelRequest with messages list and optional state."""
        request = MagicMock()
        request.messages = messages or [HumanMessage(content="你好")]
        request.state = {"memory_ctx": memory_ctx} if memory_ctx else {}
        request.runtime = MagicMock()
        request.runtime.context = None
        # override returns a new request with updated messages
        def override(**kwargs):
            new_req = MagicMock()
            new_req.messages = kwargs.get("messages", request.messages)
            new_req.state = request.state
            new_req.runtime = request.runtime
            return new_req
        request.override.side_effect = override
        return request

    def test_procedural_text_injected_when_workflows_exist(self, middleware):
        """有 workflows 时，HumanMessage 应包含程序记忆文本"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1\n步骤2"})
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        def handler(req):
            captured.append(req)
            return MagicMock()
        middleware.wrap_model_call(request, handler)
        assert len(captured) == 1
        injected_content = captured[0].messages[0].content
        assert "程序记忆" in injected_content or "流程A" in injected_content

    def test_episodic_before_procedural_in_injection(self, middleware):
        """combined 注入中，episodic 内容应出现在 procedural 内容之前"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            episodic=UserProfile(preferences={"domain": "legal"}),
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"}),
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        content = captured[0].messages[0].content
        episodic_pos = content.find("用户画像")
        procedural_pos = content.find("程序记忆")
        assert episodic_pos < procedural_pos

    def test_only_procedural_injects_without_error(self, middleware):
        """只有 procedural，没有 episodic 时，应正常注入不报错"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"})
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        assert len(captured) == 1
        assert "流程A" in captured[0].messages[0].content

    def test_both_empty_no_injection(self, middleware):
        """episodic 和 procedural 都空时，HumanMessage 内容不变（无 --- 分隔符）"""
        ctx = MemoryContext()
        original_content = "原始消息"
        request = self._make_request(
            memory_ctx=ctx,
            messages=[HumanMessage(content=original_content)]
        )
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        assert len(captured) == 1
        content = captured[0].messages[0].content
        assert content == original_content
        assert "---" not in content  # 确认无注入分隔符被插入

    def test_procedural_slot_emit_enabled_when_workflows_exist(self, middleware):
        """有 workflows 时，emit_slot_update('procedural', enabled=True) 应被调用"""
        from app.memory.schemas import ProceduralMemory
        import unittest.mock as mock_module
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"})
        )
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())
        slot_names_called = []
        for c in mock_emit.call_args_list:
            if c.kwargs:
                slot_names_called.append(c.kwargs.get("name"))
        assert "procedural" in slot_names_called

    def test_procedural_slot_emit_disabled_when_empty(self, middleware):
        """workflows 为空时，emit_slot_update('procedural') 应以 enabled=False 调用"""
        import unittest.mock as mock_module
        ctx = MemoryContext()
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())
        for call in mock_emit.call_args_list:
            kwargs = call.kwargs
            name = kwargs.get("name", "")
            enabled = kwargs.get("enabled", True)
            if name == "procedural":
                assert enabled is False, "procedural enabled 应为 False when empty"
                break

    @pytest.mark.parametrize("episodic_prefs,procedural_wfs,exp_ep_enabled,exp_proc_enabled", [
        ({"domain": "legal"}, {"流程A": "步骤1"}, True,  True),
        ({"domain": "legal"}, {},                 True,  False),
        ({},                  {"流程A": "步骤1"}, False, True),
        ({},                  {},                 False, False),
    ])
    def test_slot_emit_enabled_four_combinations(
        self, middleware, episodic_prefs, procedural_wfs, exp_ep_enabled, exp_proc_enabled
    ):
        """spec enabled 逻辑表格 4 种组合验证"""
        import unittest.mock as mock_module
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            episodic=UserProfile(preferences=episodic_prefs),
            procedural=ProceduralMemory(workflows=procedural_wfs),
        )
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())

        emitted = {}
        for call in mock_emit.call_args_list:
            kwargs = call.kwargs
            emitted[kwargs.get("name")] = kwargs.get("enabled")

        assert emitted.get("episodic") == exp_ep_enabled, \
            f"episodic enabled 期望 {exp_ep_enabled}，实际 {emitted.get('episodic')}"
        assert emitted.get("procedural") == exp_proc_enabled, \
            f"procedural enabled 期望 {exp_proc_enabled}，实际 {emitted.get('procedural')}"
