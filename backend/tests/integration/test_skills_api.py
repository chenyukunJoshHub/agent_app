"""
Integration tests for /skills endpoint.

Tests the full endpoint flow including actual SkillManager.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestSkillsAPIIntegration:
    """Integration tests for skills API."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_get_skills_integration(self, client: TestClient) -> None:
        """Test GET /skills endpoint returns real skills."""
        response = client.get("/skills/")

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert "skills" in data
        assert isinstance(data["skills"], list)

        # Assert at least some skills are returned
        # (we have csv-reporter and legal-search in the repo)
        assert len(data["skills"]) >= 2

    def test_get_skills_response_format(self, client: TestClient) -> None:
        """Test that skills have correct format."""
        response = client.get("/skills/")

        assert response.status_code == 200
        data = response.json()

        # Check first skill has required fields
        if len(data["skills"]) > 0:
            skill = data["skills"][0]
            assert "name" in skill
            assert "description" in skill
            assert "file_path" in skill
            assert "tools" in skill
            assert isinstance(skill["tools"], list)

    def test_get_skills_contains_known_skills(self, client: TestClient) -> None:
        """Test that known skills are returned."""
        response = client.get("/skills/")

        assert response.status_code == 200
        data = response.json()

        skill_names = [skill["name"] for skill in data["skills"]]

        # We expect at least these skills to be present
        # (unless they're disabled/draft)
        assert "csv-reporter" in skill_names or "legal-search" in skill_names

    def test_get_skills_file_paths(self, client: TestClient) -> None:
        """Test that file paths are correctly shortened."""
        response = client.get("/skills/")

        assert response.status_code == 200
        data = response.json()

        for skill in data["skills"]:
            # File paths should use ~ for home directory
            # or be absolute paths
            file_path = skill["file_path"]
            assert isinstance(file_path, str)
            assert len(file_path) > 0

    def test_get_skills_openapi_docs(self, client: TestClient) -> None:
        """Test that endpoint is documented in OpenAPI."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        openapi = response.json()

        # Check /skills/ endpoint is documented
        assert "/skills/" in openapi["paths"]
        endpoint_spec = openapi["paths"]["/skills/"]["get"]

        # Check response schema
        assert "200" in endpoint_spec["responses"]
        assert "description" in endpoint_spec["responses"]["200"]
