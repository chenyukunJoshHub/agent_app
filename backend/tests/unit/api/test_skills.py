"""
Unit tests for app.api.skills.

These tests verify the /skills endpoint.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.skills import router as skills_router
from app.skills.models import SkillEntry, SkillSnapshot


class TestSkillsEndpoint:
    """Test GET /skills endpoint."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with skills router."""
        app = FastAPI()
        app.include_router(skills_router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_snapshot(self) -> SkillSnapshot:
        """Create mock skill snapshot."""
        return SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[
                SkillEntry(
                    name="csv-reporter",
                    description="Generate CSV reports from data",
                    file_path="~/skills/csv-reporter/SKILL.md",
                    tools=["web_search"],
                ),
                SkillEntry(
                    name="legal-search",
                    description="Search legal documents",
                    file_path="~/skills/legal-search/SKILL.md",
                    tools=["read_file"],
                ),
            ],
            prompt="<skills>...</skills>",
        )

    def test_get_skills_returns_list(self, client: TestClient, mock_snapshot: SkillSnapshot) -> None:
        """Test that GET /skills returns a list of skills."""
        with patch("app.api.skills.get_skill_manager") as mock_get_manager:
            # Mock SkillManager
            mock_manager = MagicMock()
            mock_manager.build_snapshot.return_value = mock_snapshot
            mock_get_manager.return_value = mock_manager

            # Make request
            response = client.get("/skills/")

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert "skills" in data
            assert isinstance(data["skills"], list)
            assert len(data["skills"]) == 2

    def test_get_skills_includes_required_fields(self, client: TestClient, mock_snapshot: SkillSnapshot) -> None:
        """Test that skills include name, description, file_path, and tools."""
        with patch("app.api.skills.get_skill_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.build_snapshot.return_value = mock_snapshot
            mock_get_manager.return_value = mock_manager

            response = client.get("/skills/")

            assert response.status_code == 200
            data = response.json()
            skill = data["skills"][0]

            # Verify required fields
            assert "name" in skill
            assert "description" in skill
            assert "file_path" in skill
            assert "tools" in skill

    def test_get_skills_serializes_correctly(self, client: TestClient, mock_snapshot: SkillSnapshot) -> None:
        """Test that skills are serialized correctly."""
        with patch("app.api.skills.get_skill_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.build_snapshot.return_value = mock_snapshot
            mock_get_manager.return_value = mock_manager

            response = client.get("/skills/")

            assert response.status_code == 200
            data = response.json()

            # Check first skill
            assert data["skills"][0]["name"] == "csv-reporter"
            assert data["skills"][0]["description"] == "Generate CSV reports from data"
            assert data["skills"][0]["file_path"] == "~/skills/csv-reporter/SKILL.md"
            assert data["skills"][0]["tools"] == ["web_search"]

            # Check second skill
            assert data["skills"][1]["name"] == "legal-search"
            assert data["skills"][1]["description"] == "Search legal documents"
            assert data["skills"][1]["file_path"] == "~/skills/legal-search/SKILL.md"
            assert data["skills"][1]["tools"] == ["read_file"]

    def test_get_skills_empty_list(self, client: TestClient) -> None:
        """Test that GET /skills returns empty list when no skills."""
        with patch("app.api.skills.get_skill_manager") as mock_get_manager:
            # Mock empty snapshot
            empty_snapshot = SkillSnapshot(
                version=1,
                skill_filter=None,
                skills=[],
                prompt="<skills></skills>",
            )
            mock_manager = MagicMock()
            mock_manager.build_snapshot.return_value = empty_snapshot
            mock_get_manager.return_value = mock_manager

            response = client.get("/skills/")

            assert response.status_code == 200
            data = response.json()
            assert data["skills"] == []

    def test_get_skills_handles_manager_error(self, client: TestClient) -> None:
        """Test that GET /skills handles SkillManager errors gracefully."""
        with patch("app.api.skills.get_skill_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.build_snapshot.side_effect = Exception("Scan failed")
            mock_get_manager.return_value = mock_manager

            response = client.get("/skills/")

            # Should return error
            assert response.status_code == 500
            data = response.json()
            assert "error" in data or "detail" in data

    def test_get_skills_endpoint_documentation(self, client: TestClient) -> None:
        """Test that endpoint has proper documentation."""
        with patch("app.api.skills.get_skill_manager"):
            response = client.get("/docs")

            # Just verify docs endpoint is accessible
            # The actual OpenAPI docs are tested by FastAPI internally
            assert response.status_code == 200


class TestSkillResponseModel:
    """Test SkillResponse model."""

    def test_skill_response_from_skill_entry(self) -> None:
        """Test creating SkillResponse from SkillEntry."""
        from app.api.skills import SkillResponse

        entry = SkillEntry(
            name="test-skill",
            description="Test description",
            file_path="~/skills/test/SKILL.md",
            tools=["web_search", "read_file"],
        )

        response = SkillResponse.from_entry(entry)

        assert response.name == "test-skill"
        assert response.description == "Test description"
        assert response.file_path == "~/skills/test/SKILL.md"
        assert response.tools == ["web_search", "read_file"]

    def test_skill_response_json_serialization(self) -> None:
        """Test that SkillResponse can be serialized to JSON."""
        from app.api.skills import SkillResponse

        response = SkillResponse(
            name="test",
            description="Test skill",
            file_path="~/skills/test/SKILL.md",
            tools=["web_search"],
        )

        # Should not raise
        data = response.model_dump()
        assert data["name"] == "test"
        assert data["description"] == "Test skill"
        assert data["file_path"] == "~/skills/test/SKILL.md"
        assert data["tools"] == ["web_search"]
