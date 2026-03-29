from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.observability.interrupt_store import InterruptStore


class TestInterruptStore:
    @pytest.mark.asyncio
    async def test_get_interrupt_returns_none_when_expired(self) -> None:
        store_backend = SimpleNamespace(
            aget=AsyncMock(
                return_value=SimpleNamespace(
                    value={
                        "interrupt_id": "expired-1",
                        "status": "pending",
                        "expires_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                    }
                )
            ),
            aput=AsyncMock(),
        )
        store = InterruptStore(store_backend)

        result = await store.get_interrupt("expired-1")

        assert result is None
        store_backend.aput.assert_awaited_once()
        stored_value = store_backend.aput.await_args.kwargs["value"]
        assert stored_value["status"] == "expired"

    @pytest.mark.asyncio
    async def test_get_interrupt_returns_value_when_not_expired(self) -> None:
        payload = {
            "interrupt_id": "active-1",
            "status": "pending",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        store_backend = SimpleNamespace(
            aget=AsyncMock(return_value=SimpleNamespace(value=payload)),
            aput=AsyncMock(),
        )
        store = InterruptStore(store_backend)

        result = await store.get_interrupt("active-1")

        assert result == payload
        store_backend.aput.assert_not_awaited()
