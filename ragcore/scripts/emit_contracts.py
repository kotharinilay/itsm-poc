"""Emit RagCore's per-audience OpenAPI documents.

Run from ``ragcore/``::

    uv run python scripts/emit_contracts.py --out ../build/contracts/ragcore

**Generated from the running application**, not from a template — the document comes from the
Pydantic models on each route, so it cannot describe something the service does not accept.

**Deterministic output.** Keys are sorted and the file ends with a newline, so a document that has
not changed produces a byte-identical file. Without that, every build shows a diff and the
comparator's signal is lost in noise nobody reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ragcore.api.app import create_app
from ragcore.api.openapi import (
    AUDIENCES,
    CONTRACT_VERSION,
    audience_document,
    disclosure_findings,
)
from ragcore.config.settings import DatabaseSettings, EdgeTrustSettings, Settings

PLACEHOLDER_DSN = "postgresql://synthia@localhost:5432/synthia"
"""Emission builds the app but never connects. The DSN satisfies validation and is used for nothing.

It is a local hostname with no password, so it is neither a secret nor a hint about a deployment.
"""


PLACEHOLDER_CERTIFICATE_HASH = "0" * 64
"""Satisfies the gateway allow-list so the app starts. Matches no certificate; not a secret."""


def _app_for_emission() -> object:
    """Build the application with settings that need no environment and no vault."""
    settings = Settings(
        database=DatabaseSettings(dsn=PLACEHOLDER_DSN),  # type: ignore[arg-type]
        # Emission builds the real application, and the real application refuses to start without a
        # gateway certificate allow-list. A placeholder is supplied rather than the check relaxed:
        # a document emitted from a differently-configured app is a document describing something
        # that does not run. The value is a syntactically valid digest matching no certificate.
        edge_trust=EdgeTrustSettings(gateway_certificate_thumbprints=PLACEHOLDER_CERTIFICATE_HASH),
    )
    return create_app(settings=settings)


def main(argv: list[str] | None = None) -> int:
    """Write one document per audience.

    Returns:
        ``0`` on success, ``1`` when a document would publish something it must not. Emission fails
        rather than writing a document a reviewer is then expected to catch.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    arguments = parser.parse_args(argv)

    arguments.out.mkdir(parents=True, exist_ok=True)
    app = _app_for_emission()
    failed = False

    for audience in AUDIENCES:
        document = audience_document(app, audience)  # type: ignore[arg-type]

        findings = disclosure_findings(document)
        if findings:
            failed = True
            for finding in findings:
                print(f"::error::{audience}: {finding}", file=sys.stderr)
            continue

        target = arguments.out / f"{audience}.{CONTRACT_VERSION}.openapi.json"
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        operations = sum(len(item) for item in document.get("paths", {}).values())
        print(f"{target}: {len(document.get('paths', {}))} paths, {operations} operations")

    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
