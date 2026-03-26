"""
Memory 模块日志记录器
"""
from typing import Dict, Any, Optional, List

from .base import BaseLogger


class MemoryLogger(BaseLogger):
    """
    Memory 模块日志记录器

    覆盖所有 Short Memory、Long Memory、Ephemeral 注入相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        thread_id: str,
        step_id: Optional[int] = None,
    ):
        super().__init__(
            module="memory",
            component="memory_manager",
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
            step_id=step_id,
        )

    # ========== Short Memory ==========

    def memory_short_restore_start(self, thread_id: str):
        """Short Memory 恢复开始"""
        self.debug(
            "memory.short_restore_start",
            "Short Memory restore started",
            data={
                "thread_id": thread_id,
            },
            tags=["memory", "short", "restore"],
        )

    def memory_short_restore_loaded(
        self,
        message_count: int,
        total_tokens: int,
    ):
        """Short Memory 恢复完成"""
        self.info(
            "memory.short_restore_loaded",
            "Short Memory restored",
            data={
                "message_count": message_count,
                "total_tokens": total_tokens,
            },
            tags=["memory", "short", "restore"],
        )

    def memory_short_save_start(self):
        """Short Memory 保存开始"""
        self.debug(
            "memory.short_save_start",
            "Short Memory save started",
            tags=["memory", "short", "save"],
        )

    def memory_short_save_saved(
        self,
        message_count: int,
        checkpoint_id: str,
    ):
        """Short Memory 保存完成"""
        self.info(
            "memory.short_save_saved",
            "Short Memory saved",
            data={
                "message_count": message_count,
                "checkpoint_id": checkpoint_id,
            },
            tags=["memory", "short", "save"],
        )

    # ========== Long Memory ==========

    def memory_long_load_start(
        self,
        namespace: tuple,
        key: str,
    ):
        """Long Memory 加载开始"""
        self.debug(
            "memory.long_load_start",
            "Long Memory load started",
            data={
                "namespace": namespace,
                "key": key,
            },
            tags=["memory", "long", "load"],
        )

    def memory_long_loaded(
        self,
        episodic_data: Optional[Dict[str, Any]],
        procedural_count: int,
        latency_ms: int,
    ):
        """Long Memory 加载完成"""
        self.info(
            "memory.long_loaded",
            "Long Memory loaded",
            data={
                "episodic_data": episodic_data,
                "procedural_count": procedural_count,
                "latency_ms": latency_ms,
            },
            tags=["memory", "long", "load"],
        )

    def memory_long_write_start(
        self,
        namespace: tuple,
        key: str,
    ):
        """Long Memory 写入开始"""
        self.debug(
            "memory.long_write_start",
            "Long Memory write started",
            data={
                "namespace": namespace,
                "key": key,
            },
            tags=["memory", "long", "write"],
        )

    def memory_long_written(
        self,
        changes: Dict[str, Any],
        interaction_count_new: int,
        latency_ms: int,
    ):
        """Long Memory 写入完成"""
        self.info(
            "memory.long_written",
            "Long Memory written",
            data={
                "changes": changes,
                "interaction_count_new": interaction_count_new,
                "latency_ms": latency_ms,
            },
            tags=["memory", "long", "write"],
        )

    # ========== Ephemeral 注入 ==========

    def memory_ephemeral_inject(
        self,
        type: str,
        tokens: int,
        content: Optional[str],
    ):
        """Ephemeral 内容注入"""
        self.debug(
            "memory.ephemeral_inject",
            "Ephemeral content injected",
            data={
                "type": type,
                "tokens": tokens,
                "content": content,
            },
            tags=["memory", "ephemeral", "inject"],
        )
