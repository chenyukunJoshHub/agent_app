"""Test MemoryManager P0 methods - RED phase."""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from app.memory.manager import MemoryManager
from app.memory.schemas import UserProfile, MemoryContext


@pytest.fixture
def mock_store():
    """Mock AsyncPostgresStore."""
    store = MagicMock()
    store.aput = AsyncMock()
    store.aget = AsyncMock()
    store.adelete = AsyncMock()
    return store


@pytest.fixture
def memory_manager(mock_store):
    """Create MemoryManager instance."""
    return MemoryManager(store=mock_store)


class TestMemoryManagerP0:
    """Test MemoryManager P0 implementation per architecture doc §2.4."""

    def test_init_with_store(self, memory_manager, mock_store):
        """验证 MemoryManager 用 store 初始化"""
        assert memory_manager.store == mock_store

    @pytest.mark.asyncio
    async def test_load_episodic_returns_empty_profile_when_no_store_data(
        self, memory_manager, mock_store
    ):
        """P0: store 返回 None 时返回空 UserProfile"""
        # 模拟 store 返回 None（没有保存的画像）
        mock_store.aget.return_value = None

        profile = await memory_manager.load_episodic("user-123")

        assert isinstance(profile, UserProfile)
        assert profile.user_id == ""
        assert profile.preferences == {}
        assert profile.interaction_count == 0

        # 验证调用了正确的 namespace 和 key
        mock_store.aget.assert_called_once_with(
            namespace=("profile", "user-123"), key="episodic"
        )

    @pytest.mark.asyncio
    async def test_load_episodic_returns_profile_from_store(
        self, memory_manager, mock_store
    ):
        """P0: 从 store 加载保存的用户画像"""
        # 模拟 store 返回保存的画像
        stored_data = {
            "user_id": "user-456",
            "preferences": {"domain": "legal-tech", "language": "zh"},
            "interaction_count": 10,
            "summary": "Legal-focused user"
        }
        mock_item = Mock()
        mock_item.value = stored_data
        mock_store.aget.return_value = mock_item

        profile = await memory_manager.load_episodic("user-456")

        assert profile.user_id == "user-456"
        assert profile.preferences["domain"] == "legal-tech"
        assert profile.interaction_count == 10

    @pytest.mark.asyncio
    async def test_save_episodic_persists_profile(self, memory_manager, mock_store):
        """save_episodic 应写入 store.aput。"""
        profile = UserProfile(
            user_id="user-789", preferences={"test": "value"}, interaction_count=1
        )

        await memory_manager.save_episodic("user-789", profile)

        mock_store.aput.assert_called_once_with(
            namespace=("profile", "user-789"),
            key="episodic",
            value=profile.model_dump(),
        )

    @pytest.mark.asyncio
    async def test_save_episodic_overwrites_existing_data(self, memory_manager, mock_store):
        """同一 user_id 重复写入时，后写值应成为最新值。"""
        first = UserProfile(user_id="user-123", preferences={"language": "en"}, interaction_count=1)
        second = UserProfile(user_id="user-123", preferences={"language": "zh"}, interaction_count=2)

        await memory_manager.save_episodic("user-123", first)
        await memory_manager.save_episodic("user-123", second)

        assert mock_store.aput.call_count == 2
        assert mock_store.aput.call_args.kwargs["namespace"] == ("profile", "user-123")
        assert mock_store.aput.call_args.kwargs["key"] == "episodic"
        assert mock_store.aput.call_args.kwargs["value"]["preferences"]["language"] == "zh"

    def test_build_ephemeral_prompt_with_empty_preferences(self, memory_manager):
        """空偏好时返回空字符串"""
        ctx = MemoryContext(episodic=UserProfile(user_id="user-123"))

        prompt = memory_manager.build_ephemeral_prompt(ctx)

        assert prompt == ""

    def test_build_ephemeral_prompt_with_preferences(self, memory_manager):
        """有偏好时构建注入文本"""
        profile = UserProfile(
            user_id="user-456",
            preferences={"domain": "legal-tech", "language": "zh", "style": "formal"},
        )
        ctx = MemoryContext(episodic=profile)

        prompt = memory_manager.build_ephemeral_prompt(ctx)

        assert "[用户画像]" in prompt
        assert "domain: legal-tech" in prompt
        assert "language: zh" in prompt
        assert "style: formal" in prompt

    def test_build_ephemeral_prompt_format(self, memory_manager):
        """验证生成格式符合架构文档 §2.4"""
        profile = UserProfile(
            user_id="user-789", preferences={"theme": "dark", "role": "admin"}
        )
        ctx = MemoryContext(episodic=profile)

        prompt = memory_manager.build_ephemeral_prompt(ctx)

        # 格式：每行一个偏好，缩进两个空格
        lines = prompt.strip().split("\n")
        assert lines[0] == "[用户画像]"
        assert "  theme: dark" in prompt
        assert "  role: admin" in prompt
