"""
Sessions API routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SessionCreate(BaseModel):
    """Create session request"""

    title: str | None = None


class SessionResponse(BaseModel):
    """Session response model"""

    id: str
    title: str | None
    created_at: str
    message_count: int


@router.get("/", response_model=list[SessionResponse])
async def list_sessions():
    """List all sessions for current user"""
    # TODO: Implement with database
    return []


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details"""
    # TODO: Implement with database
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/", response_model=SessionResponse)
async def create_session(request: SessionCreate):
    """Create new session"""
    # TODO: Implement with database
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    # TODO: Implement with database
    raise HTTPException(status_code=501, detail="Not implemented")
