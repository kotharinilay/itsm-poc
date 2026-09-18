"""The Azure identity rule, enforced on **this** tree (X6).

``build/policy/azure-identity.json`` is the one registry: every Azure resource this platform
reaches, whether managed identity is required for it, and — where it is not — the named reason.
This module is the **third enforcer**. RagCore has
``ragcore/tests/security/test_azure_identity.py``; the monolith has
``dotnet/tests/Synthia.ArchitectureTests/AzureIdentityTests.cs``.

**Until this file existed, the one deployable holding every organisation's connector credentials was
the one deployable whose source was not scanned for credential material.** A
``ClientSecretCredential`` in ``integrations/src`` would have passed every gate in the repository.
That is not a theoretical gap: this service is the only component with a Key Vault role for
``secret:synthia-connector-*`` and the only one with an egress path to a customer system, so it is
precisely where an application-owned credential would be most tempting and most damaging.

**Being on the workload audience does not cover this.** That the API is reached with a workload
token through APIM is true, tested, and a different rule: it governs who may *call* this service.
These tests govern what this service's own source may *contain*. A hard-coded client secret is
equally a violation on an audience nobody can reach.

**It reads the shared registry rather than restating it.** Two hand-maintained lists drift, and the
drift is invisible until the weaker one is the one somebody checked against.

**The helpers below are duplicated from RagCore's enforcer deliberately** (constitution
Principle VI). Each tree scans only itself, so neither suite reads the other's files — extracting a
shared test package would be the build-level dependency between deployables that ADR-0001 and
ADR-0007 exist to prevent, and it would be a dependency created for the convenience of a test.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

pytestmark = pytest.mark.security

ROOT: Final = Path(__file__).resolve().parents[3]
"""The repository root — ``integrations/tests/security`` is three levels down."""

POLICY_PATH: Final = ROOT / "build" / "policy" / "azure-identity.json"

PRODUCTION_ROOTS: Final = (
    ROOT / "integrations" / "src",
    ROOT / "integrations" / "workers",
)
"""What ships. **Tests are excluded and must stay excluded**: a test fixture legitimately names a
banned type to assert it is banned, and a scan that punished the assertion would get the assertion
deleted."""

COMMITTED_CONFIG_GLOBS: Final = (
    "integrations/**/*.toml",
    "integrations/**/*.ini",
    "integrations/**/*.yaml",
    "integrations/**/*.yml",
)
"""Committed configuration is the other half of the surface, and the half that gets missed.

A secret removed from source and left in a manifest has not been removed. ``build/**`` and
``.github/**`` are **not** here: they are shared, and RagCore's enforcer already scans them.
Scanning them twice would mean two failures for one defect and two places to fix a false positive.
"""

SKIP_DIRECTORIES: Final = frozenset(
    {".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)

REACHED_RESOURCES: Final = frozenset({"postgresql", "servicebus", "keyvault", "monitor"})
"""The registered resources this service actually reaches.

Its durable store, the two integration queues, Key Vault for its own secrets **and** for
per-organisation connector credentials, and Application Insights under its own service name.
"""

UNREACHED_RESOURCES: Final = frozenset({"signalr", "aisearch", "foundry", "redis"})
"""The registered resources this service deliberately does **not** reach.

Each absence is a control, and each is mirrored by a withheld role assignment in
``build/infra/identity/managed-identities.json``:

* ``signalr`` — notification is RagCore's leaf; this service notifies nobody.
* ``aisearch`` — it retrieves nothing.
* ``foundry`` — it does no reasoning (`FR-INTEG-007`); a model client here would be a second,
  ungoverned egress outside the AI Gateway's metering, budgets and content safety.
* ``redis`` — it caches nothing. A cached entitlement is a revoked entitlement that still works.

Asserted as an **absence in this tree**, which is the half a role assignment cannot express:
withholding the role stops the call succeeding, but only this stops the client being written.
"""


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    """The shared registry, parsed once."""
    loaded: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return loaded


def _python_files() -> list[Path]:
    """Every production Python file in this tree, excluding tests and build output."""
    return sorted(
        path
        for root in PRODUCTION_ROOTS
        if root.exists()
        for path in root.rglob("*.py")
        if not SKIP_DIRECTORIES & set(path.parts)
    )


def _names_in(path: Path) -> set[str]:
    """Every bare name, attribute and imported name a module mentions.

    Read from the AST rather than the text, so a docstring explaining why
    ``ClientSecretCredential`` is banned does not itself trip the ban. A guard that punishes the
    explanation gets the explanation deleted, and then nobody remembers what the guard was for.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[-1] for alias in node.names)
    return names


def _imported_modules_in(path: Path) -> set[str]:
    """Every **dotted module path** a module imports from.

    Distinct from :func:`_names_in`, and the distinction was found by mutation rather than by
    reading. ``_names_in`` collects the *names* an import binds: for
    ``from azure.search.documents.aio import SearchClient`` it yields ``SearchClient`` and never
    the module path. A guard matching on ``search.documents`` therefore matched nothing, and
    reported success — which is precisely the vacuous pass these tests exist to prevent.

    Args:
        path: The module to read.

    Returns:
        The full dotted paths, so a marker can match the package rather than the bound name.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # The module path AND each name qualified onto it, so both
            # `import azure.search.documents` and `from azure.search.documents import X` match.
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _string_literals_in(path: Path) -> list[str]:
    """Every string literal in a module, docstrings excluded.

    A literal is code — a connection string in quotes is exactly what several of these rules look
    for. Docstrings are excluded for the same reason the AST is used for names.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# ---------------------------------------------------------------------------
# This enforcer reads the shared registry, and there is something to scan
# ---------------------------------------------------------------------------


def test_the_shared_registry_is_readable_from_here(policy: dict[str, Any]) -> None:
    """Not a reimplementation of the policy — the same file the other two enforcers read."""
    assert POLICY_PATH.is_file()
    assert policy["forbiddenEverywhere"]["credentialTypes"]
    assert {resource["id"] for resource in policy["resources"]} >= REACHED_RESOURCES


def test_there_is_production_source_to_scan() -> None:
    """**The test that stops every rule below passing vacuously.**

    A scan over an empty file list reports success exactly as loudly as a scan that found nothing
    wrong. If `PRODUCTION_ROOTS` is ever renamed, moved or mistyped, this is the assertion that
    fails instead of the whole suite quietly going green.
    """
    files = _python_files()
    assert len(files) > 30, f"only {len(files)} production files found; the scan roots are wrong"
    assert any(path.name == "settings.py" for path in files)


# ---------------------------------------------------------------------------
# What must never appear in this tree
# ---------------------------------------------------------------------------


def test_no_application_owned_credential_type_is_constructed(policy: dict[str, Any]) -> None:
    """``ClientSecretCredential`` and its relatives are how an application owns a secret.

    Each is a perfectly good Azure SDK type and each is prohibited here: they all take a credential
    the application holds, which is the thing managed identity exists to remove. **Most load-bearing
    in this tree of all three**, because this is the process that also holds the vault role for
    every organisation's connector secrets.
    """
    banned = set(policy["forbiddenEverywhere"]["credentialTypes"])
    offenders = [
        f"{path.relative_to(ROOT)}: {sorted(found)}"
        for path in _python_files()
        if (found := _names_in(path) & banned)
    ]
    assert not offenders, "an application-owned Azure credential is constructed:\n  " + "\n  ".join(
        offenders
    )


def test_no_credential_is_constructed_in_this_tree_at_all() -> None:
    """**Stronger than RagCore's rule, because this service can be.**

    RagCore permits ``DefaultAzureCredential`` in exactly one module. This service constructs none:
    every client takes an injected credential — the Service Bus publisher and the Graph adapter both
    receive one — so there is no construction site to audit.

    Asserted rather than assumed, because the weaker outcome is invisible. If a credential is ever
    genuinely needed here, it belongs in one named module and this test should be changed to say so
    deliberately, in the same commit, with the module named.
    """
    constructors = {
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in _python_files()
        if {"DefaultAzureCredential", "ManagedIdentityCredential"} & _names_in(path)
    }
    assert not constructors, (
        f"a credential is constructed in this tree: {sorted(constructors)}. Every client here "
        "takes an injected credential; introducing a construction site needs one named module and "
        "a deliberate change to this test."
    )


def test_no_connection_string_token_appears_in_source(policy: dict[str, Any]) -> None:
    """A key inside a connection string is still a key.

    Matched against string literals rather than whole files, so the prose in this module — which
    necessarily contains several banned tokens — does not trip its own rule.
    """
    tokens = [token.lower() for token in policy["forbiddenEverywhere"]["connectionStringTokens"]]
    offenders: list[str] = []
    for path in _python_files():
        for literal in _string_literals_in(path):
            lowered = literal.lower()
            if hits := [token for token in tokens if token in lowered]:
                offenders.append(f"{path.relative_to(ROOT)}: {hits}")
    assert not offenders, (
        "a credential-bearing connection string appears in source:\n  " + "\n  ".join(offenders)
    )


def test_no_dsn_literal_carries_a_password() -> None:
    """``postgresql://user:secret@host`` in a literal is the violation, in any file.

    Its own assertion because a DSN carrying a real password and a DSN carrying a token look
    identical, and only one of them is allowed. `PersistenceSettings` refuses an embedded password
    at startup; this refuses one reaching the repository at all.
    """
    pattern = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/@\"']+:[^\s@\"']+@", re.IGNORECASE)
    offenders = [
        f"{path.relative_to(ROOT)}: {literal[:40]}…"
        for path in _python_files()
        for literal in _string_literals_in(path)
        if pattern.search(literal)
    ]
    assert not offenders, "a PostgreSQL DSN carries an embedded password:\n  " + "\n  ".join(
        offenders
    )


def test_no_settings_field_holds_a_secret_value(policy: dict[str, Any]) -> None:
    """Settings hold a *name*; the value is resolved at the point of use.

    A field called ``client_secret`` is a defect whether or not it currently holds anything — the
    type is what tells the next author where a secret is allowed to live. The ``*_secret_name``
    convention is what keeps a reviewer able to tell a name from a value at a glance, and
    `ObservabilitySettings.connection_string_secret_name` is this service's example of it.
    """
    settings = ROOT / "integrations" / "src" / "integrations" / "config" / "settings.py"
    assert settings.is_file()

    banned = {key.lower() for key in policy["forbiddenEverywhere"]["configurationKeys"]}
    tree = ast.parse(settings.read_text(encoding="utf-8"), filename=str(settings))

    offenders = [
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id.lower() in banned
        and not node.target.id.endswith("_secret_name")
    ]
    assert not offenders, (
        f"settings fields naming a secret value rather than a reference: {offenders}"
    )


def test_no_committed_configuration_carries_a_credential(policy: dict[str, Any]) -> None:
    """The half that gets missed: a secret moved out of source and into a manifest."""
    tokens = [token.lower() for token in policy["forbiddenEverywhere"]["connectionStringTokens"]]
    offenders: list[str] = []
    for pattern in COMMITTED_CONFIG_GLOBS:
        for path in ROOT.glob(pattern):
            if SKIP_DIRECTORIES & set(path.parts):
                continue
            lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
            if hits := [token for token in tokens if token in lowered]:
                offenders.append(f"{path.relative_to(ROOT)}: {hits}")
    assert not offenders, "committed configuration carries a credential:\n  " + "\n  ".join(
        offenders
    )


# ---------------------------------------------------------------------------
# What this service reaches, and what it must never reach
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("resource_id", sorted(REACHED_RESOURCES))
def test_every_resource_this_service_reaches_requires_managed_identity(
    resource_id: str, policy: dict[str, Any]
) -> None:
    """Each of the four, named individually so a registry edit cannot quietly exempt one.

    Key Vault especially: it is the resource that holds every other credential, and the registry
    forbids exempting it at all.
    """
    resource = next(item for item in policy["resources"] if item["id"] == resource_id)

    assert resource["managedIdentity"] in {"required", "conditional"}
    if resource["managedIdentity"] == "conditional":
        assert resource.get("condition"), f"{resource_id} is conditional without a condition"


@pytest.mark.parametrize("resource_id", sorted(UNREACHED_RESOURCES))
def test_a_resource_this_service_does_not_reach_leaves_no_trace_in_its_source(
    resource_id: str,
) -> None:
    """**The absence is the control**, and a withheld role cannot express this half.

    The role assignment being absent stops the call from succeeding. It does not stop the client
    from being written, reviewed and merged — and the resulting failure surfaces in production as an
    authorization error against a resource nobody expected this service to use.

    Matched on the **imported module path**, not on the word and not on the bound name: this module
    names all four in prose above, and a guard that flagged its own explanation is a guard somebody
    disables. Using the module path rather than the bound name is what makes
    ``from azure.search.documents.aio import SearchClient`` visible at all — matching the name
    would look for ``SearchClient`` and miss every other client in the same package.
    """
    markers = {
        "signalr": ("signalr",),
        "aisearch": ("azure.search",),
        "foundry": ("openai", "azure.ai.inference", "azure.ai.projects"),
        "redis": ("redis",),
    }[resource_id]

    # CONTAINMENT, NOT `startswith`, and mutation is what settled it. An earlier version used
    # `startswith`, which caught `redis.asyncio` but MISSED
    # `azure.messaging.signalr` — the vendor puts the product name last, so a prefix match only
    # ever catches the packages that happen to be named after their product. The markers are
    # specific enough that containment adds no false positive: no legitimate import in this tree
    # contains any of them, which the baseline run asserts.
    offenders = [
        f"{path.relative_to(ROOT)}: {sorted(hits)}"
        for path in _python_files()
        if (
            hits := {
                module
                for module in _imported_modules_in(path)
                if any(marker in module.lower() for marker in markers)
            }
        )
    ]
    detail = "\n  ".join(offenders)
    assert not offenders, (
        f"this service reaches {resource_id}, which it must not:\n  {detail}\n"
        "The withheld role assignment would make the call fail at runtime; this is what stops the "
        "client being written, reviewed and merged in the first place."
    )
