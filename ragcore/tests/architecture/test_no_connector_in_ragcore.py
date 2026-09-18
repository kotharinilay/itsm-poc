"""No connector, and no way back to one (T297).

Spec `FR-DEMO-021`, `FR-EXT-011`, ADR-0007. Every external connector left this deployable with
T296. These tests exist so that it stays gone — because the expensive failure is not the removal
being wrong, it is a connector being added back six months later by someone who had no idea the
absence was load-bearing.

**Static AST checks rather than import-time ones**, for the same reason as
:mod:`tests.architecture.test_layering`: importing a module to inspect it executes it, and a
violation behind a conditional import would be missed. Reading the source finds it either way.

**Three different claims, three different tests**, because they fail for different reasons and a
single "no connectors" assertion would pass while two of the three were violated:

1. no connector **library** is importable from this tree;
2. no module holds an external **endpoint**, which is the first thing a direct call needs;
3. nothing **binds** a connector into the composition root, which is where an adapter would have
   to be wired to matter.

**This test is necessary and not sufficient, and saying so is the point.** An absence assertion
passes equally where the path exists and simply has no caller yet. The deployed proof is T311,
which *attempts* the connection and observes it refused; this one catches the regression on the
branch, before it reaches anywhere it could be attempted.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ragcore"

# The one subtree that may hold outbound model code. Reasoning is RagCore's; integration is not.
MODEL_PACKAGE = SRC / "integrations" / "model"

# Client libraries whose only purpose is to talk to a customer system. `azure` is deliberately NOT
# here: RagCore legitimately uses Azure SDKs for its own platform resources — Service Bus, Key Vault
# for its own secrets, Entra tokens for the gateway. Banning a whole vendor namespace would either
# be false or force an exception list long enough to hide a real violation in.
CONNECTOR_LIBRARIES = frozenset(
    {
        "mcp",
        "pysnow",
        "msgraph",
        "msgraph_core",
        "onelogin",
        "duo_client",
        "duo_universal",
    }
)

# Names that only exist to reach a customer system. Matched on the identifier, because that is what
# a reintroduction would actually look like in a diff.
CONNECTOR_SYMBOLS = (
    "ServiceNowAdapter",
    "MicrosoftGraphAdapter",
    "McpToolClient",
    "McpClient",
    "OneLoginAdapter",
    "DuoAdapter",
    "TenantCredentialResolver",
    "CredentialReferenceStorePort",
    "EntitlementCredentials",
)

# Host fragments belonging to systems this deployable must not know how to reach. A destination is
# not itself an authorization, but code that can name one is code someone can later point at it.
EXTERNAL_HOSTS = (
    "service-now.com",
    "servicenow.com",
    "graph.microsoft.com",
    "onelogin.com",
    "duosecurity.com",
)


def _modules() -> list[Path]:
    """Every RagCore source module outside the permitted model subtree."""
    return [
        path
        for path in SRC.rglob("*.py")
        if MODEL_PACKAGE not in path.parents and path != MODEL_PACKAGE
    ]


def _imported_roots(path: Path) -> set[str]:
    """The top-level package of every import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_connector_library_is_imported_anywhere_in_ragcore() -> None:
    """**1 of 3.** A connector client library in this tree is a direct path by construction."""
    offenders = {
        path.relative_to(SRC).as_posix(): sorted(_imported_roots(path) & CONNECTOR_LIBRARIES)
        for path in _modules()
        if _imported_roots(path) & CONNECTOR_LIBRARIES
    }

    assert not offenders, (
        f"RagCore imports a connector library: {offenders}. Every external connector belongs to "
        "the Integrations Service (ADR-0007). RagCore reaches it through APIM or over Service Bus."
    )


def test_no_connector_type_is_defined_or_instantiated_in_ragcore() -> None:
    """**2 of 3.** Catches the reintroduction that brings no new dependency with it.

    An adapter written by hand over ``httpx`` imports nothing this suite bans, which is exactly why
    the library check alone is not enough. ``httpx`` itself is legitimate here — it is how RagCore
    reaches the gateway, its own index and the Integrations Service — so what is checked is the
    *name*, which is what a reintroduction looks like in a diff.
    """
    offenders: dict[str, list[str]] = {}

    for path in _modules():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        found = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef) and node.name in CONNECTOR_SYMBOLS
        } | {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in CONNECTOR_SYMBOLS
        }
        if found:
            offenders[path.relative_to(SRC).as_posix()] = sorted(found)

    assert not offenders, (
        f"RagCore defines or instantiates a connector: {offenders}. These types moved to the "
        "Integrations Service with T288–T292; a copy here would be the direct path the boundary "
        "removes, and the platform would have two answers to 'who may call ServiceNow'."
    )


def test_no_module_outside_the_model_package_holds_an_external_endpoint() -> None:
    """**3 of 3.** An address is the first thing a direct call needs.

    The model package is exempt because the AI Gateway is a **platform** destination: RagCore owns
    its own reasoning path, and the gateway is not a customer system behind a per-organisation
    credential. That exemption is why the host list below names customer systems only.
    """
    offenders: dict[str, list[str]] = {}

    for path in _modules():
        source = path.read_text(encoding="utf-8")
        found = [host for host in EXTERNAL_HOSTS if host in source]
        if found:
            offenders[path.relative_to(SRC).as_posix()] = found

    assert not offenders, (
        f"RagCore names an external system's address: {offenders}. Knowing where a customer system "
        "lives permits nothing on its own, but it is the one thing a direct call cannot be written "
        "without — so the address belongs in the Integrations Service's connector registry."
    )


def test_the_composition_root_binds_no_connector() -> None:
    """The four ports that used to hold adapters are bound to ``None``, and that is deliberate.

    **A stand-in would be worse than a connector**, which is why this asserts `None` rather than
    merely asserting that no adapter class is named. A stand-in is an object with a method to call,
    and the first caller to call it would have re-created the in-process path this removes — while
    every test kept passing, because a stand-in returns successfully.
    """
    from ragcore.config.composition import Container
    from ragcore.config.settings import Settings

    container = Container(settings=Settings.model_construct(), clock=None)  # type: ignore[arg-type]

    for port in ("case_system", "directory", "execution", "discovery"):
        assert getattr(container, port) is None, (
            f"{port} is bound to something. It must be None: capabilities execute in the "
            "Integrations Service, and an in-process implementation here would be the direct path "
            "ADR-0007 removes."
        )


def test_the_permitted_model_subtree_is_the_only_exemption() -> None:
    """The exemption is **one named directory**, asserted rather than assumed.

    If this file's notion of "permitted" ever widened silently — by a second exempt path, or by the
    model package moving — the three tests above would keep passing while checking less. Pinning the
    exemption is what stops the guard from quietly shrinking.
    """
    assert MODEL_PACKAGE.is_dir()
    assert MODEL_PACKAGE.relative_to(SRC).as_posix() == "integrations/model"

    # And the thing it is exempt FOR is a gateway, not a connector.
    gateway = (MODEL_PACKAGE / "gateway.py").read_text(encoding="utf-8")
    assert not any(host in gateway for host in EXTERNAL_HOSTS)
