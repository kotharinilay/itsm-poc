"""Import-boundary tests.

The full rule set arrives at Stage 2 (T036). This file exists now, with the one assertion
that can be made against a Stage 1 tree, so the category is wired into CI from the start
rather than appearing later and passing trivially on its first run.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

DOMAIN = Path(__file__).resolve().parents[2] / "src" / "ragcore" / "domain"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_imports_nothing_outside_the_standard_library() -> None:
    """``domain/`` may import only the standard library — no framework, no adapter, no provider."""
    allowed = sys.stdlib_module_names | {"ragcore", "__future__"}
    for module in DOMAIN.rglob("*.py"):
        offenders = _imported_roots(module) - allowed
        assert not offenders, (
            f"{module.name} imports outside the standard library: {sorted(offenders)}"
        )
