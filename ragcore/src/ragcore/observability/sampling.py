"""Sampling is decided **per correlated journey**, never per request. Head sampling is prohibited.

A journey that suspends and resumes hours later must be wholly sampled or wholly not
(spec FR-OPS-012). A strategy that can retain the request half of an approval journey and discard
the resume half defeats `SC-OPS-001` — and it is the strategy every default gives you, because the
default decides at the first span, before the journey is known to be interesting.

**Two mechanisms, at two different layers, and both are needed.**

*In this process*, :class:`CorrelationJourneySampler` derives its decision from the **correlation
identifier** rather than from the trace identifier. Every span of one journey therefore reaches the
same decision independently — in the API replica that started it, in the worker that resumes it two
hours later, in a third process that never spoke to either. No coordination is required, which is
what makes it work across a suspension: there is nothing to keep alive between the halves.

*In the collector*, true tail sampling — deciding after the spans are in — is declared in
``build/infra/monitoring/telemetry.json``. It is the only place a decision can genuinely be made
with the whole journey in view. This sampler does not pretend to be that; what it does is make the
in-process decision **consistent**, so the collector is never handed a half-sampled journey to
reason about.

**Interesting traces are kept regardless.** Every trace carrying an error, a governance denial or an
approval is retained whatever the ratio says (plan §Telemetry retention and sampling). The whole
point of sampling is to discard the ordinary, and a denial is never ordinary — it is the record of
the platform refusing something, which is exactly what an operator goes looking for.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Final

from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
from opentelemetry.trace import Link, SpanKind
from opentelemetry.util.types import Attributes

from ragcore.api.middleware.correlation import correlation_id_var

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Sequence

    from opentelemetry.trace.span import TraceState

ALWAYS_SAMPLED_ATTRIBUTE: Final = "synthia.retain"
"""The attribute a span sets to declare itself interesting.

Set by the governance gate on a denial, by the approval path, and by anything recording an error.
A span carrying it is retained whatever the ratio says.
"""

_FULL_RANGE: Final = 1 << 64
"""The hash space the ratio is compared against."""


def journey_is_sampled(correlation_id: str, ratio: float) -> bool:
    """Whether this journey is sampled, decided from its identifier alone.

    Deterministic and stateless, which is the property that matters: two processes hours apart reach
    the same answer for the same journey without sharing anything. A random draw per span, or a
    decision cached in one process's memory, would both split a suspended journey in half.

    Args:
        correlation_id: The journey identifier. An empty one is treated as *sampled* — work with no
            correlation identifier is unusual enough to be worth seeing, and silently discarding it
            would hide the defect that produced it.
        ratio: The proportion to retain, ``0.0`` to ``1.0``.

    Returns:
        Whether to record.
    """
    if ratio >= 1.0 or not correlation_id:
        return True
    if ratio <= 0.0:
        return False

    # SHA-256 of the identifier rather than `hash()`, whose per-process randomisation would give
    # the two halves of one journey different answers — the exact failure this exists to prevent.
    digest = hashlib.sha256(correlation_id.encode("utf-8")).digest()

    return int.from_bytes(digest[:8], "big") < ratio * _FULL_RANGE


class CorrelationJourneySampler(Sampler):
    """Samples by journey, and always keeps a span that declared itself interesting.

    **This module imports the OpenTelemetry SDK directly**, where its siblings guard the import.
    The difference is not inconsistency: the others call optional *functions*, and a missing SDK
    simply means they do nothing. This one must *subclass* ``Sampler``, so there is no version of it
    that works without the SDK — and ``opentelemetry-sdk`` is a declared, locked dependency, so
    pretending otherwise would be defensiveness against a state the lockfile does not permit.
    """

    def __init__(self, ratio: float) -> None:
        """Bind the sampler to a ratio.

        Args:
            ratio: The proportion of ordinary journeys to retain.
        """
        self._ratio = ratio

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        """Decide, from the **correlation identifier** rather than from the trace identifier.

        ``trace_id`` is deliberately unused, and that is the whole point of this class: a decision
        derived from it would be per-trace, and the resume half of a suspended journey is a
        different trace from the request half.
        """
        del parent_context, trace_id, name, kind, links

        retain = bool(attributes and attributes.get(ALWAYS_SAMPLED_ATTRIBUTE))
        sampled = retain or journey_is_sampled(correlation_id_var.get(), self._ratio)

        return SamplingResult(
            Decision.RECORD_AND_SAMPLE if sampled else Decision.DROP,
            attributes,
            trace_state,
        )

    def get_description(self) -> str:
        """Named so it is identifiable in a diagnostic dump."""
        return f"CorrelationJourneySampler({self._ratio})"


def build_sampler(ratio: float) -> Sampler:
    """The sampler to configure the tracer provider with.

    A function rather than a bare constructor call at the one call site, so that "which sampler does
    this platform use" has a single answer that is greppable by name.

    Args:
        ratio: The proportion of ordinary journeys to retain.

    Returns:
        The sampler.
    """
    return CorrelationJourneySampler(ratio)
