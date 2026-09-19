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
    """Internal-only vocabulary, forbidden anywhere in a document. Exact match.

    Exact rather than substring: ``checkpoint`` must not be a field, but a schema called
    ``CheckpointPolicySummary`` would be a legitimate read model and a substring rule would reject
    it.

    **Derived authority is not in this set**, and that is a correction rather than an omission.
    ``tenantId`` in a *response* is the organisation a row belongs to, reported to a caller already
    entitled to the row; forbidding the name outright would force an audit read model to hide the
    organisation a record concerns, which is the field a staff reviewer opens it for. What must not
    exist is a channel by which a client *asserts* one — see :func:`authority_findings`.
    """
    return frozenset(_policy()["internalTerms"]["implementationDetail"])


def derived_authority() -> frozenset[str]:
    """Authority the platform derives and never accepts from a client. Exact match."""
    return frozenset(_policy()["internalTerms"]["derivedAuthority"])


def structural_keys() -> frozenset[str]:
    """Keys of the OpenAPI format itself, which are never findings."""
    return frozenset(_policy()["structuralKeys"]["keys"])


def _normalise(name: str) -> str:
    """Reduce a name to letters for matching, so ``api_key`` and ``api-key`` compare alike."""
    return "".join(character for character in name.lower() if character.isalnum())


def _walk_names(node: Any, path: str = "") -> Iterable[tuple[str, str]]:
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


def authority_findings(document: Mapping[str, Any], audience: str) -> list[str]:
    """Every place in ``document`` a client could assert tenant, role or audience.

    **A position rule, not a name rule.** The platform derives tenant, roles and audience and never
    accepts them (constitution P-I, contracts §README rule 1), so what must not exist is a *channel*
    — a parameter or a request-body field. A name rule would be satisfied by renaming the field
    rather than by removing the channel, which is a rule that looks enforced and is not.

    The narrowing exception is read from the policy file rather than written here: ``tenantId`` is a
    staff-only query filter selecting *within* the set the caller may already see.

    Args:
        document: A generated OpenAPI document.
        audience: The audience it describes, which decides whether the exception applies.

    Returns:
        Human-readable findings, empty when the document offers no such channel.
    """
    names = derived_authority()
    positions = _policy()["authorityPositions"]
    forbidden = frozenset(positions["forbiddenIn"])

    def permitted(name: str, location: str) -> bool:
        return any(
            _normalise(exception["name"]) == _normalise(name)
            and exception["in"] == location
            and audience in exception["audiences"]
            for exception in positions["exceptions"]
        )

    findings: list[str] = []
    methods = frozenset({"get", "put", "post", "delete", "patch", "head", "options", "trace"})

    for path, item in document.get("paths", {}).items():
        if not isinstance(item, dict):
            continue

        for method, operation in item.items():
            if method.lower() not in methods or not isinstance(operation, dict):
                continue

            if "parameter" in forbidden:
                for parameter in operation.get("parameters", []) or []:
                    if not isinstance(parameter, dict):
                        continue
                    name = str(parameter.get("name", ""))
                    where = str(parameter.get("in", ""))
                    if _normalise(name) in names and not permitted(name, where):
                        findings.append(
                            f"client-suppliable authority: {where} parameter {name!r} on "
                            f"{method.upper()} {path}"
                        )

            if "requestBody" in forbidden:
                body = operation.get("requestBody")
                if isinstance(body, dict):
                    findings.extend(_authority_in_request(document, body, names))

    return sorted(set(findings))


def _authority_in_request(
    document: Mapping[str, Any], body: Any, names: frozenset[str]
) -> list[str]:
    """Findings among the schemas one request body reaches, transitively.

    Transitive because a body referencing a wrapper that references the offending schema is the same
    channel one level down — exactly where a check looking only at the top level would stop.
    """
    schemas: Mapping[str, Any] = document.get("components", {}).get("schemas", {})
    frontier = set(_references(body))
    reached: set[str] = set()
    findings: list[str] = []

    while frontier:
        schema_name = frontier.pop()
        if schema_name in reached or schema_name not in schemas:
            continue
        reached.add(schema_name)
        schema = schemas[schema_name]
        frontier |= set(_references(schema)) - reached

        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if not isinstance(properties, dict):
            continue

        findings.extend(
            f"client-suppliable authority: request field {field!r} on schema {schema_name!r}"
            for field in properties
            if _normalise(field) in names
        )

    return findings


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


def _references(node: Any) -> Iterable[str]:
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


# ---------------------------------------------------------------------------
# RFC 9457: the media type the error contract is published at
# ---------------------------------------------------------------------------

PROBLEM_SCHEMA_REF: Final = "#/components/schemas/ProblemDetails"
PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
_DEFAULT_MEDIA_TYPE: Final = "application/json"


def _is_problem(content_entry: Any) -> bool:
    """Whether one ``content`` entry carries the problem-details schema."""
    schema = content_entry.get("schema") if isinstance(content_entry, dict) else None
    return isinstance(schema, dict) and schema.get("$ref") == PROBLEM_SCHEMA_REF


def relabel_problem_media_type(document: dict[str, Any]) -> dict[str, Any]:
    """Publish every problem response at ``application/problem+json``.

    **Why a pass rather than a declaration.** FastAPI writes an operation's additional responses at
    the media type of the *route's* response class, so the error responses of a route that succeeds
    with JSON are documented as ``application/json``. RFC 9457 requires ``application/problem+json``
    and that is what :mod:`ragcore.api.middleware.problems` actually sends, so a document saying
    otherwise describes a response the service does not produce.

    The alternative — giving every route a problem response class — would change the media type of
    its *success* body too, which is wrong in a louder way.

    This is a relabelling of a generated document, not a second description of it: the schema, the
    statuses and the titles all come from the route declarations. It is applied by
    :func:`install_contract_openapi` so the served document and the emitted artifact are the same
    bytes.

    Args:
        document: The generated document. Mutated in place and returned.

    Returns:
        The same document.
    """
    for item in document.get("paths", {}).values():
        if not isinstance(item, dict):
            continue
        for operation in item.values():
            if not isinstance(operation, dict):
                continue
            for response in operation.get("responses", {}).values():
                content = response.get("content") if isinstance(response, dict) else None
                if not isinstance(content, dict):
                    continue
                entry = content.get(_DEFAULT_MEDIA_TYPE)
                if _is_problem(entry) and PROBLEM_MEDIA_TYPE not in content:
                    content[PROBLEM_MEDIA_TYPE] = content.pop(_DEFAULT_MEDIA_TYPE)

    return document


def install_contract_openapi(app: FastAPI) -> None:
    """Make ``/openapi.json`` and the published artifact the same document.

    The served document is what a developer reads and what APIM imports; the artifact is what CI
    compares. Generating them by two paths is how they come to disagree, so there is one path and
    this installs it.

    Args:
        app: The application to install onto.
    """
    generated: dict[str, Any] = {}

    def contract_openapi() -> dict[str, Any]:
        # FastAPI caches in `app.openapi_schema`; this cache exists for the same reason and is
        # separate only because the attribute is FastAPI's to manage.
        if not generated:
            from fastapi.openapi.utils import get_openapi  # Deferred, heavy import

            generated.update(
                relabel_problem_media_type(
                    get_openapi(
                        title=app.title,
                        version=app.version,
                        description=app.description,
                        routes=app.routes,
                    )
                )
            )
        return generated

    app.openapi = contract_openapi  # type: ignore[method-assign]
