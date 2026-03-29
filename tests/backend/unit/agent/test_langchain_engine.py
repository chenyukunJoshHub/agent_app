"""
Unit tests for app.agent.langchain_engine.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from app.agent.langchain_engine import create_react_agent, get_default_tools


class TestGetDefaultTools:
    def test_returns_expected_builtin_tools(self) -> None:
        tools = get_default_tools()
        tool_names = [tool.name for tool in tools]
        assert "web_search" in tool_names
        assert "send_email" in tool_names
        assert "read_file" in tool_names

    def test_returns_list(self) -> None:
        assert isinstance(get_default_tools(), list)


class TestCreateReactAgent:
    @pytest.fixture(autouse=True)
    def reset_agent_cache(self):
        import app.agent.langchain_engine as engine_module

        engine_module._agent_cache = None
        yield
        engine_module._agent_cache = None

    @pytest.fixture(autouse=True)
    def mock_prompt_and_skills(self):
        with (
            patch("app.agent.langchain_engine.SkillManager.get_instance") as mock_get_instance,
            patch("app.agent.langchain_engine.build_system_prompt") as mock_build_system_prompt,
        ):
            mock_skill_manager = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.skills = []
            mock_snapshot.version = 1
            mock_skill_manager.build_snapshot.return_value = mock_snapshot
            mock_get_instance.return_value = mock_skill_manager

            mock_slot_snapshot = MagicMock()
            mock_slot_snapshot.total_tokens = 42
            mock_slot_snapshot.to_dict.return_value = {"slots": []}
            mock_build_system_prompt.return_value = (
                "AI 助手 web_search send_email read_file 不要编造信息",
                mock_slot_snapshot,
            )
            yield

    @pytest.mark.asyncio
    async def test_create_agent_with_defaults(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            assert agent == mock_graph
            call_kwargs = mock_create_agent.call_args[1]
            assert "model" in call_kwargs
            assert "tools" in call_kwargs
            assert "system_prompt" in call_kwargs
            assert "middleware" in call_kwargs

    @pytest.mark.asyncio
    async def test_create_agent_with_custom_llm(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
            patch("app.agent.langchain_engine.create_summarization_middleware") as mock_summarization,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_summarization.return_value = MagicMock()

            custom_llm = MagicMock(spec=BaseChatModel)
            await create_react_agent(llm=custom_llm)

            assert mock_create_agent.call_args[1]["model"] == custom_llm

    @pytest.mark.asyncio
    async def test_create_agent_with_custom_tools_adds_read_file_and_restricts_custom_meta(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            custom_tool = MagicMock()
            custom_tool.name = "custom_tool"

            await create_react_agent(tools=[custom_tool])

            call_kwargs = mock_create_agent.call_args[1]
            tools = call_kwargs["tools"]
            tool_names = [tool.name for tool in tools]
            assert "custom_tool" in tool_names
            assert "read_file" in tool_names

            middleware = call_kwargs["middleware"]
            policy_middleware = middleware[3]
            custom_meta = policy_middleware.tool_manager.get_meta("custom_tool")
            read_file_meta = policy_middleware.tool_manager.get_meta("read_file")
            assert custom_meta is not None
            assert custom_meta.effect_class == "external_write"
            assert custom_meta.allowed_decisions == ["ask", "deny"]
            assert read_file_meta is not None
            assert read_file_meta.effect_class == "read"

    @pytest.mark.asyncio
    async def test_create_agent_includes_new_middleware_stack(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent()

            middleware = mock_create_agent.call_args[1]["middleware"]
            assert len(middleware) == 5

            from app.agent.middleware.memory import MemoryMiddleware
            from app.agent.middleware.tool_execution import ToolExecutionMiddleware
            from app.agent.middleware.tool_policy import PolicyHITLMiddleware
            from app.agent.middleware.trace import TraceMiddleware

            assert isinstance(middleware[0], MemoryMiddleware)
            assert isinstance(middleware[2], TraceMiddleware)
            assert isinstance(middleware[3], PolicyHITLMiddleware)
            assert isinstance(middleware[4], ToolExecutionMiddleware)

    @pytest.mark.asyncio
    async def test_create_agent_system_prompt_is_forwarded(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent()

            system_prompt = mock_create_agent.call_args[1]["system_prompt"]
            assert "AI 助手" in system_prompt
            assert "web_search" in system_prompt
            assert "send_email" in system_prompt
            assert "read_file" in system_prompt
            assert "不要编造信息" in system_prompt

    @pytest.mark.asyncio
    async def test_create_agent_logs_creation(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.logger") as mock_logger,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent()

            assert mock_logger.info.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_agent_handles_creation_error(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.logger") as mock_logger,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_create_agent.side_effect = Exception("Creation failed")
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            with pytest.raises(Exception, match="Creation failed"):
                await create_react_agent()

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_uses_llm_factory_by_default(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.llm_factory") as mock_llm_factory,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
            patch("app.agent.langchain_engine.create_summarization_middleware") as mock_summarization,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_llm = MagicMock(spec=BaseChatModel)
            mock_llm_factory.return_value = mock_llm
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_summarization.return_value = MagicMock()

            await create_react_agent()

            mock_llm_factory.assert_called_once()
            assert mock_create_agent.call_args[1]["model"] == mock_llm

    @pytest.mark.asyncio
    async def test_create_agent_uses_default_tools_when_none_provided(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent()

            tools = mock_create_agent.call_args[1]["tools"]
            tool_names = [tool.name for tool in tools]
            assert "web_search" in tool_names
            assert "send_email" in tool_names
            assert "read_file" in tool_names

    @pytest.mark.asyncio
    async def test_trace_middleware_present_when_sse_queue_is_provided(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent(sse_queue=MagicMock())

            middleware = mock_create_agent.call_args[1]["middleware"]
            from app.agent.middleware.trace import TraceMiddleware

            assert isinstance(middleware[2], TraceMiddleware)

    @pytest.mark.asyncio
    async def test_policy_and_execution_middleware_share_same_tool_manager(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            await create_react_agent()

            middleware = mock_create_agent.call_args[1]["middleware"]
            policy_middleware = middleware[3]
            execution_middleware = middleware[4]
            assert policy_middleware.tool_manager is execution_middleware.tool_manager

    @pytest.mark.asyncio
    async def test_agent_has_required_methods(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_graph.astream = AsyncMock()
            mock_graph.ainvoke = AsyncMock()
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            assert hasattr(agent, "astream")
            assert hasattr(agent, "ainvoke")

    @pytest.mark.asyncio
    async def test_agent_is_compiled_graph(self) -> None:
        with (
            patch("app.agent.langchain_engine.create_agent") as mock_create_agent,
            patch("app.agent.langchain_engine.get_store") as mock_get_store,
            patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer,
        ):
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            assert agent is not None
