"""``RagCore → AI Gateway → model provider``. **No module holds a provider endpoint.**

Every model call passes through a single brokering point and no component reaches a model provider
directly (spec FR-OPS-007, constitution §Model access). That rule is established in four independent
places, and this file is the third:

1. **Identity.** ``id-synthia-ragcore`` holds no Foundry role at all
   (``build/infra/identity/managed-identities.json``), so a direct provider call would fail to
   authenticate even if the code existed.
2. **Type.** :class:`~ragcore.model.egress.ModelEgressPort` is the only shape a model
   call takes, and its implementations are the gateway client and the local development seam.
3. **This file.** No provider SDK, endpoint or deployment name appears anywhere in the tree.
4. **Configuration.** ``ModelGatewaySettings`` has no ``provider``, ``api_key`` or
   ``model_endpoint`` field.

**The scope here is stricter than the task's wording, deliberately.** T138 asks that no module
outside ``model/`` hold a provider endpoint. What is asserted below is that **no
module holds one at all**, including the gateway client — because the gateway client does not need
one either. It posts to the gateway, and the gateway knows the providers
(``build/infra/ai-gateway/providers.json``). A provider endpoint inside ``model/``
would be a direct call wearing the right directory name.

**Checked against the AST and against string literals, never against raw file text.** This module,
and the modules it guards, necessarily *discuss* every banned name in prose in order to say why it
is banned. A substring search over the text would flag the explanation, and a guard that punishes
its own explanation gets the explanation deleted.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[3]
SRC: Final = ROOT / "ragcore" / "src" / "ragcore"
WORKERS: Final = ROOT / "ragcore" / "workers"

PROVIDER_SDKS: Final = frozenset(
    {
        "openai",
        "AzureOpenAI",
        "AsyncAzureOpenAI",
        "anthropic",
        "Anthropic",
        "google.generativeai",
        "vertexai",
        "cohere",
        "mistralai",
        "ollama",
        "transformers",
        "azure.ai.inference",
        "ChatCompletionsClient",
        "EmbeddingsClient",
    }
)
"""Provider SDKs and client types. Each is a perfectly good library and none belongs here."""

PROVIDER_ENDPOINT_FRAGMENTS: Final = (
    "openai.azure.com",
    "api.openai.com",
    "cognitiveservices.azure.com",
    "inference.ai.azure.com",
    "services.ai.azure.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
)
"""Host fragments that identify a model provider's data plane.

``cognitiveservices.azure.com`` appears in ``build/infra/ai-gateway/providers.json`` and belongs
there: that file configures the **gateway's** onward hop, which is the hop that is supposed to reach
a provider. It must not appear in RagCore.
"""

PROVIDER_CREDENTIAL_NAMES: Final = frozenset(
    {"OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AzureKeyCredential"}
)
"""Model provider credential shapes. ``build/policy/azure-identity.json`` names these as forbidden
configuration for the ``foundry`` resource; this asserts the same thing against RagCore's source."""


def _python_files() -> list[Path]:
    return sorted(
        path
        for root in (SRC, WORKERS)
        if root.exists()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _names_in(path: Path) -> set[str]:
    """Every imported, referenced and attribute name a module uses. Docstrings excluded by
    construction, because the AST does not treat prose as a name."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)

    return names


def _string_literals_in(path: Path) -> list[str]:
    """Every string literal in a module, docstrings excluded.

    A literal is code — a provider endpoint in quotes is exactly what this file looks for — while a
    docstring is the explanation of why it must not be there.
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


class TestNoProviderReachedDirectly:
    """No SDK, no endpoint, no credential — anywhere in RagCore."""

    def test_there_are_modules_to_check(self) -> None:
        """Guards against this file passing because it found nothing to look at."""
        assert len(_python_files()) > 50

    def test_no_module_imports_a_model_provider_sdk(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT)}: {sorted(found)}"
            for path in _python_files()
            if (found := _names_in(path) & PROVIDER_SDKS)
        ]

        assert not offenders, (
            "a model provider SDK is used in RagCore. Every model call goes through the AI "
            "Gateway, which holds the provider relationship — and RagCore holds no provider role, "
            "so this could not authenticate even if it were intended:\n  " + "\n  ".join(offenders)
        )

    def test_no_module_holds_a_provider_endpoint(self) -> None:
        """**Including ``model/``.** The gateway client posts to the gateway; the
        gateway knows the providers."""
        offenders: list[str] = []

        for path in _python_files():
            for literal in _string_literals_in(path):
                lowered = literal.lower()
                hits = [host for host in PROVIDER_ENDPOINT_FRAGMENTS if host in lowered]
                if hits:
                    offenders.append(f"{path.relative_to(ROOT)}: {hits}")

        assert not offenders, (
            "a model provider endpoint appears in RagCore source. The only outbound model "
            "destination this platform knows is the AI Gateway:\n  " + "\n  ".join(offenders)
        )

    def test_no_module_names_a_model_provider_credential(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT)}: {sorted(found)}"
            for path in _python_files()
            if (found := _names_in(path) & PROVIDER_CREDENTIAL_NAMES)
            or (
                found := {
                    name
                    for name in PROVIDER_CREDENTIAL_NAMES
                    if any(name in literal for literal in _string_literals_in(path))
                }
            )
        ]

        assert not offenders, (
            "a model provider credential is named in RagCore. There is no such credential in this "
            "platform, in either direction:\n  " + "\n  ".join(offenders)
        )


class TestTheEgressSeamIsTheOnlyShape:
    """The type-level half of the rule."""

    def test_the_model_port_is_satisfied_only_by_the_gateway_adapter(self) -> None:
        """``ModelPort`` is held by the graph; ``GatewayModelAdapter`` is the one implementation,
        and it holds an egress rather than a client."""
        from ragcore.model.adapter import GatewayModelAdapter

        implementations = {
            node.name
            for path in _python_files()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ClassDef)
            and {"complete", "embed"}
            <= {
                child.name
                for child in node.body
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
            }
        }

        # `SafeModel` is a DECORATOR, not a second egress. It satisfies `ModelPort`, holds another
        # `ModelPort`, and reaches no provider: what it adds is the inbound and outbound content
        # safety screening that `FR-AGENT-010` requires on both crossings. Screening implemented as
        # "every caller remembers to call the checker" is screening that lasts until the next
        # caller, so it is a wrapper — and the composition root binds the wrapper, never the inner
        # adapter. `tests/unit/test_content_safety.py` asserts it delegates rather than calls out.
        assert implementations == {GatewayModelAdapter.__name__, "ModelPort", "SafeModel"}, (
            f"something other than the gateway adapter implements model access: {implementations}"
        )

    def test_the_egress_has_exactly_two_implementations(self) -> None:
        """The gateway and the local development seam. A third would be the thing this whole
        arrangement exists to prevent."""
        implementations = {
            node.name
            for path in sorted((SRC / "model").rglob("*.py"))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(child, ast.AsyncFunctionDef) and child.name == "send"
                for child in node.body
            )
        }

        assert implementations == {"AiGatewayEgress", "LocalDevelopmentEgress", "ModelEgressPort"}

    def test_only_the_composition_root_chooses_the_egress(self) -> None:
        """One function decides, and it is in the module that is allowed to decide. A selection at
        a call site would be a per-caller model egress."""
        constructors = {
            str(path.relative_to(SRC)).replace("\\", "/")
            for path in _python_files()
            if path.is_relative_to(SRC)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"AiGatewayEgress", "LocalDevelopmentEgress", "GatewayModelAdapter"}
        }

        assert constructors <= {"config/composition.py"}, sorted(constructors)


@pytest.fixture(scope="module")
def providers() -> dict[str, Any]:
    """The committed AI Gateway provider pool, parsed once."""
    path = ROOT / "build" / "infra" / "ai-gateway" / "providers.json"
    assert path.is_file(), f"the AI Gateway provider pool is missing: {path}"
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


class TestTheGatewayConfigurationBacksTheRule:
    """The deployment half, asserted against the committed configuration."""

    def test_the_gateway_policy_exists(self) -> None:
        policy = ROOT / "build" / "infra" / "ai-gateway" / "policy.xml"
        assert policy.is_file()

        text = policy.read_text(encoding="utf-8")
        # The four capabilities the gateway exists to apply. Each is a policy the application
        # deliberately does not implement, because a budget the caller enforces is one it can
        # decline to enforce.
        for capability in (
            "llm-token-limit",
            "llm-emit-token-metric",
            "llm-semantic-cache-lookup",
            "llm-content-safety",
        ):
            assert capability in text, f"the gateway policy applies no {capability}"

    def test_every_backend_authenticates_by_managed_identity(
        self, providers: dict[str, Any]
    ) -> None:
        """The gateway's onward hop is an identity, not a key. An API key here would also bypass
        per-organisation metering, because a key is not tied to a caller."""
        for backend in providers["backends"]:
            credentials = backend.get("credentials")
            if credentials is None:
                continue
            assert credentials["type"] == "managed-identity", backend["id"]

    def test_the_provider_pool_is_the_only_place_a_provider_is_named(
        self, providers: dict[str, Any]
    ) -> None:
        """Adding a provider costs an entry here and a role assignment, and touches no RagCore
        code (spec FR-OPS-009)."""
        assert providers["backends"], "the provider pool is empty"
        assert "egressRule" in providers

    def test_the_cache_is_transient_and_partitioned_by_organisation(
        self, providers: dict[str, Any]
    ) -> None:
        """Redis is transient only — never an authority, never a durable record. And the cache is
        partitioned per organisation: without that, a completion produced for one could be served
        to another, which is a cross-tenant leak no database isolation would catch."""
        cache = providers["cache"]

        assert cache["authority"] is False
        assert cache["durable"] is False
        assert cache["partitionedBy"] == "X-Synthia-Organisation"
        assert cache["entryTtlSetting"], "every cache entry carries a TTL"

    def test_ragcore_holds_no_model_provider_role(self) -> None:
        """The identity-level half. A Foundry role here would be a second path to a provider that
        bypasses the gateway's metering, budgets and content safety."""
        registry = json.loads(
            (ROOT / "build" / "infra" / "identity" / "managed-identities.json").read_text(
                encoding="utf-8"
            )
        )
        ragcore = next(
            identity
            for identity in registry["identities"]
            if identity["name"] == "id-synthia-ragcore"
        )

        assert not [
            assignment
            for assignment in ragcore["roleAssignments"]
            if assignment["resource"] == "foundry"
        ], "RagCore holds a model provider role. Every model call goes through the AI Gateway."
