"""
File reading tool for Agent system.

Provides secure file reading capability with size limits and validation.
"""
import mimetypes
from pathlib import Path

from langchain_core.tools import tool
from loguru import logger

# Default workspace root: two levels up from this file (backend/app/tools/ → project root)
_DEFAULT_WORKSPACE = Path(__file__).parents[3]

# Maximum file size for reading files (256KB)
MAX_FILE_BYTES = 256_000

# Blocked MIME types (binary files that should not be read as text)
BLOCKED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/svg+xml',
    'video/mp4',
    'video/webm',
    'video/quicktime',
    'audio/mpeg',
    'audio/wav',
    'application/pdf',
    'application/zip',
    'application/x-tar',
    'application/gzip',
}


def _get_workspace() -> Path:
    """Return the configured workspace root, falling back to _DEFAULT_WORKSPACE."""
    try:
        from app.config import settings
        if settings.workspace_dir:
            return Path(settings.workspace_dir).expanduser().resolve()
    except Exception:
        pass
    return _DEFAULT_WORKSPACE


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

    # Resolve relative paths against workspace root instead of CWD
    if not input_path.is_absolute() and "~" not in str(path):
        expanded = (_get_workspace() / input_path).resolve()
    else:
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

    # Check MIME type to prevent reading binary files
    mime_type, _ = mimetypes.guess_type(str(expanded))
    if mime_type and mime_type in BLOCKED_MIME_TYPES:
        raise ValueError(
            f"Cannot read binary file: {mime_type}. "
            f"The read_file tool only supports text files. "
            f"Images, videos, audio files, and PDFs are not supported."
        )

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
    logger.info(f"📄 [工具:read_file] 开始读取文件: {path}")
    # Validate path is within allowed directory (prevents path traversal)
    validated_path = _validate_path(path)
    logger.debug(f"🔒 [工具:read_file] 路径安全校验通过: {validated_path}")

    # Check file size
    try:
        file_size = validated_path.stat().st_size
    except Exception as e:
        logger.error(f"❌ [工具:read_file] 获取文件大小失败: {path} — {e}")
        raise

    if file_size > MAX_FILE_BYTES:
        logger.error(f"❌ [工具:read_file] 文件过大，拒绝读取: {file_size} > {MAX_FILE_BYTES} 字节")
        raise ValueError(
            f"File too large: {file_size} > {MAX_FILE_BYTES}"
        )

    # Read file content
    try:
        with validated_path.open(encoding="utf-8") as f:
            content = f.read()
        logger.info(
            f"✅ [工具:read_file] 文件读取成功: {validated_path}，大小={file_size} 字节"
        )
        return content
    except PermissionError:
        logger.error(f"❌ [工具:read_file] 权限不足，无法读取: {validated_path}")
        raise
    except Exception as e:
        logger.error(f"❌ [工具:read_file] 读取异常: {validated_path} — {e}")
        raise


# Tool list for LangGraph
__all__ = ["read_file"]
