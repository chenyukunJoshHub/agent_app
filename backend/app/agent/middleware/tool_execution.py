from __future__ import annotations

import asyncio
import json
from inspect import isawaitable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.tools.base import ToolMeta
from app.tools.idempotency import IdempotencyStore
from app.tools.manager import ToolManager


class ToolExecutionMiddleware(AgentMiddleware):
    """Runtime governance for retries, idempotency, and error normalization."""

    def __init__(
        self,
        tool_manager: ToolManager,
        idempotency_store: IdempotencyStore | None = None,
    ) -> None:
        self.tool_manager = tool_manager
        self.idempotency_store = idempotency_store or IdempotencyStore()

    @staticmethod
    def _extract_thread_id(request: Any) -> str:
        runtime = getattr(request, "runtime", None)
        config = getattr(runtime, "config", {}) or {}
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        thread_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
        return thread_id if isinstance(thread_id, str) else ""

    @staticmethod
    def _build_idempotency_key(
        thread_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        meta: ToolMeta,
    ) -> str:
        if meta.idempotency_key_fn:
            generated = meta.idempotency_key_fn(tool_args)
            if generated is not None:
                return f"{thread_id}:{tool_name}:{generated}"
        try:
            stable_args = json.dumps(tool_args, ensure_ascii=False, sort_keys=True)
        except TypeError:
            stable_args = str(tool_args)
        return f"{thread_id}:{tool_name}:{stable_args}"

    @staticmethod
    def _skipped_message(tool_name: str, tool_call_id: str, idempotency_key: str) -> ToolMessage:
        return ToolMessage(
            content=json.dumps(
                {
                    "success": True,
                    "skipped": True,
                    "reason": "idempotent_replay",
                    "idempotency_key": idempotency_key,
                },
                ensure_ascii=False,
            ),
            name=tool_name,
            tool_call_id=tool_call_id,
            status="success",
        )

    @staticmethod
    def _error_message(tool_name: str, tool_call_id: str, error: Exception) -> ToolMessage:
        return ToolMessage(
            content=str(error),
            name=tool_name,
            tool_call_id=tool_call_id,
            status="error",
        )

    @staticmethod
    async def _sleep_for_attempt(meta: ToolMeta, attempt: int) -> None:
        if not meta.backoff:
            return
        base_seconds = float(meta.backoff.get("base_seconds", 0))
        if base_seconds <= 0:
            return
        strategy = str(meta.backoff.get("strategy", "fixed"))
        if strategy == "exponential":
            delay = base_seconds * (2 ** max(0, attempt - 1))
        else:
            delay = base_seconds
        await asyncio.sleep(delay)

    async def awrap_tool_call(self, request: Any, handler: Any) -> ToolMessage | Any:
        tool_call = request.tool_call
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]
        meta = self.tool_manager.get_meta(tool_name) or ToolMeta(effect_class="read")

        idempotency_key: str | None = None
        if meta.idempotent:
            idempotency_key = self._build_idempotency_key(
                self._extract_thread_id(request),
                tool_name,
                tool_args,
                meta,
            )
            if self.idempotency_store.check_and_mark(idempotency_key):
                return self._skipped_message(tool_name, tool_call_id, idempotency_key)

        attempts = 1 + max(0, meta.max_retries if meta.idempotent else 0)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                result = handler(request)
                if isawaitable(result):
                    result = await result
                return result
            except Exception as error:  # noqa: BLE001
                last_error = error
                if attempt >= attempts:
                    break
                await self._sleep_for_attempt(meta, attempt)

        if idempotency_key:
            self.idempotency_store.discard(idempotency_key)
        assert last_error is not None
        return self._error_message(tool_name, tool_call_id, last_error)
