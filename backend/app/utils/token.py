"""
Token utilities for Agent system.

Provides token counting and budget management functionality.
"""
import logging
import tiktoken

logger = logging.getLogger(__name__)

# Model encoding mapping (same as tools/token.py)
MODEL_ENCODINGS = {
    "gpt-4": "cl100k_base",
    "gpt-4-32k": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-3.5-turbo-16k": "cl100k_base",
    "claude-3-opus": "cl100k_base",
    "claude-3-sonnet": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    "claude-3.5-sonnet": "cl100k_base",
}


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    计算文本的 token 数量。

    Args:
        text: 要计算 token 数的文本内容
        model: 模型名称（默认 gpt-4）

    Returns:
        int: token 数量
    """
    if not text:
        return 0

    # Get encoding for the model
    encoding_name = MODEL_ENCODINGS.get(model, "cl100k_base")
    encoding = tiktoken.get_encoding(encoding_name)

    # Encode and count
    tokens = encoding.encode(text)
    return len(tokens)


class TokenBudget:
    """
    Token 预算管理类。

    管理 32K 上下文窗口的预算分配。
    """

    def __init__(self, total_budget: int = 32000) -> None:
        """
        初始化 Token 预算。

        Args:
            total_budget: 总预算（默认 32000）
        """
        self.total_budget = total_budget
        # 预算分配
        self.system_prompt = 2000
        self.tools_schema = 3000
        self.few_shot = 2000
        self.long_memory = 1000
        self.short_memory = 8000
        self.current_input = 2000
        self.reserved = 14000  # 预留

    def get_available_for_history(self) -> int:
        """
        获取可用于历史的 token 数量。

        Returns:
            int: 可用于历史对话的 token 数量
        """
        # Available = total - (system + tools + few_shot + long_memory + current_input + reserved)
        # Available = 32000 - (2000 + 3000 + 2000 + 1000 + 2000 + 14000) = 8000
        allocated = (
            self.system_prompt
            + self.tools_schema
            + self.few_shot
            + self.long_memory
            + self.current_input
            + self.reserved
        )
        return self.total_budget - allocated

    def should_truncate_history(self, current_tokens: int) -> bool:
        """
        判断是否需要截断历史。

        Args:
            current_tokens: 当前历史的 token 数量

        Returns:
            bool: 是否需要截断
        """
        available = self.get_available_for_history()
        return current_tokens > available

    def calculate_overflow(self, current_tokens: int) -> int:
        """
        计算超出预算的 token 数量。

        Args:
            current_tokens: 当前历史的 token 数量

        Returns:
            int: 超出的 token 数量（如果没有超出则返回 0）
        """
        available = self.get_available_for_history()
        overflow = current_tokens - available
        return max(0, overflow)

    def truncate_to_fit(self, current_tokens: int) -> int:
        """
        计算截断后应该保留的 token 数量。

        Args:
            current_tokens: 当前历史的 token 数量

        Returns:
            int: 截断后应该保留的 token 数量
        """
        available = self.get_available_for_history()
        if current_tokens <= available:
            return current_tokens

        # Log warning about truncation
        overflow = current_tokens - available
        logger.warning(
            f"Token budget exceeded: {current_tokens} > {available}. "
            f"Truncating {overflow} tokens from history."
        )

        return available

    def get_allocation_summary(self) -> dict:
        """
        获取预算分配摘要。

        Returns:
            dict: 包含各项分配的字典
        """
        return {
            "total_budget": self.total_budget,
            "system_prompt": self.system_prompt,
            "tools_schema": self.tools_schema,
            "few_shot": self.few_shot,
            "long_memory": self.long_memory,
            "short_memory": self.short_memory,
            "current_input": self.current_input,
            "reserved": self.reserved,
            "available_for_history": self.get_available_for_history(),
        }


__all__ = ["count_tokens", "TokenBudget"]
