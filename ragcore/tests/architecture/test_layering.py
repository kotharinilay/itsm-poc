"""Import-boundary tests (T036).

``api → application → domain``. Adapters implement ports declared by their consumer. Dependency
direction points inward, toward business and application policy; infrastructure is an outer
implementation detail (.claude/rules/10-principles.md P-5).

These are static AST checks rather than import-time checks, deliberately: importing a module to
inspect it executes it, and a violation that only appears under a conditional import would be
missed. Reading the source finds it either way.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ragcore"
DOMAIN = SRC / "domain"
APPLICATION = SRC / "application"

STDLIB = sys.stdlib_module_names

# Packages that are, by definition, infrastructure. None of them may appear in domain or
# application: a provider type reaching inward is how a provider swap becomes a rewrite.
PROVIDER_PACKAGES = frozenset(
    {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "asyncpg",
        "alembic",
        "alembic_utils",
        "azure",
        "httpx",
        "langgraph",
        "langchain",
        "mcp",
        "opentelemetry",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
    }
)


def _imported_roots(path: Path) -> set[str]:
    """Return the top-level package of every import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative imports are banned outright by ruff (flake8-tidy-imports); if one
                # appears anyway, it is not resolvable here and the lint gate owns it.
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _modules(package: Path) -> list[Path]:
    return sorted(package.rglob("*.py"))


class TestDomainPurity:
    """``domain/`` imports nothing outside the standard library."""

    def test_domain_has_modules_to_check(self) -> None:
        """Guards against the suite passing because it found nothing to look at."""
        assert len(_modules(DOMAIN)) > 1

    def test_domain_imports_only_the_standard_library(self) -> None:
        allowed = STDLIB | {"ragcore", "__future__"}
        violations: list[str] = []

        for module in _modules(DOMAIN):
            offenders = _imported_roots(module) - allowed
            if offenders:
                violations.append(f"{module.relative_to(SRC)}: {sorted(offenders)}")

        assert not violations, (
            "domain/ imported outside the standard library. The domain is pure by rule, "
            "and this is the rule:\n  " + "\n  ".join(violations)
        )

    def test_domain_imports_nothing_from_outer_layers(self) -> None:
        """Even within ``ragcore``, the domain does not reach outward."""
        forbidden = {
            "ragcore.application",
            "ragcore.api",
            "ragcore.persistence",
            "ragcore.model",
            "ragcore.egress",
            "ragcore.platform_clients",
            "ragcore.graph",
            "ragcore.governance",
            "ragcore.retrieval",
            "ragcore.execution",
            "ragcore.messaging",
            "ragcore.notifications",
            "ragcore.config",
            "ragcore.ingestion",
            "ragcore.observability",
        }
        violations: list[str] = []

        for module in _modules(DOMAIN):
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                if any(node.module.startswith(f) for f in forbidden):
                    violations.append(f"{module.relative_to(SRC)} -> {node.module}")

        assert not violations, "\n  ".join(violations)


class TestApplicationLayer:
    """``application/`` depends on ``domain`` and declares ports. It holds no adapter."""

    def test_application_imports_no_provider_package(self) -> None:
        violations: list[str] = []

        for module in _modules(APPLICATION):
            offenders = _imported_roots(module) & PROVIDER_PACKAGES
            if offenders:
                violations.append(f"{module.relative_to(SRC)}: {sorted(offenders)}")

        assert not violations, (
            "A provider package reached the application layer. Ports are declared in terms of "
            "domain types only:\n  " + "\n  ".join(violations)
        )

    def test_application_does_not_import_the_api_layer(self) -> None:
        """Dependency direction points inward. ``api → application``, never the reverse."""
        violations: list[str] = []

        for module in _modules(APPLICATION):
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                if node.module.startswith("ragcore.api"):
                    violations.append(f"{module.relative_to(SRC)} -> {node.module}")

        assert not violations, "\n  ".join(violations)

    def test_ports_module_exists_and_declares_protocols(self) -> None:
        """Ports belong to the consuming module, and this is where consumers declare them."""
        ports = APPLICATION / "ports.py"
        assert ports.exists()

        tree = ast.parse(ports.read_text(encoding="utf-8"), filename=str(ports))
        protocols = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any((isinstance(base, ast.Name) and base.id == "Protocol") for base in node.bases)
        ]

        # The boundaries the plan names. Each is genuinely infrastructure; authorization and
        # treatment policy are deliberately absent because they are pure domain logic.
        for expected in (
            "ClockPort",
            "TenantRegistryPort",
            "WorkItemRepositoryPort",
            "OperationCataloguePort",
            "RetrievalPort",
            "IdempotencyStorePort",
            "ToolExecutionPort",
            "OutboxPort",
            "MessagePublisherPort",
            "NotificationPort",
            "AuditSinkPort",
            "ModelPort",
            "IngestionPort",
        ):
            assert expected in protocols, f"{expected} is missing from application/ports.py"


class TestAuthorizationIsNotAPort:
    """A rule worth asserting, because the tempting refactor is the wrong one.

    Authorization is a pure function over two role sets. Making it injectable would mean an
    implementation could consult a database, a cache or a configuration flag — and the moment it
    can, a treatment or a role can arrive from somewhere that is not the catalogue.
    """

    def test_no_authorization_port_exists(self) -> None:
        ports = (APPLICATION / "ports.py").read_text(encoding="utf-8")
        tree = ast.parse(ports)
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

        for forbidden in ("AuthorizationPort", "AuthorizerPort", "PolicyPort", "GovernancePort"):
            assert forbidden not in names, (
                f"{forbidden} was added to ports.py. Authorization and treatment policy are pure "
                "domain functions; a port invites an implementation that consults infrastructure."
            )

    def test_authorization_lives_in_the_domain(self) -> None:
        assert (DOMAIN / "roles.py").exists()
        source = (DOMAIN / "roles.py").read_text(encoding="utf-8")
        assert "def evaluate(" in source
