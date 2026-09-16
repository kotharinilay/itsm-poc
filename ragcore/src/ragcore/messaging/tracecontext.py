"""W3C Trace Context across the asynchronous hop.

**One journey, followable end to end** (spec FR-DEMO-009, FR-OPS-001). A request enters at the edge,
becomes durable state, crosses a queue, and is resumed minutes later by a different process. Without
this, that is four unrelated traces and an operator correlating them by timestamp.

Two identifiers travel together and answer different questions:

- ``correlationId`` — the **journey**. Minted at the edge, quoted by a user in a support request,
  present on every log record, span, trigger and audit row. It survives everything.
- ``traceparent`` — the **causal link** for this hop. Standard W3C, so Application Insights stitches
  the consumer's span to the producer's without either knowing about the other.

**Captured at publish and restored at consume.** The ``contextvars`` this reads are per-task, so a
dispatcher publishing a batch captures each row's own context rather than whatever the last one set.

This module carries no OpenTelemetry import. The propagator is resolved lazily, and its absence is
not an error: a scaffold without a configured exporter still correlates by ``correlationId``, which
is the identifier that matters to a human. A telemetry dependency that could stop a trigger being
published would be observability outranking the work it observes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from ragcore.api.middleware.correlation import correlation_id_var

_traceparent_var: ContextVar[str] = ContextVar("traceparent", default="")
_tracestate_var: ContextVar[str] = ContextVar("tracestate", default="")


@dataclass(frozen=True, slots=True)
class TraceContext:
    """The correlation identifier and W3C trace context for one hop."""

    correlation_id: str
    traceparent: str = ""
    tracestate: str = ""

    @property
    def has_trace(self) -> bool:
        """Whether a W3C trace is being continued, as opposed to correlation alone."""
        return bool(self.traceparent)


def current_trace_context() -> TraceContext:
    """Capture the ambient context, for attaching to an outbox row or a message.

    Returns:
        The context. ``traceparent`` is empty when no tracer is configured, which is normal on a
        developer machine and never fatal.
    """
    return TraceContext(
        correlation_id=correlation_id_var.get(),
        traceparent=_traceparent_var.get() or _traceparent_from_otel(),
        tracestate=_tracestate_var.get(),
    )


def _traceparent_from_otel() -> str:
    """Format the active span as a W3C ``traceparent``, when there is one.

    Returns:
        The header value, or ``""`` when OpenTelemetry is absent or no span is recording.
    """
    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover — optional at this stage
        return ""

    span = trace.get_current_span()
    context = span.get_span_context()

    if not context.is_valid:
        return ""

    return f"00-{context.trace_id:032x}-{context.span_id:016x}-{context.trace_flags:02x}"


@contextmanager
def restored(context: TraceContext) -> Iterator[TraceContext]:
    """Restore a captured context as the ambient one, for the duration of the block.

    Used by the consumer so that everything the resumed work produces — logs, spans, audit rows —
    carries the journey identifier the original request was issued under, rather than a fresh one
    that makes the asynchronous half look like unrelated activity.

    Args:
        context: What the producer captured.

    Yields:
        The same context, for convenience.
    """
    tokens = (
        correlation_id_var.set(context.correlation_id),
        _traceparent_var.set(context.traceparent),
        _tracestate_var.set(context.tracestate),
    )
    try:
        yield context
    finally:
        # Reset in `finally` so a cancelled consumer does not leak one message's journey into
        # whatever the event loop runs next. No `except`: cancellation passes straight through.
        correlation_id_var.reset(tokens[0])
        _traceparent_var.reset(tokens[1])
        _tracestate_var.reset(tokens[2])
