"""Test UserProfile and updated MemoryContext - RED phase."""
import pytest
from pydantic import ValidationError

from app.memory.schemas import UserProfile, MemoryContext


class TestUserProfile:
    """Test UserProfile model (user profile per architecture doc §2.9)."""

    def test_create_user_profile_with_defaults(self):
        """验证创建用户画像使用默认值"""
        profile = UserProfile(user_id="user-123")
        assert profile.user_id == "user-123"
        assert profile.preferences == {}
        assert profile.interaction_count == 0
        assert profile.summary == ""

    def test_user_profile_with_preferences(self):
        """验证带偏好设置的用户画像"""
        profile = UserProfile(
            user_id="user-123",
            preferences={"domain": "legal-tech", "language": "zh"},
            interaction_count=10,
            summary="Legal-tech user focused on contract management"
        )
        assert profile.preferences["domain"] == "legal-tech"
        assert profile.interaction_count == 10
        assert "Legal-tech" in profile.summary

    def test_user_profile_serialization(self):
        """验证用户画像可序列化为 dict"""
        profile = UserProfile(
            user_id="user-123",
            preferences={"theme": "dark"}
        )
        data = profile.model_dump()
        assert data["user_id"] == "user-123"
        assert data["preferences"] == {"theme": "dark"}
        assert data["interaction_count"] == 0

    def test_user_profile_deserialization(self):
        """验证从 dict 创建用户画像"""
        data = {
            "user_id": "user-456",
            "preferences": {"language": "en"},
            "interaction_count": 5,
            "summary": "Test user"
        }
        profile = UserProfile(**data)
        assert profile.user_id == "user-456"
        assert profile.preferences["language"] == "en"


class TestMemoryContextWithUserProfile:
    """Test MemoryContext with UserProfile (per architecture doc §2.9)."""

    def test_create_memory_context_with_empty_profile(self):
        """验证创建带空画像的上下文"""
        ctx = MemoryContext()
        assert ctx.episodic.user_id == ""
        assert ctx.episodic.preferences == {}

    def test_memory_context_with_user_profile(self):
        """验证带用户画像的上下文"""
        profile = UserProfile(
            user_id="user-789",
            preferences={"domain": "finance"}
        )
        ctx = MemoryContext(episodic=profile)
        assert ctx.episodic.user_id == "user-789"
        assert ctx.episodic.preferences["domain"] == "finance"

    def test_memory_context_default_profile(self):
        """验证默认创建空 UserProfile"""
        ctx = MemoryContext()
        assert isinstance(ctx.episodic, UserProfile)
        assert ctx.episodic.interaction_count == 0
