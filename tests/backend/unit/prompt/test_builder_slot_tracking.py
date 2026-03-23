"""Tests for build_system_prompt with slot tracking.

Tests the enhanced build_system_prompt function that tracks slot content.
"""
import pytest

from app.prompt.builder import build_system_prompt, get_slot_snapshot
from app.skills.models import SkillSnapshot, SkillDefinition, SkillMetadata, SkillStatus
from app.memory.schemas import UserProfile


class TestBuildSystemPromptSlotTracking:
    """Test build_system_prompt with slot tracking"""

    def test_returns_tuple_when_track_slots_true(self):
        """Should return (prompt, snapshot) tuple when track_slots=True"""
        result = build_system_prompt(track_slots=True)

        assert isinstance(result, tuple)
        assert len(result) == 2
        prompt, snapshot = result
        assert isinstance(prompt, str)
        assert snapshot is not None

    def test_returns_string_when_track_slots_false(self):
        """Should return string only when track_slots=False"""
        result = build_system_prompt(track_slots=False)

        assert isinstance(result, str)
        assert not isinstance(result, tuple)

    def test_default_track_slots_is_true(self):
        """Default behavior should track slots"""
        result = build_system_prompt()

        assert isinstance(result, tuple)
        prompt, snapshot = result
        assert len(prompt) > 0

    def test_includes_system_slot(self):
        """Snapshot should include system slot"""
        _, snapshot = build_system_prompt(track_slots=True)

        system_slot = snapshot.slots.get("system")
        assert system_slot is not None
        assert system_slot.name == "system"  # name is the key
        assert system_slot.display_name == "系统提示词（基础）"
        assert system_slot.enabled is True
        assert system_slot.tokens > 0

    def test_includes_tools_slot_when_available(self):
        """Should include tools slot when available_tools provided"""
        _, snapshot = build_system_prompt(
            available_tools=["web_search", "send_email"],
            track_slots=True,
        )

        tools_slot = snapshot.slots.get("tools")
        assert tools_slot is not None
        assert tools_slot.tokens > 0
        assert "web_search" in tools_slot.content or "send_email" in tools_slot.content

    def test_includes_few_shot_slot(self):
        """Should include few_shot slot"""
        _, snapshot = build_system_prompt(track_slots=True)

        few_shot_slot = snapshot.slots.get("few_shot")
        assert few_shot_slot is not None
        assert "示例" in few_shot_slot.content
        assert few_shot_slot.tokens > 0

    def test_includes_episodic_slot_when_provided(self):
        """Should include episodic slot when UserProfile provided"""
        episodic = UserProfile(preferences={"domain": "legal-tech", "language": "zh"})
        _, snapshot = build_system_prompt(episodic=episodic, track_slots=True)

        episodic_slot = snapshot.slots.get("episodic")
        assert episodic_slot is not None
        assert "domain" in episodic_slot.content or "legal-tech" in episodic_slot.content

    def test_includes_skill_registry_when_snapshot_provided(self):
        """Should include skill_registry slot when SkillSnapshot provided"""
        skill_snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[
                SkillDefinition(
                    id="test-skill",
                    name="Test Skill",
                    version="1.0.0",
                    metadata=SkillMetadata(
                        description="Test skill for unit testing",
                        priority=1,
                    ),
                    file_path="/test/skill.md",
                    status=SkillStatus.ACTIVE,
                )
            ],
            prompt="Custom skill prompt",
        )
        _, snapshot = build_system_prompt(
            skill_snapshot=skill_snapshot,
            track_slots=True,
        )

        registry_slot = snapshot.slots.get("skill_registry")
        assert registry_slot is not None
        # Should contain the skill name
        assert "Test Skill" in registry_slot.content or "test" in registry_slot.content

    def test_includes_active_skill_slot_when_content_provided(self):
        """Should include active_skill slot when content provided"""
        active_skill_content = "# Active Skill Content\n\nThis is the active skill."
        _, snapshot = build_system_prompt(
            active_skill_content=active_skill_content,
            track_slots=True,
        )

        active_skill_slot = snapshot.slots.get("active_skill")
        assert active_skill_slot is not None
        assert active_skill_slot.content == active_skill_content

    def test_calculates_total_tokens(self):
        """Should calculate total tokens across all slots"""
        _, snapshot = build_system_prompt(
            available_tools=["web_search"],
            track_slots=True,
        )

        assert snapshot.total_tokens > 0
        # Total should be sum of all enabled slot tokens
        expected_total = sum(
            slot.tokens for slot in snapshot.slots.values() if slot.enabled
        )
        assert snapshot.total_tokens == expected_total

    def test_timestamp_is_set(self):
        """Snapshot should have current timestamp"""
        import time

        before = time.time()
        _, snapshot = build_system_prompt(track_slots=True)
        after = time.time()

        assert before <= snapshot.timestamp <= after


class TestGetSlotSnapshot:
    """Test get_slot_snapshot convenience function"""

    def test_returns_slot_snapshot(self):
        """Should return SlotSnapshot without full prompt"""
        from app.prompt.slot_tracker import SlotSnapshot

        snapshot = get_slot_snapshot()

        assert isinstance(snapshot, SlotSnapshot)
        assert len(snapshot.slots) > 0

    def test_includes_all_slots(self):
        """Should include all default slots"""
        snapshot = get_slot_snapshot()

        # Check for key slots
        expected_slots = ["system", "few_shot", "skill_protocol", "output_format"]
        for slot_name in expected_slots:
            assert slot_name in snapshot.slots
