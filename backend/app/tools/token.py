"""
Token counting tool for Agent system.

Provides accurate token counting for various LLM models.
"""
import json

import tiktoken
from langchain_core.tools import tool
from loguru import logger

# Default model encoding
DEFAULT_MODEL = "gpt-4"

# Supported model encodings
MODEL_ENCODINGS = {
    "gpt-4": "cl100k_base",
    "gpt-4-32k": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-3.5-turbo-16k": "cl100k_base",
    "text-embedding-ada-002": "cl100k_base",
    "text-embedding-3-small": "cl100k_base",
    "text-embedding-3-large": "cl100k_base",
    # Claude models use a different encoding, but we'll approximate with cl100k_base
    # For production, you might want to use Anthropic's official tokenizer
    "claude-3-opus": "cl100k_base",
    "claude-3-sonnet": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    "claude-3.5-sonnet": "cl100k_base",
}


def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """
    Get the appropriate tiktoken encoding for a given model.

    Args:
        model: Model name (e.g., "gpt-4", "claude-3-sonnet")

    Returns:
        tiktoken.Encoding: The encoding for the model
    """
    # Try to get encoding from our mapping
    encoding_name = MODEL_ENCODINGS.get(model, "cl100k_base")

    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return encoding
    except KeyError:
        # Fallback to cl100k_base if encoding not found
        logger.warning(f"Encoding {encoding_name} not found for model {model}, using cl100k_base")
        return tiktoken.get_encoding("cl100k_base")


@tool
def token_counter(text: str, model: str = DEFAULT_MODEL) -> str:
    """
    计算文本的 token 数量（精确计数）。

    适用场景：
    - 估算 LLM API 调用成本（按 token 计费）
    - 检查文本是否超出模型上下文窗口限制
    - 分析 prompt 长度和响应 token 数
    - 优化 prompt 以节省 token

    不适用场景：
    - 非 LLM 相关的文本统计（应用 len() 或字符计数）
    - 需要精确到字符级别的分析

    Args:
        text: 要计算 token 数的文本内容
        model: 模型名称（默认 gpt-4，支持 gpt-3.5-turbo、claude-3-* 等）

    Returns:
        str: JSON 字符串，格式：{"count": int, "model": str, "text_length": int}
    """
    try:
        # Get encoding for the model
        encoding = get_encoding_for_model(model)

        # Encode text to tokens
        tokens = encoding.encode(text)

        # Count tokens
        token_count = len(tokens)

        # Prepare result
        result = {
            "count": token_count,
            "model": model,
            "text_length": len(text),
        }

        logger.info(
            f"Counted {token_count} tokens for model {model} (text length: {len(text)})"
        )

        # Return as JSON string
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        # Return error info in JSON format
        error_result = {
            "count": -1,
            "model": model,
            "error": str(e),
        }
        return json.dumps(error_result, ensure_ascii=False)


# Tool list for LangGraph
__all__ = ["token_counter"]
