"""
Unit tests for app.tools.search.

These tests verify the web_search tool functionality.
"""
import os
from unittest.mock import MagicMock

import pytest


class TestWebSearchTool:
    """Test web_search tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.search import web_search

        assert web_search.name == "web_search"
        assert web_search.description is not None
        assert "搜索互联网" in web_search.description
        # Description is in Chinese, doesn't contain "Tavily"
        assert "适用场景" in web_search.description or "搜索" in web_search.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.search import web_search

        schema = web_search.args_schema
        assert schema is not None
        # Should have 'query' argument
        assert "query" in schema.model_fields

    @pytest.mark.requires_api_key
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set",
    )
    @pytest.mark.asyncio
    async def test_web_search_with_valid_query(self) -> None:
        """Test web_search with a valid query."""
        from app.tools.search import web_search

        result = await web_search.ainvoke({"query": "茅台股价"})
        assert result is not None
        assert isinstance(result, str)

        # Should be JSON
        import json

        data = json.loads(result)
        assert "query" in data
        assert "results" in data

    def test_web_search_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test web_search returns error when API key is missing."""
        monkeypatch.setenv("TAVILY_API_KEY", "")

        from app.tools.search import web_search

        result = web_search.invoke({"query": "test"})
        assert "错误" in result
        assert "TAVILY_API_KEY" in result

    def test_web_search_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test web_search with mocked Tavily client."""
        from unittest.mock import patch
        import sys

        # Setup mock
        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_response = {
                "query": "茅台股价",
                "answer": "茅台今天股价为1680元",
                "results": [
                    {
                        "title": "贵州茅台股票行情",
                        "url": "https://example.com",
                        "content": "茅台股价 1680.00 元",
                    }
                ],
            }
            mock_client.search.return_value = mock_response

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            # Execute
            result = web_search.invoke({"query": "茅台股价"})

            # Verify
            mock_client_class.assert_called_once_with(api_key="test_key")
            mock_client.search.assert_called_once()

            import json

            data = json.loads(result)
            assert data["query"] == "茅台股价"
            assert len(data["results"]) == 1

    def test_web_search_error_handling(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test web_search error handling."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.search.side_effect = Exception("API Error")

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            result = web_search.invoke({"query": "test"})
            assert "搜索失败" in result
            assert "API Error" in result

    def test_web_search_max_results(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that web_search limits results to 5."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            # Return 5 results as the API would with max_results=5
            mock_client.search.return_value = {
                "query": "test",
                "answer": "",
                "results": [
                    {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": ""}
                    for i in range(5)
                ],
            }

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            result = web_search.invoke({"query": "test"})

            import json

            data = json.loads(result)
            # Should have 5 results (API respects max_results=5)
            assert len(data["results"]) == 5
            # Verify that max_results=5 was passed to the API
            mock_client.search.assert_called_once()
            call_kwargs = mock_client.search.call_args[1]
            assert call_kwargs["max_results"] == 5

    def test_web_search_includes_answer(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that web_search includes Tavily's answer."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.search.return_value = {
                "query": "test",
                "answer": "This is the AI-generated answer",
                "results": [],
            }

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            result = web_search.invoke({"query": "test"})

            import json

            data = json.loads(result)
            assert data["answer"] == "This is the AI-generated answer"


class TestWebSearchEdgeCases:
    """Test web_search edge cases."""

    def test_empty_query(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test web_search with empty query."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            result = web_search.invoke({"query": ""})
            # Should still call search (Tavily handles empty queries)
            mock_client.search.assert_called_once()

    def test_special_characters_in_query(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test web_search with special characters."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.search.return_value = {"query": "", "answer": "", "results": []}

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            result = web_search.invoke({"query": "测试！@#$%^&*()"})
            mock_client.search.assert_called_once()

    def test_very_long_query(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test web_search with very long query."""
        from unittest.mock import patch
        import sys

        monkeypatch.setenv("TAVILY_API_KEY", "test_key")

        # Reload config to pick up new env var
        import importlib
        import app.config
        app.config._settings = None
        importlib.reload(app.config)

        # Remove app.tools.search from module cache to force fresh import
        if "app.tools.search" in sys.modules:
            del sys.modules["app.tools.search"]

        # Use patch as context manager
        with patch("tavily.TavilyClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.search.return_value = {"query": "", "answer": "", "results": []}

            # Import web_search AFTER patch is applied and config is reloaded
            from app.tools.search import web_search

            long_query = "test " * 1000
            result = web_search.invoke({"query": long_query})
            mock_client.search.assert_called_once()


# Import os
import os
