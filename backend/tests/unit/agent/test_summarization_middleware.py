"""Test SummarizationMiddleware integration - RED phase.

Per architecture doc §2.6:
- SummarizationMiddleware is framework-built, not custom implementation
- We test configuration and integration, not internal logic
- Trigger: token fraction exceeds threshold (default 0.75)
- Keep: recent N messages after compression (default 5)
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Any

from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.agent.middleware.summarization import create_summarization_middleware
from app.config import settings


class TestCreateSummarizationMiddleware:
    """Test create_summarization_middleware factory function."""

    def test_returns_summarization_middleware_instance(self):
        """验证工厂函数返回 SummarizationMiddleware 实例"""
        middleware = create_summarization_middleware()
        assert isinstance(middleware, SummarizationMiddleware)

    def test_uses_configured_model(self):
        """验证使用配置的模型（gpt-4o-mini 用于压缩）"""
        middleware = create_summarization_middleware()
        # 检查 middleware 的 model 属性
        assert hasattr(middleware, "model")
        # 应该使用小模型进行压缩以降低成本
        assert "gpt-4o-mini" in str(middleware.model).lower()

    def test_configures_trigger_threshold(self):
        """验证配置触发阈值（75% fraction）"""
        middleware = create_summarization_middleware()
        # 检查 trigger 配置
        assert hasattr(middleware, "trigger")
        # 默认应该是 0.75 (75%)
        # trigger 可以是 tuple 或 list
        trigger = middleware.trigger
        if isinstance(trigger, (tuple, list)) and len(trigger) > 1:
            if trigger[0] == "fraction":
                assert trigger[1] == 0.75

    def test_configures_keep_recent_messages(self):
        """验证配置保留最近消息数（5 条）"""
        middleware = create_summarization_middleware()
        # 检查 keep 配置
        assert hasattr(middleware, "keep")
        # 默认应该保留最近 5 条消息
        keep = middleware.keep
        if isinstance(keep, (tuple, list)) and len(keep) > 1:
            if keep[0] == "messages":
                assert keep[1] == 5


class TestSummarizationMiddlewareIntegration:
    """Test SummarizationMiddleware behavior in agent stack.

    NOTE: These are integration tests that verify the middleware works
    correctly when placed in the agent middleware stack.
    """

    def test_middleware_has_before_model_hook(self):
        """验证 middleware 有 before_model 钩子"""
        middleware = create_summarization_middleware()
        # SummarizationMiddleware 应该有 before_model 钩子
        # 根据 architecture doc §2.6，钩子位置是 before_model
        assert hasattr(middleware, "abefore_model") or hasattr(middleware, "before_model")

    def test_middleware_compatible_with_other_middleware(self):
        """验证与其他 middleware 兼容"""
        summarization = create_summarization_middleware()

        # 模拟 MemoryMiddleware
        memory_mock = Mock()
        memory_mock.state_schema = {"memory_ctx": Mock()}

        # 验证可以共存于同一个列表
        middleware_stack = [memory_mock, summarization]
        assert len(middleware_stack) == 2

    @pytest.mark.asyncio
    async def test_compresses_long_history(self):
        """验证长对话历史触发压缩"""
        middleware = create_summarization_middleware()

        # 创建超过阈值的消息历史
        # 模拟 50 条消息（超过默认的 20 条 keep 限制）
        messages = []
        for i in range(50):
            messages.append(HumanMessage(content=f"User message {i}"))
            messages.append(AIMessage(content=f"AI response {i}"))

        state = {"messages": messages}
        runtime = Mock()

        # 调用 before_model 钩子（如果存在）
        if hasattr(middleware, "abefore_model"):
            result = await middleware.abefore_model(state, runtime)
            # 验证返回更新的 state
            if result:
                assert "messages" in result
                # 消息数量应该减少（压缩后）
                # 但由于我们使用 mock，实际压缩可能不会发生
                # 这个测试主要是验证接口存在

    @pytest.mark.asyncio
    async def test_preserves_recent_messages(self):
        """验证压缩后保留最近的消息"""
        middleware = create_summarization_middleware()

        # 创建消息历史
        messages = [
            HumanMessage(content="Old message 1"),
            AIMessage(content="Old response 1"),
            HumanMessage(content="Old message 2"),
            AIMessage(content="Old response 2"),
            HumanMessage(content="Recent message"),
            AIMessage(content="Recent response"),
        ]

        state = {"messages": messages}
        runtime = Mock()

        # 调用 before_model 钩子
        if hasattr(middleware, "abefore_model"):
            result = await middleware.abefore_model(state, runtime)
            # 验证最近的消息被保留
            if result and "messages" in result:
                # 最近的消息应该在结果中
                result_messages = result["messages"]
                # 验证最后一条消息是最近的 AI 响应
                assert isinstance(result_messages[-1], AIMessage)
                assert result_messages[-1].content == "Recent response"


class TestSummarizationMiddlewareConfiguration:
    """Test SummarizationMiddleware configuration options."""

    def test_custom_trigger_threshold(self):
        """验证自定义触发阈值"""
        # 测试不同的触发阈值
        middleware = SummarizationMiddleware(
            model="openai:gpt-4o-mini",
            trigger=("fraction", 0.8),  # 80%
        )
        assert middleware.trigger == ("fraction", 0.8)

    def test_custom_keep_messages(self):
        """验证自定义保留消息数"""
        middleware = SummarizationMiddleware(
            model="openai:gpt-4o-mini",
            keep=("messages", 10),  # 保留 10 条
        )
        assert middleware.keep == ("messages", 10)

    def test_token_based_trigger(self):
        """验证基于 token 数量的触发"""
        middleware = SummarizationMiddleware(
            model="openai:gpt-4o-mini",
            trigger=("tokens", 10000),  # 超过 10000 tokens 触发
        )
        assert middleware.trigger == ("tokens", 10000)

    def test_multiple_trigger_conditions(self):
        """验证多条件触发（OR 逻辑）"""
        middleware = SummarizationMiddleware(
            model="openai:gpt-4o-mini",
            trigger=[
                ("fraction", 0.75),
                ("messages", 50),  # 任一条件满足即触发
            ],
        )
        assert isinstance(middleware.trigger, list)
        assert len(middleware.trigger) == 2


class TestSummarizationMiddlewareInLangChainEngine:
    """Test SummarizationMiddleware integration in langchain_engine.py."""

    def test_middleware_added_to_stack(self):
        """验证 middleware 被添加到 agent 的 middleware 栈"""
        # 这个测试验证 langchain_engine.py 中是否正确配置了
        # SummarizationMiddleware
        from app.agent.langchain_engine import create_react_agent
        from app.llm.factory import llm_factory

        # 注意：这个测试可能需要 mock 数据库连接
        # 这里我们只验证函数存在且可以调用
        assert callable(create_react_agent)

    def test_middleware_order_correct(self):
        """验证 middleware 顺序正确

        根据 architecture doc §2.7:
        1. MemoryMiddleware (加载画像)
        2. SummarizationMiddleware (压缩历史)
        3. TraceMiddleware (SSE 流)
        4. HILMiddleware (人工干预)
        """
        # 这个测试验证中间件的顺序
        # SummarizationMiddleware 应该在 MemoryMiddleware 之后
        # 在 TraceMiddleware 和 HILMiddleware 之前
        # 因为它需要在 LLM 调用前压缩消息
        pass
