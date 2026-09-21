"""Architecture guards. **The boundary is enforced here, or it is not enforced.**

.claude/rules/10-principles.md P-24: module boundaries are enforced by architecture tests, not
convention, and
a boundary that exists only in a diagram erodes.

Four rules, each with a distinct failure it prevents:

1. **No import of `ragcore`.** The two are separate deployables meeting only at APIM and Service
   Bus. An import would be a build-level dependency that no network check could see.
2. **No shared library between them.** The tempting fix for duplicated middleware is a common
   package; it would be the same coupling wearing a friendlier name.
3. **`domain/` imports only the standard library.** Infrastructure is an outer detail; a domain that
   imports a provider type has inverted the dependency direction.
4. **Only the composition root constructs adapters.** Otherwise Service Locator arrives by
   accident, one `Settings()` call at a time.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_SRC = Path(__file__).resolve().parents[2] / "src" / "integrations"
_WORKERS = Path(__file__).resolve().parents[2] / "workers"

# Standard-library modules `domain/` may import. Deliberately enumerated rather than detected:
# a detected list would grow silently with the interpreter, and the point is that adding an import
# to the domain is a decision someone makes on purpose.
_DOMAIN_ALLOWED = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "typing",
        "uuid",
    }
)


def _python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _imported_roots(path: Path) -> set[str]:
    """Every top-level module name imported by one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_module_imports_ragcore() -> None:
    """The Integrations Service MUST NOT import RagCore.

    They are separate deployables (ADR-0007) meeting only at APIM and Service Bus. An import would
    make them one deployable that merely deploys twice — and it would not show up in any network
    or gateway check, because it never crosses a wire.
    """
    offenders = [
        str(path.relative_to(_SRC.parent.parent))
        for path in _python_files(_SRC) + _python_files(_WORKERS)
        if "ragcore" in _imported_roots(path)
    ]
    assert offenders == [], (
        "these modules import `ragcore`: "
        + ", ".join(offenders)
        + ". The two services meet at APIM and Service Bus, and nowhere else."
    )


def test_no_shared_library_between_the_two_python_services() -> None:
    """No `synthia_common`-style package is imported by either side.

    .claude/rules/10-principles.md P-6: duplication across a boundary is cheaper than a false shared
    contract. A shared package would be a build-level dependency between two deployables required
    to have none — and, unlike an application call, it would not appear as a cross-tree path where
    `build/scripts/check-boundaries.sh` could catch it.
    """
    banned = {"synthia_common", "synthia_shared", "synthia"}
    offenders = [
        str(path.relative_to(_SRC.parent.parent))
        for path in _python_files(_SRC) + _python_files(_WORKERS)
        if _imported_roots(path) & banned
    ]
    assert offenders == [], (
        "these modules import a shared Synthia package: "
        + ", ".join(offenders)
        + ". The duplication between the two services is deliberate."
    )


def test_domain_imports_only_the_standard_library() -> None:
    """`domain/` is pure model: no I/O, no framework, no provider type.

    Dependency direction points inward, toward business policy. A domain importing `httpx`,
    `sqlalchemy` or a provider SDK has inverted it, and every rule that rests on the domain being
    testable in isolation rests on nothing.
    """
    domain = _SRC / "domain"
    offenders: list[str] = []
    for path in _python_files(domain):
        for root in _imported_roots(path):
            if root not in _DOMAIN_ALLOWED and root != "integrations":
                offenders.append(f"{path.name} imports {root}")

    assert offenders == [], (
        "the domain imports outside the standard library: "
        + ", ".join(offenders)
        + ". Infrastructure is an outer detail; the domain MUST NOT depend on it."
    )


def test_only_the_composition_root_builds_the_container() -> None:
    """`build_container` is called in exactly one place outside tests.

    .claude/rules/10-principles.md P-26 prohibits Service Locator and requires registration to live
    in composition-root code. The failure this prevents is gradual: one module calls
    `build_container()` "just for settings", then another, and dependency injection has quietly
    become global lookup with no single place left to review what is wired to what.
    """
    callers = [
        str(path.relative_to(_SRC.parent.parent))
        for path in _python_files(_SRC)
        if "build_container(" in path.read_text(encoding="utf-8")
        and path.name not in {"composition.py", "app.py"}
    ]
    assert callers == [], (
        "these modules build the container themselves: "
        + ", ".join(callers)
        + ". Only the composition root constructs dependencies; everything else receives them."
    )
