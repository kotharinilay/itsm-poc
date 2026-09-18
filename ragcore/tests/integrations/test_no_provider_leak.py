"""No provider SDK and no provider type reaches ``domain/`` or ``application/`` (spec FR-EXT-011).

A provider type that reaches inward is how a provider swap becomes a rewrite. The rule is stated in
the plan, declared by :mod:`ragcore.application.ports` — every Protocol there is written in domain
terms — and asserted here, against the tree rather than against intent.

**Two halves, and the second is the one that gets missed.** The first is the obvious one: no
``import azure``, no ``import httpx``, no ``from mcp import …`` in the inner layers. The second is
vocabulary: a port method named ``create_incident``, a field called ``sys_id``, a parameter typed
``ChatCompletion``. None of those imports anything, and each one couples the platform's model to a
provider just as firmly — the ServiceNow adapter could be replaced tomorrow and the *word*
``incident`` would still be in the application layer, meaning something specific to a system nobody
uses any more.

**Static AST checks, not import-time ones.** Importing a module to inspect it executes it, and a
violation behind a conditional import would be missed. Reading the source finds it either way.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

SRC: Final = Path(__file__).resolve().parents[2] / "src" / "ragcore"
INNER: Final = (SRC / "domain", SRC / "application")

PROVIDER_PACKAGES: Final = frozenset(
    {
        "azure",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "aiohttp",
        "mcp",
        "langchain",
        "langgraph",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "fastapi",
        "starlette",
        "redis",
    }
)
"""Packages that are provider or transport detail by definition.

``langgraph`` is on the list although the platform uses it heavily: the graph is orchestration, it
lives in ``graph/``, and a ``StateGraph`` in an application port would make the use case
constructible only inside a graph run.
"""

PROVIDER_VOCABULARY: Final = {
    "sys_id": "ServiceNow's row identifier",
    "servicenow": "the system of record, by name",
    "incident_number": "ServiceNow's case numbering",
    "odata": "Graph and AI Search query syntax",
    "userprincipalname": "Graph's own identity field",
    "chatcompletion": "a provider's response type",
    "deployment_name": "a provider's model deployment",
    "azure_openai": "a provider, by name",
    "api_key": "a credential shape, and one no port should name",
}
"""Words that couple the inner layers to a provider without importing anything.

Each entry names what it is, so a failure explains the problem rather than reporting a banned
string. Matched against identifiers from the AST — never against the file text — so a docstring
explaining why ``sys_id`` must not appear does not itself trip the rule. A guard that punishes its
own explanation gets the explanation deleted.
"""


def _modules(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    """The top-level package of every import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])

    return roots


def _identifiers(path: Path) -> set[str]:
    """Every name, attribute, argument, function and class identifier a module declares or uses."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)

    return names


class TestNoProviderPackageReachesInward:
    """``domain/`` and ``application/`` import no provider or transport package."""

    def test_there_are_modules_to_check(self) -> None:
        """Guards against this file passing because it found nothing to look at."""
        assert sum(len(_modules(root)) for root in INNER) > 5

    @pytest.mark.parametrize("layer", ["domain", "application"])
    def test_the_layer_imports_no_provider_package(self, layer: str) -> None:
        violations = [
            f"{module.relative_to(SRC)}: {sorted(found)}"
            for module in _modules(SRC / layer)
            if (found := _imported_roots(module) & PROVIDER_PACKAGES)
        ]

        assert not violations, (
            f"a provider package reached {layer}/. Ports are declared in terms of domain types "
            "only, and an adapter's SDK belongs behind it:\n  " + "\n  ".join(violations)
        )

    @pytest.mark.parametrize("layer", ["domain", "application"])
    def test_the_layer_does_not_import_the_adapters(self, layer: str) -> None:
        """Dependency direction points inward. An adapter implements a port; a port names none."""
        outward = ("ragcore.integrations", "ragcore.retrieval", "ragcore.persistence")
        violations: list[str] = []

        for module in _modules(SRC / layer):
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
            violations.extend(
                f"{module.relative_to(SRC)} -> {node.module}"
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith(outward)
            )

        assert not violations, "\n  ".join(violations)


class TestNoProviderVocabularyReachesInward:
    """The half that imports nothing and couples just as firmly."""

    @pytest.mark.parametrize("layer", ["domain", "application"])
    def test_the_layer_names_no_provider_concept(self, layer: str) -> None:
        violations: list[str] = []

        for module in _modules(SRC / layer):
            lowered = {name.lower() for name in _identifiers(module)}
            for word, meaning in PROVIDER_VOCABULARY.items():
                if any(word in name for name in lowered):
                    violations.append(f"{module.relative_to(SRC)}: {word!r} — {meaning}")

        assert not violations, (
            f"{layer}/ names a provider's own concept. A provider swap would leave the word "
            "behind, "
            "meaning something specific to a system nobody uses any more:\n  "
            + "\n  ".join(violations)
        )


class TestTheAdaptersAreWhereTheProviderDetailLives:
    """The positive half: the boundaries exist and hold the detail the inner layers do not."""

    @pytest.mark.parametrize(
        "adapter",
        [
            "integrations/model/gateway.py",
            "integrations/model/local.py",
            # `integrations/servicenow/adapter.py` was HERE and has RELOCATED to the Integrations
            # Service (ADR-0007, plan Stage 16). Its absence is now the property that matters:
            # `build/scripts/check-boundaries.sh` fails the build if RagCore imports it back, and
            # the adapter's own tests moved with it. The remaining connectors relocate in the
            # following tasks and are removed from this list as each one does.
            "integrations/graph/adapter.py",
            "integrations/mcp/client.py",
            "integrations/onelogin/adapter.py",
            "integrations/duo/adapter.py",
            "integrations/http.py",
            "integrations/validation.py",
            "integrations/credentials.py",
            "retrieval/search.py",
        ],
    )
    def test_the_adapter_exists_and_is_documented(self, adapter: str) -> None:
        path = SRC / adapter
        assert path.is_file(), f"the {adapter!r} boundary is missing"
        assert ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))), (
            f"{adapter} has no docstring. A boundary that does not say what it is for is a file."
        )

    def test_each_external_system_has_exactly_one_owning_module(self) -> None:
        """All traffic to a given external system passes through a single owning integration
        boundary (spec FR-EXT-011).

        Asserted by counting which modules name each system's own host. Two modules naming the same
        provider host means two boundaries, and the second one is the one nobody reviews.

        ``config/settings.py`` is excluded and is not an exception to the rule. The rule is about
        *traffic*: one module owns the calls to a system. Settings holds **addresses** — where a
        system is, never how to reach it or what to send — and every one of them is read by the
        single adapter that owns that system. Counting it would make the rule unsatisfiable for any
        system whose address is configurable, which is all of them.
        """
        hosts = {
            "service-now.com": "the system of record",
            "graph.microsoft.com": "Microsoft Graph",
            "search.azure.com": "Azure AI Search",
        }
        addresses_only = {"config/settings.py"}
        owners: dict[str, set[str]] = {host: set() for host in hosts}

        for module in sorted(SRC.rglob("*.py")):
            if str(module.relative_to(SRC)).replace("\\", "/") in addresses_only:
                continue
            text = module.read_text(encoding="utf-8")
            for host in hosts:
                if host in text:
                    owners[host].add(str(module.relative_to(SRC)).replace("\\", "/"))

        for host, meaning in hosts.items():
            assert len(owners[host]) <= 1, (
                f"{meaning} is named by more than one module: {sorted(owners[host])}. "
                "One owning boundary per external system."
            )
