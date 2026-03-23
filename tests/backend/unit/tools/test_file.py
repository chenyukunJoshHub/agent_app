"""
Unit tests for app.tools.file.

These tests verify the read_file tool functionality.
"""
import os
import tempfile

import pytest


class TestReadFileTool:
    """Test read_file tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.file import read_file

        assert read_file.name == "read_file"
        assert read_file.description is not None
        assert "读取" in read_file.description and "文件" in read_file.description
        # Should include usage guidance
        assert "适用" in read_file.description or "配置" in read_file.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.file import read_file

        schema = read_file.args_schema
        assert schema is not None
        # Should have 'path' argument
        assert "path" in schema.model_fields

    def test_read_file_success(self) -> None:
        """Test read_file with a valid file."""
        from app.tools.file import read_file

        test_content = "Hello, World!\nThis is a test file."

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = read_file.invoke({"path": temp_path})
            assert result == test_content
        finally:
            os.unlink(temp_path)

    def test_read_file_file_not_found(self) -> None:
        """Test read_file raises FileNotFoundError for non-existent file."""
        from app.tools.file import read_file

        with pytest.raises(FileNotFoundError) as exc_info:
            read_file.invoke({"path": "nonexistent_file.txt"})

        assert "File not found" in str(exc_info.value)

    def test_read_file_size_limit(self) -> None:
        """Test read_file raises ValueError for files larger than 256KB."""
        from app.tools.file import read_file, MAX_FILE_BYTES

        # Create a file larger than 256KB
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            # Write 300KB of data
            large_content = b"x" * (MAX_FILE_BYTES + 50_000)
            f.write(large_content)
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                read_file.invoke({"path": temp_path})

            assert "File too large" in str(exc_info.value)
            assert str(MAX_FILE_BYTES) in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_read_file_permission_denied(self) -> None:
        """Test read_file handles permission errors."""
        from app.tools.file import read_file

        # Create a file with no read permissions
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("secret content")
            temp_path = f.name

        try:
            # Remove read permissions
            os.chmod(temp_path, 0o000)

            # Should raise PermissionError
            with pytest.raises(PermissionError):
                read_file.invoke({"path": temp_path})
        finally:
            # Restore permissions to delete
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)

    def test_read_file_utf8_encoding(self) -> None:
        """Test read_file handles UTF-8 encoded content."""
        from app.tools.file import read_file

        # Test with various UTF-8 characters
        test_content = """
        English: Hello World
        Chinese: 你好世界
        Japanese: こんにちは
        Emoji: 🎉🚀🔥
        Math: ∑(i=0,n) i²
        """

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = read_file.invoke({"path": temp_path})
            assert result == test_content
            # Verify specific characters are preserved
            assert "你好世界" in result
            assert "🎉" in result
            assert "∑" in result
        finally:
            os.unlink(temp_path)

    def test_read_file_empty_file(self) -> None:
        """Test read_file handles empty files."""
        from app.tools.file import read_file

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            result = read_file.invoke({"path": temp_path})
            assert result == ""
        finally:
            os.unlink(temp_path)

    def test_read_file_multiline_content(self) -> None:
        """Test read_file preserves line breaks and formatting."""
        from app.tools.file import read_file

        test_content = """Line 1
Line 2
Line 3

Line 5 (with blank line above)
"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = read_file.invoke({"path": temp_path})
            assert result == test_content
            assert result.count("\n") == test_content.count("\n")
        finally:
            os.unlink(temp_path)

    def test_read_file_size_limit_boundary(self) -> None:
        """Test read_file accepts files exactly at the limit."""
        from app.tools.file import read_file, MAX_FILE_BYTES

        # Create a file exactly at the limit
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            content = b"x" * MAX_FILE_BYTES
            f.write(content)
            temp_path = f.name

        try:
            # Should succeed
            result = read_file.invoke({"path": temp_path})
            assert len(result) == MAX_FILE_BYTES
        finally:
            os.unlink(temp_path)

    def test_read_file_size_limit_one_byte_over(self) -> None:
        """Test read_file rejects files one byte over the limit."""
        from app.tools.file import read_file, MAX_FILE_BYTES

        # Create a file one byte over the limit
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            content = b"x" * (MAX_FILE_BYTES + 1)
            f.write(content)
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                read_file.invoke({"path": temp_path})

            assert "File too large" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_read_file_absolute_path(self) -> None:
        """Test read_file works with absolute paths."""
        from app.tools.file import read_file

        test_content = "Absolute path test"
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(test_content)
            temp_path = os.path.abspath(f.name)

        try:
            result = read_file.invoke({"path": temp_path})
            assert result == test_content
        finally:
            os.unlink(temp_path)

    def test_read_file_relative_path(self) -> None:
        """Test read_file works with relative paths."""
        from app.tools.file import read_file

        # Create a temp file in current directory
        test_content = "Relative path test"
        test_filename = "test_read_file_relative.tmp"
        original_cwd = os.getcwd()

        try:
            # Create file in current directory
            with open(test_filename, "w", encoding="utf-8") as f:
                f.write(test_content)

            result = read_file.invoke({"path": test_filename})
            assert result == test_content
        finally:
            if os.path.exists(test_filename):
                os.unlink(test_filename)
            os.chdir(original_cwd)


class TestReadFileToolEdgeCases:
    """Test read_file tool edge cases."""

    def test_read_file_description_clarity(self) -> None:
        """Test that tool description is clear and helpful."""
        from app.tools.file import read_file

        desc = read_file.description.lower()
        # Should mention what it's for
        assert any(keyword in desc for keyword in ["配置", "文档", "读取"])
        # Should mention limitations
        assert "不适用" in desc or "binary" in desc or "二进制" in desc

    def test_read_file_returns_string(self) -> None:
        """Test that read_file always returns a string."""
        from app.tools.file import read_file

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("Test")
            temp_path = f.name

        try:
            result = read_file.invoke({"path": temp_path})
            assert isinstance(result, str)
        finally:
            os.unlink(temp_path)

    def test_read_file_with_special_filename(self) -> None:
        """Test read_file handles filenames with special characters."""
        from app.tools.file import read_file

        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Filename with spaces and special chars
            test_filename = "test file (1).txt"
            test_path = os.path.join(tmpdir, test_filename)
            test_content = "Special filename test"

            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_content)

            result = read_file.invoke({"path": test_path})
            assert result == test_content

    def test_max_file_bytes_constant(self) -> None:
        """Test that MAX_FILE_BYTES is defined correctly."""
        from app.tools.file import MAX_FILE_BYTES

        # Should be 256KB
        assert MAX_FILE_BYTES == 256_000


class TestReadFileSecurity:
    """Test read_file security features and path traversal protection."""

    def test_read_file_blocks_path_traversal_with_double_dots(self) -> None:
        """Test that path traversal using ../ is blocked."""
        from app.tools.file import read_file

        # Attempt to escape using ../
        with pytest.raises(ValueError) as exc_info:
            read_file.invoke({"path": "../../../etc/passwd"})

        assert "Access denied" in str(exc_info.value) or "path traversal" in str(exc_info.value).lower()

    def test_read_file_blocks_path_traversal_single_dot(self) -> None:
        """Test that path traversal using ./../ is blocked."""
        from app.tools.file import read_file

        # Various path traversal attempts
        malicious_paths = [
            "./../etc/passwd",
            "../test/../../etc/passwd",
            "....//....//etc/passwd",
        ]

        for path in malicious_paths:
            with pytest.raises(ValueError):
                read_file.invoke({"path": path})

    def test_read_file_blocks_sensitive_system_paths(self) -> None:
        """Test that sensitive system paths are blocked."""
        from app.tools.file import read_file

        # System paths that should be blocked
        sensitive_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/proc/self/environ",
            "/sys/kernel/debug",
            "/boot/config",
            "/var/log/auth.log",
        ]

        for path in sensitive_paths:
            with pytest.raises(ValueError) as exc_info:
                read_file.invoke({"path": path})
            assert "Access denied" in str(exc_info.value)

    def test_read_file_blocks_ssh_key_access(self) -> None:
        """Test that accessing SSH keys is blocked."""
        from app.tools.file import read_file

        # Attempt to read SSH private key
        with pytest.raises(ValueError) as exc_info:
            read_file.invoke({"path": "~/.ssh/id_rsa"})

        assert "Access denied" in str(exc_info.value)

    def test_read_file_blocks_gnupg_access(self) -> None:
        """Test that accessing GPG keys is blocked."""
        from app.tools.file import read_file

        # Attempt to read GPG private key
        with pytest.raises(ValueError) as exc_info:
            read_file.invoke({"path": "~/.gnupg/private-keys-v1.d/key"})

        assert "Access denied" in str(exc_info.value)

    def test_read_file_blocks_aws_credentials(self) -> None:
        """Test that accessing AWS credentials is blocked."""
        from app.tools.file import read_file

        # Attempt to read AWS credentials
        with pytest.raises(ValueError) as exc_info:
            read_file.invoke({"path": "~/.aws/credentials"})

        assert "Access denied" in str(exc_info.value)

    def test_read_file_allows_normal_files(self) -> None:
        """Test that normal files are allowed."""
        from app.tools.file import read_file

        # Create a normal temp file
        test_content = "Normal file content"

        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(test_content)
            temp_path = f.name

        try:
            # Should succeed with absolute path
            result = read_file.invoke({"path": temp_path})
            assert result == test_content
        finally:
            os.unlink(temp_path)

    def test_read_file_allows_project_files(self) -> None:
        """Test that project files are allowed."""
        from app.tools.file import read_file

        # Create a test file in current directory (simulating project file)
        test_content = "Project file content"
        test_filename = "test_project_file.py"

        try:
            with open(test_filename, "w", encoding="utf-8") as f:
                f.write(test_content)

            # Should allow access to project files
            result = read_file.invoke({"path": test_filename})
            assert result == test_content
        finally:
            if os.path.exists(test_filename):
                os.unlink(test_filename)

    def test_validate_path_blocks_malicious_paths(self) -> None:
        """Test that _validate_path blocks malicious path patterns."""
        from app.tools.file import _validate_path

        # Each path should be blocked for different reasons:
        # - ../../../etc/passwd: path traversal (..)
        # - /etc/passwd: blocked system directory
        # - /proc/self/environ: blocked system directory
        # - ~/.ssh/id_rsa: blocked home directory (raises ValueError)
        # - ~/.aws/credentials: blocked home directory (raises ValueError)
        # - /boot/config.txt: blocked system directory
        malicious_paths_with_expected_error = [
            ("../../../etc/passwd", ValueError),  # path traversal
            ("/etc/passwd", ValueError),  # blocked system dir
            ("/proc/self/environ", ValueError),  # blocked system dir
            ("~/.ssh/id_rsa", ValueError),  # blocked home dir
            ("~/.aws/credentials", ValueError),  # blocked home dir
            ("/boot/config.txt", ValueError),  # blocked system dir
        ]

        for path, expected_error in malicious_paths_with_expected_error:
            with pytest.raises(expected_error):
                _validate_path(path)
