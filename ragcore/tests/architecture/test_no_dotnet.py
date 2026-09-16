"""The cross-deployable rule, asserted from inside RagCore (T037).

RagCore and the .NET monolith have **no application-level dependency in either direction** — no API
call, no library reference, no deployment coupling (ADR-0001). They meet at exactly two places:
PostgreSQL, through versioned views RagCore owns, and Service Bus, through opaque triggers.

``build/scripts/check-boundaries.sh`` checks the same rule over the whole tree.
``dotnet/tests/Synthia.ArchitectureTests`` checks it from the other side. All three exist because
they fail differently, and because this boundary has no compiler to catch a breach: there is
nothing to compile across it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "ragcore"
WORKERS = ROOT / "workers"

# The .NET assembly names. A RagCore module naming one of these is either importing it (impossible)
# or addressing it over HTTP (prohibited) — both are breaches.
DOTNET_ASSEMBLIES = (
    "Synthia.Api",
    "Synthia.Modules",
    "Synthia.Contracts",
    "Synthia.Persistence",
    "Synthia.SharedKernel",
    "Synthia.Observability",
)

BASE_URL_PATTERN = re.compile(
    r"(base_?url|BaseAddress)\s*[=:]\s*['\"][^'\"]*(synthia[-.]api|synthia_api)",
    re.IGNORECASE,
)


def _python_modules() -> list[Path]:
    return sorted([*SRC.rglob("*.py"), *WORKERS.rglob("*.py")])


def test_there_are_modules_to_check() -> None:
    """Guards against this suite passing because it found nothing to look at."""
    assert len(_python_modules()) > 10


def test_no_module_imports_a_dotnet_namespace() -> None:
    """No ``import Synthia...`` anywhere. There is no package to import — that is the point."""
    violations: list[str] = []

    for module in _python_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]

            for name in names:
                if name == "Synthia" or name.startswith("Synthia."):
                    violations.append(f"{module.relative_to(ROOT)} -> {name}")

    assert not violations, "RagCore imported a .NET module:\n  " + "\n  ".join(violations)


def test_no_module_names_a_dotnet_assembly() -> None:
    """Catches a string reference an import check would miss — a URL, a config key, a comment.

    Docstrings and comments are exempt: this file and the ports module both discuss the rule, and a
    check that forbids naming the thing it protects makes the rule undocumentable.
    """
    violations: list[str] = []

    for module in _python_modules():
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module))

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Skip docstrings: a module, class or function docstring is the first statement
                # of its body, and ast.get_docstring identifies those.
                for assembly in DOTNET_ASSEMBLIES:
                    if assembly in node.value and not _is_docstring(tree, node):
                        violations.append(
                            f"{module.relative_to(ROOT)} names {assembly} in a string literal"
                        )

    assert not violations, "\n  ".join(violations)


def _is_docstring(tree: ast.AST, target: ast.Constant) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and body[0].value is target:
                return True
    return False


def test_no_module_configures_an_http_client_targeting_the_monolith() -> None:
    """Specification 13.4: there is no direct service-to-service path.

    A base address naming the other deployable is that path, however it is spelled.
    """
    violations: list[str] = []

    for module in _python_modules():
        source = module.read_text(encoding="utf-8")
        if BASE_URL_PATTERN.search(source):
            violations.append(str(module.relative_to(ROOT)))

    assert not violations, (
        "RagCore configures an HTTP client targeting the monolith:\n  " + "\n  ".join(violations)
    )


def test_ragcore_declares_no_dotnet_dependency() -> None:
    """The dependency manifest names nothing from the other stack."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    for assembly in DOTNET_ASSEMBLIES:
        assert assembly not in pyproject
