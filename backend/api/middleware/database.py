"""
数据库中间件

为 FastAPI 集成数据库连接和 RLS 用户上下文。
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..db import get_db_connection, set_user_context


class DatabaseMiddleware(BaseHTTPMiddleware):
    """
    数据库中间件

    为每个请求设置数据库连接和用户上下文。
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # 从 JWT token 中提取 user_id（由认证中间件设置）
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            # 为每个数据库连接设置用户上下文
            # 注意：这需要在请求处理时显式调用 set_user_context
            request.state.db_user_id = user_id

        response = await call_next(request)
        return response


async def get_db_with_user_context(request: Request):
    """
    依赖注入：获取带有用户上下文的数据库连接

    使用方式：
        @app.get("/api/sessions")
        async def list_sessions(db = Depends(get_db_with_user_context)):
            # db 连接已经设置了 user_id 上下文
            sessions = await SessionRepository.list_by_user(db, user_id)
            return sessions
    """
    from ..db import get_db_with_user_context as get_db_ctx
    from ..db.connection import AsyncConnection

    user_id = getattr(request.state, "db_user_id", None)

    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User not authenticated")

    async for conn in get_db_ctx(user_id):
        yield conn


# ============================================================
-- 使用示例
-- ============================================================

"""
from fastapi import APIRouter, Depends
from ..api.middleware.database import get_db_with_user_context
from ..db.models import Session
from ..db.queries import SessionRepository

router = APIRouter()

@router.get("/api/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db = Depends(get_db_with_user_context)
) -> list[Session]:
    # 从请求状态获取 user_id
    # db 连接已经通过 RLS 隔离，只能访问当前用户的数据
    user_id = db.info.get("user_id")

    sessions = await SessionRepository.list_by_user(db, user_id, limit, offset)
    return sessions


@router.post("/api/sessions")
async def create_session(
    title: str,
    db = Depends(get_db_with_user_context)
) -> Session:
    user_id = db.info.get("user_id")

    session = SessionCreate(
        id=str(uuid4()),
        user_id=user_id,
        title=title
    )

    return await SessionRepository.create(db, session)
"""
