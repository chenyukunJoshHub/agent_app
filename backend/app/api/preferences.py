"""
User Preferences API.

GET  /api/user/preferences?user_id=dev_user  — 读取用户偏好
POST /api/user/preferences                   — 写入/更新用户偏好
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.postgres import get_store
from app.memory.manager import MemoryManager

router = APIRouter(prefix="/api/user", tags=["preferences"])


class PreferencesRequest(BaseModel):
    user_id: str = Field(default="dev_user", description="用户标识符")
    preferences: dict = Field(..., description="偏好键值对，与现有偏好合并")


@router.get("/preferences")
async def get_preferences(user_id: str = "dev_user") -> dict:
    """读取用户画像偏好。"""
    store = await get_store()
    mm = MemoryManager(store=store)
    profile = await mm.load_episodic(user_id)
    return {"user_id": user_id, "preferences": profile.preferences}


@router.post("/preferences")
async def set_preferences(req: PreferencesRequest) -> dict:
    """写入或更新用户画像偏好（merge 语义，不覆盖未涉及的 key）。"""
    store = await get_store()
    mm = MemoryManager(store=store)
    profile = await mm.load_episodic(req.user_id)
    profile.preferences.update(req.preferences)

    # NOTE:
    # MemoryManager.save_episodic() 在当前阶段仍是 no-op。
    # 这里直接落库，确保 API 的“写入/更新”语义真实生效。
    await store.aput(
        namespace=("profile", req.user_id),
        key="episodic",
        value=profile.model_dump(),
    )
    return {"status": "ok", "user_id": req.user_id, "preferences": profile.preferences}


class ProceduralRequest(BaseModel):
    user_id: str = Field(default="dev_user", description="用户标识符")
    workflows: dict = Field(..., description="工作流键值对，与现有程序记忆合并")


@router.get("/procedural")
async def get_procedural(user_id: str = "dev_user") -> dict:
    """读取用户程序记忆（工作流 SOP）。"""
    store = await get_store()
    mm = MemoryManager(store=store)
    data = await mm.load_procedural(user_id)
    return {"user_id": user_id, "workflows": data.get("workflows", {})}


@router.post("/procedural")
async def set_procedural(req: ProceduralRequest) -> dict:
    """写入或更新程序记忆工作流（merge 语义）。"""
    store = await get_store()
    mm = MemoryManager(store=store)

    # workflow 级 merge：只覆盖同名 workflow，不清空其他已有 workflow
    existing = await mm.load_procedural(req.user_id)
    existing_workflows = existing.get("workflows", {})
    merged_workflows = {**existing_workflows, **req.workflows}
    await mm.save_procedural(req.user_id, {"workflows": merged_workflows})
    data = await mm.load_procedural(req.user_id)
    return {"status": "ok", "user_id": req.user_id, "workflows": data.get("workflows", {})}
