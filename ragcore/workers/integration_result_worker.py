"""Worker entry point: consumes `integration.completed` / `integration.failed`.

The other end of the asynchronous seam (ADR-0007, `FR-INTEG-027`). The Integrations Service executed
something and reported an outcome; this is where RagCore learns of it and resumes.

**The message is a wake-up, not an answer.** It carries a job identifier, a correlation identifier
and a routing hint, and *none of them is the outcome*. The outcome is read from the four result
columns on RagCore's own ``integration_job`` row — which is why a lost, duplicated or forged result
message cannot change what the platform believes happened. The worst a forged
`integration.completed` achieves is a read that finds no recorded result.

**A failure result MUST NOT cause a re-dispatch**, and this module is where that rule is kept. A
failed authorized action requires **fresh human authorization** (`FR-EXEC-006`): re-publishing a
command here would spend one authority record twice, and would do so in a loop that looks like
resilience. :func:`concluded_from` returns a conclusion and has no verb that could re-dispatch — the
prohibition is enforced by there being nothing to call.

**RagCore holds Receiver and not Sender on this queue**
(``build/infra/messaging/queues.json``). Even if this module tried, the platform would refuse it.
Two mechanisms for one rule, deliberately: the code cannot express it and the role does not permit
it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from ragcore.domain.envelopes import IntegrationMessageKind
from ragcore.domain.identifiers import CorrelationId, IntegrationJobId
from ragcore.messaging.publisher import TRACEPARENT_PROPERTY, TRACESTATE_PROPERTY
from ragcore.messaging.tracecontext import TraceContext

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.persistence.integration_jobs import IntegrationResult

__all__ = [
    "ConsumedResult",
    "Conclusion",
    "UndeserializableResultError",
    "concluded_from",
    "main",
    "parse_result_message",
]

_log: Final = logging.getLogger(__name__)

HANDLED_KINDS: Final[frozenset[IntegrationMessageKind]] = frozenset(
    {IntegrationMessageKind.COMPLETED, IntegrationMessageKind.FAILED}
)
"""What this consumer accepts.

**`EXECUTE` is deliberately absent.** It travels on the command queue in the other direction, and a
consumer that accepted it here would be RagCore executing its own dispatch. An explicit allow-list
rather than "everything in the enum", for the same reason ``resume_worker`` keeps one: the enum is
the *contract*, this is what this process can actually do.
"""


class UndeserializableResultError(ValueError):
    """The message body is not a result this platform recognises.

    Raised rather than defaulted. A body that will not parse is one whose job identifier cannot be
    trusted, and the safe reading of "I cannot verify this" is never "proceed".
    """


class Conclusion(Enum):
    """What RagCore concludes from a recorded outcome. **Not what the far side reported.**

    The distinction is the constitution's verification split (Principle III): the Integrations
    Service reports what it *observed*; RagCore decides what the platform may *say*.
    """

    RESOLVED = "resolved"
    """A server-side read confirmed the effect. The only value reportable to a user as resolved."""

    ACTED_UNVERIFIED = "acted_unverified"
    """The call succeeded and nobody checked. **MUST NOT** be presented as confirmed resolution."""

    FAILED = "failed"
    """The operation did not complete, or a read contradicted the claim.

    Escalates; **never retries**.
    """

    PENDING = "pending"
    """No result is recorded yet. A duplicate or early delivery — wait, do not conclude."""


@dataclass(frozen=True, slots=True)
class ConsumedResult:
    """A parsed result notification and the trace context it travelled with."""

    job_id: IntegrationJobId
    correlation_id: CorrelationId
    kind: IntegrationMessageKind
    trace: TraceContext


def parse_result_message(body: str | bytes, properties: dict[Any, Any] | None) -> ConsumedResult:
    """Parse a Service Bus message into a result notification and its trace context.

    Strict on purpose, and **closed on the field set**: a body carrying a field the contract does
    not name is refused rather than ignored. Ignoring it would let a publisher believe the field had
    been honoured, and would leave a forged `tenantId` sitting in the queue looking accepted.

    Args:
        body: The message body.
        properties: The application properties, carrying the W3C trace context.

    Returns:
        The parsed notification.

    Raises:
        UndeserializableResultError: When the body is malformed, carries an unpermitted field, or
            names a kind this consumer does not accept.
    """
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise TypeError("body is not a JSON object")

        forbidden = set(payload) - {"jobId", "correlationId", "kind"}
        if forbidden:
            # The count, never the names. A forged field could carry an organisation identifier or
            # a log-format token, and this message is the thing most likely to be logged.
            raise ValueError(
                f"the message carries {len(forbidden)} field(s) the contract does not permit"
            )

        kind = IntegrationMessageKind(payload["kind"])
        if kind not in HANDLED_KINDS:
            raise ValueError(f"{kind.value} is not consumed on the results queue")

        parsed = ConsumedResult(
            job_id=IntegrationJobId(UUID(payload["jobId"])),
            correlation_id=CorrelationId(payload["correlationId"]),
            kind=kind,
            trace=TraceContext(
                correlation_id=str(payload["correlationId"]),
                traceparent=_text((properties or {}).get(TRACEPARENT_PROPERTY)),
                tracestate=_text((properties or {}).get(TRACESTATE_PROPERTY)),
            ),
        )
    except (ValueError, KeyError, TypeError) as error:
        raise UndeserializableResultError(
            f"the message body is not a well-formed integration result: {error!r}"
        ) from error

    return parsed


def concluded_from(result: IntegrationResult | None) -> Conclusion:
    """What the platform may conclude from the recorded outcome.

    **Reads durable state, never the message.** The caller loads the row by the job identifier the
    message carried; this function turns that row into a conclusion. Nothing here takes the message
    kind as an argument, and that omission is the control: a `integration.completed` naming a job
    whose row says nothing happened concludes ``PENDING``, not success.

    Args:
        result: The row's recorded result, or ``None`` when the job does not exist.

    Returns:
        The conclusion. There is **no re-dispatch outcome**, because a failed authorized action
        requires fresh human authorization rather than an automatic retry (`FR-EXEC-006`).
    """
    if result is None or result.is_pending:
        return Conclusion.PENDING

    if not result.executed:
        return Conclusion.FAILED

    # `may_report_resolution` is the single place "did the platform actually check" is asked. Read
    # here rather than re-compared, so no surface can write `if executed:` and answer a different
    # question (ADR-0004).
    return Conclusion.RESOLVED if result.may_report_resolution else Conclusion.ACTED_UNVERIFIED


def _text(value: Any) -> str:  # An application property is loosely typed
    """One application property as text, or empty when absent."""
    return str(value) if value is not None else ""


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, Service Bus receiver, the job repository and the graph
    checkpointer — belongs to the deployment that runs this and is wired alongside the other
    workers. :func:`parse_result_message` and :func:`concluded_from` are the behaviour, and are what
    the tests exercise.

    Raises:
        NotImplementedError: Always, for now. Deliberately loud rather than a loop that connects to
            nothing: a worker that started and consumed no message would leave every dispatched job
            apparently in flight for ever, which is indistinguishable from a slow external system.
    """
    raise NotImplementedError(
        "the consumer's parsing and conclusion paths are implemented and tested; the worker's "
        "process wiring lands with the other workers — see specs/001-platform-scaffold/tasks.md"
    )
