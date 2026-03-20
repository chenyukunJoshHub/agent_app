"""
Skills API routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SkillResponse(BaseModel):
    """Skill response model"""

    name: str
    version: str
    description: str
    author: str
    is_loaded: bool


@router.get("/", response_model=list[SkillResponse])
async def list_skills():
    """List all available skills"""
    from app.skills.manager import skill_manager

    skills = skill_manager.list_all()
    return [
        SkillResponse(
            name=skill.name,
            version=skill.version,
            description=skill.description,
            author=skill.author,
            is_loaded=skill.name in skill_manager._loaded_skills,
        )
        for skill in skills.values()
    ]


@router.post("/reload")
async def reload_skills():
    """Reload all skills from disk"""
    from app.skills.manager import skill_manager

    await skill_manager.reload()
    return {"message": "Skills reloaded successfully"}


@router.get("/{skill_name}", response_model=SkillResponse)
async def get_skill(skill_name: str):
    """Get skill details"""
    from app.skills.manager import skill_manager

    skill = skill_manager.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillResponse(
        name=skill.name,
        version=skill.version,
        description=skill.description,
        author=skill.author,
        is_loaded=True,
    )
