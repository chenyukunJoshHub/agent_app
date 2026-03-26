from __future__ import annotations

from app.tools.base import ToolMeta


class ToolManager:
    def __init__(self, tool_metas: dict[str, ToolMeta]):
        self._metas = tool_metas

    def get_meta(self, tool_name: str) -> ToolMeta | None:
        return self._metas.get(tool_name)

    def list_available(self) -> list[str]:
        return list(self._metas.keys())

    def can_retry(self, tool_name: str) -> bool:
        meta = self._metas.get(tool_name)
        return bool(meta and meta.idempotent and meta.max_retries > 0)


__all__ = ["ToolManager"]
