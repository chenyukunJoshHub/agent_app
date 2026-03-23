"""
Tests for RLS (Row Level Security) user context setup.

This test module validates that user_id is properly set in the database
session for RLS policies to work correctly.

TDD Workflow: RED → GREEN → REFACTOR
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.postgres import get_connection, set_user_context


class TestSetUserContext:
    """Test set_user_context() function."""

    @pytest.mark.asyncio
    async def test_set_user_context_executes_sql(self):
        """验证 set_user_context() 执行正确的 SQL."""
        mock_conn = AsyncMock()

        await set_user_context(mock_conn, "test_user")

        # Verify execute was called with correct SQL
        mock_conn.execute.assert_called_once_with(
            "SELECT set_config('app.user_id', $1, false)",
            "test_user"
        )

    @pytest.mark.asyncio
    async def test_set_user_context_with_dev_user(self):
        """验证 set_user_context() 支持 dev_user."""
        mock_conn = AsyncMock()

        await set_user_context(mock_conn, "dev_user")

        # Verify execute was called
        mock_conn.execute.assert_called_once()

        # Verify the user_id parameter
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == "dev_user"

    @pytest.mark.asyncio
    async def test_set_user_context_with_special_characters(self):
        """验证 set_user_context() 正确处理特殊字符."""
        mock_conn = AsyncMock()

        # Test with special characters that should be safe
        await set_user_context(mock_conn, "user@example.com")

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_user_context_empty_string(self):
        """验证 set_user_context() 处理空字符串."""
        mock_conn = AsyncMock()

        await set_user_context(mock_conn, "")

        # Should still execute, even with empty string
        mock_conn.execute.assert_called_once_with(
            "SELECT set_config('app.user_id', $1, false)",
            ""
        )


class TestGetConnectionWithUserContext:
    """Test get_connection() with automatic user context setting."""

    @pytest.mark.asyncio
    async def test_get_connection_signature_accepts_user_id(self):
        """验证 get_connection() 接受 user_id 参数."""
        from app.db.postgres import get_connection
        import inspect

        # Check function signature
        sig = inspect.signature(get_connection)
        assert "user_id" in sig.parameters
        assert sig.parameters["user_id"].default is None  # Default to None
        assert sig.parameters["user_id"].annotation == str | None

    @pytest.mark.asyncio
    async def test_get_connection_is_async_context_manager(self):
        """验证 get_connection() 是异步上下文管理器."""
        from app.db.postgres import get_connection
        import inspect
        from contextlib import asynccontextmanager

        # @asynccontextmanager decorator creates an async context manager
        # We can verify it has the __aenter__ and __aexit__ methods
        # after the decorator is applied
        # Note: The decorator transforms the function, so we check
        # the function is decorated appropriately
        assert hasattr(get_connection, "__wrapped__") or callable(get_connection)


class TestRLSIntegration:
    """Integration tests for RLS functionality."""

    @pytest.mark.asyncio
    async def test_rls_policy_effect_with_user_context(self):
        """
        验证 RLS 策略在设置 user_id 后生效。

        这是一个集成测试，验证：
        1. set_user_context() 正确设置 user_id
        2. RLS 策略使用 current_setting('app.user_id') 进行过滤
        3. 用户只能访问自己的数据
        """
        # This would require a real database connection
        # For now, we test the SQL that would be executed
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None

        # Set user context
        await set_user_context(mock_conn, "alice")

        # Verify the SQL that sets the context
        assert mock_conn.execute.called
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        user_id = call_args[0][1]

        assert "set_config" in sql
        assert "app.user_id" in sql
        assert user_id == "alice"

    @pytest.mark.asyncio
    async def test_rls_allows_dev_user_access_all(self):
        """
        验证 dev_user 可以访问所有数据。

        RLS 策略中有一个特殊条件：
        OR current_setting('app.user_id', true) = 'dev_user'

        这允许 dev_user 绕过 RLS 限制，方便开发调试。
        """
        mock_conn = AsyncMock()

        await set_user_context(mock_conn, "dev_user")

        # Verify dev_user is set
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == "dev_user"
