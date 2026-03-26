"""
Context 模块日志记录器
"""
from typing import Dict, Any, Optional, List

from .base import BaseLogger


class ContextLogger(BaseLogger):
    """
    Context 模块日志记录器

    覆盖所有 Context Window 组装、Memory 读写相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        thread_id: str,
    ):
        super().__init__(
            module="context",
            component="context_assembler",
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
        )

    # ========== Context 组装 ==========

    def context_assemble_start(self, llm_call_index: int):
        """Context 组装开始"""
        self.debug(
            "context.assemble_start",
            "Context assembly started",
            data={
                "llm_call_index": llm_call_index,
            },
            tags=["context", "assemble"],
        )

    def context_slot1_system_prompt(
        self,
        tokens: Dict[str, int],
    ):
        """Slot ① System Prompt"""
        self.debug(
            "context.slot1_system_prompt",
            "Slot ① System Prompt assembled",
            data={
                "tokens": tokens,
            },
            tags=["context", "slot1", "system_prompt"],
        )

    def context_slot3_dynamic_fewshot(
        self,
        count: int,
        total_tokens: int,
        retrieval_ms: int,
    ):
        """Slot ③ 动态 Few-shot"""
        self.info(
            "context.slot3_dynamic_fewshot",
            "Slot ③ Dynamic Few-shot loaded",
            data={
                "count": count,
                "total_tokens": total_tokens,
                "retrieval_ms": retrieval_ms,
            },
            tags=["context", "slot3", "fewshot"],
        )

    def context_slot4_rag_chunks(
        self,
        count: int,
        total_tokens: int,
        retrieval_ms: int,
    ):
        """Slot ④ RAG 背景知识"""
        self.info(
            "context.slot4_rag_chunks",
            "Slot ④ RAG chunks loaded",
            data={
                "count": count,
                "total_tokens": total_tokens,
                "retrieval_ms": retrieval_ms,
            },
            tags=["context", "slot4", "rag"],
        )

    def context_slot7_tool_schemas(
        self,
        tool_count: int,
        total_tokens: int,
    ):
        """Slot ⑦ 工具 Schema"""
        self.debug(
            "context.slot7_tool_schemas",
            "Slot ⑦ Tool schemas assembled",
            data={
                "tool_count": tool_count,
                "total_tokens": total_tokens,
            },
            tags=["context", "slot7", "tools"],
        )

    def context_slot8_history(
        self,
        message_count: int,
        total_tokens: int,
        compressed: bool,
    ):
        """Slot ⑧ 会话历史"""
        self.info(
            "context.slot8_history",
            "Slot ⑧ History loaded",
            data={
                "message_count": message_count,
                "total_tokens": total_tokens,
                "compressed": compressed,
            },
            tags=["context", "slot8", "history"],
        )

    def context_slot10_user_input(
        self,
        tokens: int,
    ):
        """Slot ⑩ 用户输入"""
        self.info(
            "context.slot10_user_input",
            "Slot ⑩ User input added",
            data={
                "tokens": tokens,
            },
            tags=["context", "slot10", "user_input"],
        )

    def context_budget_check(
        self,
        total_tokens: int,
        max_tokens: int,
        overflow: bool,
    ):
        """Token 预算检查"""
        self.info(
            "context.budget_check",
            "Token budget checked",
            data={
                "total_tokens": total_tokens,
                "max_tokens": max_tokens,
                "overflow": overflow,
            },
            tags=["context", "budget"],
        )

    def context_compress_start(
        self,
        current_tokens: int,
        target_tokens: int,
    ):
        """消息压缩开始"""
        self.warning(
            "context.compress_start",
            "Message compression started",
            data={
                "current_tokens": current_tokens,
                "target_tokens": target_tokens,
            },
            tags=["context", "compress"],
        )

    def context_compress_end(
        self,
        compressed_tokens: int,
        compression_ratio: float,
    ):
        """消息压缩完成"""
        self.info(
            "context.compress_end",
            "Message compression completed",
            data={
                "compressed_tokens": compressed_tokens,
                "compression_ratio": compression_ratio,
            },
            tags=["context", "compress"],
        )

    def context_assemble_end(
        self,
        total_input_tokens: int,
        max_output_tokens: int,
    ):
        """Context 组装完成"""
        self.debug(
            "context.assemble_end",
            "Context assembly completed",
            data={
                "total_input_tokens": total_input_tokens,
                "max_output_tokens": max_output_tokens,
            },
            tags=["context", "assemble"],
        )
