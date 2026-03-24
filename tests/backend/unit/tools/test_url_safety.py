"""Unit tests for app.tools._url_safety — SSRF protection."""

import pytest

from app.tools._url_safety import is_safe_url, UnsafeURLError


class TestIsSafeUrl:
    def test_allows_normal_https_url(self) -> None:
        assert is_safe_url("https://example.com") is True

    def test_allows_normal_http_url(self) -> None:
        assert is_safe_url("http://example.com") is True

    def test_allows_https_with_path(self) -> None:
        assert is_safe_url("https://example.com/path/to/page") is True

    def test_allows_https_with_query(self) -> None:
        assert is_safe_url("https://example.com/search?q=test") is True

    def test_rejects_ftp_scheme(self) -> None:
        with pytest.raises(UnsafeURLError, match="scheme"):
            is_safe_url("ftp://example.com")

    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(UnsafeURLError, match="scheme"):
            is_safe_url("file:///etc/passwd")

    def test_rejects_gopher_scheme(self) -> None:
        with pytest.raises(UnsafeURLError, match="scheme"):
            is_safe_url("gopher://example.com")

    def test_rejects_no_scheme(self) -> None:
        with pytest.raises(UnsafeURLError, match="scheme"):
            is_safe_url("example.com")

    def test_rejects_empty_url(self) -> None:
        with pytest.raises(UnsafeURLError):
            is_safe_url("")

    def test_rejects_private_ip_10_range(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://10.0.0.1")

    def test_rejects_private_ip_172_16_range(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://172.16.0.1")

    def test_rejects_private_ip_192_168_range(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://192.168.1.1")

    def test_rejects_loopback_127(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://127.0.0.1:8000")

    def test_rejects_loopback_ipv6(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://[::1]:8000")

    def test_rejects_link_local_metadata(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_localhost(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://localhost:8000")

    def test_rejects_0_0_0_0(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://0.0.0.0:8000")

    def test_rejects_ipv6_mapped_ipv4(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://[::ffff:10.0.0.1]:8000")


class TestIsSafeUrlEdgeCases:
    def test_rejects_broadcast_address(self) -> None:
        with pytest.raises(UnsafeURLError, match="private"):
            is_safe_url("http://255.255.255.255")
