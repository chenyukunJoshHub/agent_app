"""
Built-in tools for the agent
"""

import json
from pathlib import Path
from typing import Literal

import httpx
from tiktoken import Encoding, get_encoding

from app.core.config import settings
from app.core.logger import loguru_logger
from app.tools.registry import register_tool

# Initialize tiktoken encoding
_encoding: Encoding | None = None


def get_encoding() -> Encoding:
    """Get cached tiktoken encoding"""
    global _encoding
    if _encoding is None:
        _encoding = get_encoding("cl100k_base")
    return _encoding


@register_tool()
async def read_file(path: str, start_line: int = 0, end_line: int | None = None) -> str:
    """
    Read file contents with line range support.

    Args:
        path: Path to the file to read
        start_line: Starting line number (0-indexed)
        end_line: Ending line number (inclusive), None means read to end

    Returns:
        File contents as string
    """
    # Path safety validation
    file_path = Path(path).resolve()

    # Check if path is in allowed directories
    allowed = False
    for allowed_dir in settings.read_file_allowed_dirs:
        try:
            if file_path.is_relative_to(Path(allowed_dir).resolve()):
                allowed = True
                break
        except (ValueError, OSError):
            continue

    if not allowed and settings.read_file_allowed_dirs:
        raise PermissionError(f"Path not in allowed directories: {path}")

    # Read file
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if end_line is None:
            end_line = len(lines)

        result = "".join(lines[start_line : end_line + 1])
        loguru_logger.info(f"Read file: {path} (lines {start_line}-{end_line})")
        return result

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except Exception as e:
        raise RuntimeError(f"Failed to read file: {e}")


@register_tool()
async def fetch_url(url: str, method: Literal["GET", "POST"] = "GET") -> str:
    """
    Fetch content from a URL.

    Args:
        url: The URL to fetch
        method: HTTP method (GET or POST)

    Returns:
        Response content as string
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            if method == "GET":
                response = await client.get(url)
            else:
                response = await client.post(url)

            response.raise_for_status()
            loguru_logger.info(f"Fetched URL: {url} (status {response.status_code})")
            return response.text

        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error: {e}")


@register_tool()
async def token_counter(text: str) -> str:
    """
    Count tokens in text using tiktoken.

    Args:
        text: The text to count tokens for

    Returns:
        JSON string with token count
    """
    encoding = get_encoding()
    tokens = encoding.encode(text)
    count = len(tokens)

    loguru_logger.info(f"Counted tokens: {count}")
    return json.dumps({"token_count": count, "text_length": len(text)})


@register_tool()
async def tavily_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily API.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        JSON string with search results
    """
    # Placeholder - requires API key
    loguru_logger.info(f"Tavily search (placeholder): {query}")
    return json.dumps({"error": "Tavily API key not configured"})


@register_tool()
async def browser_use(url: str, action: Literal["visit", "screenshot"] = "visit") -> str:
    """
    Browser automation tool.

    Args:
        url: URL to visit
        action: Action to perform (visit or screenshot)

    Returns:
        Result description
    """
    loguru_logger.info(f"Browser use (placeholder): {action} on {url}")
    return f"Browser automation not yet implemented. Would {action} {url}"


@register_tool()
async def python_repl(code: str) -> str:
    """
    Execute Python code in a REPL environment.

    Args:
        code: Python code to execute

    Returns:
        Execution result
    """
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        exec(code, {"__name__": "__main__"})
        output = captured_output.getvalue()
        loguru_logger.info(f"Python REPL executed {len(code)} chars")
        return output or "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        sys.stdout = old_stdout
