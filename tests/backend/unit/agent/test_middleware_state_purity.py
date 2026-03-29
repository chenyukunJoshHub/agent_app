"""Guardrail tests for middleware state mutation patterns."""

from __future__ import annotations

import ast
from pathlib import Path


def _is_state_subscript(node: ast.expr) -> bool:
    """Return True when the node is a `state[...]` subscript expression."""
    return isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "state"


def test_middleware_files_do_not_assign_to_state_subscript() -> None:
    """Middleware should return state patches instead of mutating `state[...]` in-place."""
    repo_root = Path(__file__).resolve().parents[4]
    middleware_dir = repo_root / "backend" / "app" / "agent" / "middleware"
    violations: list[str] = []

    for file_path in sorted(middleware_dir.glob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            else:
                continue

            for target in targets:
                if _is_state_subscript(target):
                    violations.append(f"{file_path}:{node.lineno}")

    assert not violations, (
        "Found in-place state mutation(s) in middleware. "
        "Return a state patch dict instead:\n" + "\n".join(violations)
    )
