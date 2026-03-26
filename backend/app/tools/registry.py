"""Tool Registry for centralized tool management.

Per architecture doc §2.1:
- Provides centralized tool registration via build_tool_registry()
- Returns ToolManager and PolicyEngine for policy enforcement
- ToolRegistry class removed (was dead code)
"""
from typing import List

from langchain_core.tools import BaseTool
from loguru import logger


__all__ = ["build_tool_registry"]


def build_tool_registry(
    enable_hil: bool = False,
) -> tuple[list, "ToolManager", "PolicyEngine"]:
    from app.tools.base import ToolMeta
    from app.tools.csv_analyze import csv_analyze
    from app.tools.fetch import fetch_url
    from app.tools.file import read_file
    from app.tools.manager import ToolManager
    from app.tools.policy import PolicyEngine
    from app.tools.readonly.skill_loader import activate_skill
    from app.tools.search import web_search

    tool_defs = [
        (web_search, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff={"strategy": "exponential", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["network", "search", "readonly"],
        )),
        (fetch_url, ToolMeta(
            effect_class="read",
            allowed_decisions=["ask"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff={"strategy": "exponential", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["network", "fetch", "readonly"],
        )),
        (csv_analyze, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff=None,
            can_parallelize=True,
            audit_tags=["data", "csv", "readonly"],
        )),
        (read_file, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=1,
            timeout_seconds=10,
            backoff=None,
            can_parallelize=True,
            audit_tags=["file", "readonly"],
        )),
        (activate_skill, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=10,
            backoff={"strategy": "fixed", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["skill", "readonly"],
        )),
    ]

    if enable_hil:
        from app.tools.send_email import send_email

        tool_defs.append((send_email, ToolMeta(
            effect_class="external_write",
            requires_hil=True,
            allowed_decisions=["ask", "deny"],
            idempotent=False,
            idempotency_key_fn=lambda args: f"email:{args.get('to', '')}:{args.get('subject', '')}",
            max_retries=0,
            timeout_seconds=30,
            backoff=None,
            can_parallelize=False,
            concurrency_group="external_io",
            permission_key="email.send",
            audit_tags=["network", "email", "external", "write"],
        )))

    tools_list = [tool_fn for tool_fn, _ in tool_defs]
    tool_metas = {tool_fn.name: meta for tool_fn, meta in tool_defs}

    tool_manager = ToolManager(tool_metas)
    policy_engine = PolicyEngine()

    return tools_list, tool_manager, policy_engine
