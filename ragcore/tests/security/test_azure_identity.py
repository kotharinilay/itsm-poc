"""Azure clients authenticate as a managed identity. Application-owned credentials are refused.

**The rule is cross-platform and the registry is shared.** ``build/policy/azure-identity.json``
lists
every Azure resource this platform reaches, whether managed identity is required for it, and the
named
reason wherever it is not. The .NET side enforces the same file from
``dotnet/tests/Synthia.ArchitectureTests/AzureIdentityTests.cs``, and
:class:`TestBothPlatformsEnforceTheSamePolicy` asserts the two cover the same resources — because
two
lists drift, and the drift is invisible until the day the weaker of the two is the one that
mattered.

**Structural, not runtime.** These read source rather than opening a connection, so the rule holds
in
CI without an Azure subscription and a failure names the file and the construct rather than
producing
an authentication error three layers down. A credential defect that only appears when deployed is
one
that ships.

**Why the local-development case is not an exception.** ``DefaultAzureCredential`` resolves a
developer identity locally through the same code path it uses for a managed identity in production,
so
there is no second branch to get wrong. A credential type that works only on a laptop is still a
violation here: the rule is about what the code can *express*, not about where it happens to run.

**These tests pass today against a codebase with no Azure client in it**, and that is the point of
writing them now. The rule is cheap to satisfy before the clients exist and expensive to retrofit
afterwards, when the first violation is already load-bearing.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[3]
"""The repository root — ``ragcore/tests/security`` is three levels down."""

POLICY_PATH: Final = ROOT / "build" / "policy" / "azure-identity.json"

PRODUCTION_ROOTS: Final = (
    ROOT / "ragcore" / "src",
    ROOT / "ragcore" / "workers",
    ROOT / "ragcore" / "migrations",
)

COMMITTED_CONFIG_GLOBS: Final = (
    "ragcore/**/*.toml",
    "ragcore/**/*.ini",
    "ragcore/**/*.yaml",
    "ragcore/**/*.yml",
    "build/**/*.yaml",
    "build/**/*.yml",
    "build/**/*.json",
    ".github/**/*.yml",
)

SKIP_DIRECTORIES: Final = frozenset(
    {
        ".venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "bin",
        "obj",
    }
)


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    """The shared registry, parsed once."""
    loaded: dict[str, Any] = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return loaded


def _python_files() -> list[Path]:
    """Every production Python file, excluding tests and build output."""
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
# The registry itself must be well-formed before it can be enforced
# ---------------------------------------------------------------------------


class TestThePolicyRegistryIsUsable:
    """A malformed registry would silently enforce nothing, which is worse than no registry."""

    def test_the_policy_file_exists(self) -> None:
        """Both stacks read this one file. Its absence is a failure, not a skip."""
        assert POLICY_PATH.is_file(), f"the shared Azure identity policy is missing: {POLICY_PATH}"

    def test_every_named_resource_is_covered(self, policy: dict[str, Any]) -> None:
        """The eight resources this platform reaches, each present exactly once."""
        expected = {
            "postgresql",
            "servicebus",
            "signalr",
            "keyvault",
            "aisearch",
            "foundry",
            "monitor",
            "redis",
        }
        listed = [resource["id"] for resource in policy["resources"]]
        assert len(listed) == len(set(listed)), f"a resource is listed twice: {listed}"
        assert set(listed) == expected

    def test_every_resource_declares_its_managed_identity_position(
        self, policy: dict[str, Any]
    ) -> None:
        """``required`` or ``conditional``. There is deliberately no ``optional``."""
        for resource in policy["resources"]:
            assert resource["managedIdentity"] in {"required", "conditional"}, resource["id"]

    def test_a_conditional_resource_states_its_condition(self, policy: dict[str, Any]) -> None:
        """Conditional without a written condition is optional wearing a better word."""
        for resource in policy["resources"]:
            if resource["managedIdentity"] == "conditional":
                assert resource.get("condition"), (
                    f"{resource['id']} is conditional but names no condition. State which "
                    "configurations support Entra authentication, or make it required."
                )

    def test_key_vault_can_never_be_exempted(self, policy: dict[str, Any]) -> None:
        """A secret used to reach the secret store defeats the entire arrangement."""
        vault = next(r for r in policy["resources"] if r["id"] == "keyvault")
        assert vault["managedIdentity"] == "required"
        assert vault.get("exemptionPermitted") is False

    def test_every_exemption_is_fully_named(self, policy: dict[str, Any]) -> None:
        """An exemption without an owner and a review date is a permanent exemption.

        The registry ships with none. This test exists for the day somebody adds one — the friction
        is the feature, because the exemption is the thing that needs review, not the credential.
        """
        required = {
            "resource",
            "providerLimitation",
            "credentialType",
            "storedIn",
            "owner",
            "reviewBy",
        }
        for entry in policy["exemptions"]:
            if "$comment" in entry:
                continue
            missing = required - entry.keys()
            assert not missing, f"exemption {entry!r} is missing {sorted(missing)}"
            assert entry["storedIn"] == "keyvault", (
                "an exempted credential still lives in Key Vault; there is nowhere else to put it"
            )
            assert entry["resource"] != "keyvault", "Key Vault cannot be exempted from itself"


# ---------------------------------------------------------------------------
# The credential chain
# ---------------------------------------------------------------------------


class TestTheCredentialChain:
    """One credential, constructed once, shared by every client."""

    def test_no_application_owned_credential_type_is_constructed(
        self, policy: dict[str, Any]
    ) -> None:
        """``ClientSecretCredential`` and its relatives are how an application owns a secret.

        Each of these is a perfectly good Azure SDK type and each is prohibited here: they all take
        a credential the application holds, which is the thing managed identity exists to remove.
        """
        banned = set(policy["forbiddenEverywhere"]["credentialTypes"])
        offenders = [
            f"{path.relative_to(ROOT)}: {sorted(found)}"
            for path in _python_files()
            if (found := _names_in(path) & banned)
        ]
        assert not offenders, (
            "an application-owned Azure credential is constructed:\n  " + "\n  ".join(offenders)
        )

    def test_the_credential_is_constructed_in_one_module(self) -> None:
        """A client that builds its own credential is a second, weaker auth path beside the first.

        Constructing it once means there is one place to audit, one place to change, and one place
        for a reviewer to look when asking how this process authenticates.
        """
        constructors = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in _python_files()
            if "DefaultAzureCredential" in _names_in(path)
        }
        permitted = {"ragcore/src/ragcore/infrastructure/azure_credentials.py"}
        assert constructors <= permitted, (
            "DefaultAzureCredential is constructed outside the shared credential module: "
            f"{sorted(constructors - permitted)}. Every client takes the shared credential."
        )


# ---------------------------------------------------------------------------
# What must never appear, anywhere
# ---------------------------------------------------------------------------


class TestNoApplicationOwnedCredentialInSourceOrConfiguration:
    """The shapes an Azure credential actually takes, matched where they actually appear."""

    def test_no_connection_string_token_appears_in_source(self, policy: dict[str, Any]) -> None:
        """A key inside a connection string is still a key.

        Matched against string literals rather than whole files, so the prose in this module — which
        necessarily contains every banned token — does not trip its own rule.
        """
        tokens = [t.lower() for t in policy["forbiddenEverywhere"]["connectionStringTokens"]]
        offenders: list[str] = []
        for path in _python_files():
            for literal in _string_literals_in(path):
                lowered = literal.lower()
                hits = [token for token in tokens if token in lowered]
                if hits:
                    offenders.append(f"{path.relative_to(ROOT)}: {hits}")
        assert not offenders, (
            "a credential-bearing connection string appears in source:\n  " + "\n  ".join(offenders)
        )

    def test_no_settings_field_holds_a_secret_value(self, policy: dict[str, Any]) -> None:
        """Settings hold a *name*; the value is resolved at the point of use.

        A field called ``client_secret`` is a defect whether or not it currently holds anything —
        the type is what tells the next author where a secret is allowed to live. The
        ``*_secret_name``
        convention is what keeps a reviewer able to tell a name from a value at a glance.
        """
        settings = ROOT / "ragcore" / "src" / "ragcore" / "config" / "settings.py"
        if not settings.is_file():
            pytest.skip("settings module not present")

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

    def test_no_committed_configuration_carries_a_credential(self, policy: dict[str, Any]) -> None:
        """Committed configuration is the other half of the surface, and the half that gets missed.

        A secret removed from source and left in a deployment manifest has not been removed.
        """
        tokens = [t.lower() for t in policy["forbiddenEverywhere"]["connectionStringTokens"]]
        offenders: list[str] = []
        for pattern in COMMITTED_CONFIG_GLOBS:
            for path in ROOT.glob(pattern):
                if SKIP_DIRECTORIES & set(path.parts) or path == POLICY_PATH:
                    continue
                lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
                hits = [token for token in tokens if token in lowered]
                if hits:
                    offenders.append(f"{path.relative_to(ROOT)}: {hits}")
        assert not offenders, "committed configuration carries a credential:\n  " + "\n  ".join(
            offenders
        )


# ---------------------------------------------------------------------------
# PostgreSQL — the one where correct usage and a violation look alike
# ---------------------------------------------------------------------------


class TestPostgreSqlAccess:
    """Entra authentication presents the token in the password position.

    That is why this needs its own assertion: a DSN carrying a real password and a DSN carrying a
    token look identical in a config file, and only one of them is allowed.
    """

    def test_no_dsn_literal_carries_a_password(self) -> None:
        """``postgresql://user:secret@host`` in a literal is the violation, in any file."""
        pattern = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/@\"']+:[^\s@\"']+@", re.IGNORECASE)
        offenders: list[str] = []
        for path in _python_files():
            for literal in _string_literals_in(path):
                if pattern.search(literal):
                    offenders.append(f"{path.relative_to(ROOT)}: {literal[:40]}…")
        assert not offenders, "a PostgreSQL DSN carries an embedded password:\n  " + "\n  ".join(
            offenders
        )

    def test_the_database_settings_hold_no_password_field(self) -> None:
        """The DSN arrives whole, from Key Vault, with the token supplied at connect time."""
        settings = ROOT / "ragcore" / "src" / "ragcore" / "config" / "settings.py"
        if not settings.is_file():
            pytest.skip("settings module not present")

        tree = ast.parse(settings.read_text(encoding="utf-8"), filename=str(settings))
        fields = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        assert not fields & {"password", "db_password", "client_secret"}


# ---------------------------------------------------------------------------
# Per-resource coverage, so a new client cannot arrive unguarded
# ---------------------------------------------------------------------------


class TestEachResourceIsReachedByManagedIdentity:
    """One test per resource, parametrised, so a failure names the resource that regressed."""

    @pytest.mark.parametrize(
        "resource_id",
        [
            "postgresql",
            "servicebus",
            "signalr",
            "keyvault",
            "aisearch",
            "foundry",
            "monitor",
            "redis",
        ],
    )
    def test_the_resource_declares_no_unexempted_key_auth(
        self, policy: dict[str, Any], resource_id: str
    ) -> None:
        """A resource is either reached by managed identity or carries a named exemption.

        There is no third state. A resource whose client has not been written yet passes trivially —
        which is correct: the rule is in place before the client is, so the first implementation is
        written against it rather than retrofitted to it.
        """
        resource = next(r for r in policy["resources"] if r["id"] == resource_id)
        exempted = {entry["resource"] for entry in policy["exemptions"] if "resource" in entry}

        if resource["managedIdentity"] == "required":
            assert resource_id not in exempted or resource.get("exemptionPermitted") is not False, (
                f"{resource_id} requires managed identity and cannot hold this exemption"
            )

        # Whatever its position, no client for it may construct an application-owned credential —
        # that is asserted globally above. What is asserted here is that the registry has not been
        # edited into a state where the global rule no longer applies to this resource.
        assert resource["managedIdentity"] in {"required", "conditional"}
        if resource["managedIdentity"] == "conditional":
            assert resource.get("condition"), f"{resource_id} is conditional without a condition"


# ---------------------------------------------------------------------------
# Cross-platform parity
# ---------------------------------------------------------------------------


class TestBothPlatformsEnforceTheSamePolicy:
    """A rule enforced on one stack and not the other decides where insecure code gets written."""

    def test_the_dotnet_enforcer_exists(self) -> None:
        """Its absence would mean this policy covers half the platform."""
        enforcer = ROOT / "dotnet" / "tests" / "Synthia.ArchitectureTests" / "AzureIdentityTests.cs"
        assert enforcer.is_file(), (
            "the .NET half of the Azure identity rule is missing. Both deployables reach Azure "
            "resources; a rule that only binds RagCore is not a platform rule."
        )

    def test_the_dotnet_enforcer_reads_the_shared_registry(self) -> None:
        """Not a reimplementation of it — the same file, so the two cannot disagree."""
        enforcer = ROOT / "dotnet" / "tests" / "Synthia.ArchitectureTests" / "AzureIdentityTests.cs"
        source = enforcer.read_text(encoding="utf-8")
        assert "azure-identity.json" in source, (
            "the .NET enforcer does not read build/policy/azure-identity.json. Two hand-maintained "
            "lists drift, and the drift is invisible until the weaker one is the one that mattered."
        )

    def test_both_enforcers_cover_every_registered_resource(self, policy: dict[str, Any]) -> None:
        """Each resource id appears in the .NET enforcer's parametrised coverage."""
        enforcer = ROOT / "dotnet" / "tests" / "Synthia.ArchitectureTests" / "AzureIdentityTests.cs"
        source = enforcer.read_text(encoding="utf-8")
        missing = [
            resource["id"]
            for resource in policy["resources"]
            if f'"{resource["id"]}"' not in source
        ]
        assert not missing, f"the .NET enforcer does not name these resources: {missing}"
