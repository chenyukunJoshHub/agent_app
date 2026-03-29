"""
Integration tests for /chat and /chat/resume API endpoints.

These tests validate current API contracts:
- GET /chat (SSE streaming)
- POST /chat/resume (HIL resume via native Command payload)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.types import Command

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _fake_done_stream(*args: Any, **kwargs: Any):
    """Yield one deterministic SSE done event."""
    yield "event: done\ndata: {\"answer\": \"ok\"}\n\n"


class _NotFoundInterruptStore:
    async def get_interrupt(self, interrupt_id: str) -> None:
        return None


class _ProcessedInterruptStore:
    async def get_interrupt(self, interrupt_id: str) -> dict[str, Any]:
        return {"status": "confirmed"}


class _PendingInterruptStore:
    async def get_interrupt(self, interrupt_id: str) -> dict[str, Any]:
        return {
            "status": "pending",
            "tool_name": "send_email",
            "tool_args": {
                "to": "resume@example.com",
                "subject": "Resume Subject",
                "body": "Resume Body",
            },
        }

    async def update_interrupt_status(self, interrupt_id: str, status: str) -> None:
        return None


class _FakeState:
    values = {"messages": []}


class _CaptureInputAgent:
    def __init__(self, sink: list[Any]) -> None:
        self._sink = sink

    async def astream(self, input_data: Any, *args: Any, **kwargs: Any):
        self._sink.append(input_data)
        if False:
            yield None

    async def aget_state(self, config: dict[str, Any]) -> _FakeState:
        return _FakeState()


class TestChatEndpoint:
    """Test GET /chat endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_root_endpoint(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, async_client: AsyncClient) -> None:
        with patch("app.api.chat._run_agent_stream", new=_fake_done_stream):
            response = await async_client.get(
                "/chat",
                params={
                    "message": "你好",
                    "session_id": "test_session",
                    "user_id": "test_user",
                },
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert response.headers.get("X-Accel-Buffering") == "no"
        assert "event: done" in response.text

    @pytest.mark.asyncio
    async def test_chat_request_validation(self, async_client: AsyncClient) -> None:
        # Missing message
        response = await async_client.get(
            "/chat",
            params={"session_id": "test_session", "user_id": "test_user"},
        )
        assert response.status_code == 422

        # Missing session_id
        response = await async_client.get(
            "/chat",
            params={"message": "test", "user_id": "test_user"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_default_user_id(self, async_client: AsyncClient) -> None:
        with patch("app.api.chat._run_agent_stream", new=_fake_done_stream):
            response = await async_client.get(
                "/chat",
                params={
                    "message": "test",
                    "session_id": "test_session",
                },
            )

        assert response.status_code == 200


class TestChatResumeEndpoint:
    """Test POST /chat/resume endpoint."""

    @pytest.mark.asyncio
    async def test_resume_interrupt_not_found(self, async_client: AsyncClient) -> None:
        with patch(
            "app.observability.interrupt_store.get_interrupt_store",
            new=AsyncMock(return_value=_NotFoundInterruptStore()),
        ):
            response = await async_client.post(
                "/chat/resume",
                json={
                    "session_id": "test_session",
                    "user_id": "test_user",
                    "interrupt_id": "not-found",
                    "approved": True,
                },
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "event: error" in response.text
        assert "不存在或已过期" in response.text

    @pytest.mark.asyncio
    async def test_resume_interrupt_already_processed(self, async_client: AsyncClient) -> None:
        with patch(
            "app.observability.interrupt_store.get_interrupt_store",
            new=AsyncMock(return_value=_ProcessedInterruptStore()),
        ):
            response = await async_client.post(
                "/chat/resume",
                json={
                    "session_id": "test_session",
                    "user_id": "test_user",
                    "interrupt_id": "already-processed",
                    "approved": True,
                },
            )

        assert response.status_code == 200
        assert "event: error" in response.text
        assert "中断已被处理" in response.text

    @pytest.mark.asyncio
    async def test_resume_approve_uses_native_command(self, async_client: AsyncClient) -> None:
        call_inputs: list[Any] = []

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=_PendingInterruptStore()),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=_CaptureInputAgent(call_inputs)),
            ),
        ):
            response = await async_client.post(
                "/chat/resume",
                json={
                    "session_id": "test_session",
                    "user_id": "test_user",
                    "interrupt_id": "interrupt-approve",
                    "approved": True,
                },
            )

        assert response.status_code == 200
        assert "event: hil_resolved" in response.text
        assert len(call_inputs) == 1
        assert isinstance(call_inputs[0], Command)
        payload = call_inputs[0].resume["interrupt-approve"]
        assert payload["decisions"][0]["type"] == "approve"

    @pytest.mark.asyncio
    async def test_resume_reject_uses_native_command(self, async_client: AsyncClient) -> None:
        call_inputs: list[Any] = []

        with (
            patch(
                "app.observability.interrupt_store.get_interrupt_store",
                new=AsyncMock(return_value=_PendingInterruptStore()),
            ),
            patch(
                "app.api.chat.create_react_agent",
                new=AsyncMock(return_value=_CaptureInputAgent(call_inputs)),
            ),
        ):
            response = await async_client.post(
                "/chat/resume",
                json={
                    "session_id": "test_session",
                    "user_id": "test_user",
                    "interrupt_id": "interrupt-reject",
                    "approved": False,
                },
            )

        assert response.status_code == 200
        assert "event: hil_resolved" in response.text
        assert len(call_inputs) == 1
        assert isinstance(call_inputs[0], Command)
        payload = call_inputs[0].resume["interrupt-reject"]
        assert payload["decisions"][0]["type"] == "reject"


class TestChatSessionGrantsEndpoint:
    @pytest.mark.asyncio
    async def test_get_session_grants_returns_current_grants(self, async_client: AsyncClient) -> None:
        with patch(
            "app.api.chat.get_session_granted_tools",
            new=AsyncMock(return_value=["send_email"]),
        ):
            response = await async_client.get(
                "/chat/session-grants",
                params={"session_id": "test_session"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": "test_session",
            "granted_tools": ["send_email"],
        }

    @pytest.mark.asyncio
    async def test_revoke_session_grant_returns_remaining_tools(self, async_client: AsyncClient) -> None:
        with patch(
            "app.api.chat.revoke_session_tool_access",
            new=AsyncMock(return_value=[]),
        ) as revoke_mock:
            response = await async_client.post(
                "/chat/session-grants/revoke",
                json={
                    "session_id": "test_session",
                    "user_id": "test_user",
                    "tool_name": "send_email",
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "session_id": "test_session",
            "revoked_tool": "send_email",
            "granted_tools": [],
        }
        revoke_mock.assert_awaited_once_with("test_session", "send_email")


class TestChatCORS:
    @pytest.mark.asyncio
    async def test_cors_headers(self, async_client: AsyncClient) -> None:
        response = await async_client.options(
            "/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers
