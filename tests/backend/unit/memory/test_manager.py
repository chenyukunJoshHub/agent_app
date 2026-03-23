"""Test MemoryManager - RED phase."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.memory.manager import MemoryManager
from app.memory.schemas import EpisodicData


@pytest.fixture
def mock_store():
    """Mock AsyncPostgresStore."""
    store = MagicMock()
    store.aset = AsyncMock()
    store.aget = AsyncMock()
    store.adelete = AsyncMock()
    return store


@pytest.fixture
def memory_manager(mock_store):
    """Create MemoryManager instance."""
    return MemoryManager(store=mock_store)


class TestMemoryManager:
    """Test MemoryManager P0 implementation."""

    def test_init_with_store(self, memory_manager, mock_store):
        """验证 MemoryManager 用 store 初始化"""
        assert memory_manager.store == mock_store

    @pytest.mark.asyncio
    async def test_get_user_context_returns_none_p0(self, memory_manager, mock_store):
        """P0: get_user_context 返回 None（空实现）"""
        # Mock store 返回 None
        mock_store.aget.return_value = None

        ctx = await memory_manager.get_user_context("user-123")
        # P0: 返回 None 因为空的 UserProfile 没有 user_id
        assert ctx is None

    @pytest.mark.asyncio
    async def test_update_context_is_noop_p0(self, memory_manager):
        """P0: update_context 空操作，不抛异常"""
        # 不应该抛出任何异常
        await memory_manager.update_context("user-123", {"interaction_count": 1})
        # store 不应该被调用（P0 空实现）
        assert memory_manager.store.aset.call_count == 0

    @pytest.mark.asyncio
    async def test_add_episodic_is_noop_p0(self, memory_manager):
        """P0: add_episodic 空操作，不抛异常"""
        data = EpisodicData(
            memory_id="mem-001",
            user_id="user-123",
            session_id="session-456",
            interaction_type="web_search",
            content={"query": "test"},
            created_at=datetime.now()
        )
        # 不应该抛出任何异常
        await memory_manager.add_episodic(data)
        # store 不应该被调用（P0 空实现）
        assert memory_manager.store.aset.call_count == 0
