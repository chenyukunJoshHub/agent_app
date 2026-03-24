"""
Unit tests for app.tools.readonly.skill_loader — activate_skill tool.
"""
import pytest

from unittest.mock import patch, Mock

from app.skills.manager import SkillManager


@pytest.fixture
def mock_skill_manager():
    """Fixture that provides a mocked SkillManager."""
    # Create a mock instance
    mock_manager = Mock(spec=SkillManager)

    # Mock read_skill_content to return sample content
    mock_manager.read_skill_content.return_value = "# Test Skill Content\n\nInstructions..."

    # Mock scan to do nothing
    mock_manager.scan.return_value = None

    return mock_manager


@pytest.fixture
def monkeypatch_skill_manager(monkeypatch, mock_skill_manager):
    """Fixture that monkeypatches SkillManager.get_instance to return mock."""
    # Create a singleton-style mock
    instance_mock = Mock(return_value=mock_skill_manager)

    # Monkeypatch get_instance
    monkeypatch.setattr("app.skills.manager.SkillManager.get_instance", instance_mock)

    yield

    # Cleanup
    monkeypatch.undo()


class TestActivateSkillExisting:
    def test_returns_skill_content(self, monkeypatch_skill_manager):
        """Test that activate_skill returns skill content."""
        from app.tools.readonly.skill_loader import activate_skill

        result = activate_skill.invoke({"name": "test-skill"})
        assert "Test Skill Content" in result
        assert "Instructions" in result

    def test_scans_skills(self, monkeypatch_skill_manager):
        """Test that activate_skill calls scan()."""
        from app.tools.readonly.skill_loader import activate_skill

        activate_skill.invoke({"name": "test-skill"})
        # Verify scan was called
        from app.skills.manager import SkillManager
        SkillManager.get_instance().scan.assert_called_once()


class TestActivateSkillMissing:
    def test_returns_error_with_available_list(self, monkeypatch_skill_manager):
        """Test that activate_skill returns error for missing skill."""
        from app.tools.readonly.skill_loader import activate_skill

        # Set up mock to return error message for missing skill
        from app.skills.manager import SkillManager
        SkillManager.get_instance().read_skill_content.return_value = "Error: skill 'nonexistent-skill' not found. Available: [test-skill]"

        result = activate_skill.invoke({"name": "nonexistent-skill"})
        assert "Error:" in result
        assert "not found" in result
        assert "nonexistent-skill" in result
        assert "Available:" in result

    def test_shows_available_skills_in_error(self, monkeypatch_skill_manager):
        """Test that error message shows available skills."""
        from app.tools.readonly.skill_loader import activate_skill

        # Set up mock to return error message
        from app.skills.manager import SkillManager
        SkillManager.get_instance().read_skill_content.return_value = "Error: skill 'nonexistent-skill' not found. Available: [test-skill]"

        result = activate_skill.invoke({"name": "nonexistent-skill"})
        assert "Available:" in result
