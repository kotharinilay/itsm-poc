"""Validate an emitted OpenAPI document against the rules a published contract must satisfy.

**One validator for both stacks, run over the EMITTED artifacts.** RagCore and the .NET monolith
generate their documents by different machinery; they are checked by one program reading one policy
file, because a rule implemented twice is a rule that is weaker on one side and nobody finds out
until the weaker side is the one that mattered.

**It validates artifacts, never source.** A rule applied to the code can be satisfied by code the
generator does not publish, and a rule applied to a hand-written copy is a rule about the copy. What
a client receives is the document, so the document is what is checked.

Four checks, each answering a question a reviewer would otherwise be asked to answer by reading:

``secrets``
    No secret, credential or internal implementation detail is named anywhere in the document
    (spec FR-DEMO-012). Matched against **names**, never descriptions: a description explaining that
    an operation carries no credential is correct documentation, and a scanner that flagged the
    prose would get the prose deleted.

``authority``
    Tenant, roles and audience never appear where a **client can supply them** — as a parameter or
    in a request body (A1 §4.5, contracts §README rule 1). They are permitted in a
    response, which is the organisation a row belongs to being reported back to a caller already
    entitled to it. The one narrowing exception is named in the policy file and scoped to the staff
    documents.

``problems``
    Every non-2xx response is an RFC 9457 problem document at ``application/problem+json``. Both
    deployables emit one error contract so a client parses one error shape; an operation that
    declares a different one, or declares nothing, is how a client grows a second error path.

``publication``
    The document is versioned by its **API** version rather than an assembly version, and carries no
    ``servers`` block. A ``servers`` entry names the host the document was generated on — the test
    host, a container address — which is configuration material describing a deployment rather than
    the contract, and it differs between the machine that emits and the machine that verifies.

Exit codes: ``0`` clean, ``1`` one or more findings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

FAILED: Final = 1

_METHODS: Final = frozenset(
    {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
)

_SCHEMA_REF_PREFIX: Final = "#/components/schemas/"
_PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

DEFAULT_POLICY: Final = Path(__file__).resolve().parents[1] / "policy" / "openapi-disclosure.json"


# ---------------------------------------------------------------------------
# Reading a document
# ---------------------------------------------------------------------------


def _normalise(name: str) -> str:
    """Reduce a name to letters and digits, so ``api_key`` and ``api-key`` compare alike."""
    return "".join(character for character in name.lower() if character.isalnum())


def _operations(document: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Every ``(path, method, operation)`` in a document."""
    found: list[tuple[str, str, dict[str, Any]]] = []
    for path, item in document.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() in _METHODS and isinstance(operation, dict):
                found.append((path, method.lower(), operation))
    return found


def _walk_names(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every ``(json path, key name)`` pair in a document. Keys only; values are not scanned."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            found.append((here, str(key)))
            found.extend(_walk_names(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk_names(value, f"{path}[{index}]"))
    return found


def _referenced(node: Any) -> set[str]:
    """Every component schema name reachable from ``node``, one level."""
    names: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith(_SCHEMA_REF_PREFIX):
                names.add(value[len(_SCHEMA_REF_PREFIX) :])
            else:
                names |= _referenced(value)
    elif isinstance(node, list):
        for value in node:
            names |= _referenced(value)
    return names


def _request_schemas(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The component schemas a **request body** can reach, transitively.

    Transitive because a request body referencing a wrapper that references the offending schema is
    the same channel one level down, which is exactly where a check that looked only at the top
    level would stop looking.
    """
    schemas: dict[str, Any] = document.get("components", {}).get("schemas", {})
    frontier: set[str] = set()

    for _, _, operation in _operations(document):
        body = operation.get("requestBody")
        if isinstance(body, dict):
            frontier |= _referenced(body)

    reached: dict[str, dict[str, Any]] = {}
    while frontier:
        name = frontier.pop()
        schema = schemas.get(name)
        if not isinstance(schema, dict) or name in reached:
            continue
        reached[name] = schema
        frontier |= _referenced(schema) - set(reached)

    return reached


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def secret_findings(document: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Names that must not be published anywhere in a document."""
    secrets = frozenset(policy["secretTerms"]["terms"])
    internals = frozenset(policy["internalTerms"]["implementationDetail"])
    structural = frozenset(policy["structuralKeys"]["keys"])

    findings: list[str] = []

    for location, name in _walk_names(document):
        if name in structural:
            continue

        normalised = _normalise(name)

        if any(term in normalised for term in secrets):
            findings.append(f"secret-bearing name {name!r} at {location}")
        elif normalised in internals:
            findings.append(f"internal-only name {name!r} at {location}")

    return sorted(set(findings))


def authority_findings(
    document: dict[str, Any], policy: dict[str, Any], audience: str
) -> list[str]:
    """Places a client could assert tenant, role or audience.

    Args:
        document: The emitted document.
        policy: The shared disclosure registry.
        audience: The audience this document describes, which decides whether the narrowing
            exception applies.

    Returns:
        Findings, empty when the document offers no such channel.
    """
    names = frozenset(policy["internalTerms"]["derivedAuthority"])
    positions = policy["authorityPositions"]
    forbidden = frozenset(positions["forbiddenIn"])
    exceptions = positions["exceptions"]

    def permitted(name: str, location: str) -> bool:
        return any(
            _normalise(exception["name"]) == _normalise(name)
            and exception["in"] == location
            and audience in exception["audiences"]
            for exception in exceptions
        )

    findings: list[str] = []

    if "parameter" in forbidden:
        for path, method, operation in _operations(document):
            for parameter in operation.get("parameters", []) or []:
                if not isinstance(parameter, dict):
                    continue
                name = str(parameter.get("name", ""))
                location = str(parameter.get("in", ""))
                if _normalise(name) in names and not permitted(name, location):
                    findings.append(
                        f"client-suppliable authority: {location} parameter {name!r} on "
                        f"{method.upper()} {path}. Tenant, roles and audience are derived at the "
                        f"gateway and never accepted."
                    )

    if "requestBody" in forbidden:
        for schema_name, schema in _request_schemas(document).items():
            properties = schema.get("properties", {})
            if not isinstance(properties, dict):
                continue
            for field in properties:
                if _normalise(field) in names:
                    findings.append(
                        f"client-suppliable authority: request field {field!r} on schema "
                        f"{schema_name!r}. A request body never carries authority."
                    )

    return sorted(set(findings))


def problem_findings(document: dict[str, Any]) -> list[str]:
    """Error responses that are not RFC 9457 problem documents."""
    findings: list[str] = []

    for path, method, operation in _operations(document):
        responses = operation.get("responses", {})
        if not isinstance(responses, dict):
            continue

        errors = [
            code
            for code in responses
            if code not in {"default", "1XX", "2XX"} and not code.startswith("2")
        ]

        if not errors:
            findings.append(
                f"{method.upper()} {path} declares no error response. Every operation can be "
                f"refused; a document that says otherwise leaves a client with no error contract "
                f"to parse."
            )
            continue

        for code in sorted(errors):
            response = responses[code]
            content = response.get("content") if isinstance(response, dict) else None

            if not isinstance(content, dict) or not content:
                findings.append(
                    f"{method.upper()} {path} {code} declares no body. An error a client cannot "
                    f"parse is an error a client reports as 'something went wrong'."
                )
                continue

            if _PROBLEM_MEDIA_TYPE not in content:
                findings.append(
                    f"{method.upper()} {path} {code} is published as "
                    f"{sorted(content)} rather than {_PROBLEM_MEDIA_TYPE}. Both deployables emit "
                    f"one RFC 9457 error contract so a client parses one error shape."
                )

    return sorted(set(findings))


def publication_findings(document: dict[str, Any], version: str) -> list[str]:
    """Version and deployment material a published contract must not carry."""
    findings: list[str] = []

    declared = str(document.get("info", {}).get("version", ""))
    if declared != version:
        findings.append(
            f"info.version is {declared!r}, expected {version!r}. The published version is the one "
            f"in the path, because that is the version a client is pinned to — not an assembly "
            f"version that moves on a patch release changing no route."
        )

    if document.get("servers"):
        findings.append(
            "a 'servers' block is published. It names the host the document was generated on, "
            "which is configuration material rather than contract and differs between the machine "
            "that emits and the machine that verifies. The public address is the gateway's to "
            "state."
        )

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _audience_of(path: Path) -> str:
    """The audience an artifact describes, from its file name (``staff.v1.openapi.json``)."""
    return path.name.split(".", 1)[0]


def validate(path: Path, policy: dict[str, Any], version: str) -> list[str]:
    """Every finding in one emitted document.

    Args:
        path: The artifact.
        policy: The shared disclosure registry.
        version: The API version the artifact must declare.

    Returns:
        Findings, empty when the document is publishable.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    audience = _audience_of(path)

    return [
        *secret_findings(document, policy),
        *authority_findings(document, policy, audience),
        *problem_findings(document),
        *publication_findings(document, version),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate every emitted document under a directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", required=True, type=Path, help="emitted contract directory")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="disclosure registry")
    parser.add_argument("--version", default="v1", help="the API version artifacts must declare")
    arguments = parser.parse_args(argv)

    policy: dict[str, Any] = json.loads(arguments.policy.read_text(encoding="utf-8"))
    documents = sorted(arguments.contracts.rglob("*.openapi.json"))

    if not documents:
        # Not "nothing to check": a validator that passes when it found no input is a gate that
        # opens when the emission step silently produced nothing.
        print(f"::error::no documents to validate under {arguments.contracts}", file=sys.stderr)
        return FAILED

    status = 0

    for document_path in documents:
        relative = document_path.relative_to(arguments.contracts)
        findings = validate(document_path, policy, arguments.version)

        for finding in findings:
            print(f"::error::{relative}: {finding}")

        if findings:
            status = FAILED
        else:
            print(f"{relative}: publishable")

    return status


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
