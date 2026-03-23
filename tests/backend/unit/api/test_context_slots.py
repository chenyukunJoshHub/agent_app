"""Tests for GET /session/{session_id}/slots endpoint.

Tests the Slot details API endpoint that returns Slot content
and token counts for each Slot.

Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.skills.manager import SkillManager


@pytest.fixture(autouse=True)
def init_skill_manager(tmp_path):
    """Initialize SkillManager with a temporary skills directory."""
    # Create a temporary skills directory
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a dummy SKILL.md file to avoid errors
    (skills_dir / "example_skill").mkdir()
    (skills_dir / "example_skill" / "SKILL.md").write_text(
        """---
name: Example Skill
status: active
---

# Example Skill

This is an example skill for testing.
"""
    )

    # Initialize SkillManager
    SkillManager.get_instance(skills_dir=str(skills_dir))

    yield

    # Reset after test
    SkillManager.reset_instance()


class TestGetSessionSlots:
    """Test GET /session/{session_id}/slots endpoint"""

    def test_returns_slot_details(self, client: TestClient):
        """Should return slot details for valid session"""
        response = client.get("/session/test-session-123/slots")

        assert response.status_code == 200

        data = response.json()
        assert "session_id" in data
        assert "slots" in data
        assert "total_tokens" in data
        assert "timestamp" in data

    def test_session_id_matches_request(self, client: TestClient):
        """Session ID in response should match request"""
        session_id = "test-session-xyz"
        response = client.get(f"/session/{session_id}/slots")

        data = response.json()
        assert data["session_id"] == session_id

    def test_returns_expected_slots(self, client: TestClient):
        """Should return expected slot names"""
        response = client.get("/session/test-session/slots")

        data = response.json()
        slots = data["slots"]

        slot_names = {slot["name"] for slot in slots}

        # Check for key slots
        expected_slots = {
            "system",
            "skill_protocol",
            "few_shot",
            "output_format",
        }
        assert expected_slots.issubset(slot_names)

    def test_each_slot_has_required_fields(self, client: TestClient):
        """Each slot should have name, display_name, content, tokens, enabled"""
        response = client.get("/session/test-session/slots")

        data = response.json()
        slots = data["slots"]

        for slot in slots:
            assert "name" in slot
            assert "display_name" in slot
            assert "content" in slot
            assert "tokens" in slot
            assert "enabled" in slot
            assert isinstance(slot["tokens"], int)
            assert isinstance(slot["enabled"], bool)
            assert slot["tokens"] >= 0

    def test_total_tokens_matches_sum_of_slot_tokens(self, client: TestClient):
        """Total tokens should be sum of enabled slot tokens"""
        response = client.get("/session/test-session/slots")

        data = response.json()
        slots = data["slots"]

        # Calculate expected total (only enabled slots)
        expected_total = sum(
            slot["tokens"] for slot in slots if slot["enabled"]
        )

        assert data["total_tokens"] == expected_total

    def test_system_slot_has_content(self, client: TestClient):
        """System slot should have content"""
        response = client.get("/session/test-session/slots")

        data = response.json()
        slots = data["slots"]

        system_slot = next((s for s in slots if s["name"] == "system"), None)
        assert system_slot is not None
        assert len(system_slot["content"]) > 0
        assert system_slot["tokens"] > 0
        assert system_slot["enabled"] is True

    def test_few_shot_slot_has_content(self, client: TestClient):
        """Few-shot slot should have static examples"""
        response = client.get("/session/test-session/slots")

        data = response.json()
        slots = data["slots"]

        few_shot_slot = next((s for s in slots if s["name"] == "few_shot"), None)
        assert few_shot_slot is not None
        assert "示例" in few_shot_slot["content"]
        assert few_shot_slot["tokens"] > 0

    def test_timestamp_is_recent(self, client: TestClient):
        """Timestamp should be recent (within last minute)"""
        import time

        response = client.get("/session/test-session/slots")

        data = response.json()
        timestamp = data["timestamp"]

        current_time = time.time()
        # Should be within last minute
        assert current_time - 60 < timestamp <= current_time

    def test_handles_special_session_id_characters(self, client: TestClient):
        """Should handle session IDs with special characters"""
        # Session ID with underscores and numbers
        session_id = "session_123_456"
        response = client.get(f"/session/{session_id}/slots")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_response_format_matches_schema(self, client: TestClient):
        """Response should match expected schema structure"""
        response = client.get("/session/test-session/slots")

        data = response.json()

        # Top-level structure
        assert isinstance(data, dict)
        assert set(data.keys()) == {"session_id", "slots", "total_tokens", "timestamp"}

        # Slots should be a list
        assert isinstance(data["slots"], list)

        # Total tokens should be an integer
        assert isinstance(data["total_tokens"], int)

        # Timestamp should be a float
        assert isinstance(data["timestamp"], float)


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)
