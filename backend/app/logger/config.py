"""
日志配置
"""
import os
from pathlib import Path
from typing import Dict, Any


# 日志根目录
LOG_ROOT = Path(os.getenv("LOG_ROOT", Path(__file__).parent.parent.parent.parent / "logs"))
LOG_ROOT.mkdir(parents=True, exist_ok=True)


# 全局日志级别（可通过环境变量覆盖）
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# 日志文件配置
LOG_FILE_CONFIG = {
    "filename": LOG_ROOT / "agent.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 10,
    "encoding": "utf-8",
}


# 模块日志级别配置
MODULE_LOG_LEVELS: Dict[str, str] = {
    "agent": "INFO",
    "context": "DEBUG",
    "tools": "INFO",
    "skills": "INFO",
    "memory": "DEBUG",
    "api": "INFO",
    "sse": "INFO",
}


# 日志格式配置
LOG_FORMAT = "%(message)s"  # JSON 格式，详细字段在 formatter 中


# 是否启用调试模式
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"


# 追踪采样率（0-1）
TRACE_SAMPLING_RATE = float(os.getenv("TRACE_SAMPLING_RATE", "0.1"))


# 结构化日志字段
STRUCTURED_FIELDS = [
    "timestamp",
    "level",
    "logger",
    "module",
    "component",
    "session_id",
    "user_id",
    "thread_id",
    "step_id",
    "trace_id",
    "message",
    "data",
    "tags",
]


# 日志标签系统
LOG_TAGS = {
    # 按模块
    "modules": ["agent", "context", "tools", "skills", "memory", "api", "sse"],
    # 按操作类型
    "operations": ["read", "write", "invoke", "execute", "inject", "save", "load"],
    # 按阶段
    "stages": [
        "before_agent",
        "after_agent",
        "wrap_model_call",
        "after_model",
        "before_model",
    ],
    # 按数据类型
    "data_types": ["short_memory", "long_memory", "ephemeral", "persistent"],
}


# JSON 序列化配置
JSON_SERIALIZE_CONFIG = {
    "ensure_ascii": False,
    "indent": None,  # 单行 JSON
    "separators": (",", ":"),
}


# 性能阈值（毫秒）
PERFORMANCE_THRESHOLDS = {
    "llm_invoke": 5000,
    "tool_execute": 5000,
    "memory_load": 100,
    "memory_save": 100,
    "context_assemble": 100,
    "skill_load": 50,
}


# 警告阈值
WARNING_THRESHOLDS = {
    "token_overflow": True,  # Token 超限时警告
    "tool_retry": 2,  # 工具重试次数超过此值警告
    "hil_trigger": True,  # HIL 触发时警告
}


def get_module_log_level(module: str) -> str:
    """获取指定模块的日志级别"""
    if DEBUG_MODE:
        return "DEBUG"
    return MODULE_LOG_LEVELS.get(module, DEFAULT_LOG_LEVEL)


def get_log_file_path(module: str) -> Path:
    """获取指定模块的日志文件路径"""
    return LOG_ROOT / f"{module}.log"


def is_trace_sampled() -> bool:
    """判断是否被追踪采样"""
    import random
    return random.random() < TRACE_SAMPLING_RATE
