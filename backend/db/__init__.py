"""
数据库模块

提供数据库连接池、连接管理和 RLS 用户上下文设置。
"""

from .connection import (
    get_pool,
    close_pool,
    get_db_connection,
    set_user_context,
)
from .models import (
    User,
    Session,
    AgentTrace,
    TraceCreate,
    TraceResponse,
)
from .queries import (
    UserRepository,
    SessionRepository,
    AgentTraceRepository,
)

__all__ = [
    # Connection
    "get_pool",
    "close_pool",
    "get_db_connection",
    "set_user_context",
    # Models
    "User",
    "Session",
    "AgentTrace",
    "TraceCreate",
    "TraceResponse",
    # Repositories
    "UserRepository",
    "SessionRepository",
    "AgentTraceRepository",
]
