"""
Memory Middleware for Long Memory (User Profile).

Phase 21:
- abefore_agent: load episodic/procedural + save episodic baseline
- wrap_model_call: ephemeral injection into request messages
- aafter_agent: profile writeback with rule/llm modes + dirty flag
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.config import settings
from app.llm.factory import llm_factory
from app.memory.schemas import MemoryContext, ProceduralMemory, UserProfile
from app.observability.trace_events import emit_slot_update, emit_trace_event

if TYPE_CHECKING:
    from app.memory.manager import MemoryManager


LEGAL_KEYWORDS = (
    "合同",
    "签署",
    "法务",
    "条款",
    "电子签名",
    "e签宝",
    "legal",
    "contract",
)
STOCK_KEYWORDS = (
    "a股",
    "茅台",
    "股票",
    "基金",
    "量化",
    "stock",
    "equity",
)


class MemoryState(TypedDict, total=False):
    """Middleware state schema per architecture doc §2.5."""

    memory_ctx: MemoryContext
    memory_ctx_baseline: UserProfile


class MemoryMiddleware(AgentMiddleware):
    """Middleware for managing Long Memory (user profiles)."""

    state_schema = MemoryState

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.mm = memory_manager
        logger.info("MemoryMiddleware initialized (Phase21 mode: baseline + dirty + B/C update)")

    @staticmethod
    def _extract_sse_queue(runtime_or_request: Any) -> Any:
        """Extract SSE queue from runtime.context or request.runtime.context."""
        ctx: Any = getattr(runtime_or_request, "context", None)
        if ctx is None:
            rt = getattr(runtime_or_request, "runtime", None)
            ctx = getattr(rt, "context", None)
        return getattr(ctx, "sse_queue", None) if ctx is not None else None

    @staticmethod
    def _extract_user_id(runtime: Any) -> str:
        """Resolve user_id from runtime.context first, then runtime.config fallback."""
        ctx: Any = getattr(runtime, "context", None)
        ctx_user_id = getattr(ctx, "user_id", "") if ctx is not None else ""
        if isinstance(ctx_user_id, str) and ctx_user_id:
            return ctx_user_id

        config = getattr(runtime, "config", None)
        if isinstance(config, dict):
            configurable = config.get("configurable", {})
            if isinstance(configurable, dict):
                uid = configurable.get("user_id", "")
                if isinstance(uid, str):
                    return uid
        return ""

    @staticmethod
    def _extract_turn_text(messages: list[Any]) -> str:
        """Collect recent message text for lightweight preference extraction."""
        parts: list[str] = []
        for msg in messages[-12:]:
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(str(item) for item in content)
            else:
                text = str(content)
            text = text.strip()
            if text:
                parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _detect_language(text: str) -> str | None:
        if not text:
            return None
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[A-Za-z]", text):
            return "en"
        return None

    @staticmethod
    def _detect_domain(text: str) -> str | None:
        if not text:
            return None
        lower = text.lower()
        legal_hits = sum(1 for kw in LEGAL_KEYWORDS if kw in text or kw in lower)
        stock_hits = sum(1 for kw in STOCK_KEYWORDS if kw in text or kw in lower)
        if legal_hits == 0 and stock_hits == 0:
            return None
        return "legal-tech" if legal_hits >= stock_hits else "stock"

    def _apply_rule_updates(self, profile: UserProfile, turn_text: str) -> None:
        """Deterministic rule extraction (方案 B)."""
        domain = self._detect_domain(turn_text)
        if domain:
            profile.preferences["domain"] = domain

        language = self._detect_language(turn_text)
        if language:
            profile.preferences["language"] = language

    def _should_run_llm_extraction(self, interaction_count: int) -> bool:
        """Run C mode extraction every N interactions."""
        if settings.memory_profile_update_mode != "llm":
            return False
        interval = max(1, settings.memory_profile_llm_interval)
        return interaction_count > 0 and (interaction_count % interval == 0)

    @staticmethod
    def _parse_llm_payload(raw: str) -> dict[str, Any]:
        """Parse strict JSON payload from model output."""
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("No JSON object found in LLM output")

        payload = json.loads(raw[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("LLM payload is not an object")

        prefs = payload.get("preferences", {})
        if not isinstance(prefs, dict):
            prefs = {}

        summary = payload.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)

        retain_entries: list[dict[str, Any]] = []
        raw_retain = payload.get("retain", [])
        if isinstance(raw_retain, list):
            for item in raw_retain:
                if not isinstance(item, dict):
                    continue
                kind = str(item.get("type", "")).strip().upper()
                if kind not in {"W", "B", "O", "S"}:
                    continue
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                conf_raw = item.get("confidence", 1.0 if kind != "O" else 0.0)
                try:
                    confidence = float(conf_raw)
                except (TypeError, ValueError):
                    confidence = 0.0

                entry: dict[str, Any] = {
                    "type": kind,
                    "text": text,
                    "confidence": confidence,
                }
                pref_map = item.get("preference")
                if isinstance(pref_map, dict):
                    entry["preference"] = pref_map
                if "key" in item and "value" in item:
                    entry["key"] = str(item["key"])
                    entry["value"] = item["value"]
                retain_entries.append(entry)

        return {
            "preferences": prefs,
            "summary": summary.strip(),
            "retain": retain_entries,
        }

    @staticmethod
    def _format_confidence(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _render_retain_block(self, retain_entries: list[dict[str, Any]], ts: str) -> str:
        """Render Retain lightweight format into summary block."""
        lines: list[str] = []
        for entry in retain_entries:
            kind = str(entry.get("type", "")).upper()
            text = str(entry.get("text", "")).strip()
            if not text:
                continue
            if kind == "W":
                lines.append(f"W @{ts}: {text}")
            elif kind == "B":
                lines.append(f"B @{ts}: {text}")
            elif kind == "S":
                lines.append(f"S @{ts}: {text}")
            elif kind == "O":
                confidence = float(entry.get("confidence", 0.0))
                lines.append(f"O(c={self._format_confidence(confidence)}) @{ts}: {text}")
        return "\n".join(lines)

    def _merge_llm_result(self, profile: UserProfile, llm_payload: dict[str, Any]) -> None:
        """Merge C mode extraction into profile (preferences + summary)."""
        merged_preferences = dict(profile.preferences)

        for key, value in llm_payload.get("preferences", {}).items():
            if isinstance(key, str) and key:
                merged_preferences[key] = value

        threshold = settings.memory_profile_opinion_min_confidence
        retain_entries = llm_payload.get("retain", [])
        if isinstance(retain_entries, list):
            for entry in retain_entries:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("type", "")).upper() != "O":
                    continue
                confidence = float(entry.get("confidence", 0.0))
                if confidence < threshold:
                    continue

                pref_map = entry.get("preference")
                if isinstance(pref_map, dict):
                    for p_key, p_val in pref_map.items():
                        if isinstance(p_key, str) and p_key:
                            merged_preferences[p_key] = p_val
                    continue

                p_key = entry.get("key")
                if isinstance(p_key, str) and p_key:
                    merged_preferences[p_key] = entry.get("value")

        profile.preferences = merged_preferences

        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
        retain_block = self._render_retain_block(retain_entries, ts) if isinstance(retain_entries, list) else ""
        llm_summary = str(llm_payload.get("summary", "")).strip()

        if retain_block and llm_summary:
            profile.summary = f"{retain_block}\n\n{llm_summary}"
        elif retain_block:
            profile.summary = retain_block
        elif llm_summary:
            profile.summary = llm_summary

    async def _extract_profile_with_llm(
        self,
        turn_text: str,
        current_profile: UserProfile,
    ) -> dict[str, Any] | None:
        """Run C mode extraction via LLM; return None on any failure."""
        if not turn_text.strip():
            return None

        try:
            llm = llm_factory()
            system_prompt = (
                "你是用户画像提炼器。仅输出 JSON，不要解释。"
                "JSON schema: {"
                "\"preferences\": object,"
                "\"summary\": string,"
                "\"retain\": ["
                "{\"type\":\"W|B|O|S\",\"text\":string,\"confidence\":number,"
                "\"preference\":object,\"key\":string,\"value\":any}"
                "]}"
            )
            human_prompt = (
                f"当前画像: {current_profile.model_dump_json(ensure_ascii=False)}\n\n"
                f"本轮对话文本:\n{turn_text}\n\n"
                "要求:\n"
                "1) preferences 只包含可落地偏好键值\n"
                "2) retain 使用 W/B/O/S\n"
                "3) O 必须提供 confidence\n"
                "4) 若无可提炼内容，返回空对象字段"
            )

            resp = await llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            )
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
            return self._parse_llm_payload(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"MemoryMiddleware: llm extraction failed, fallback to rule mode: {exc}")
            return None

    async def abefore_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """Hook called at the start of each agent turn."""
        logger.debug("MemoryMiddleware: abefore_agent called")
        sse_queue = self._extract_sse_queue(runtime)
        user_id = self._extract_user_id(runtime)

        await emit_trace_event(
            sse_queue,
            stage="memory",
            step="load_start",
            status="start",
        )

        logger.info("MemoryMiddleware: abefore_agent load_episodic + load_procedural")
        episodic = await self.mm.load_episodic(user_id)
        procedural_data = await self.mm.load_procedural(user_id)
        procedural = (
            ProceduralMemory(workflows=procedural_data.get("workflows", {}))
            if procedural_data
            else ProceduralMemory()
        )

        memory_ctx = MemoryContext(episodic=episodic, procedural=procedural)
        baseline = episodic.model_copy(deep=True)

        await emit_trace_event(
            sse_queue,
            stage="memory",
            step="load_success",
            payload={
                "user_id": user_id,
                "preferences_count": len(episodic.preferences),
            },
        )

        return {
            "memory_ctx": memory_ctx,
            "memory_ctx_baseline": baseline,
        }

    def wrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """Hook called before each LLM invocation (sync version)."""
        import asyncio

        from app.utils.token import count_tokens

        logger.debug("MemoryMiddleware: wrap_model_call called")

        sse_queue = self._extract_sse_queue(request)

        memory_ctx = None
        if request.state and "memory_ctx" in request.state:
            memory_ctx = request.state["memory_ctx"]
        if memory_ctx is None:
            return handler(request)

        parts: dict[str, str] = {}
        if memory_ctx:
            parts = self.mm.build_injection_parts(memory_ctx)
        memory_text = "".join(parts.values())

        raw_messages = getattr(request, "messages", [])
        try:
            messages = list(raw_messages) if raw_messages is not None else []
        except TypeError:
            messages = []
        if memory_text:
            injected_tokens = count_tokens(memory_text)
            last_human_idx = next(
                (i for i in reversed(range(len(messages))) if isinstance(messages[i], HumanMessage)),
                None,
            )
            if last_human_idx is not None:
                original = messages[last_human_idx]
                original_content = (
                    original.content if isinstance(original.content, str) else str(original.content)
                )
                messages[last_human_idx] = HumanMessage(
                    content=memory_text + "\n\n---\n\n" + original_content
                )
            else:
                messages.append(HumanMessage(content=memory_text))

            if sse_queue is not None:
                try:
                    coro = emit_trace_event(
                        sse_queue,
                        stage="memory",
                        step="inject_success",
                        payload={
                            "injected_chars": len(memory_text),
                            "injected_tokens": injected_tokens,
                        },
                    )
                    asyncio.create_task(coro)
                except RuntimeError:
                    coro.close()
        else:
            reason = "no_memory_ctx" if not memory_ctx else "empty_preferences"
            if sse_queue is not None:
                try:
                    coro = emit_trace_event(
                        sse_queue,
                        stage="memory",
                        step="inject_skip",
                        status="skip",
                        payload={"reason": reason},
                    )
                    asyncio.create_task(coro)
                except RuntimeError:
                    coro.close()

        display_names = {p.slot_name: p.display_name for p in self.mm.processors}

        for slot_name, text in parts.items():
            coro = emit_slot_update(
                sse_queue,
                name=slot_name,
                display_name=display_names.get(slot_name, ""),
                tokens=count_tokens(text) if text else 0,
                enabled=bool(text),
                content=text,
            )
            try:
                asyncio.create_task(coro)
            except RuntimeError:
                coro.close()

        if sse_queue is not None:
            try:
                history_tokens = sum(
                    count_tokens(str(m.content or ""))
                    for m in messages
                    if not isinstance(m, SystemMessage)
                )
                coro = emit_slot_update(
                    sse_queue,
                    name="history",
                    display_name="对话历史",
                    tokens=history_tokens,
                    enabled=True,
                )
                asyncio.create_task(coro)
            except RuntimeError:
                coro.close()

        return handler(request.override(messages=messages))

    async def awrap_model_call(
        self, request: Any, handler: Any
    ) -> Any:
        """Hook called before each LLM invocation (async version)."""
        result = self.wrap_model_call(request, handler)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def aafter_agent(
        self, state: Any, runtime: Any
    ) -> dict[str, Any] | None:
        """Hook called at the end of each agent turn."""
        logger.debug("MemoryMiddleware: aafter_agent called")
        sse_queue = self._extract_sse_queue(runtime)
        user_id = self._extract_user_id(runtime)

        memory_ctx = state.get("memory_ctx") if isinstance(state, dict) else None
        if not isinstance(memory_ctx, MemoryContext):
            await emit_trace_event(
                sse_queue,
                stage="memory",
                step="save_skip",
                status="skip",
                payload={"reason": "missing_memory_ctx"},
            )
            return None

        baseline = state.get("memory_ctx_baseline") if isinstance(state, dict) else None
        if not isinstance(baseline, UserProfile):
            baseline = memory_ctx.episodic.model_copy(deep=True)

        updated = memory_ctx.episodic.model_copy(deep=True)
        if not updated.user_id and user_id:
            updated.user_id = user_id

        messages = state.get("messages", []) if isinstance(state, dict) else []
        has_interaction = any(isinstance(m, HumanMessage) for m in messages)
        if has_interaction:
            updated.interaction_count = max(0, updated.interaction_count) + 1

        turn_text = self._extract_turn_text(messages)
        self._apply_rule_updates(updated, turn_text)

        llm_triggered = False
        llm_applied = False
        if self._should_run_llm_extraction(updated.interaction_count):
            llm_triggered = True
            llm_payload = await self._extract_profile_with_llm(turn_text=turn_text, current_profile=updated)
            if llm_payload:
                self._merge_llm_result(updated, llm_payload)
                llm_applied = True

        dirty = updated.model_dump() != baseline.model_dump()

        if not user_id:
            await emit_trace_event(
                sse_queue,
                stage="memory",
                step="save_skip",
                status="skip",
                payload={
                    "reason": "missing_user_id",
                    "mode": settings.memory_profile_update_mode,
                    "llm_triggered": llm_triggered,
                    "llm_applied": llm_applied,
                },
            )
            return None

        if not dirty:
            await emit_trace_event(
                sse_queue,
                stage="memory",
                step="save_skip",
                status="skip",
                payload={
                    "reason": "dirty_false",
                    "mode": settings.memory_profile_update_mode,
                    "llm_triggered": llm_triggered,
                    "llm_applied": llm_applied,
                },
            )
            return None

        await self.mm.save_episodic(user_id=user_id, data=updated)

        await emit_trace_event(
            sse_queue,
            stage="memory",
            step="save_success",
            payload={
                "mode": settings.memory_profile_update_mode,
                "interaction_count": updated.interaction_count,
                "dirty": True,
                "llm_triggered": llm_triggered,
                "llm_applied": llm_applied,
                "preferences_count": len(updated.preferences),
            },
        )

        return None


__all__ = ["MemoryMiddleware", "MemoryState"]
