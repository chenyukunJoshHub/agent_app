"""
HTTP fetch tool for Agent system.

Provides secure HTTP GET capability with timeout, error handling, and SSRF protection.
"""

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.tools._url_safety import is_safe_url, UnsafeURLError

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
        UnsafeURLError: URL 指向私有网络、内部服务或违反 SSRF 安全策略
        httpx.TimeoutException: 请求超时（10秒）
        httpx.ConnectError: 连接失败
        httpx.HTTPStatusError: HTTP 错误（但 404/500 等仍返回内容）
    """
    logger.info(f"🌐 [工具:fetch_url] 开始抓取 URL: {url}")
    # SSRF 安全检查
    try:
        is_safe_url(url)
        logger.debug(f"🔒 [工具:fetch_url] SSRF 安全检查通过: {url}")
    except UnsafeURLError as e:
        logger.error(f"❌ [工具:fetch_url] SSRF 安全拦截，URL 不安全: {url} — {e}")
        raise

    try:
        # Make HTTP GET request with timeout
        logger.debug(f"📡 [工具:fetch_url] 发送 HTTP GET 请求，超时={DEFAULT_TIMEOUT}s...")
        response = httpx.get(url, timeout=DEFAULT_TIMEOUT)

        logger.info(
            f"✅ [工具:fetch_url] 抓取成功: {url} — 状态码={response.status_code}，内容大小={len(response.text)} 字符"
        )

        # Return response text (even for error status codes)
        # This allows agent to see error messages
        return response.text

    except httpx.TimeoutException:
        logger.error(f"❌ [工具:fetch_url] 请求超时: {url}")
        raise
    except httpx.ConnectError:
        logger.error(f"❌ [工具:fetch_url] 连接失败: {url}")
        raise
    except httpx.HTTPStatusError:
        logger.error(f"❌ [工具:fetch_url] HTTP 错误: {url}")
        raise
    except Exception as e:
        logger.error(f"❌ [工具:fetch_url] 未知异常: {url} — {e}")
        raise


# Tool list for LangGraph
__all__ = ["fetch_url"]
