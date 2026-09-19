"""Structural questions about the Front Door definition, for ``check-edge-path.sh``.

**Why an interpreter in a guard that is otherwise grep-only.** The rules this answers are about
*structure* — which origin group a route targets, whether every origin is private — and a grep that
answered them would be answering an easier question that happens to match. The rest of the guard
stays grep-only because its rules really are textual: a header is stripped, a token is validated.

Prints one line, and nothing else, so the shell can compare it. No dependency beyond the standard
library, and no import from either deployable: this is build tooling and must run on a machine with
neither toolchain installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

GATEWAY_GROUP = "apim"
"""The one origin group that may serve an API. The portals serve static files."""


def _document(path: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return loaded


def groups(document: dict[str, Any]) -> str:
    """Every origin group name, in declaration order."""
    return " ".join(group["name"] for group in document["originGroups"])


def public_origins(document: dict[str, Any]) -> str:
    """Origins reached without Private Link — each one a target holding a public endpoint.

    **The link must actually name a resource**, not merely be present. Asserting the key exists
    was the first version of this check, and the guard prover caught it: an entry whose
    ``privateLink`` had been renamed still had the outer key, so a public origin passed. A control
    that checks a container rather than its contents is a control somebody empties.
    """
    return " ".join(
        origin["name"]
        for group in document["originGroups"]
        for origin in group["origins"]
        if not str(origin.get("sharedPrivateLinkResource", {}).get("privateLink", "")).strip()
    )


def api_on_portal(document: dict[str, Any]) -> str:
    """Routes that publish an ``/api`` path anywhere but the gateway group.

    A portal host answering ``/api`` would reach the platform on a host APIM never saw — the
    bypass the single gateway exists to prevent, wearing the costume of a routing entry.
    """
    return " ".join(
        f"{route['name']}->{pattern}"
        for route in document["routes"]
        if route["originGroup"] != GATEWAY_GROUP
        for pattern in route["patternsToMatch"]
        if pattern.startswith("/api")
    )


QUESTIONS = {
    "groups": groups,
    "public-origins": public_origins,
    "api-on-portal": api_on_portal,
}


def main(argv: list[str]) -> int:
    """Answer one question about one Front Door definition."""
    if len(argv) != 3 or argv[1] not in QUESTIONS:
        print(f"usage: edge_front_door.py [{'|'.join(QUESTIONS)}] <front-door.json>", file=sys.stderr)
        return 2

    print(QUESTIONS[argv[1]](_document(argv[2])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
