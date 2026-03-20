"""
Chat API routes - SSE streaming endpoint
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.routes.chat import ChatRequest, ChatResponse

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model"""

    message: str
    session_id: str | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    """Chat response model"""

    response: str
    session_id: str
    tokens_used: int


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat responses using SSE"""
    from app.agent.executor import AgentExecutor

    executor = AgentExecutor(session_id=request.session_id)

    async def event_generator():
        """Generate SSE events"""
        try:
            async for event in executor.execute_stream(request.message):
                yield f"event: {event['type']}\n"
                yield f"data: {event['data']}\n\n"

        except Exception as e:
            yield f"event: error\n"
            yield f"data: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/completion", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """Non-streaming chat completion"""
    from app.agent.executor import AgentExecutor

    executor = AgentExecutor(session_id=request.session_id)

    try:
        result = await executor.execute(request.message)
        return ChatResponse(
            response=result["response"],
            session_id=executor.session_id,
            tokens_used=result.get("tokens_used", 0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
