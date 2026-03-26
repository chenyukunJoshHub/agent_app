"""
API 层日志记录器
"""
from typing import Dict, Any, Optional

from .base import BaseLogger


class ApiLogger(BaseLogger):
    """
    API 层日志记录器

    覆盖所有请求、响应、SSE 流相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
    ):
        super().__init__(
            module="api",
            component="api_handler",
            session_id=session_id,
            user_id=user_id,
        )

    # ========== 请求处理 ==========

    def api_request_received(
        self,
        endpoint: str,
        method: str,
        message_length: int,
    ):
        """请求接收"""
        self.info(
            "api.request_received",
            "API request received",
            data={
                "endpoint": endpoint,
                "method": method,
                "message_length": message_length,
            },
            tags=["api", "request"],
        )

    def api_request_validated(
        self,
        valid: bool,
        errors: Optional[list],
    ):
        """请求验证"""
        self.debug(
            "api.request_validated",
            "API request validated",
            data={
                "valid": valid,
                "errors": errors,
            },
            tags=["api", "validation"],
        )

    def api_agent_invoked(
        self,
        session_id: str,
        user_id: str,
        message: str,
    ):
        """Agent 调用"""
        self.info(
            "api.agent_invoked",
            "Agent invoked",
            data={
                "session_id": session_id,
                "user_id": user_id,
                "message": message,
            },
            tags=["api", "agent"],
        )

    # ========== SSE 流 ==========

    def api_sse_stream_start(self, session_id: str, client_ip: str):
        """SSE 流启动"""
        self.info(
            "api.sse_stream_start",
            "SSE stream started",
            data={
                "session_id": session_id,
                "client_ip": client_ip,
            },
            tags=["api", "sse", "start"],
        )

    def api_sse_event_sent(
        self,
        event_type: str,
        data_length: int,
    ):
        """SSE 事件推送"""
        self.debug(
            "api.sse_event_sent",
            "SSE event sent",
            data={
                "event_type": event_type,
                "data_length": data_length,
            },
            tags=["api", "sse", "event"],
        )

    def api_sse_stream_end(
        self,
        session_id: str,
        total_events: int,
        total_bytes: int,
    ):
        """SSE 流结束"""
        self.info(
            "api.sse_stream_end",
            "SSE stream ended",
            data={
                "session_id": session_id,
                "total_events": total_events,
                "total_bytes": total_bytes,
            },
            tags=["api", "sse", "end"],
        )

    # ========== 请求完成 ==========

    def api_request_completed(
        self,
        session_id: str,
        status_code: int,
        total_latency_ms: int,
    ):
        """请求完成"""
        self.info(
            "api.request_completed",
            "API request completed",
            data={
                "session_id": session_id,
                "status_code": status_code,
                "total_latency_ms": total_latency_ms,
            },
            tags=["api", "request"],
        )

    def api_request_error(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str],
    ):
        """请求错误"""
        self.error(
            "api.request_error",
            "API request error",
            data={
                "session_id": session_id,
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
            },
            tags=["api", "error"],
        )
