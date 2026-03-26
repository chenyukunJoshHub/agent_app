"""
SSE 流日志记录器
"""
from typing import Optional

from .base import BaseLogger


class SseLogger(BaseLogger):
    """
    SSE 流日志记录器

    覆盖所有 SSE 连接、事件推送相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ):
        super().__init__(
            module="sse",
            component="sse_handler",
            session_id=session_id,
            user_id=user_id,
        )

    # ========== 连接管理 ==========

    def sse_connection_established(self, session_id: str, client_ip: str):
        """SSE 连接建立"""
        self.info(
            "sse.connection_established",
            "SSE connection established",
            data={
                "session_id": session_id,
                "client_ip": client_ip,
            },
            tags=["sse", "connection"],
        )

    def sse_connection_closed(
        self,
        session_id: str,
        reason: str,
        duration_seconds: float,
    ):
        """SSE 连接关闭"""
        self.info(
            "sse.connection_closed",
            "SSE connection closed",
            data={
                "session_id": session_id,
                "reason": reason,
                "duration_seconds": duration_seconds,
            },
            tags=["sse", "connection"],
        )

    # ========== 事件推送 ==========

    def sse_event_push(
        self,
        event_type: str,
        event_data: str,
    ):
        """SSE 事件推送"""
        self.debug(
            "sse.event_push",
            "SSE event pushed",
            data={
                "event_type": event_type,
                "event_data": event_data,
            },
            tags=["sse", "event"],
        )

    def sse_event_thought(
        self,
        token_text: str,
        cumulative_tokens: int,
    ):
        """thought 事件"""
        # self.info(
        #     "sse.event_thought",
        #     "SSE thought event",
        #     data={
        #         "token_text": token_text,
        #         "cumulative_tokens": cumulative_tokens,
        #     },
        #     tags=["sse", "thought"],
        # )

    def sse_event_tool_start(self, tool_name: str, args: dict):
        """tool_start 事件"""
        # self.info(
        #     "sse.event_tool_start",
        #     "SSE tool_start event",
        #     data={
        #         "tool_name": tool_name,
        #         "args": args,
        #     },
        #     tags=["sse", "tool_start"],
        # )

    def sse_event_tool_result(self, tool_name: str, result_length: int):
        """tool_result 事件"""
        # self.info(
        #     "sse.event_tool_result",
        #     "SSE tool_result event",
        #     data={
        #         "tool_name": tool_name,
        #         "result_length": result_length,
        #     },
        #     tags=["sse", "tool_result"],
        # )

    def sse_event_hil_interrupt(
        self,
        interrupt_id: str,
        tool_name: str,
        tool_args: dict,
    ):
        """hil_interrupt 事件"""
        # self.info(
        #     "sse.event_hil_interrupt",
        #     "SSE hil_interrupt event",
        #     data={
        #         "interrupt_id": interrupt_id,
        #         "tool_name": tool_name,
        #         "tool_args": tool_args,
        #     },
        #     tags=["sse", "hil_interrupt"],
        # )

    def sse_event_done(
        self,
        final_answer_length: int,
        total_tokens: int,
    ):
        """done 事件"""
        # self.info(
        #     "sse.event_done",
        #     "SSE done event",
        #     data={
        #         "final_answer_length": final_answer_length,
        #         "total_tokens": total_tokens,
        #     },
        #     tags=["sse", "done"],
        # )

    def sse_event_error(self, error_message: str):
        """error 事件"""
        self.error(
            "sse.event_error",
            "SSE error event",
            data={
                "error_message": error_message,
            },
            tags=["sse", "error"],
        )
