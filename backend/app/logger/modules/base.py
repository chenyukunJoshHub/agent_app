"""
Base Logger 基类
"""
import logging
from typing import Any, Dict, List, Optional

from ..formatter import LogContext, create_logger


class BaseLogger:
    """
    Base Logger 基类

    所有模块 Logger 都继承此类，提供统一的日志接口
    """

    def __init__(
        self,
        module: str,
        component: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        step_id: Optional[int] = None,
    ):
        """
        初始化 Base Logger

        Args:
            module: 模块名称
            component: 组件名称
            session_id: 会话 ID
            user_id: 用户 ID
            thread_id: Thread ID
            step_id: Step ID
        """
        self._logger = create_logger(
            name=f"{module}.{component}" if component else module,
            module=module,
        )
        self._module = module
        self._component = component

        # 上下文字段（避免覆盖 LogRecord 保留字段）
        self._context: Dict[str, Any] = {}

        if component:
            self._context["component"] = component
        if session_id:
            self._context["session_id"] = session_id
        if user_id:
            self._context["user_id"] = user_id
        if thread_id:
            self._context["thread_id"] = thread_id
        if step_id is not None:
            self._context["step_id"] = step_id

    def _log(
        self,
        level: int,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """
        内部日志方法

        Args:
            level: 日志级别
            logger_name: Logger 名称
            message: 日志消息
            data: 结构化数据
            tags: 标签列表
            **kwargs: 额外字段
        """
        # 构建完整上下文（使用不同的键名避免覆盖 LogRecord 保留字段）
        extra = {
            "log_module": self._module,
            "log_component": self._component,
        }
        if self._component:
            extra["log_component"] = self._component
        if "session_id" in self._context:
            extra["session_id"] = self._context["session_id"]
        if "user_id" in self._context:
            extra["user_id"] = self._context["user_id"]
        if "thread_id" in self._context:
            extra["thread_id"] = self._context["thread_id"]
        if "step_id" in self._context:
            extra["step_id"] = self._context["step_id"]
        if "trace_id" in self._context:
            extra["trace_id"] = self._context["trace_id"]

        # 数据字段
        extra["data"] = data or {}
        extra["tags"] = tags or []

        # 添加额外的字段到 data
        if kwargs:
            extra["data"].update(kwargs)

        # 使用 LogContext 设置上下文
        with LogContext(**self._context):
            self._logger.log(level, message, extra=extra)

    def debug(
        self,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """DEBUG 级别日志"""
        self._log(logging.DEBUG, logger_name, message, data, tags, **kwargs)

    def info(
        self,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """INFO 级别日志"""
        self._log(logging.INFO, logger_name, message, data, tags, **kwargs)

    def warning(
        self,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """WARNING 级别日志"""
        self._log(logging.WARNING, logger_name, message, data, tags, **kwargs)

    def error(
        self,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """ERROR 级别日志"""
        self._log(logging.ERROR, logger_name, message, data, tags, **kwargs)

    def critical(
        self,
        logger_name: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """CRITICAL 级别日志"""
        self._log(logging.CRITICAL, logger_name, message, data, tags, **kwargs)

    def exception(
        self,
        logger_name: str,
        message: str,
        exc_info: bool = True,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        """EXCEPTION 级别日志（自动包含异常信息）"""
        # 构建完整上下文
        extra = {
            **self._context,
            "data": data or {},
            "tags": tags or [],
        }

        # 添加额外的字段到 data
        if kwargs:
            extra["data"].update(kwargs)

        # 使用 LogContext 设置上下文
        with LogContext(**self._context):
            self._logger.exception(message, exc_info=exc_info, extra=extra)

    def update_context(self, **kwargs):
        """
        更新日志上下文

        Args:
            **kwargs: 要更新的上下文字段
        """
        self._context.update(kwargs)

    def set_step(self, step_id: int):
        """设置当前 Step ID"""
        self._context["step_id"] = step_id

    def increment_step(self):
        """递增 Step ID"""
        if "step_id" in self._context:
            self._context["step_id"] += 1
        else:
            self._context["step_id"] = 0
