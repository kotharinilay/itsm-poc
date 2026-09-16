"""Telemetry configuration: traces, metrics and structured logs to Azure Monitor.

**Configured once, at startup, from the lifespan that owns the process.** A tracer provider set
lazily on first use is one that some code paths reached before it existed, and those paths are
silently untraced rather than loudly broken.

**The connection string is a secret reference, never a value.** Application Insights' connection
string carries an instrumentation key, which is a write credential for a telemetry workspace: hold
it and you can inject telemetry into somebody else's dashboards. It is therefore a Key Vault secret
name in configuration (``ObservabilitySettings.connection_string_secret_name``), resolved through
managed identity at startup like every other secret, and it never appears in a manifest, an image or
a log line.

Azure Monitor's Entra-authenticated ingestion is used where the exporter supports it — the
``id-synthia-ragcore`` identity holds ``Monitoring Metrics Publisher`` on the workspace
(``build/infra/identity/managed-identities.json``), so ingestion authenticates as the identity and
the connection string contributes the endpoint rather than the authority.

**Nothing here is allowed to fail the process.** :func:`configure_telemetry` returns cleanly when
the SDK is absent or the workspace is unconfigured, which is the developer-machine case and a
legitimate one. Structured logging and correlation still work — they need no exporter — so a
developer loses the dashboards and keeps everything they read during development. The opposite
trade, a process that will not start without a telemetry workspace, makes observability a
dependency of the work rather than a view onto it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from ragcore.observability.logging import configure_logging
from ragcore.observability.propagation import configure_propagation
from ragcore.observability.sampling import build_sampler

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.secrets import SecretValue
    from ragcore.config.settings import ObservabilitySettings

_log: Final = logging.getLogger(__name__)

SERVICE_NAMESPACE: Final = "synthia"
"""The resource namespace both deployables report under, so one query spans the platform."""


def configure_telemetry(
    settings: ObservabilitySettings,
    *,
    connection_string: SecretValue | None = None,
) -> None:
    """Configure tracing, metrics and structured logging for this process.

    Called once from the application lifespan, and once from each worker's entry point — workers
    emit telemetry too, and a worker that configured none would make the resume half of every
    journey invisible, which is precisely the half FR-OPS-012 exists to protect.

    Args:
        settings: The validated observability settings.
        connection_string: The Application Insights connection string, already resolved from Key
            Vault. **A** :class:`~ragcore.config.secrets.SecretValue`, so a caller that logs it gets
            ``<redacted>``, and it is revealed exactly once — at the line that hands it to the
            exporter. Omitted on a developer machine, where no exporter is configured at all.
    """
    # Order matters. Logging first, so that anything the rest of this function reports is already
    # structured and redacted. Propagation second, so a span created during export configuration
    # uses the right format. The exporter last, because it is the only part that can be absent.
    configure_logging()
    configure_propagation()

    if connection_string is None:
        _log.info(
            "No Application Insights workspace is configured; telemetry stays local. "
            "Structured logging and correlation are unaffected."
        )
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:  # pragma: no cover — the exporter is optional on a developer machine
        _log.info("The Azure Monitor exporter is not installed; telemetry stays local.")
        return

    sampler = build_sampler(settings.trace_sample_ratio)

    configure_azure_monitor(
        # Revealed here and nowhere else, at the moment it is handed to the exporter, so the plain
        # string exists in the fewest frames possible.
        connection_string=connection_string.reveal(),
        # The identity the workspace grants ingestion to. Passing the credential means ingestion is
        # authorised by role assignment rather than by the instrumentation key inside the
        # connection string — the key becomes an address, not an authority.
        credential=_credential(),
        resource_attributes={
            "service.name": settings.service_name,
            "service.namespace": SERVICE_NAMESPACE,
        },
        # Correlation-keyed sampling, never head sampling (spec FR-OPS-012).
        sampler=sampler,
        # Logging is configured above, with redaction and a fixed field set. Letting the exporter
        # install its own handler would add a second, unfiltered path to a sink.
        logger_name=None,
        disable_logging=False,
    )

    _log.info(
        "Telemetry is exporting to Azure Monitor. service=%s sampling=%s retention_days=%d",
        settings.service_name,
        sampler.get_description(),
        settings.retention_days,
    )


def _credential() -> Any:  # noqa: ANN401 — the concrete type needs the SDK imported
    """The shared managed identity, for Entra-authenticated ingestion.

    The process-wide credential, never one built here: a second credential is a second
    authentication path beside the first, and ``tests/security/test_azure_identity.py`` asserts
    there is exactly one construction site.

    Returns:
        The shared :class:`AsyncTokenCredential`.
    """
    from ragcore.infrastructure.azure_credentials import azure_credential

    return azure_credential()
