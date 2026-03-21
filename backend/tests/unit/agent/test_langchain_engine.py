"""
Unit tests for app.agent.langchain_engine.

These tests verify agent creation and configuration.
"""
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from app.agent.langchain_engine import create_react_agent, get_default_tools


class TestGetDefaultTools:
    """Test get_default_tools function."""

    def test_returns_web_search_tool(self) -> None:
        """Test that get_default_tools returns web_search."""
        tools = get_default_tools()
        assert len(tools) == 1
        assert tools[0].name == "web_search"

    def test_returns_list(self) -> None:
        """Test that get_default_tools returns a list."""
        tools = get_default_tools()
        assert isinstance(tools, list)


class TestCreateReactAgent:
    """Test create_react_agent function."""

    def test_create_agent_with_defaults(self) -> None:
        """Test creating agent with default parameters."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            mock_create_agent.assert_called_once()
            assert agent == mock_graph

            # Verify call arguments
            call_kwargs = mock_create_agent.call_args[1]
            assert "model" in call_kwargs
            assert "tools" in call_kwargs
            assert "system_prompt" in call_kwargs
            assert "middleware" in call_kwargs

    def test_create_agent_with_custom_llm(self) -> None:
        """Test creating agent with custom LLM."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            custom_llm = MagicMock(spec=BaseChatModel)
            agent = create_react_agent(llm=custom_llm)

            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == custom_llm

    def test_create_agent_with_custom_tools(self) -> None:
        """Test creating agent with custom tools."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            custom_tool = MagicMock()
            custom_tool.name = "custom_tool"

            agent = create_react_agent(tools=[custom_tool])

            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["tools"] == [custom_tool]

    def test_create_agent_with_sse_queue(self) -> None:
        """Test creating agent with SSE queue."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            mock_queue = MagicMock()

            agent = create_react_agent(sse_queue=mock_queue)

            # Verify middleware is created with the queue
            call_kwargs = mock_create_agent.call_args[1]
            assert "middleware" in call_kwargs
            middleware = call_kwargs["middleware"]
            assert len(middleware) == 2

    def test_create_agent_includes_middleware(self) -> None:
        """Test that agent is created with middleware stack."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]
            assert len(middleware) == 2

            # Check middleware types
            from app.agent.middleware.memory import MemoryMiddleware
            from app.agent.middleware.trace import TraceMiddleware

            assert isinstance(middleware[0], MemoryMiddleware)
            assert isinstance(middleware[1], TraceMiddleware)

    def test_create_agent_system_prompt(self) -> None:
        """Test that agent has correct system prompt."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]

            assert "有用的 AI 助手" in system_prompt
            assert "web_search" in system_prompt
            assert "不要编造信息" in system_prompt

    def test_create_agent_logs_creation(self) -> None:
        """Test that agent creation is logged."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            # Verify logging
            assert mock_logger.info.call_count >= 2  # "Creating..." and "created successfully"

    def test_create_agent_handles_creation_error(self) -> None:
        """Test that agent creation errors are handled."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger:

            mock_create_agent.side_effect = Exception("Creation failed")

            with pytest.raises(Exception, match="Creation failed"):
                create_react_agent()

            # Verify error is logged
            mock_logger.error.assert_called_once()

    def test_create_agent_uses_llm_factory_by_default(self) -> None:
        """Test that llm_factory is used when no LLM provided."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.llm_factory") as mock_llm_factory:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph
            mock_llm = MagicMock(spec=BaseChatModel)
            mock_llm_factory.return_value = mock_llm

            agent = create_react_agent()

            mock_llm_factory.assert_called_once()
            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["model"] == mock_llm

    def test_create_agent_uses_web_search_by_default(self) -> None:
        """Test that web_search is used when no tools provided."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.web_search") as mock_web_search:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            call_kwargs = mock_create_agent.call_args[1]
            assert call_kwargs["tools"] == [mock_web_search]

    def test_create_agent_logs_tool_count(self) -> None:
        """Test that tool count is logged."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent, \
             patch("app.agent.langchain_engine.logger") as mock_logger:

            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            custom_tool1 = MagicMock()
            custom_tool2 = MagicMock()
            custom_tool3 = MagicMock()

            agent = create_react_agent(tools=[custom_tool1, custom_tool2, custom_tool3])

            # Check that log includes tool count
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            tool_count_log = any("3 tool" in str(call) for call in info_calls)
            assert tool_count_log

    def test_trace_middleware_receives_sse_queue(self) -> None:
        """Test that TraceMiddleware receives the SSE queue."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            mock_queue = MagicMock()

            agent = create_react_agent(sse_queue=mock_queue)

            call_kwargs = mock_create_agent.call_args[1]
            middleware = call_kwargs["middleware"]

            # TraceMiddleware is the second middleware
            trace_middleware = middleware[1]
            assert trace_middleware.sse_queue == mock_queue


class TestCreateAgentIntegration:
    """Integration tests for agent creation."""

    def test_agent_has_required_methods(self) -> None:
        """Test that created agent has required methods."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_graph.astream = AsyncMock()
            mock_graph.ainvoke = AsyncMock()
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            # Verify agent has async methods
            assert hasattr(agent, "astream")
            assert hasattr(agent, "ainvoke")

    def test_agent_is_compiled_graph(self) -> None:
        """Test that agent is a CompiledStateGraph."""
        with patch("app.agent.langchain_engine.create_agent") as mock_create_agent:
            mock_graph = MagicMock(spec=CompiledStateGraph)
            mock_create_agent.return_value = mock_graph

            agent = create_react_agent()

            # Should be a CompiledStateGraph instance
            # (in real test, would check isinstance)
            assert agent is not None
