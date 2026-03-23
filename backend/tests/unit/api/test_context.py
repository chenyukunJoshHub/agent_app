"""
Unit tests for GET /session/{id}/context endpoint.

Tests the token budget state retrieval endpoint.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.context import router as context_router
from app.prompt.budget import TokenBudget


class TestGetSessionContext:
    """Test GET /session/{session_id}/context endpoint."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test app with context router."""
        app = FastAPI()
        app.include_router(context_router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_token_budget(self) -> TokenBudget:
        """Create mock token budget."""
        return TokenBudget()

    def test_get_session_context_returns_budget_state(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that GET /session/{id}/context returns token budget state."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            # Make request
            response = client.get("/session/test-session-123/context")

            # Assert response
            assert response.status_code == 200
            data = response.json()

            # Verify required fields
            assert "session_id" in data
            assert "token_budget" in data
            assert data["session_id"] == "test-session-123"

    def test_get_session_context_includes_model_specs(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that context includes model specifications."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            response = client.get("/session/test-session-456/context")

            assert response.status_code == 200
            data = response.json()

            # Check model specs
            budget = data["token_budget"]
            assert "model_context_window" in budget
            assert "working_budget" in budget
            assert budget["model_context_window"] == 200_000
            assert budget["working_budget"] == 32_768

    def test_get_session_context_includes_slot_allocations(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that context includes slot allocations."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            response = client.get("/session/test-session-789/context")

            assert response.status_code == 200
            data = response.json()

            # Check slot allocations
            budget = data["token_budget"]
            assert "slots" in budget
            slots = budget["slots"]

            # Verify fixed slots
            assert "system" in slots
            assert "active_skill" in slots
            assert "episodic" in slots
            assert "tools" in slots

            # Verify elastic slot
            assert "history" in slots

    def test_get_session_context_includes_usage_metrics(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that context includes usage metrics."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            response = client.get("/session/test-session-abc/context")

            assert response.status_code == 200
            data = response.json()

            # Check usage metrics
            budget = data["token_budget"]
            assert "usage" in budget
            usage = budget["usage"]

            assert "total_used" in usage
            assert "total_remaining" in usage
            assert "input_budget" in usage
            assert "output_reserve" in usage

    def test_get_session_context_calculates_remaining_budget(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that remaining budget is calculated correctly."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            response = client.get("/session/test-session-xyz/context")

            assert response.status_code == 200
            data = response.json()

            budget = data["token_budget"]
            usage = budget["usage"]

            # Verify calculation: remaining = working_budget - used
            # For P0, used should be 0 (no actual session state tracking yet)
            expected_remaining = budget["working_budget"]
            assert usage["total_remaining"] == expected_remaining

    def test_get_session_context_handles_missing_session(
        self, client: TestClient
    ) -> None:
        """Test that endpoint handles missing session gracefully."""
        # For P0, we return default budget even for non-existent sessions
        # (since we don't have persistent session state yet)
        response = client.get("/session/non-existent-session/context")

        # Should still return 200 with default budget
        assert response.status_code == 200
        data = response.json()
        assert "token_budget" in data

    def test_get_session_context_response_format(
        self, client: TestClient, mock_token_budget: TokenBudget
    ) -> None:
        """Test that response follows expected format."""
        with patch("app.api.context.DEFAULT_BUDGET", mock_token_budget):
            response = client.get("/session/test-session-format/context")

            assert response.status_code == 200
            data = response.json()

            # Verify top-level structure
            assert isinstance(data, dict)
            assert set(data.keys()) == {"session_id", "token_budget"}

            # Verify token_budget structure
            budget = data["token_budget"]
            assert isinstance(budget, dict)
            assert set(budget.keys()) >= {
                "model_context_window",
                "working_budget",
                "slots",
                "usage",
            }


class TestContextResponseModel:
    """Test ContextResponse model."""

    def test_context_response_model_structure(self) -> None:
        """Test that ContextResponse has correct structure."""
        from app.api.context import ContextResponse, SlotAllocation, UsageMetrics

        # Create usage metrics
        usage = UsageMetrics(
            total_used=0,
            total_remaining=32768,
            input_budget=24576,
            output_reserve=8192,
        )

        # Create slot allocations
        slots = SlotAllocation(
            system=2000,
            active_skill=0,
            few_shot=0,
            rag=0,
            episodic=500,
            procedural=0,
            tools=1200,
            history=21068,
        )

        # Create response
        response = ContextResponse(
            session_id="test-session",
            token_budget={
                "model_context_window": 200000,
                "working_budget": 32768,
                "slots": slots.model_dump(),
                "usage": usage.model_dump(),
            },
        )

        assert response.session_id == "test-session"
        assert response.token_budget["model_context_window"] == 200000

    def test_context_response_json_serialization(self) -> None:
        """Test that ContextResponse can be serialized to JSON."""
        from app.api.context import ContextResponse, SlotAllocation, UsageMetrics

        usage = UsageMetrics(
            total_used=0,
            total_remaining=32768,
            input_budget=24576,
            output_reserve=8192,
        )

        slots = SlotAllocation(
            system=2000,
            active_skill=0,
            few_shot=0,
            rag=0,
            episodic=500,
            procedural=0,
            tools=1200,
            history=21068,
        )

        response = ContextResponse(
            session_id="test",
            token_budget={
                "model_context_window": 200000,
                "working_budget": 32768,
                "slots": slots.model_dump(),
                "usage": usage.model_dump(),
            },
        )

        # Should not raise
        data = response.model_dump()
        assert data["session_id"] == "test"
        assert "token_budget" in data
