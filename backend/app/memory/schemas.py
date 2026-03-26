"""Memory data models."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    """Memory type enumeration."""

    EPISODIC = "episodic"  # 情景记忆
    PROCEDURAL = "procedural"  # 程序记忆
    SEMANTIC = "semantic"  # 语义记忆


class EpisodicData(BaseModel):
    """Episodic memory: single interaction record (P2, for future use)."""

    memory_id: str = Field(..., description="Unique memory identifier")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    interaction_type: str = Field(..., description="Type of interaction")
    content: dict[str, Any] = Field(..., description="Interaction content")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score 0-1")
    created_at: datetime = Field(..., description="Creation timestamp")
    access_count: int = Field(default=0, ge=0, description="Number of times accessed")


class UserProfile(BaseModel):
    """User profile for long-term memory (per architecture doc §2.9).

    This represents the user's cross-session profile stored in AsyncPostgresStore.
    Namespace: ("profile", user_id), Key: "episodic"

    Attributes:
        user_id: User identifier
        preferences: User preferences (domain, language, style, etc.)
        interaction_count: Total number of interactions across sessions
        summary: User profile summary
    """

    user_id: str = Field(default="", description="User identifier")
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="User preferences"
    )
    interaction_count: int = Field(default=0, ge=0, description="Total interaction count")
    summary: str = Field(default="", description="User profile summary")


class ProceduralMemory(BaseModel):
    """Procedural memory: workflow SOPs (per architecture doc §2.9).

    Stores named workflow instructions to be injected into LLM prompts.
    Namespace: ("profile", user_id), Key: "procedural"

    Attributes:
        workflows: Mapping of workflow name to instruction text
    """

    workflows: dict[str, str] = Field(
        default_factory=dict, description="Workflow name → SOP instruction"
    )


class MemoryContext(BaseModel):
    """Working memory turn-level cache (per architecture doc §2.9).

    This is created by MemoryMiddleware.abefore_agent and consumed by
    MemoryMiddleware.wrap_model_call for ephemeral injection.

    Attributes:
        episodic: User profile loaded from store
        procedural: Procedural memory loaded from store
    """

    episodic: UserProfile = Field(
        default_factory=UserProfile, description="User profile from long-term memory"
    )
    procedural: ProceduralMemory = Field(
        default_factory=ProceduralMemory, description="Procedural memory from long-term memory"
    )
