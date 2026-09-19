"""The composition root. **The only place a concrete adapter is constructed.**

Constitution §Dependency injection: registration belongs in composition-root code, Service Locator
is prohibited, and domain and application policy MUST NOT depend on an infrastructure
implementation. `integrations/tests/architecture/test_layering.py` asserts that no module outside
this one instantiates a concrete adapter — which is what makes the rule checkable rather than
remembered.

**Ports belong to the consuming module** (Principle V), so they are declared where they are used —
`application/ports.py` for application-level ports, `credentials/` for the credential port whose
consumer is an adapter. This module only *binds* them.

**Startup validates and then fails.** Configuration binds once here; an invalid value raises out of
application startup and stops the process. A service that started in a state it cannot be secure in
has already lost, and lost invisibly.

**Optional bindings are `None`, never a stub.** Where a dependency is unconfigured — no DSN in a
unit test, no vault in local development — the container holds `None` and the API answers 503.
Constitution Principle IX: a fallback is explicit and visible, and stubbing a success is prohibited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from integrations.api.health import ReadinessRegistry
from integrations.catalogue.registry import ConnectorRegistry
from integrations.catalogue.repository import CatalogueRepository, TenantResolver
from integrations.config.settings import IntegrationsSettings, settings
from integrations.connectors.servicenow.adapter import ServiceNowAdapter
from integrations.credentials.resolver import TenantCredentialResolver
from integrations.egress.http import ResilientCaller
from integrations.observability.logging import configure_logging
from integrations.observability.telemetry import ConnectorMetrics, configure_telemetry
from integrations.persistence.engine import Database, ReadinessProbeAdapter, build_engine

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.credentials.resolver import SecretResolverPort
    from integrations.policy.checks import AccessPolicy

__all__ = ["Container", "build_container"]


@dataclass(frozen=True, slots=True)
class Container:
    """Everything the application needs, constructed once.

    Attributes:
        settings: Validated configuration.
        readiness: The **platform** dependency probes this process waits on. Never an external
            customer system.
        connector_metrics: Attempts, outcomes and duration, on this service's own meter.
        catalogue: The tenant-resolved capability set, over published views.
        tenants: Organisation recovery from a durable platform object — the only way this service
            learns an organisation on the synchronous path.
        access_policy: The execution-time re-check.
        servicenow: The system-of-record connector, or ``None`` when unconfigured. `None` is
            answered as 503, never stubbed.
    """

    settings: IntegrationsSettings
    readiness: ReadinessRegistry
    connector_metrics: ConnectorMetrics
    catalogue: CatalogueRepository
    tenants: TenantResolver
    access_policy: AccessPolicy
    servicenow: ServiceNowAdapter | None


def build_container(secrets: SecretResolverPort | None = None) -> Container:
    """Bind configuration, observability, persistence, policy and connectors.

    Args:
        secrets: The Key Vault resolver. Supplied by tests; in a deployed environment it is
            constructed from the vault URL and the managed identity. ``None`` leaves the
            system-of-record connector unbound, which the API reports as 503 rather than stubbing.

    Returns:
        The container.

    Raises:
        pydantic.ValidationError: When configuration is invalid. **Deliberately uncaught** — it
            propagates out of startup and stops the process, so a misconfigured revision fails its
            rollout visibly rather than going green and serving wrongly.
    """
    # Imported here rather than at module scope to keep the import graph acyclic: policy consumes
    # ports that the catalogue modules implement, and a top-level import would make this module and
    # the policy module mutually reachable at import time.
    from integrations.policy.checks import AccessPolicy

    resolved = settings()

    configure_logging(resolved.observability)
    configure_telemetry(resolved.observability)

    engine = build_engine(resolved.persistence)
    database = Database(engine, resolved.persistence)

    catalogue = CatalogueRepository(database)
    tenants = TenantResolver(database)
    registry = ConnectorRegistry(database)
    access_policy = AccessPolicy(catalogue, registry)

    # Always registered. `build_engine` refuses to start without a DSN, so there is no configured
    # process in which the store is absent — the guard that stood here protected a case that could
    # not be reached, and made readiness look optional when it is not.
    readiness = ReadinessRegistry()
    readiness.register(ReadinessProbeAdapter(database))

    servicenow: ServiceNowAdapter | None = None
    if secrets is not None:
        credentials = TenantCredentialResolver(database, secrets)
        servicenow = ServiceNowAdapter(ResilientCaller(ResilientCaller.build_client()), credentials)

    return Container(
        settings=resolved,
        readiness=readiness,
        connector_metrics=ConnectorMetrics(),
        catalogue=catalogue,
        tenants=tenants,
        access_policy=access_policy,
        servicenow=servicenow,
    )
