"""Emit the Integrations Service OpenAPI document. **From the running application, never by hand.**

Spec `FR-DEMO-013`, `FR-INTEG-025`. The contract is an artifact rather than a document: it is
generated from the FastAPI application's own route models, so it cannot describe something the
service does not accept.

**One document per audience per deployable, and never merged.** RagCore and this service both serve
the workload audience and each emits its own; the compatibility gate diffs per deployable. A merged
document would let a customer-facing client discover this surface.

**Determinism is a gate, not a convention.** Every downstream check compares bytes, so this writes
sorted keys and bare line feeds. A generator that reordered a map or stamped the host it ran on
would make each build report changes nobody made — and hide the ones somebody did.

**Health is excluded** (`include_in_schema=False` on its router). Probes are platform infrastructure
rather than an API operation, and publishing them would describe an unauthenticated surface in a
document handed to API consumers.

**The CLI matches RagCore's exactly — `--out <directory>`** — and that is not cosmetic. Both are
invoked by the same workflow, and an emitter that silently accepted a different argument shape
produced a file named after the flag while the real document went unwritten. The comparison
downstream then diffed a directory against itself and passed. `--out` is `required` here for the
same reason it is there: a default output path is a path CI can take by accident.

**This module does NOT re-check disclosure**, and the omission is deliberate (constitution
Principle VI). `build/scripts/openapi_validate.py` is the one place the publishability policy is
expressed, it runs over the emitted tree in CI, and a second implementation here would be a second
answer to "may this be published" — with only one of the two ever exercised.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

from integrations.api.app import create_app
from integrations.api.health import ReadinessRegistry
from integrations.catalogue.registry import ConnectorRegistry
from integrations.catalogue.repository import CatalogueRepository, TenantResolver
from integrations.config.composition import Container
from integrations.config.settings import (
    IntegrationsSettings,
    ObservabilitySettings,
    PersistenceSettings,
)
from integrations.observability.telemetry import ConnectorMetrics
from integrations.persistence.engine import Database, build_engine
from integrations.policy.checks import AccessPolicy

AUDIENCE: Final = "workload"
"""The one audience this service serves.

There is no customer or staff document, and there will not be one: every route here is
service-to-service, reached by a workload principal through APIM. A customer-facing document
describing this surface would advertise it to clients that may never call it.
"""

CONTRACT_VERSION: Final = "v1"
"""Matches the version in the route path, because that is what a client pins to."""

DOCUMENT_NAME: Final = f"{AUDIENCE}.{CONTRACT_VERSION}.openapi.json"

# A syntactically valid placeholder so the application composes without a deployed environment. The
# document describes ROUTES AND SCHEMAS, neither of which depends on what the DSN points at, and
# emitting must not require a database — a contract that can only be produced from production is a
# contract nobody regenerates.
_EMIT_DSN: Final = "postgresql+asyncpg://localhost/contract-emission"


def build_emission_container() -> Container:
    """Compose the application for document emission only."""
    resolved = IntegrationsSettings(
        persistence=PersistenceSettings(dsn=_EMIT_DSN),
        observability=ObservabilitySettings(),
    )
    database = Database(build_engine(resolved.persistence), resolved.persistence)
    catalogue = CatalogueRepository(database)

    return Container(
        settings=resolved,
        readiness=ReadinessRegistry(),
        connector_metrics=ConnectorMetrics(),
        catalogue=catalogue,
        tenants=TenantResolver(database),
        access_policy=AccessPolicy(catalogue, ConnectorRegistry(database)),
        # Unbound: the connector's presence changes no route and no schema, and binding it here
        # would need a vault.
        servicenow=None,
    )


def emit(out_dir: Path) -> Path:
    """Write the document into a directory.

    Args:
        out_dir: The output **directory**, matching RagCore's emitter. Created if absent.

    Returns:
        The path written.
    """
    document = create_app(build_emission_container()).openapi()

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / DOCUMENT_NAME

    # `newline=""` writes the bare line feeds this string already contains. Python's default
    # translates them to the platform's ending, which on Windows produces an artifact differing from
    # the Linux one on every line while describing the identical API — and every gate downstream
    # compares bytes. RagCore's emitter and the .NET one normalise for the same reason.
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    return target


def main() -> int:
    """Emit the document.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description="Emit the Integrations OpenAPI document.")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    arguments = parser.parse_args()

    target = emit(arguments.out)
    document = json.loads(target.read_text(encoding="utf-8"))
    operations = sum(len(item) for item in document.get("paths", {}).values())
    print(  # A CLI entry point is where printing is allowed
        f"{target}: {len(document.get('paths', {}))} paths, {operations} operations"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
