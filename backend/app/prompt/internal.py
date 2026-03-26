"""内部操作 Prompt - 系统级 LLM 调用

本模块从 templates.py 导入内部节点使用的 Prompt 模板。
这些 Prompt 不会暴露给用户，仅用于系统级 LLM 调用。

用途：
- 压缩器：将长对话历史压缩成摘要
- HIL 确认：生成人工介入确认消息
- 错误恢复：指导 Agent 处理工具调用失败
"""

from app.prompt.templates import (
    COMPRESSOR_PROMPT,
    HIL_CONFIRM_TEMPLATE,
    ERROR_RECOVERY_RULES,
    COMPRESSOR_FEW_SHOT,
)

__all__ = [
    "COMPRESSOR_PROMPT",
    "HIL_CONFIRM_TEMPLATE",
    "ERROR_RECOVERY_RULES",
    "COMPRESSOR_FEW_SHOT",
]
