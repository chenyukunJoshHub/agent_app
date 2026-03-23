"""Test Memory Schemas - RED phase."""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.memory.schemas import MemoryType, EpisodicData, UserProfile, MemoryContext


class TestMemoryType:
    """Test MemoryType enum."""

    def test_memory_type_values(self):
        """验证 MemoryType 枚举值正确"""
        assert MemoryType.EPISODIC == "episodic"
        assert MemoryType.PROCEDURAL == "procedural"
        assert MemoryType.SEMANTIC == "semantic"


class TestEpisodicData:
    """Test EpisodicData model."""

    def test_create_episodic_data_with_required_fields(self):
        """验证创建情景记忆所需字段"""
        data = EpisodicData(
            memory_id="mem-001",
            user_id="user-123",
            session_id="session-456",
            interaction_type="web_search",
            content={"query": "茅台股价", "result": "1600元"},
            created_at=datetime.now()
        )
        assert data.memory_id == "mem-001"
        assert data.user_id == "user-123"
        assert data.importance == 0.5  # 默认值
        assert data.access_count == 0  # 默认值

    def test_episodic_data_importance_validation(self):
        """验证 importance 字段接受 0-1 范围"""
        data = EpisodicData(
            memory_id="mem-002",
            user_id="user-123",
            session_id="session-456",
            interaction_type="send_email",
            content={"recipient": "test@example.com"},
            importance=0.8,
            created_at=datetime.now()
        )
        assert data.importance == 0.8

    def test_episodic_data_missing_required_field(self):
        """验证缺少必需字段时抛出 ValidationError"""
        with pytest.raises(ValidationError):
            EpisodicData(
                memory_id="mem-003",
                user_id="user-123",
                # 缺少 session_id
                interaction_type="web_search",
                content={},
                created_at=datetime.now()
            )


class TestMemoryContext:
    """Test MemoryContext model (updated per architecture doc §2.9)."""

    def test_create_memory_context_with_defaults(self):
        """验证创建用户画像使用默认值"""
        from app.memory.schemas import UserProfile

        ctx = MemoryContext()
        assert ctx.episodic.user_id == ""
        assert ctx.episodic.preferences == {}
        assert ctx.episodic.interaction_count == 0

    def test_memory_context_with_preferences(self):
        """验证带偏好设置的上下文"""
        from app.memory.schemas import UserProfile

        profile = UserProfile(
            user_id="user-123",
            preferences={"language": "zh-CN", "theme": "dark"},
            interaction_count=10,
            summary="Test user"
        )
        ctx = MemoryContext(episodic=profile)
        assert ctx.episodic.preferences["language"] == "zh-CN"
        assert ctx.episodic.interaction_count == 10

    def test_memory_context_default_profile(self):
        """验证默认创建空 UserProfile"""
        ctx = MemoryContext()
        assert isinstance(ctx.episodic, UserProfile)
        assert ctx.episodic.user_id == ""
