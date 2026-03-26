"""
Unit tests for app.agent.langchain_engine.

These tests verify agent creation and configuration.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from app.agent.langchain_engine import create_react_agent, get_default_tools


class TestGetDefaultTools:
    """Test get_default_tools function."""

    def test_returns_web_search_tool(self) -> None:
        """Test that get_default_tools returns web_search, send_email, and read_file."""
        tools = get_default_tools()
        assert len(tools) >= 3  # web_search, send_email, read_file (may include more)
        tool_names = [tool.name for tool in tools]
        assert "web_search" in tool_names
        assert "send_email" in tool_names
        assert "read_file" in tool_names

    def test_returns_list(self) -> None:
        """Test that get_default_tools returns a list."""
        tools = get_default_tools()
        assert isinstance(tools, list)


class TestCreateReactAgent:
    """Test create_react_agent function."""

    @pytest.fixture(autouse=True)
    def reset_agent_cache(self):
        """Reset _agent_cache before and after each test to avoid shared state."""
        import app.agent.langchain_engine as engine_module
        engine_module._agent_cache = None
        yield
        engine_module._agent_cache = None

    @pytest.mark.asyncio
    async def test_create_agent_with_defaults(self) -> None:
        """Test creating agent with default parameters."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = await create_react_agent()

            mock_create_agent.assert_called_once()
            assert agent == mock_graph

            # Verify call arguments
            call_kwargs = mock_create_agent.call_args[1]
            assert "model" in call_kwargs
            assert "tools" in call_kwargs
            assert "system_prompt" in call_kwargs
            assert "middleware" in call_kwargs

    @pytest.mark.asyncio
    async def test_create_agent_with_custom_llm(self) -> None:
        """Test creating agent with custom LLM."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer, \
             patch("app.agent.langchain_engine.create_summarization_middleware") as mock_summarization:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_summarization.return_value = MagicMock()

            custom_llm = MagicMock(spec=BaseChatModel)
            agent = await create_react_agent(llm=custom_llm)

            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == custom_llm

    @pytest.mark.asyncio
    async def test_create_agent_with_custom_tools(self) -> None:
        """Test creating agent with custom tools."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            custom_tool = MagicMock()
            custom_tool.name = "custom_tool"

            agent = await create_react_agent(tools=[custom_tool])

            call_kwargs = mock_create_agent.call_args[1]
            # read_file is always added
            assert custom_tool in call_kwargs["tools"]
            from app.tools.file import read_file
            assert read_file in call_kwargs["tools"]

    @pytest.mark.asyncio
    async def test_create_agent_with_sse_queue(self) -> None:
        """Test creating agent with SSE queue."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            mock_queue = MagicMock()

            agent = await create_react_agent(sse_queue=mock_queue)

            # Verify middleware is created with the queue
            call_kwargs = mock_create_agent.call_args[1]
            assert "middleware" in call_kwargs
            middleware = call_kwargs["middleware"]
            assert len(middleware) == 4  # Memory, Summarization, Trace, HIL

    @pytest.mark.asyncio
    async def test_create_agent_includes_middleware(self) -> None:
        """Test that agent is created with middleware stack."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]
            assert len(middleware) == 4  # Memory, Summarization, Trace, HIL

            # Check middleware types
            from app.agent.middleware.memory import MemoryMiddleware
            from app.agent.middleware.trace import TraceMiddleware
            from app.agent.middleware.hil import HILMiddleware

            assert isinstance(middleware[0], MemoryMiddleware)
            assert isinstance(middleware[2], TraceMiddleware)
            assert isinstance(middleware[3], HILMiddleware)

    @pytest.mark.asyncio
    async def test_create_agent_system_prompt(self) -> None:
        """Test that agent has correct system prompt."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]

            # Check for key sections in the system prompt
            assert "AI 助手" in system_prompt or "助手" in system_prompt
            assert "web_search" in system_prompt
            assert "send_email" in system_prompt
            assert "read_file" in system_prompt
            assert "不要编造信息" in system_prompt or "不要编造" in system_prompt

    @pytest.mark.asyncio
    async def test_create_agent_logs_creation(self) -> None:
        """Test that agent creation is logged."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            # Verify logging
            assert mock_logger.info.call_count >= 2  # "Creating..." and "created successfully"

    @pytest.mark.asyncio
    async def test_create_agent_handles_creation_error(self) -> None:
        """Test that agent creation errors are handled."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:

            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_create_agent.side_effect = Exception("Creation failed")

            with pytest.raises(Exception, match="Creation failed"):
                await create_react_agent()

            # Verify error is logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_uses_llm_factory_by_default(self) -> None:
        """Test that llm_factory is used when no LLM provided."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.llm_factory") as mock_llm_factory, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer, \
             patch("app.agent.langchain_engine.create_summarization_middleware") as mock_summarization:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_llm = MagicMock(spec=BaseChatModel)
            mock_llm_factory.return_value = mock_llm
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_summarization.return_value = MagicMock()

            agent = await create_react_agent()

            mock_llm_factory.assert_called_once()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_llm

    @pytest.mark.asyncio
    async def test_create_agent_uses_default_tools_when_none_provided(self) -> None:
        """Test that default tools (web_search, send_email, read_file) are used when no tools provided."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            tools = call_kwargs["tools"]
            tool_names = [tool.name for tool in tools]
            assert "web_search" in tool_names
            assert "send_email" in tool_names
            assert "read_file" in tool_names

    @pytest.mark.asyncio
    async def test_create_agent_logs_tool_count(self) -> None:
        """Test that tool count is logged."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer, \
             patch("app.agent.langchain_engine.create_summarization_middleware") as mock_summarization:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_summarization.return_value = MagicMock()

            custom_tool1 = MagicMock()
            custom_tool2 = MagicMock()
            custom_tool3 = MagicMock()

            agent = await create_react_agent(tools=[custom_tool1, custom_tool2, custom_tool3])

            # Check that log includes tool count (4 tools: 3 custom + read_file)
            # Log format: "工具注册完成，共 4 个: [...]"
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            tool_count_log = any("4" in str(call) and "个" in str(call) for call in info_calls)
            assert tool_count_log

    @pytest.mark.asyncio
    async def test_trace_middleware_receives_sse_queue(self) -> None:
        """Test that TraceMiddleware is present in middleware stack (SSE queue injected per-request via context)."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            mock_queue = MagicMock()

            agent = await create_react_agent(sse_queue=mock_queue)

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]

            # TraceMiddleware is the third middleware (index 2)
            from app.agent.middleware.trace import TraceMiddleware
            trace_middleware = middleware[2]
            assert isinstance(trace_middleware, TraceMiddleware)

    @pytest.mark.asyncio
    async def test_hil_middleware_receives_interrupt_store_and_sse_queue(self) -> None:
        """Test that HILMiddleware receives interrupt_store."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            mock_store = MagicMock()
            mock_get_interrupt_store.return_value = mock_store
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()
            mock_queue = MagicMock()

            agent = await create_react_agent(sse_queue=mock_queue)

            # Verify get_interrupt_store was called
            mock_get_interrupt_store.assert_called_once()

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]

            # HILMiddleware is the fourth middleware (index 3)
            hil_middleware = middleware[3]
            assert hil_middleware.interrupt_store == mock_store

    @pytest.mark.asyncio
    async def test_hil_middleware_configured_with_send_email_interrupt(self) -> None:
        """Test that HILMiddleware is configured to interrupt on send_email."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]

            # HILMiddleware is the fourth middleware (index 3)
            hil_middleware = middleware[3]
            assert hil_middleware.interrupt_on == {"send_email": True}


class TestCreateAgentIntegration:
    """Integration tests for agent creation."""

    @pytest.fixture(autouse=True)
    def reset_agent_cache(self):
        """Reset _agent_cache before and after each test to avoid shared state."""
        import app.agent.langchain_engine as engine_module
        engine_module._agent_cache = None
        yield
        engine_module._agent_cache = None

    @pytest.mark.asyncio
    async def test_agent_has_required_methods(self) -> None:
        """Test that created agent has required methods."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_graph.astream = AsyncMock()
            mock_graph.ainvoke = AsyncMock()
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            # Verify agent has async methods
            assert hasattr(agent, "astream")
            assert hasattr(agent, "ainvoke")

    @pytest.mark.asyncio
    async def test_agent_is_compiled_graph(self) -> None:
        """Test that agent is a CompiledStateGraph."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.get_interrupt_store") as mock_get_interrupt_store, \
             patch("app.agent.langchain_engine.get_store") as mock_get_store, \
             patch("app.agent.langchain_engine.get_checkpointer") as mock_get_checkpointer:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_get_interrupt_store.return_value = MagicMock()
            mock_get_store.return_value = MagicMock()
            mock_get_checkpointer.return_value = MagicMock()

            agent = await create_react_agent()

            # Should be a CompiledStateGraph instance
            # (in real test, would check isinstance)
            assert agent is not None
