"""
Web search tool using Tavily API.

Provides real-time web search capability for the agent.
"""
from langchain_core.tools import tool
from loguru import logger

from app.config import settings


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
        return "错误：未配置 TAVILY_API_KEY，无法使用搜索功能"

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        logger.info(f"Executing web search: {query}")

        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
            include_raw_content=False,
        )

        # Format results for LLM consumption
        import json

        results = {
            "query": query,
            "answer": response.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                }
                for r in response.get("results", [])
            ],
        }

        return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"搜索失败：{str(e)}"


# Tool list for LangGraph
__all__ = ["web_search"]
