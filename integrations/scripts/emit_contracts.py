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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

from integrations.api.app import create_app
from integrations.api.health import ReadinessRegistry
from integrations.catalogue.registry import ConnectorRegistry
from integrations.catalogue.repository import CatalogueRepository, TenantResolver
from integrations.config.composition import Container
from integrations.config.settings import (
    EdgeTrustSettings,
    IntegrationsSettings,
    ObservabilitySettings,
    PersistenceSettings,
)
from integrations.observability.telemetry import ConnectorMetrics
from integrations.persistence.engine import Database, build_engine
from integrations.policy.checks import AccessPolicy

OUTPUT: Final = Path("build/contracts/integrations/workload.v1.openapi.json")

# A syntactically valid placeholder so the application composes without a deployed environment. The
# document describes ROUTES AND SCHEMAS, neither of which depends on what the DSN points at, and
# emitting must not require a database — a contract that can only be produced from production is a
# contract nobody regenerates.
_EMIT_DSN: Final = "postgresql+asyncpg://localhost/contract-emission"
_EMIT_THUMBPRINT: Final = "0" * 64


def build_emission_container() -> Container:
    """Compose the application for document emission only.

    The certificate allow-list carries a placeholder rather than being empty: an empty one refuses
    to construct at all, which is the intended production behaviour and would stop emission dead.

    Returns:
        A container sufficient to describe the API surface.
    """
    resolved = IntegrationsSettings(
        edge_trust=EdgeTrustSettings(gateway_certificate_thumbprints=frozenset({_EMIT_THUMBPRINT})),
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


def emit(destination: Path) -> None:
    """Write the document.

    Args:
        destination: Where to write it. Parent directories are created.
    """
    document = create_app(build_emission_container()).openapi()

    destination.parent.mkdir(parents=True, exist_ok=True)
    # `sort_keys` and an explicit trailing newline; `\n` regardless of platform, because CI compares
    # bytes and a CRLF from a Windows developer would read as a whole-file change.
    serialised = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    destination.write_text(serialised, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    emit(target)
    print(f"wrote {target}")  # noqa: T201 — a CLI entry point is where printing is allowed
