"""
Unit tests for app.tools.fetch.

These tests verify the fetch_url tool functionality.
"""
from unittest.mock import Mock, patch

import pytest
import httpx


class TestFetchUrlTool:
    """Test fetch_url tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.fetch import fetch_url

        assert fetch_url.name == "fetch_url"
        assert fetch_url.description is not None
        assert "获取" in fetch_url.description or "网页" in fetch_url.description
        # Should include usage guidance
        assert "适用" in fetch_url.description or "不适用" in fetch_url.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.fetch import fetch_url

        schema = fetch_url.args_schema
        assert schema is not None
        # Should have 'url' argument
        assert "url" in schema.model_fields

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_success(self, mock_get: Mock) -> None:
        """Test fetch_url with a valid URL."""
        from app.tools.fetch import fetch_url

        # Mock successful response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "<html><body>Hello World</body></html>"
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com"})
        assert result == "<html><body>Hello World</body></html>"
        mock_get.assert_called_once()

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_timeout(self, mock_get: Mock) -> None:
        """Test fetch_url handles timeout errors."""
        from app.tools.fetch import fetch_url

        # Mock timeout error
        mock_get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(httpx.TimeoutException):
            fetch_url.invoke({"url": "https://example.com"})

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_404_error(self, mock_get: Mock) -> None:
        """Test fetch_url handles 404 errors."""
        from app.tools.fetch import fetch_url

        # Mock 404 response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com/notfound"})
        # Should still return content even with 404
        assert "Not Found" in result

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_500_error(self, mock_get: Mock) -> None:
        """Test fetch_url handles 500 errors."""
        from app.tools.fetch import fetch_url

        # Mock 500 response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com/error"})
        # Should still return content even with 500
        assert "Internal Server Error" in result

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_connection_error(self, mock_get: Mock) -> None:
        """Test fetch_url handles connection errors."""
        from app.tools.fetch import fetch_url

        # Mock connection error
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(httpx.ConnectError):
            fetch_url.invoke({"url": "https://invalid-url-that-does-not-exist-12345.com"})

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_with_timeout_param(self, mock_get: Mock) -> None:
        """Test fetch_url uses timeout parameter correctly."""
        from app.tools.fetch import fetch_url

        # Mock successful response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_get.return_value = mock_response

        fetch_url.invoke({"url": "https://example.com"})

        # Verify timeout was set (should be 10 seconds)
        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == 10.0

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_empty_response(self, mock_get: Mock) -> None:
        """Test fetch_url handles empty response."""
        from app.tools.fetch import fetch_url

        # Mock empty response
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = ""
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com"})
        assert result == ""

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_large_content(self, mock_get: Mock) -> None:
        """Test fetch_url handles large content."""
        from app.tools.fetch import fetch_url

        # Mock large response (1MB)
        large_content = "x" * (1024 * 1024)
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = large_content
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com/large"})
        assert len(result) == 1024 * 1024

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_utf8_content(self, mock_get: Mock) -> None:
        """Test fetch_url handles UTF-8 content."""
        from app.tools.fetch import fetch_url

        # Mock response with UTF-8 content
        utf8_content = """
        English: Hello World
        Chinese: 你好世界
        Japanese: こんにちは
        Emoji: 🎉🚀🔥
        Math: ∑(i=0,n) i²
        """
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = utf8_content
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com/utf8"})
        assert "你好世界" in result
        assert "🎉" in result

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_http_error(self, mock_get: Mock) -> None:
        """Test fetch_url handles generic HTTP errors."""
        from app.tools.fetch import fetch_url

        # Mock HTTP error
        mock_get.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=Mock(status_code=502)
        )

        with pytest.raises(httpx.HTTPStatusError):
            fetch_url.invoke({"url": "https://example.com"})


class TestFetchUrlToolEdgeCases:
    """Test fetch_url tool edge cases."""

    def test_fetch_url_description_clarity(self) -> None:
        """Test that tool description is clear and helpful."""
        from app.tools.fetch import fetch_url

        desc = fetch_url.description.lower()
        # Should mention what it's for
        assert any(keyword in desc for keyword in ["网页", "url", "http", "获取"])
        # Should mention limitations
        assert "不适用" in desc or "登录" in desc or "二进制" in desc

    def test_fetch_url_returns_string(self) -> None:
        """Test that fetch_url always returns a string."""
        from app.tools.fetch import fetch_url

        with patch("app.tools.fetch.httpx.get") as mock_get:
            mock_response = Mock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.text = "Test content"
            mock_get.return_value = mock_response

            result = fetch_url.invoke({"url": "https://example.com"})
            assert isinstance(result, str)

    def test_fetch_url_with_invalid_url_format(self) -> None:
        """Test fetch_url handles invalid URL format."""
        from app.tools.fetch import fetch_url

        # Invalid URL format (should raise exception from httpx)
        with pytest.raises(Exception):
            fetch_url.invoke({"url": "not-a-valid-url"})

    @patch("app.tools.fetch.httpx.get")
    def test_fetch_url_redirect_followed(self, mock_get: Mock) -> None:
        """Test fetch_url follows redirects by default."""
        from app.tools.fetch import fetch_url

        # Mock redirect response
        final_response = Mock(spec=httpx.Response)
        final_response.status_code = 200
        final_response.text = "Final content"
        mock_get.return_value = final_response

        result = fetch_url.invoke({"url": "https://example.com/redirect"})
        assert result == "Final content"


class TestFetchUrlSSRFProtection:
    """Test SSRF protection in fetch_url."""

    def test_blocks_private_ip_10_range(self) -> None:
        """Test that fetch_url blocks private IP (10.x.x.x)."""
        from app.tools.fetch import fetch_url
        from app.tools._url_safety import UnsafeURLError

        with pytest.raises(UnsafeURLError, match="private"):
            fetch_url.invoke({"url": "http://10.0.0.1"})

    def test_blocks_private_ip_192_168_range(self) -> None:
        """Test that fetch_url blocks private IP (192.168.x.x)."""
        from app.tools.fetch import fetch_url
        from app.tools._url_safety import UnsafeURLError

        with pytest.raises(UnsafeURLError, match="private"):
            fetch_url.invoke({"url": "http://192.168.1.1"})

    def test_blocks_localhost(self) -> None:
        """Test that fetch_url blocks localhost."""
        from app.tools.fetch import fetch_url
        from app.tools._url_safety import UnsafeURLError

        with pytest.raises(UnsafeURLError, match="private"):
            fetch_url.invoke({"url": "http://localhost:8000"})

    def test_blocks_link_local_metadata(self) -> None:
        """Test that fetch_url blocks link-local metadata endpoint."""
        from app.tools.fetch import fetch_url
        from app.tools._url_safety import UnsafeURLError

        with pytest.raises(UnsafeURLError, match="private"):
            fetch_url.invoke({"url": "http://169.254.169.254/latest/meta-data/"})

    def test_blocks_invalid_scheme(self) -> None:
        """Test that fetch_url blocks invalid schemes."""
        from app.tools.fetch import fetch_url
        from app.tools._url_safety import UnsafeURLError

        with pytest.raises(UnsafeURLError, match="scheme"):
            fetch_url.invoke({"url": "file:///etc/passwd"})

    @patch("app.tools.fetch.httpx.get")
    def test_allows_normal_https_url(self, mock_get: Mock) -> None:
        """Test that fetch_url allows normal HTTPS URLs."""
        from app.tools.fetch import fetch_url

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "https://example.com"})
        assert result == "OK"
        mock_get.assert_called_once()

    @patch("app.tools.fetch.httpx.get")
    def test_allows_normal_http_url(self, mock_get: Mock) -> None:
        """Test that fetch_url allows normal HTTP URLs."""
        from app.tools.fetch import fetch_url

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_get.return_value = mock_response

        result = fetch_url.invoke({"url": "http://example.com"})
        assert result == "OK"
        mock_get.assert_called_once()
