"""
数据库模型

定义数据库表的 Pydantic 模型。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


# ============================================================
-- Users 模型
-- ============================================================

class UserBase(BaseModel):
    """用户基础模型"""
    email: str = Field(..., max_length=255)


class UserCreate(UserBase):
    """用户创建模型"""
    id: str = Field(..., max_length=255)


class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[str] = Field(None, max_length=255)


class User(UserBase):
    """用户响应模型"""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
-- Sessions 模型
-- ============================================================

class SessionBase(BaseModel):
    """会话基础模型"""
    title: Optional[str] = Field(None, max_length=500)


class SessionCreate(SessionBase):
    """会话创建模型"""
    id: str = Field(..., max_length=255)
    user_id: str = Field(..., max_length=255)


class SessionUpdate(SessionBase):
    """会话更新模型"""
    title: Optional[str] = Field(None, max_length=500)


class Session(SessionBase):
    """会话响应模型"""
    id: str
    user_id: str
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
-- Agent Traces 模型
-- ============================================================

class FinishReason(str):
    """完成原因枚举"""
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class TokenUsage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)


class ToolCall(BaseModel):
    """工具调用记录"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class ThoughtStep(BaseModel):
    """推理步骤"""
    step: int
    content: str
    timestamp: datetime


class TraceCreate(BaseModel):
    """追踪创建模型"""
    session_id: str = Field(..., max_length=255)
    user_input: str = Field(..., max_length=10000)
    thought_chain: List[ThoughtStep] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    token_usage: TokenUsage
    latency_ms: int = Field(..., ge=0)
    finish_reason: FinishReason


class TraceUpdate(BaseModel):
    """追踪更新模型"""
    final_answer: Optional[str] = Field(None, max_length=50000)
    finish_reason: Optional[FinishReason] = None


class AgentTrace(BaseModel):
    """追踪响应模型"""
    id: UUID
    session_id: str
    user_id: str
    user_input: Optional[str]
    final_answer: Optional[str]
    thought_chain: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    token_usage: Dict[str, Any]
    latency_ms: int
    finish_reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    """追踪响应（包含会话信息）"""
    trace: AgentTrace
    session_title: Optional[str] = None


# ============================================================
-- 分页模型
-- ============================================================

class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedTraces(PaginatedResponse):
    """分页追踪响应"""
    items: List[AgentTrace]


class PaginatedSessions(PaginatedResponse):
    """分页会话响应"""
    items: List[Session]
