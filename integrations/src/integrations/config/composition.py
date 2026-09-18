"""The composition root. **The only place a concrete adapter is constructed.**

Constitution §Dependency injection: registration belongs in composition-root code, Service Locator
is prohibited, and domain and application policy MUST NOT depend on an infrastructure
implementation. `integrations/tests/architecture/test_layering.py` asserts that no module outside
this one instantiates a concrete adapter — which is what makes the rule checkable rather than
remembered.

**Ports belong to the consuming module** (Principle V), so they are declared where they are used —
`application/` for application-level ports, `credentials/` for the credential port whose consumer is
an adapter. This module only *binds* them.

**Startup validates and then fails.** Configuration binds once here; an invalid value raises out of
application startup and stops the process. A service that started in a state it cannot be secure in
has already lost, and lost invisibly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from integrations.api.health import ReadinessRegistry
from integrations.config.settings import IntegrationsSettings, settings
from integrations.observability.logging import configure_logging
from integrations.observability.telemetry import ConnectorMetrics, configure_telemetry

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    pass

__all__ = ["Container", "build_container"]


@dataclass(frozen=True, slots=True)
class Container:
    """Everything the application needs, constructed once.

    Attributes:
        settings: Validated configuration.
        readiness: The platform-dependency probes this process waits on. **Probes are registered by
            the subsystem that owns them** as each lands — the durable store, the message transport
            and the secret store. An empty registry means "nothing to wait for", which is the
            honest state for a process that has not yet bound any of them.
        connector_metrics: Attempts, outcomes and duration, on this service's own meter.
    """

    settings: IntegrationsSettings
    readiness: ReadinessRegistry
    connector_metrics: ConnectorMetrics


def build_container() -> Container:
    """Bind configuration, observability and the readiness registry.

    Returns:
        The container.

    Raises:
        pydantic.ValidationError: When configuration is invalid. **Deliberately uncaught** — it
            propagates out of startup and stops the process. In particular an empty gateway
            certificate allow-list fails here, because an allow-list that fails open cannot be
            distinguished at request time from one that is simply permissive.
    """
    resolved = settings()

    configure_logging(resolved.observability)
    configure_telemetry(resolved.observability)

    return Container(
        settings=resolved,
        readiness=ReadinessRegistry(),
        connector_metrics=ConnectorMetrics(),
    )
