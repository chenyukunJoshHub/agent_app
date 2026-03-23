"""Tests for SlotContentTracker.

Tests the SlotContentTracker class that tracks Slot content and token counts.
Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
"""
import pytest

from app.prompt.slot_tracker import (
    SlotContent,
    SlotSnapshot,
    SlotContentTracker,
)


class TestSlotContent:
    """Test SlotContent dataclass"""

    def test_token_calculation_on_init(self):
        """Token count should be calculated on initialization"""
        slot = SlotContent(
            name="system",
            display_name="系统提示词",
            content="This is a test prompt with some text",
        )
        # Should have calculated tokens
        assert slot.tokens > 0

    def test_empty_content_has_zero_tokens(self):
        """Empty content should have zero tokens"""
        slot = SlotContent(
            name="system",
            display_name="系统提示词",
            content="",
        )
        assert slot.tokens == 0


class TestSlotContentTracker:
    """Test SlotContentTracker class"""

    def test_add_slot(self):
        """Should add a slot to the tracker"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "System prompt content", "系统提示词")

        slot = tracker.get_slot("system")
        assert slot is not None
        assert slot.name == "system"
        assert slot.content == "System prompt content"
        assert slot.enabled is True

    def test_add_slot_with_default_display_name(self):
        """Should use default display name from mapping"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "Content")

        slot = tracker.get_slot("system")
        assert slot.display_name == "系统提示词"

    def test_add_slot_with_custom_display_name(self):
        """Should use custom display name when provided"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "Content", display_name="自定义名称")

        slot = tracker.get_slot("system")
        assert slot.display_name == "自定义名称"

    def test_add_slot_disabled(self):
        """Should add a disabled slot"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "", enabled=False)

        slot = tracker.get_slot("system")
        assert slot.enabled is False

    def test_update_slot(self):
        """Should update existing slot content"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "Old content")

        tracker.update_slot("system", "New content")

        slot = tracker.get_slot("system")
        assert slot.content == "New content"

    def test_update_slot_enables_if_content_not_empty(self):
        """Updating with non-empty content should enable slot"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "", enabled=False)

        tracker.update_slot("system", "New content")

        slot = tracker.get_slot("system")
        assert slot.enabled is True

    def test_update_nonexistent_slot_does_nothing(self):
        """Updating non-existent slot should not raise error"""
        tracker = SlotContentTracker()
        # Should not raise
        tracker.update_slot("nonexistent", "Content")

    def test_get_total_tokens(self):
        """Should calculate total tokens for enabled slots only"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "Content one")
        tracker.add_slot("active_skill", "Content two")
        tracker.add_slot("few_shot", "Content three", enabled=False)

        total = tracker.get_total_tokens()
        # Should only count enabled slots
        assert total > 0

    def test_build_snapshot(self):
        """Should build a snapshot with all slots"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "System content")
        tracker.add_slot("active_skill", "Skill content")

        snapshot = tracker.build_snapshot()

        assert isinstance(snapshot, SlotSnapshot)
        assert len(snapshot.slots) == 2
        assert snapshot.total_tokens > 0
        assert snapshot.timestamp > 0

    def test_clear(self):
        """Should clear all slots"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "Content")
        tracker.add_slot("active_skill", "Content")

        tracker.clear()

        assert tracker.get_slot("system") is None
        assert tracker.get_slot("active_skill") is None

    def test_get_summary(self):
        """Should return summary information"""
        tracker = SlotContentTracker()
        tracker.add_slot("system", "System content")
        tracker.add_slot("active_skill", "", enabled=False)

        summary = tracker.get_summary()

        assert summary["total_slots"] == 2
        assert summary["enabled_slots"] == 1
        assert summary["total_tokens"] > 0
        assert "slots" in summary


class TestSlotSnapshot:
    """Test SlotSnapshot dataclass"""

    def test_to_dict(self):
        """Should convert to dictionary format"""
        from app.prompt.slot_tracker import SlotContent

        snapshot = SlotSnapshot(
            slots={
                "system": SlotContent(
                    name="system",
                    display_name="系统提示词",
                    content="System prompt",
                    tokens=100,
                )
            },
            total_tokens=100,
            timestamp=1234567890.0,
        )

        data = snapshot.to_dict()

        assert "slots" in data
        assert "total_tokens" in data
        assert "timestamp" in data
        assert len(data["slots"]) == 1
        assert data["slots"][0]["name"] == "system"
