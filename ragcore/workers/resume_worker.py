"""Consumes triggers: load, verify, claim, execute, record.

**Every trigger is untrusted.** The message carried three fields — a work identifier, a correlation
identifier and a routing hint — and *none of them is authority*. The tenant, the requester and
whatever was decided all come from the durable work record loaded by that identifier. A consumer
that read authority from a message would be defective regardless of where the message came from
(``contracts/triggers.md``).

``kind`` is a **routing hint only**. It says which handler to dispatch to; it never says what may
happen. A forged ``approval.granted`` reaches a handler that then looks at the record, finds no
approval, and refuses.

**The scaffold wires the sample-flow kind only.** The four decision kinds remain in the closed set
and their handlers are deferred (spec FR-DEMO-016). One arriving now is dead-lettered with an alert
and is **never** treated as authorization to proceed (spec FR-DEMO-018) — which is the fail-closed
behaviour, not a gap: an unbuilt handler must refuse, never assume.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from ragcore.domain.envelopes import TriggerEnvelope, TriggerKind
from ragcore.domain.identifiers import CorrelationId, WorkItemId
from ragcore.messaging.deadletter import DeadLetterReport, report_dead_letter
from ragcore.messaging.publisher import TRACEPARENT_PROPERTY, TRACESTATE_PROPERTY
from ragcore.messaging.tracecontext import TraceContext

_log: Final = logging.getLogger(__name__)

HANDLED_KINDS: Final[frozenset[TriggerKind]] = frozenset({TriggerKind.SAMPLE_FLOW})
"""What this build can act on.

An explicit allow-list rather than "everything in the enum". The enum is the *contract*, which
includes kinds whose handlers are not written; this is what this process can actually do. An
unhandled kind therefore dead-letters instead of falling through a ``match`` statement into
whatever the last branch happened to be.
"""


class UndeserializableTriggerError(ValueError):
    """The message body is not a trigger this platform recognises.

    A pre-claim failure, so it is retryable and ultimately dead-letterable — never something to
    guess past. A body that will not parse is one whose authority claims cannot be checked.
    """


@dataclass(frozen=True, slots=True)
class ConsumedTrigger:
    """A parsed trigger and the trace context it travelled with."""

    envelope: TriggerEnvelope
    trace: TraceContext


def parse_message(body: str | bytes, properties: dict[Any, Any] | None) -> ConsumedTrigger:
    """Parse a Service Bus message into a trigger and its trace context.

    Strict on purpose. An unknown ``kind``, a missing field or an unparsable identifier raises
    rather than being defaulted: every one of those is a message this consumer cannot verify, and
    the safe reading of "I cannot verify this" is never "proceed".

    Args:
        body: The message body.
        properties: The application properties, carrying the W3C trace context.

    Returns:
        The trigger and its trace context.

    Raises:
        UndeserializableTriggerError: When the body is not a well-formed trigger.
    """
    try:
        payload = json.loads(body)
        envelope = TriggerEnvelope(
            work_item_id=WorkItemId(UUID(payload["workItemId"])),
            correlation_id=CorrelationId(payload["correlationId"]),
            kind=TriggerKind(payload["kind"]),
        )
    except (ValueError, KeyError, TypeError) as error:
        raise UndeserializableTriggerError(
            f"the message body is not a well-formed trigger: {error!r}"
        ) from error

    supplied = properties or {}
    trace = TraceContext(
        correlation_id=str(envelope.correlation_id),
        traceparent=_text(supplied.get(TRACEPARENT_PROPERTY)),
        tracestate=_text(supplied.get(TRACESTATE_PROPERTY)),
    )

    return ConsumedTrigger(envelope=envelope, trace=trace)


def _text(value: Any) -> str:  # An application property is loosely typed
    """Decode an application property to text, tolerating the SDK's bytes."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def refuse_unhandled_kind(trigger: ConsumedTrigger) -> DeadLetterReport:
    """Dead-letter a kind this build cannot act on.

    **Never treated as authorization to proceed.** The four decision kinds are specified in full and
    their handlers are deferred; until they exist, one arriving is refused. Refusing is the correct
    behaviour rather than a placeholder — a handler that did not exist and let the work through
    would be worse than one that does not exist.

    Args:
        trigger: The parsed trigger.

    Returns:
        The dead-letter report. ``GOVERNANCE`` severity for a granted decision, because a human
        authorized work that will now not run.
    """
    return report_dead_letter(
        work_item_id=str(trigger.envelope.work_item_id),
        correlation_id=str(trigger.envelope.correlation_id),
        kind=trigger.envelope.kind.value,
        reason=(
            "no handler is wired for this kind in this build (spec FR-DEMO-016); refused rather "
            "than proceeded, because an unhandled kind is never authorization"
        ),
    )


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, Service Bus receiver, checkpointer and the dispatch
    table — belongs to the deployment that runs this and is wired at Stage 12 alongside the other
    workers. :func:`parse_message`, :func:`refuse_unhandled_kind` and
    :func:`ragcore.messaging.sample_flow.execute_sample_flow` are the behaviour, and are what the
    tests exercise.
    """
    raise NotImplementedError(
        "the consumer's parsing, refusal and execution paths are implemented and tested; the "
        "worker's process wiring lands with the other workers."
    )
