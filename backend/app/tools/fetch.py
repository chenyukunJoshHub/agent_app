"""
HTTP fetch tool for Agent system.

Provides secure HTTP GET capability with timeout and error handling.
"""

import httpx
from langchain_core.tools import tool
from loguru import logger

# Default timeout in seconds
DEFAULT_TIMEOUT = 10.0


@tool
def fetch_url(url: str) -> str:
    """
    获取指定 URL 的网页内容。

    适用场景：
    - 获取公开网页的 HTML 内容
    - 获取 API 的 JSON 响应
    - 抓取新闻、博客、文档等文本内容
    - 获取静态资源（CSS、JS 等）

    不适用场景：
    - 需要登录认证的页面
    - 二进制文件（图片、视频、PDF 等）
    - 需要复杂交互的页面（JavaScript 渲染）
    - 违反网站服务条款的爬取

    Args:
        url: 完整的 URL 地址（必须以 http:// 或 https:// 开头）

    Returns:
        str: 网页内容的文本形式

    Raises:
        httpx.TimeoutException: 请求超时（10秒）
        httpx.ConnectError: 连接失败
        httpx.HTTPStatusError: HTTP 错误（但 404/500 等仍返回内容）
    """
    try:
        # Make HTTP GET request with timeout
        response = httpx.get(url, timeout=DEFAULT_TIMEOUT)

        # Log response info
        logger.info(
            f"Fetched URL: {url} - Status: {response.status_code} - Size: {len(response.text)} chars"
        )

        # Return response text (even for error status codes)
        # This allows the agent to see error messages
        return response.text

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching URL: {url}")
        raise
    except httpx.ConnectError:
        logger.error(f"Connection error fetching URL: {url}")
        raise
    except httpx.HTTPStatusError:
        logger.error(f"HTTP error fetching URL: {url}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching URL {url}: {e}")
        raise


# Tool list for LangGraph
__all__ = ["fetch_url"]
