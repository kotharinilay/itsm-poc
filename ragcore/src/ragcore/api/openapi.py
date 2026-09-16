"""One OpenAPI document per audience, emitted from the running application.

**Generated, never hand-maintained.** The document comes from the Pydantic request and response
models on each route, so it cannot drift from what the service actually accepts. A hand-written
contract is a second description of the API with no mechanism keeping it true, and the first time it
disagrees, the client believes the document.

**One document per audience, and a merged document is prohibited.** ``customer``, ``staff`` and
``workload`` are separate surfaces with separate authorization; publishing them together would let a
customer-facing client discover the staff and workload operations. The split is by path prefix
because the prefix *is* the audience — the same fact APIM routes on and the same fact
``IdentityContextMiddleware`` resolves.

**Hygiene is part of emission, not a review step.** :func:`disclosure_findings` scans a document for
the three things it must never carry — secret material, internal credentials, and internal-only
implementation detail — and the contract tests fail the build on any finding. A rule applied by
reading the diff is a rule that holds until the week somebody is busy.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Iterable, Mapping

    from fastapi import FastAPI

CONTRACT_VERSION: Final = "v1"
"""The API version these documents describe. Part of the path, and part of the artifact name."""

AUDIENCES: Final[tuple[str, ...]] = ("customer", "staff", "workload")
"""The three published surfaces. There is no fourth, and no combined document."""

_PREFIX: Final = "/api/{audience}/" + CONTRACT_VERSION


def audience_prefix(audience: str) -> str:
    """The path prefix that defines an audience.

    Args:
        audience: One of :data:`AUDIENCES`.

    Returns:
        The prefix, for example ``/api/customer/v1``.

    Raises:
        ValueError: When the audience is not one of the three. A typo would otherwise emit an empty
            document, which looks like a service with no routes rather than a mistake.
    """
    if audience not in AUDIENCES:
        raise ValueError(f"unknown audience {audience!r}; expected one of {AUDIENCES}")
    return _PREFIX.replace("{audience}", audience)


# ---------------------------------------------------------------------------
# What a published document must never carry
# ---------------------------------------------------------------------------

DISCLOSURE_POLICY: Final = (
    Path(__file__).resolve().parents[3].parent / "build" / "policy" / "openapi-disclosure.json"
)
"""The shared registry of what a published document may never carry.

**Data rather than code, for two reasons.** The .NET side reads the same file, so the two stacks
cannot drift. And a list of credential-shaped words written as string literals in application source
is indistinguishable, to a secret scanner, from the credentials it describes —
``tests/security/test_azure_identity.py`` found exactly that and was right to.
"""


@lru_cache(maxsize=1)
def _policy() -> Mapping[str, Any]:
    """Load the disclosure policy once."""
    loaded: dict[str, Any] = json.loads(DISCLOSURE_POLICY.read_text(encoding="utf-8"))
    return loaded


def secret_terms() -> frozenset[str]:
    """Terms that must not appear as a field, parameter or schema name. Substring match."""
    return frozenset(_policy()["secretTerms"]["terms"])


def internal_terms() -> frozenset[str]:
    """Internal-only vocabulary and client-suppliable authority. Exact match.

    Exact rather than substring: ``roles`` must not be a parameter, but a schema called
    ``AcceptedRolesSummary`` is a legitimate read model and a substring rule would reject it.
    """
    internal = _policy()["internalTerms"]
    return frozenset(internal["implementationDetail"]) | frozenset(internal["derivedAuthority"])


def structural_keys() -> frozenset[str]:
    """Keys of the OpenAPI format itself, which are never findings."""
    return frozenset(_policy()["structuralKeys"]["keys"])


def _normalise(name: str) -> str:
    """Reduce a name to letters for matching, so ``api_key`` and ``api-key`` compare alike."""
    return "".join(character for character in name.lower() if character.isalnum())


def _walk_names(node: Any, path: str = "") -> Iterable[tuple[str, str]]:  # noqa: ANN401
    """Yield every ``(json path, key name)`` pair in a document.

    Keys only. Values are not scanned: a description saying "never carries a credential" is correct
    documentation, and a scanner that flagged it would get the documentation deleted.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            yield here, str(key)
            yield from _walk_names(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_names(value, f"{path}[{index}]")


def disclosure_findings(document: Mapping[str, Any]) -> list[str]:
    """Every name in ``document`` that must not be published.

    Args:
        document: A generated OpenAPI document.

    Returns:
        Human-readable findings, empty when the document is clean. Returned rather than raised so a
        caller can report all of them at once — three findings should cost one cycle to fix.
    """
    findings: list[str] = []
    secrets, internals, structural = secret_terms(), internal_terms(), structural_keys()

    for location, name in _walk_names(document):
        normalised = _normalise(name)

        # Skip the structural keys of OpenAPI itself; `security` and `securitySchemes` are part of
        # the format and describe *how* to authenticate, never *with what*.
        if name in structural:
            continue

        for term in secrets:
            if term in normalised:
                findings.append(f"secret-bearing name {name!r} at {location}")
                break
        else:
            for term in internals:
                if normalised == term:
                    findings.append(f"internal-only name {name!r} at {location}")
                    break

    return sorted(set(findings))


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


def audience_document(app: FastAPI, audience: str) -> dict[str, Any]:
    """Generate the OpenAPI document for one audience.

    Built by filtering the application's own generated document by path prefix, rather than by
    maintaining three apps: one app is what actually runs, and a document derived from anything else
    describes something that does not.

    Args:
        app: The application.
        audience: One of :data:`AUDIENCES`.

    Returns:
        The document, carrying only that audience's paths and only the schemas they reach.

    Raises:
        ValueError: When the audience is unknown.
    """
    prefix = audience_prefix(audience)
    full: dict[str, Any] = dict(app.openapi())

    paths = {
        path: operations
        for path, operations in full.get("paths", {}).items()
        if path.startswith(prefix)
    }

    document: dict[str, Any] = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": f"Synthia {audience.capitalize()} API",
            "version": CONTRACT_VERSION,
            "description": (
                f"The {audience} audience. Generated from the running service; "
                "not hand-maintained. Identity is derived at the gateway and no operation "
                "accepts a tenant, role or audience parameter."
            ),
        },
        "paths": dict(sorted(paths.items())),
    }

    components = _reachable_components(full, paths)
    if components:
        document["components"] = {"schemas": dict(sorted(components.items()))}

    return document


def _reachable_components(full: Mapping[str, Any], paths: Mapping[str, Any]) -> dict[str, Any]:
    """The component schemas this audience's paths actually reach, transitively.

    Carrying the whole component section into every audience would publish the staff models in the
    customer document — the leak this split exists to prevent, reintroduced one level down where
    nobody looks.
    """
    all_schemas: dict[str, Any] = dict(full.get("components", {}).get("schemas", {}))
    if not all_schemas:
        return {}

    wanted: set[str] = set()
    frontier: list[Any] = [paths]

    while frontier:
        node = frontier.pop()
        for reference in _references(node):
            if reference in all_schemas and reference not in wanted:
                wanted.add(reference)
                # Transitive: a schema reached from a path may itself reference others, and a
                # document missing a nested schema is invalid rather than merely incomplete.
                frontier.append(all_schemas[reference])

    return {name: schema for name, schema in all_schemas.items() if name in wanted}


def _references(node: Any) -> Iterable[str]:  # noqa: ANN401
    """Every ``#/components/schemas/X`` name reachable from ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                marker = "#/components/schemas/"
                if value.startswith(marker):
                    yield value[len(marker) :]
            else:
                yield from _references(value)
    elif isinstance(node, list):
        for value in node:
            yield from _references(value)
