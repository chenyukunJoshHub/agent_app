"""Token 预算管理 - P0

本模块管理 Context Window 的 Token 预算，决定每个 Slot 能用多少。
基于 Claude Sonnet 4.6 规格：200K Context Window，32K 工作预算。

使用 tiktoken 进行精确 Token 计数，而不是字符近似估算。
"""

from dataclasses import dataclass, field
from app.utils.token import count_tokens
from app.config import get_settings


@dataclass
class TokenBudget:
    """Token 预算配置（从配置文件读取）

    设计理念：
    - 模型硬上限 200K，但 Agent 工作预算设为 32K
    - 原因：多轮对话下，32K 足够且成本可控
    - 剩余预算给会话历史（Slot⑧），弹性最大

    Slot 配置原则：
    - 固定 Slot：System Prompt + 用户画像 + 工具 Schema
    - 弹性 Slot：会话历史（占大头）
    - 预留 Slot：输出（8K）

    所有配置从 .env 文件读取，避免硬编码
    """

    # -------------------------------------------------------------------------
    # 模型规格（从配置读取）
    # -------------------------------------------------------------------------
    MODEL_CONTEXT_WINDOW: int = field(init=False)
    MODEL_MAX_OUTPUT: int = field(init=False)

    # -------------------------------------------------------------------------
    # Agent 工作预算（从配置读取）
    # -------------------------------------------------------------------------
    WORKING_BUDGET: int = field(init=False)

    # -------------------------------------------------------------------------
    # Slot 配置（从配置读取）
    # -------------------------------------------------------------------------
    SLOT_OUTPUT: int = field(init=False)
    SLOT_SYSTEM: int = field(init=False)
    SLOT_ACTIVE_SKILL: int = field(init=False)
    SLOT_FEW_SHOT: int = field(init=False)
    SLOT_RAG: int = field(init=False)
    SLOT_EPISODIC: int = field(init=False)
    SLOT_PROCEDURAL: int = field(init=False)
    SLOT_TOOLS: int = field(init=False)
    AUTO_COMPACT_BUFFER_RATIO: float = field(init=False)

    # -------------------------------------------------------------------------
    # 初始化
    # -------------------------------------------------------------------------
    def __post_init__(self):
        """从配置文件读取所有 Token 预算配置"""
        settings = get_settings()

        self.MODEL_CONTEXT_WINDOW = settings.token_model_context_window
        self.MODEL_MAX_OUTPUT = settings.token_max_output
        self.WORKING_BUDGET = settings.token_working_budget
        self.SLOT_OUTPUT = settings.token_slot_output
        self.SLOT_SYSTEM = settings.token_slot_system
        self.SLOT_ACTIVE_SKILL = settings.token_slot_active_skill
        self.SLOT_FEW_SHOT = settings.token_slot_few_shot
        self.SLOT_RAG = settings.token_slot_rag
        self.SLOT_EPISODIC = settings.token_slot_episodic
        self.SLOT_PROCEDURAL = settings.token_slot_procedural
        self.SLOT_TOOLS = settings.token_slot_tools
        self.AUTO_COMPACT_BUFFER_RATIO = settings.token_autocompact_buffer_ratio

    # -------------------------------------------------------------------------
    # 计算属性
    # -------------------------------------------------------------------------

    @property
    def input_budget(self) -> int:
        """可用输入 Token = 工作预算 - 输出预留"""
        return self.WORKING_BUDGET - self.SLOT_OUTPUT

    @property
    def slot_history(self) -> int:
        """会话历史弹性预算

        计算公式：
        slot_history = input_budget - 所有固定 Slot 之和

        P0 固定 Slot = 2_000 + 500 + 1_200 = 3_700
        P0 slot_history = 24_768 - 3_700 = 21_068
        """
        fixed = (
            self.SLOT_SYSTEM + self.SLOT_ACTIVE_SKILL + self.SLOT_FEW_SHOT
            + self.SLOT_RAG + self.SLOT_EPISODIC + self.SLOT_PROCEDURAL
            + self.SLOT_TOOLS
        )
        return self.input_budget - fixed

    # -------------------------------------------------------------------------
    # Token 计算方法
    # -------------------------------------------------------------------------

    def calculate_history_usage(self, messages: list) -> int:
        """计算当前历史消息的 Token 占用

        Args:
            messages: LangChain Message 列表

        Returns:
            int: Token 数量（使用 tiktoken 精确计数）

        Note:
            使用 tiktoken 进行精确计数，而不是字符近似估算。
        """
        total_tokens = 0
        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
                if isinstance(content, str):
                    total_tokens += count_tokens(content)
                elif isinstance(content, list):
                    # 处理多模态内容
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            total_tokens += count_tokens(item['text'])

        return total_tokens

    def should_compress(self, messages: list) -> bool:
        """判断是否需要压缩历史

        Args:
            messages: LangChain Message 列表

        Returns:
            bool: True 表示需要压缩
        """
        return self.calculate_history_usage(messages) > self.slot_history

    def get_budget_summary(self) -> dict:
        """获取预算摘要（用于调试）

        Returns:
            dict: 预算分配摘要
        """
        return {
            "model_context_window": self.MODEL_CONTEXT_WINDOW,
            "working_budget": self.WORKING_BUDGET,
            "output_reserve": self.SLOT_OUTPUT,
            "input_budget": self.input_budget,
            "fixed_slots": {
                "system": self.SLOT_SYSTEM,
                "active_skill": self.SLOT_ACTIVE_SKILL,
                "few_shot": self.SLOT_FEW_SHOT,
                "rag": self.SLOT_RAG,
                "episodic": self.SLOT_EPISODIC,
                "procedural": self.SLOT_PROCEDURAL,
                "tools": self.SLOT_TOOLS,
            },
            "elastic_slot": {
                "history": self.slot_history,
            },
        }


# =============================================================================
# 默认实例
# =============================================================================

# P0: 单例模式（全局共享一个配置）
DEFAULT_BUDGET = TokenBudget()


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "TokenBudget",
    "DEFAULT_BUDGET",
]
