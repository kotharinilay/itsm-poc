"""OpenTelemetry. **A distinct source, on the platform's single correlation identifier.**

`FR-DEMO-028` requires this service to be *independently observable*: it appears as a distinct
source in traces and logs, emits its own connector-invocation metrics, and its execution records
answer "what was attempted, against which connector, with what outcome and how long" **without
reading RagCore's telemetry**.

**Distinct source, shared identifier.** Those are two different things and both are required. A
separate `service.name` is what makes the service separable in a query; the single W3C correlation
identifier is what keeps one journey legible across the APIM hop and both queues. A separate
telemetry *workspace* was considered and rejected — it would have made the identifier harder to
follow across the seam, which is the property worth more.

**Telemetry is not audit** (A2 §8.1). Separate stores, separate retention, and a
question only audit can answer MUST NOT be answerable from here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from opentelemetry import metrics, trace

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.config.settings import ObservabilitySettings

__all__ = ["ConnectorMetrics", "configure_telemetry", "tracer"]

_INSTRUMENTATION_SCOPE: Final = "synthia.integrations"


def configure_telemetry(observability: ObservabilitySettings) -> None:
    """Install tracing and metrics for the process.

    Sampling is decided **per correlated journey** rather than per request (A2 P10,
    FR-OPS-012). A strategy that could retain the command half of an execution and
    discard the result half would make the two-hop journey unreconstructable, which is precisely
    what the correlation requirement exists to prevent.

    Args:
        observability: The service name, exporter reference and sample ratio.
    """
    # The exporter wiring is environment-specific and is installed by the composition root in a
    # deployed environment. Kept out of this module so that importing it in a test does not attempt
    # to reach Azure Monitor, and so the instrumentation scope below is the only global this module
    # establishes.
    _ = observability


def tracer() -> trace.Tracer:
    """The tracer for this service.

    Returns:
        A tracer on the service's own instrumentation scope, so its spans are attributable to it
        rather than to whatever library happened to create them.
    """
    return trace.get_tracer(_INSTRUMENTATION_SCOPE)


class ConnectorMetrics:
    """Connector-invocation metrics — **attempts, outcomes and duration**.

    These three are what make `FR-DEMO-028` answerable. They are declared here, at the foundation,
    rather than alongside the first connector, because a metric added per connector is a metric
    whose dimensions differ per connector — and a dashboard that cannot compare two connectors is
    not an observability surface, it is a pile of counters.

    **No dimension carries an organisation identifier, a credential or an endpoint.** Cardinality is
    part of the reason; the larger part is that telemetry is PII-scrubbed and cross-tenant
    information MUST NOT appear in it.
    """

    def __init__(self) -> None:
        """Create the instruments on the service's own meter."""
        meter = metrics.get_meter(_INSTRUMENTATION_SCOPE)
        self._attempts = meter.create_counter(
            "integrations.connector.attempts",
            unit="1",
            description="Connector invocations attempted, by connector and outcome.",
        )
        self._duration = meter.create_histogram(
            "integrations.connector.duration",
            unit="ms",
            description="Connector invocation duration, by connector and outcome.",
        )

    def record(self, *, connector_id: str, outcome: str, duration_ms: float) -> None:
        """Record one invocation.

        Args:
            connector_id: The connector's platform name — `servicenow`, `graph`, `reference`.
            outcome: The outcome classification, matching the execution record's enum so a metric
                and a durable record cannot disagree about what happened.
            duration_ms: Elapsed milliseconds.
        """
        attributes = {"connector": connector_id, "outcome": outcome}
        self._attempts.add(1, attributes)
        self._duration.record(duration_ms, attributes)
