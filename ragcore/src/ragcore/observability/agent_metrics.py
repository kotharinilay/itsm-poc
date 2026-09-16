"""The five agent signals, and the organisation each one belongs to (spec FR-OPS-003).

Model token usage, cache-hit ratio, guardrail actions, control-gate outcome distribution and
retrieval confidence distribution. The specification names exactly these, and this module records
exactly these — a metric nobody asked for still costs cardinality, storage and attention.

**Every signal is dimensioned by organisation, from trusted context.** The organisation comes from
:func:`~ragcore.observability.context.current_tenant_id`, which can only have been written from an
admitted :class:`~ragcore.domain.tenancy.TenantContext`. It is never read from a header or from
message content (spec FR-OPS-002), and there is no parameter on any function here through which a
caller could supply one.

**These are telemetry and MUST NOT answer an audit question** (spec FR-OPS-004). The distinction is
enforced by retention as well as by intent: telemetry keeps 30 days, audit keeps seven years, so
after a month a question only audit can answer demonstrably cannot be answered from here. The
practical consequence is visible below — a gate outcome is counted, not *recorded*. The durable
record of who was denied what is an audit event, written through
:class:`~ragcore.application.ports.AuditSinkPort`; this is the count an operator watches on a
dashboard.

**Dimensions are bounded, deliberately.** Nothing here takes a free-form string: an outcome is an
enum, a guardrail action is an enum, and a confidence score is bucketed by the histogram rather than
becoming a label. One unbounded dimension — a session identifier, a catalogue identifier, a user —
is how a metrics bill and a query timeout arrive together.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Final

from ragcore.observability.context import current_tenant_id

METER_NAME: Final = "synthia.ragcore.agent"

TENANT_DIMENSION: Final = "synthia.organisation"
"""The one dimension every signal here carries.

Named for the platform identifier rather than the directory one: the Entra ``tid`` is one join away
from naming a real company on a dashboard nobody treats as sensitive.
"""


class GuardrailAction(Enum):
    """What a guardrail did. Bounded, because this is a metric dimension."""

    ALLOWED = "allowed"
    BLOCKED_INPUT = "blocked_input"
    """Content safety refused a prompt before it reached a provider."""

    BLOCKED_OUTPUT = "blocked_output"
    """Content safety refused a completion before it reached the agent loop."""

    REJECTED_AT_BOUNDARY = "rejected_at_boundary"
    """Provider output failed contract validation (spec FR-EXT-021)."""


class AgentMetrics:
    """The five signals, recorded through one object.

    One object rather than five module-level instruments so that a process which never configured a
    meter has one thing to be a no-op, and so a test can assert on what was recorded without
    reaching into the SDK.

    **Every method is a no-op when no meter is configured**, which is the developer-machine case. A
    metric that could raise would make telemetry able to fail the work it observes.
    """

    def __init__(self, meter: Any | None = None) -> None:  # noqa: ANN401 — the type needs the SDK
        """Build the instruments, or nothing at all.

        Args:
            meter: An OpenTelemetry ``Meter``. When omitted the class resolves the global one, and
                when OpenTelemetry is absent every method below does nothing.
        """
        self._instruments: dict[str, Any] = {}

        resolved = meter if meter is not None else _global_meter()
        if resolved is None:
            return

        self._instruments = {
            "tokens": resolved.create_counter(
                "synthia.model.tokens",
                unit="{token}",
                description="Model tokens consumed, in provider-neutral units (FR-OPS-008).",
            ),
            "cache": resolved.create_counter(
                "synthia.model.cache_lookups",
                unit="{lookup}",
                description="Model cache lookups, dimensioned by hit or miss (FR-OPS-010).",
            ),
            "guardrail": resolved.create_counter(
                "synthia.guardrail.actions",
                unit="{action}",
                description="Guardrail actions taken, by kind.",
            ),
            "gate": resolved.create_counter(
                "synthia.governance.gate_outcomes",
                unit="{decision}",
                description="Control-gate outcome distribution. A count, never the record.",
            ),
            "confidence": resolved.create_histogram(
                "synthia.retrieval.confidence",
                unit="1",
                description="Retrieval confidence distribution. A score, not a probability.",
            ),
        }

    def record_tokens(self, count: int, *, purpose: str) -> None:
        """Model tokens consumed by this organisation.

        The authoritative meter is the AI Gateway, which counts what a provider actually billed
        (``build/infra/ai-gateway/policy.xml``). This is the caller-side view of the same thing, and
        the two disagreeing is itself worth seeing — a gap means calls reaching a provider by some
        path other than the one being metered.

        Args:
            count: Tokens.
            purpose: ``completion`` or ``embedding``. Bounded by the caller's enum, not free text.
        """
        self._add("tokens", count, {"synthia.purpose": purpose})

    def record_cache_lookup(self, *, hit: bool) -> None:
        """One model cache lookup, hit or miss.

        A ratio is deliberately not computed here. Two counters divided at query time survive
        restarts, scale-out and a partial outage; a ratio computed in-process is a number about one
        replica's memory since the last deployment.
        """
        self._add("cache", 1, {"synthia.cache": "hit" if hit else "miss"})

    def record_guardrail(self, action: GuardrailAction) -> None:
        """One guardrail action."""
        self._add("guardrail", 1, {"synthia.action": action.value})

    def record_gate_outcome(self, treatment: str, *, permitted: bool) -> None:
        """One control-gate outcome.

        **A count, not the record.** The durable answer to "who was denied what, and on what
        grounds" is an audit event; this is the shape of the distribution, for an operator watching
        whether denials have suddenly tripled.

        Args:
            treatment: The assigned treatment's name. Bounded — there are exactly four.
            permitted: Whether the gate let it proceed.
        """
        self._add(
            "gate",
            1,
            {
                "synthia.treatment": treatment,
                "synthia.outcome": "permitted" if permitted else "refused",
            },
        )

    def record_retrieval_confidence(self, score: float) -> None:
        """One retrieval confidence observation.

        A histogram rather than a gauge: the specification asks for the *distribution*, and a gauge
        of the last value answers nothing about whether grounding is getting worse.
        """
        instrument = self._instruments.get("confidence")
        if instrument is not None:
            instrument.record(score, self._dimensions({}))

    def _add(self, name: str, value: int, dimensions: dict[str, str]) -> None:
        """Add to one counter, if there is one."""
        instrument = self._instruments.get(name)
        if instrument is not None:
            instrument.add(value, self._dimensions(dimensions))

    @staticmethod
    def _dimensions(extra: dict[str, str]) -> dict[str, str]:
        """Attach the organisation from trusted context.

        Omitted rather than defaulted when there is none: work belonging to no organisation must not
        be attributed to one, and a bucket called ``unknown`` is one somebody eventually reads as a
        real tenant.
        """
        tenant_id = current_tenant_id()
        return {**extra, TENANT_DIMENSION: tenant_id} if tenant_id else dict(extra)


def _global_meter() -> Any | None:  # noqa: ANN401 — the concrete type needs the SDK imported
    """The process meter, or ``None`` when OpenTelemetry is absent."""
    try:
        from opentelemetry import metrics
    except ImportError:  # pragma: no cover — optional on a developer machine
        return None

    return metrics.get_meter(METER_NAME)
