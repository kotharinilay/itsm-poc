"""Compare a generated OpenAPI document against its committed baseline. Fail on a breaking change.

**One comparator for both stacks.** RagCore and the .NET monolith each emit their own documents;
this compares all of them. A second implementation would drift, and the drift would be invisible
until the weaker of the two was the one that mattered — the same reasoning as the shared Azure
identity registry.

**Breaking is defined from the client's side, not the server's.** The question is never "did the
document change" — it changes on every feature — but "would a client built against the old document
still work against the new one?" So:

*Breaking*
  Removing a path, an operation, a response code, or a response field a client may already read.
  Adding a **required** request field or parameter, which rejects requests that used to succeed.
  Narrowing a type or removing an enum value the client may already send.
  Making an optional request field required.

*Not breaking*
  Adding a path, an operation, an optional request field, a response field, or an enum value in a
  **response**. A client that ignores what it does not recognise keeps working.

**Enum direction matters and is easy to get backwards.** Removing a value a client may *send* breaks
it; adding one it may *receive* can break a strict client but is the accepted cost of evolution, and
is reported as a warning rather than a failure.

Exit codes: ``0`` clean or additive only, ``1`` breaking change, ``2`` a baseline is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BREAKING: int = 1
MISSING_BASELINE: int = 2

_METHODS = frozenset({"get", "put", "post", "delete", "patch", "head", "options", "trace"})


def _operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Every ``(path, method)`` operation in a document."""
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for path, item in document.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() in _METHODS and isinstance(operation, dict):
                found[(path, method.lower())] = operation
    return found


def _resolve(document: dict[str, Any], node: Any) -> Any:  # noqa: ANN401
    """Follow a ``$ref`` one level into the document's own components."""
    if isinstance(node, dict) and "$ref" in node:
        marker = "#/components/schemas/"
        reference = node["$ref"]
        if isinstance(reference, str) and reference.startswith(marker):
            return (
                document.get("components", {}).get("schemas", {}).get(reference[len(marker) :], {})
            )
    return node


def _request_schema(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    """The JSON request schema of an operation, resolved, or an empty mapping."""
    body = operation.get("requestBody", {})
    content = body.get("content", {}) if isinstance(body, dict) else {}
    schema = content.get("application/json", {}).get("schema", {})
    resolved = _resolve(document, schema)
    return resolved if isinstance(resolved, dict) else {}


def _response_schema(
    document: dict[str, Any], operation: dict[str, Any], code: str
) -> dict[str, Any]:
    """The JSON response schema for one status code, resolved, or an empty mapping."""
    response = operation.get("responses", {}).get(code, {})
    content = response.get("content", {}) if isinstance(response, dict) else {}
    schema = content.get("application/json", {}).get("schema", {})
    resolved = _resolve(document, schema)
    return resolved if isinstance(resolved, dict) else {}


def _required(schema: dict[str, Any]) -> set[str]:
    required = schema.get("required", [])
    return set(required) if isinstance(required, list) else set()


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    return properties if isinstance(properties, dict) else {}


def _type_of(schema: dict[str, Any]) -> str:
    """A comparable rendering of a property's type, tolerant of OpenAPI's several spellings."""
    if "type" in schema:
        return str(schema["type"])
    if "$ref" in schema:
        return str(schema["$ref"])
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema and isinstance(schema[key], list):
            return key + "[" + ",".join(sorted(_type_of(part) for part in schema[key])) + "]"
    return "unspecified"


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Compare two documents.

    Args:
        baseline: The committed contract.
        current: The freshly generated document.

    Returns:
        ``(breaking, additive)`` — two lists of human-readable findings.
    """
    breaking: list[str] = []
    additive: list[str] = []

    old_ops = _operations(baseline)
    new_ops = _operations(current)

    for key in sorted(set(old_ops) - set(new_ops)):
        breaking.append(f"operation removed: {key[1].upper()} {key[0]}")

    for key in sorted(set(new_ops) - set(old_ops)):
        additive.append(f"operation added: {key[1].upper()} {key[0]}")

    for key in sorted(set(old_ops) & set(new_ops)):
        path, method = key
        where = f"{method.upper()} {path}"
        old, new = old_ops[key], new_ops[key]

        old_codes = set(old.get("responses", {}))
        new_codes = set(new.get("responses", {}))
        for code in sorted(old_codes - new_codes):
            breaking.append(f"response {code} removed: {where}")
        for code in sorted(new_codes - old_codes):
            additive.append(f"response {code} added: {where}")

        _compare_request(baseline, current, old, new, where, breaking, additive)

        for code in sorted(old_codes & new_codes):
            _compare_response(baseline, current, old, new, code, where, breaking, additive)

        _compare_parameters(old, new, where, breaking, additive)

    return breaking, additive


def _compare_request(
    baseline: dict[str, Any],
    current: dict[str, Any],
    old: dict[str, Any],
    new: dict[str, Any],
    where: str,
    breaking: list[str],
    additive: list[str],
) -> None:
    """A request gets stricter: that is the breaking direction."""
    old_schema = _request_schema(baseline, old)
    new_schema = _request_schema(current, new)

    if not old_schema and not new_schema:
        return

    old_required, new_required = _required(old_schema), _required(new_schema)
    old_props, new_props = _properties(old_schema), _properties(new_schema)

    for field in sorted(new_required - old_required):
        # Rejects requests that used to succeed, whether the field is new or was optional.
        breaking.append(f"request field now required: {field} in {where}")

    for field in sorted(set(new_props) - set(old_props) - new_required):
        additive.append(f"optional request field added: {field} in {where}")

    for field in sorted(set(old_props) - set(new_props)):
        breaking.append(f"request field removed: {field} in {where}")

    for field in sorted(set(old_props) & set(new_props)):
        old_type = _type_of(_resolve(baseline, old_props[field]))
        new_type = _type_of(_resolve(current, new_props[field]))
        if old_type != new_type:
            breaking.append(
                f"request field type changed: {field} in {where} ({old_type} -> {new_type})"
            )

        removed = _enum_of(old_props[field]) - _enum_of(new_props[field])
        if removed:
            # A value the client may already be sending stops being accepted.
            breaking.append(f"request enum value removed: {field} in {where} ({sorted(removed)})")


def _compare_response(
    baseline: dict[str, Any],
    current: dict[str, Any],
    old: dict[str, Any],
    new: dict[str, Any],
    code: str,
    where: str,
    breaking: list[str],
    additive: list[str],
) -> None:
    """A response gets thinner: that is the breaking direction."""
    old_schema = _response_schema(baseline, old, code)
    new_schema = _response_schema(current, new, code)

    old_props, new_props = _properties(old_schema), _properties(new_schema)

    for field in sorted(set(old_props) - set(new_props)):
        breaking.append(f"response field removed: {field} in {where} {code}")

    for field in sorted(set(new_props) - set(old_props)):
        additive.append(f"response field added: {field} in {where} {code}")

    for field in sorted(set(old_props) & set(new_props)):
        old_type = _type_of(_resolve(baseline, old_props[field]))
        new_type = _type_of(_resolve(current, new_props[field]))
        if old_type != new_type:
            breaking.append(
                f"response field type changed: {field} in {where} {code} ({old_type} -> {new_type})"
            )


def _compare_parameters(
    old: dict[str, Any],
    new: dict[str, Any],
    where: str,
    breaking: list[str],
    additive: list[str],
) -> None:
    """A new required parameter rejects calls that used to work."""

    def indexed(operation: dict[str, Any]) -> dict[str, dict[str, Any]]:
        parameters = operation.get("parameters", [])
        if not isinstance(parameters, list):
            return {}
        return {
            f"{parameter.get('in')}:{parameter.get('name')}": parameter
            for parameter in parameters
            if isinstance(parameter, dict)
        }

    old_parameters, new_parameters = indexed(old), indexed(new)

    for key in sorted(set(old_parameters) - set(new_parameters)):
        breaking.append(f"parameter removed: {key} in {where}")

    for key in sorted(set(new_parameters) - set(old_parameters)):
        if new_parameters[key].get("required"):
            breaking.append(f"required parameter added: {key} in {where}")
        else:
            additive.append(f"optional parameter added: {key} in {where}")

    for key in sorted(set(old_parameters) & set(new_parameters)):
        if new_parameters[key].get("required") and not old_parameters[key].get("required"):
            breaking.append(f"parameter now required: {key} in {where}")


def _enum_of(schema: Any) -> set[str]:  # noqa: ANN401
    values = schema.get("enum") if isinstance(schema, dict) else None
    return {str(value) for value in values} if isinstance(values, list) else set()


def main(argv: list[str] | None = None) -> int:
    """Compare every generated document against its baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path, help="committed contracts")
    parser.add_argument("--current", required=True, type=Path, help="freshly generated contracts")
    arguments = parser.parse_args(argv)

    generated = sorted(arguments.current.rglob("*.openapi.json"))
    if not generated:
        print(f"no generated documents under {arguments.current}", file=sys.stderr)
        return MISSING_BASELINE

    status = 0

    for document_path in generated:
        relative = document_path.relative_to(arguments.current)
        baseline_path = arguments.baseline / relative

        if not baseline_path.is_file():
            # A new contract is not a breaking change, but it must be committed deliberately —
            # otherwise the first published version of an API is whatever CI happened to generate.
            print(f"::error::no committed baseline for {relative}. Commit it to publish this API.")
            status = max(status, MISSING_BASELINE)
            continue

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current = json.loads(document_path.read_text(encoding="utf-8"))

        breaking, additive = compare(baseline, current)

        for finding in additive:
            print(f"::notice::{relative}: {finding}")

        for finding in breaking:
            print(f"::error::{relative}: BREAKING {finding}")

        if breaking:
            status = BREAKING
        elif not additive:
            print(f"{relative}: unchanged")

    return status


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
