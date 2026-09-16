"""W3C Trace Context, and **no custom header replaces it** (plan §Stage 10 contracts).

One journey is followable end to end across four different kinds of hop, and each needs the context
carried differently:

| Hop | Carrier | Where |
|---|---|---|
| Client → APIM → deployable | ``traceparent`` / ``tracestate`` headers | here |
| Deployable → deployable, and outbound to a third party | the same headers | here |
| Deployable → Service Bus → worker | envelope fields on the trigger | ``messaging.tracecontext`` |
| Request → suspension → resume | the **correlation identifier** | ``middleware.correlation`` |

**Two identifiers, doing different jobs, and neither replaces the other.** ``traceparent`` is the
causal link for *this* hop — standard W3C, so Application Insights stitches spans across processes
without either end knowing about the other. The correlation identifier is the *journey*: it is what
survives a flow that suspends for a day, and it is what a user quotes in a support request. A trace
cannot do the second job — a span that ended yesterday has no context to continue — and a
correlation identifier cannot do the first, because it carries no parent-child relationship.

**W3C, not a bespoke header.** The propagator is the standard one, configured here once. A custom
header would work perfectly between our own two deployables and be invisible to APIM, to the Azure
SDKs and to Application Insights' own correlation — which is to say it would work in exactly the
hops we control and fail in the ones we do not.

**Nothing in this module fails a request.** Every function tolerates OpenTelemetry being absent,
because it legitimately is on a developer machine. Telemetry that could stop work from happening is
observability outranking the thing it observes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

TRACEPARENT_HEADER: Final = "traceparent"
TRACESTATE_HEADER: Final = "tracestate"
"""The two W3C headers. Lower-case, as the specification defines them."""

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping


def configure_propagation() -> None:
    """Install W3C Trace Context as the global propagator.

    Called once at startup, before anything traces. Set explicitly rather than relied upon as a
    default: the global propagator is process-wide mutable state that any imported library may
    change, and a library that installed its own would silently move this platform onto a format
    APIM and Application Insights do not read.

    Does nothing when OpenTelemetry is absent.
    """
    try:
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except ImportError:  # pragma: no cover — optional on a developer machine
        return

    set_global_textmap(TraceContextTextMapPropagator())


def outbound_headers() -> dict[str, str]:
    """The trace headers to attach to an outbound call.

    Used by the integration adapters so that a call to the AI Gateway, the system of record or Graph
    is a child span of the request that caused it, rather than an orphan somebody has to correlate
    by timestamp.

    Returns:
        ``traceparent`` and, when present, ``tracestate``. **Empty when no span is recording**,
        which a caller can merge unconditionally — an empty mapping adds no headers rather than
        adding blank ones, and a blank ``traceparent`` is worse than none because it looks like a
        broken trace rather than an absent one.
    """
    try:
        from opentelemetry.propagate import inject
    except ImportError:  # pragma: no cover — optional on a developer machine
        return {}

    carrier: dict[str, str] = {}
    inject(carrier)

    return {key: value for key, value in carrier.items() if value}


def context_from(headers: Mapping[str, str]) -> object | None:
    """Continue an inbound trace, when the caller supplied one.

    **The trace context is correlation, never authority.** A caller can put anything in a
    ``traceparent``: the worst that achieves is a misleading trace, because nothing in this platform
    reads it to make a decision. That is why it is accepted unvalidated while the ``X-Idp-*``
    contract is refused unless it came from the gateway — they are different kinds of claim.

    Args:
        headers: The inbound headers.

    Returns:
        The extracted context to attach to a new span, or ``None`` when there is nothing to continue
        or OpenTelemetry is absent.
    """
    try:
        from opentelemetry.propagate import extract
    except ImportError:  # pragma: no cover — optional on a developer machine
        return None

    if not any(key.lower() == TRACEPARENT_HEADER for key in headers):
        return None

    return extract({key.lower(): value for key, value in headers.items()})


def current_traceparent() -> str:
    """Format the active span as a W3C ``traceparent``.

    The one place this string is constructed. :mod:`ragcore.messaging.tracecontext` captures it for
    the asynchronous hop, and an outbound HTTP call gets it through :func:`outbound_headers`; both
    therefore produce the same value from the same span.

    Returns:
        The header value, or ``""`` when OpenTelemetry is absent or no span is recording.
    """
    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover — optional on a developer machine
        return ""

    context = trace.get_current_span().get_span_context()

    if not context.is_valid:
        return ""

    return f"00-{context.trace_id:032x}-{context.span_id:016x}-{context.trace_flags:02x}"
