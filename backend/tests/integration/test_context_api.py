"""
Integration tests for GET /session/{id}/context endpoint.

Tests the full endpoint flow including actual TokenBudget.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestContextAPIIntegration:
    """Integration tests for session context API."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_get_session_context_integration(self, client: TestClient) -> None:
        """Test GET /session/{id}/context endpoint returns real budget state."""
        response = client.get("/session/test-session-123/context")

        # Assert response status
        assert response.status_code == 200

        # Assert response structure
        data = response.json()
        assert "session_id" in data
        assert "token_budget" in data
        assert data["session_id"] == "test-session-123"

    def test_get_session_context_budget_values(self, client: TestClient) -> None:
        """Test that budget values match TokenBudget configuration."""
        response = client.get("/session/integration-test/context")

        assert response.status_code == 200
        data = response.json()

        # Check model specs
        budget = data["token_budget"]
        assert budget["model_context_window"] == 200_000
        assert budget["working_budget"] == 32_768

        # Check slots
        slots = budget["slots"]
        assert slots["system"] == 2000
        assert slots["episodic"] == 500
        assert slots["tools"] == 1200
        # history = input_budget - (system + active_skill + few_shot + rag + episodic + procedural + tools)
        # history = 24576 - (2000 + 0 + 0 + 0 + 500 + 0 + 1200) = 20876
        assert slots["history"] == 20876

        # Check usage
        usage = budget["usage"]
        assert usage["input_budget"] == 24576  # 32768 - 8192
        assert usage["output_reserve"] == 8192

    def test_get_session_context_different_sessions(self, client: TestClient) -> None:
        """Test that endpoint works for different session IDs."""
        session_ids = ["session-1", "session-2", "session-abc", "session-xyz"]

        for session_id in session_ids:
            response = client.get(f"/session/{session_id}/context")
            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == session_id

    def test_get_session_context_openapi_docs(self, client: TestClient) -> None:
        """Test that endpoint is documented in OpenAPI."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        openapi = response.json()

        # Check /session/{session_id}/context endpoint is documented
        path = "/session/{session_id}/context"
        assert path in openapi["paths"]
        endpoint_spec = openapi["paths"][path]["get"]

        # Check response schema
        assert "200" in endpoint_spec["responses"]
        assert "description" in endpoint_spec["responses"]["200"]

        # Check parameters
        params = endpoint_spec.get("parameters", [])
        assert len(params) == 1
        assert params[0]["name"] == "session_id"
        assert params[0]["in"] == "path"

    def test_get_session_context_response_headers(self, client: TestClient) -> None:
        """Test that response has correct headers."""
        response = client.get("/session/test-session/context")

        assert response.status_code == 200
        # Check content type
        assert response.headers["content-type"] == "application/json"
