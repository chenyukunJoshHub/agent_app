"""
File reading tool for Agent system.

Provides secure file reading capability with size limits and validation.
"""
from pathlib import Path

from langchain_core.tools import tool
from loguru import logger

# Maximum file size for reading files (256KB)
MAX_FILE_BYTES = 256_000


def _validate_path(path: str) -> Path:
    """
    Validate and sanitize the file path to prevent security issues.

    This prevents:
    - Path traversal attacks (../../../etc/passwd)
    - Access to sensitive system files
    - Access to private keys and credentials

    Args:
        path: User-provided file path

    Returns:
        Path: Validated, absolute path

    Raises:
        ValueError: If path contains blocked patterns
        FileNotFoundError: If path doesn't exist
    """
    input_path = Path(path)

    # Block path traversal attempts
    if ".." in str(path):
        logger.error(f"Path traversal attempt blocked: {path}")
        raise ValueError(
            "Access denied: path traversal (..) is not allowed"
        )

    # Expand user home directory if present
    expanded = input_path.expanduser().resolve()

    # Check for sensitive system paths using path components
    # This handles symlinks (e.g., macOS /etc -> /private/etc)
    parts = expanded.parts

    # Check for blocked top-level directories
    # On macOS, /etc resolves to /private/etc, so we need to check parts[1]
    # and also parts[2] if parts[1] is "private"
    blocked_roots = {"etc", "proc", "sys", "boot", "root"}
    if len(parts) >= 2:
        # Direct check for blocked roots
        if parts[1] in blocked_roots:
            logger.error(f"Access to sensitive path blocked: {path}")
            raise ValueError(
                f"Access denied: system directory (/{parts[1]}) is not allowed"
            )
        # Handle macOS symlinks where /etc -> /private/etc
        if parts[1] == "private" and len(parts) >= 3 and parts[2] in blocked_roots:
            logger.error(f"Access to sensitive path blocked: {path}")
            raise ValueError(
                f"Access denied: system directory (/{parts[2]}) is not allowed"
            )

    # Check for /var/log specifically
    # Handle macOS where /var -> /private/var
    if (len(parts) >= 3 and parts[1] == "var" and parts[2] == "log") or \
       (len(parts) >= 4 and parts[1] == "private" and parts[2] == "var" and parts[3] == "log"):
        logger.error(f"Access to sensitive path blocked: {path}")
        raise ValueError(
            "Access denied: /var/log directory is not allowed"
        )

    # Check for home directory sensitive paths BEFORE checking file existence
    home = Path.home()
    try:
        relative_to_home = expanded.relative_to(home)
        home_parts = relative_to_home.parts

        blocked_home_dirs = {".ssh", ".gnupg", ".aws"}
        if home_parts and home_parts[0] in blocked_home_dirs:
            logger.error(f"Access to sensitive path blocked: {path}")
            raise ValueError(
                f"Access denied: sensitive home directory (~/{home_parts[0]}) is not allowed"
            )
    except ValueError as e:
        # Distinguish between "path not under home" (expected) and our security check
        if "Access denied" in str(e):
            # This is our security ValueError, re-raise it
            raise
        # Path is not under home directory, which is fine
        pass

    # Verify the path actually exists and is a file
    if not expanded.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    return expanded


@tool
def read_file(path: str) -> str:
    """
    读取指定文件的完整内容。

    适用场景：
    - 读取配置文件、文档资源
    - 加载文本型数据文件
    - 读取源代码文件

    不适用场景：
    - 读取二进制文件（图片、视频、可执行文件）
    - 读取超大文件（超过 256KB）

    安全限制：
    - 路径遍历攻击会被阻止（如 ../../../etc/passwd）
    - 系统敏感路径会被阻止（/etc/, /proc/, ~/.ssh/ 等）

    Args:
        path: 文件路径（支持相对路径、绝对路径、~ 展开）

    Returns:
        str: 文件完整内容（UTF-8 编码）

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无读取权限
        ValueError: 文件大小超过限制（256KB）或路径包含被阻止的模式
    """
    # Validate path is within allowed directory (prevents path traversal)
    validated_path = _validate_path(path)

    # Check file size
    try:
        file_size = validated_path.stat().st_size
    except Exception as e:
        logger.error(f"Error getting file size for {path}: {e}")
        raise

    if file_size > MAX_FILE_BYTES:
        logger.error(f"File too large: {file_size} > {MAX_FILE_BYTES}")
        raise ValueError(
            f"File too large: {file_size} > {MAX_FILE_BYTES}"
        )

    # Read file content
    try:
        with validated_path.open(encoding="utf-8") as f:
            content = f.read()
        logger.info(
            f"Successfully read file: {validated_path} ({file_size} bytes)"
        )
        return content
    except PermissionError:
        logger.error(f"Permission denied reading file: {validated_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading file {validated_path}: {e}")
        raise


# Tool list for LangGraph
__all__ = ["read_file"]
