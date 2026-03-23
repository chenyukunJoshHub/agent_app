"""
Skills API endpoints.

Provides GET /skills endpoint to list all available skills.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.skills.manager import SkillManager
from app.skills.models import SkillEntry


# Response Models
class SkillResponse(BaseModel):
    """Response model for a single skill."""

    name: str
    description: str
    file_path: str
    tools: list[str]

    @classmethod
    def from_entry(cls, entry: SkillEntry) -> "SkillResponse":
        """
        Create SkillResponse from SkillEntry.

        Args:
            entry: SkillEntry object

        Returns:
            SkillResponse object
        """
        return cls(
            name=entry.name,
            description=entry.description,
            file_path=entry.file_path,
            tools=entry.tools,
        )


class SkillsListResponse(BaseModel):
    """Response model for skills list."""

    skills: list[SkillResponse]


# Router
router = APIRouter(prefix="/skills", tags=["skills"])


# Dependency to get SkillManager singleton
def get_skill_manager() -> SkillManager:
    """
    Get or create SkillManager singleton.

    Returns:
        SkillManager instance
    """
    # For now, create a new instance each time
    # In production, this should be a singleton managed by the app lifecycle
    from app.config import settings

    skills_dir = getattr(settings, "skills_dir", "skills")
    return SkillManager(skills_dir=skills_dir)


@router.get("/", response_model=SkillsListResponse)
async def list_skills() -> SkillsListResponse:
    """
    List all available skills.

    Returns a list of all active skills that can be used by the agent.
    Each skill includes its name, description, file path, and required tools.

    Returns:
        SkillsListResponse: List of available skills

    Raises:
        HTTPException: If skill scanning fails
    """
    try:
        # Get SkillManager
        manager = get_skill_manager()

        # Build snapshot to get active skills
        snapshot = manager.build_snapshot()

        # Convert SkillEntry to SkillResponse
        skill_responses = [
            SkillResponse.from_entry(entry) for entry in snapshot.skills
        ]

        logger.info(f"Retrieved {len(skill_responses)} skills")

        return SkillsListResponse(skills=skill_responses)

    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve skills: {str(e)}",
        )


__all__ = ["router"]
