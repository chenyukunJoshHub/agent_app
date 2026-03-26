"""
结构化日志格式化器
"""
import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import JSON_SERIALIZE_CONFIG


class StructuredFormatter(logging.Formatter):
    """
    结构化 JSON 日志格式化器

    所有日志都输出为 JSON 格式，包含以下字段：
    - timestamp: ISO 8601 时间戳
    - level: 日志级别
    - logger: Logger 名称
    - module: 模块名称
    - component: 组件名称
    - session_id: 会话 ID
    - user_id: 用户 ID
    - thread_id: 线程 ID
    - step_id: Step ID
    - trace_id: 追踪 ID
    - message: 日志消息
    - data: 结构化数据
    - tags: 标签列表
    """

    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录为 JSON

        Args:
            record: 日志记录

        Returns:
            JSON 格式的日志字符串
        """
        # 构建基础日志字典
        log_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
        }

        # 从 extra 字段中提取结构化数据
        # LogRecord 的自定义字段存储在 __dict__ 中
        extra = {}
        if hasattr(record, '__dict__'):
            for key in ["log_module", "component", "session_id", "user_id",
                        "thread_id", "step_id", "trace_id", "data", "tags"]:
                if key in record.__dict__:
                    extra[key] = record.__dict__[key]

        # 提取标准字段
        for field in ["log_module", "component", "session_id", "user_id",
                     "thread_id", "step_id", "trace_id"]:
            if field in extra:
                # 将 log_module 映射为 module
                json_field = "module" if field == "log_module" else field
                log_dict[json_field] = extra[field]

        # 消息文本
        log_dict["message"] = record.getMessage()

        # 数据字段
        if "data" in extra:
            log_dict["data"] = extra["data"]

        # 标签字段
        if "tags" in extra:
            log_dict["tags"] = extra["tags"]

        # 异常信息
        if record.exc_info:
            log_dict["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # 序列化为 JSON
        return json.dumps(log_dict, **JSON_SERIALIZE_CONFIG) + "\n"


class LogContext:
    """
    日志上下文管理器

    使用方式：
        with LogContext(session_id="xxx", user_id="yyy"):
            logger.info("Message")
    """

    _context = threading.local()

    def __init__(self, **kwargs):
        """
        初始化日志上下文

        Args:
            **kwargs: 上下文字段（session_id, user_id, thread_id, step_id 等）
        """
        self.context = kwargs
        self.previous = None

    def __enter__(self):
        # 保存之前的上下文
        self.previous = getattr(LogContext._context, 'current', {}).copy()
        # 设置新上下文
        LogContext._context.current = {**self.previous, **self.context}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复之前的上下文
        LogContext._context.current = self.previous

    @classmethod
    def get_current(cls) -> Dict[str, Any]:
        """获取当前日志上下文"""
        return getattr(cls._context, 'current', {})


class ContextFilter(logging.Filter):
    """
    上下文过滤器

    自动将 LogContext 中的字段添加到日志记录的 extra 中
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录，添加上下文字段

        Args:
            record: 日志记录

        Returns:
            总是返回 True，允许所有日志通过
        """
        # 获取当前上下文
        context = LogContext.get_current()

        # 将上下文字段添加到 LogRecord
        for key, value in context.items():
            setattr(record, key, value)

        return True


def create_logger(
    name: str,
    level: Optional[str] = None,
    module: Optional[str] = None,
) -> logging.Logger:
    """
    创建结构化日志记录器

    Args:
        name: Logger 名称
        level: 日志级别（默认从配置读取）
        module: 模块名称

    Returns:
        配置好的 Logger 实例
    """
    # 从配置获取日志级别
    from .config import get_module_log_level, DEBUG_MODE
    if level is None:
        if module:
            level = get_module_log_level(module)
        else:
            level = "INFO" if not DEBUG_MODE else "DEBUG"

    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 添加上下文过滤器
    context_filter = ContextFilter()
    logger.addFilter(context_filter)

    # 如果没有 handler，添加控制台 handler
    if not logger.handlers:
        # 创建控制台 handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # 设置格式化器
        formatter = StructuredFormatter()
        console_handler.setFormatter(formatter)

        # 添加 handler
        logger.addHandler(console_handler)

    return logger
