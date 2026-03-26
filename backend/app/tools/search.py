"""
Web search tool using Tavily API.

Provides real-time web search capability for the agent.
"""
import json

from langchain_core.tools import tool
from loguru import logger

from app.config import settings

MAX_RESULTS = 5
MAX_ANSWER_CHARS = 800
MAX_RESULT_CONTENT_CHARS = 1200
MAX_TOTAL_RESULT_CONTENT_CHARS = 3500


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in msg:
        return "timeout"
    if (
        isinstance(exc, ConnectionError)
        or "connection" in msg
        or "network" in msg
        or "dns" in msg
    ):
        return "network"
    if (
        "api" in msg
        or "unauthorized" in msg
        or "forbidden" in msg
        or "rate limit" in msg
        or "429" in msg
    ):
        return "api_error"
    return "unknown"


def _error_response(query: str, error_type: str, message: str) -> str:
    payload = {
        "ok": False,
        "query": query,
        "answer": "",
        "results": [],
        "error": {"type": error_type, "message": message},
    }
    return json.dumps(payload, ensure_ascii=False)


@tool
def web_search(query: str) -> str:
    """
    搜索互联网获取实时信息。

    适用场景：
    - 最新股价、汇率、市场数据
    - 新闻动态、时事更新
    - 法规变化、政策发布
    - 天气、交通等实时信息

    不适用场景：
    - 静态知识查询（历史、百科、定义）
    - 数学计算、逻辑推理
    - 代码编写、文本创作

    Args:
        query: 搜索查询字符串

    Returns:
        str: 搜索结果的 JSON 序列化字符串
    """
    if not settings.tavily_api_key:
        return _error_response(
            query=query,
            error_type="config_error",
            message="错误：未配置 TAVILY_API_KEY，无法使用搜索功能",
        )

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        logger.info(f"Executing web search: {query}")

        response = client.search(
            query=query,
            search_depth="basic",
            max_results=MAX_RESULTS,
            include_answer=True,
            include_raw_content=False,
        )

        # Format results for LLM consumption
        remaining_content_budget = MAX_TOTAL_RESULT_CONTENT_CHARS
        normalized_results = []
        for raw_item in response.get("results", []):
            title = str(raw_item.get("title", ""))
            url = str(raw_item.get("url", ""))
            content_raw = _truncate(
                str(raw_item.get("content", "")),
                MAX_RESULT_CONTENT_CHARS,
            )

            if remaining_content_budget <= 0:
                content = ""
            else:
                content = content_raw[:remaining_content_budget]
                remaining_content_budget -= len(content)

            normalized_results.append(
                {
                    "title": title,
                    "url": url,
                    "content": content,
                }
            )

        results = {
            "ok": True,
            "query": query,
            "answer": _truncate(str(response.get("answer", "")), MAX_ANSWER_CHARS),
            "results": normalized_results,
            "error": None,
        }

        return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        error_type = _classify_error(e)
        return _error_response(
            query=query,
            error_type=error_type,
            message=f"搜索失败：{str(e)}",
        )


# Tool list for LangGraph
__all__ = ["web_search"]
