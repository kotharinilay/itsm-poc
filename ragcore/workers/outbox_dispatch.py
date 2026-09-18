"""Publishes durable outbox rows to Service Bus, then marks them dispatched.

**The second half of the transactional outbox.** The writer made the state change and the message
durable together; this publishes what is already durable. It runs in its own process precisely so it
cannot be tempted to publish inside the writer's transaction.

**Duplicates are expected and correct here.** A crash between ``send`` and ``mark_dispatched``
leaves a row that will be published again on the next pass. That is the safe direction: the atomic
claim absorbs a duplicate, whereas marking dispatched before sending would lose a message entirely.
When forced to choose, this worker sends twice rather than not at all.

**A blocked row never blocks another** (``contracts/triggers.md``). Each row is attempted
independently and a failure moves to the next, because ordering is not guaranteed and not assumed
anywhere in this platform — so one poisonous row must not stall every organisation's triggers behind
it.

**The ceiling is real.** Ten attempts, then the row is marked undispatchable — left in place, never
silently dropped, never auto-retried. For a granted decision that is a *governance* failure that
surfaces as approved-but-not-executed; for a refusal kind it is an operational alert only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from ragcore.domain.envelopes import (
    IntegrationCommandEnvelope,
    IntegrationMessageKind,
    TriggerEnvelope,
    TriggerKind,
)
from ragcore.domain.identifiers import CorrelationId, IntegrationJobId, WorkItemId
from ragcore.messaging.deadletter import report_dead_letter
from ragcore.messaging.retry import BackoffPolicy

_log: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """What one dispatcher pass achieved."""

    published: int
    failed: int
    undispatchable: int

    @property
    def had_work(self) -> bool:
        """Whether this pass found anything to do."""
        return self.published + self.failed + self.undispatchable > 0


_INTEGRATION_KINDS: frozenset[str] = frozenset(member.value for member in IntegrationMessageKind)
"""The kind values that mean "this row is an integration command, not a trigger".

Derived from the enum rather than written out, so adding a kind cannot leave this behind — and a
row whose kind is in neither set raises below rather than being published as the wrong shape.
"""


def subject_of(envelope: TriggerEnvelope | IntegrationCommandEnvelope) -> str:
    """The durable row this envelope names, as a string an operator can look up.

    Args:
        envelope: The trigger or the command.

    Returns:
        The work identifier for a trigger, the job identifier for a command.
    """
    if isinstance(envelope, IntegrationCommandEnvelope):
        return str(envelope.job_id)
    return str(envelope.work_item_id)


def envelope_from_row(row: Any) -> TriggerEnvelope | IntegrationCommandEnvelope:  # noqa: ANN401
    """Rebuild the envelope from a durable outbox row.

    The row's ``payload`` holds what a consumer may see; ``kind`` is a column because the dispatcher
    routes on it and a routing value buried in JSON is one nobody can index.

    **Routing happens here, on the kind, and the identifier follows from it.** A trigger names a
    work item; an integration command names an integration job. Reading the wrong key would produce
    a message that deserialises perfectly on the far side and names a row that does not exist — so
    the key is chosen by the same value the queue is chosen by, in one place.

    Args:
        row: The outbox row.

    Returns:
        The envelope to publish.

    Raises:
        ValueError: When the row's kind belongs to neither closed set. An unrecognised kind is
            **never** published as a best guess: the dispatcher does not know which queue it
            belongs on or which identifier it carries, and either guess is a message somebody has
            to trace.
        KeyError: When the payload lacks the identifier its kind requires. Also a refusal rather
            than a blank-identifier message. Both land in :func:`dispatch_once`'s failure path,
            which retries to the ceiling and then surfaces the row to a human — so neither is
            silently dropped, and neither is published half-formed.
    """
    from uuid import UUID

    payload = row.payload or {}

    if row.kind in _INTEGRATION_KINDS:
        return IntegrationCommandEnvelope(
            job_id=IntegrationJobId(UUID(payload["jobId"])),
            correlation_id=CorrelationId(payload["correlationId"]),
            kind=IntegrationMessageKind(row.kind),
        )

    return TriggerEnvelope(
        work_item_id=WorkItemId(UUID(payload["workItemId"])),
        correlation_id=CorrelationId(payload["correlationId"]),
        kind=TriggerKind(row.kind),
    )


async def dispatch_once(
    outbox: Any,  # noqa: ANN401 — the Outbox repository, which is not a port
    publisher: Any,  # noqa: ANN401 — MessagePublisherPort plus trace kwargs
    *,
    batch_size: int,
    policy: BackoffPolicy | None = None,
) -> DispatchResult:
    """Publish one batch of undispatched rows.

    One pass rather than a loop, so the caller owns the schedule and a test can run exactly one.

    **Each row is independent.** A publish failure increments that row's attempts and moves on; it
    never aborts the batch, because a blocked row must not block another.

    Args:
        outbox: The outbox repository.
        publisher: The Service Bus publisher.
        batch_size: How many rows to attempt.
        policy: The retry policy, for the ceiling. The default ten-attempt policy when omitted.

    Returns:
        What the pass achieved.
    """
    backoff = policy if policy is not None else BackoffPolicy()
    rows = await outbox.undispatched(batch_size)

    published = failed = undispatchable = 0

    for row in rows:
        envelope = envelope_from_row(row)
        try:
            await publisher.publish(envelope)
        except Exception as error:  # noqa: BLE001 — one row's failure must not end the batch
            attempts = await outbox.record_failure(row.outbox_id)
            if backoff.exhausted(attempts):
                undispatchable += 1
                report_dead_letter(
                    # The row's own subject, whichever kind it is. An integration command names a
                    # job rather than a work item; reporting an empty string, or the wrong
                    # identifier, would put an undispatchable row in the alert with nothing an
                    # operator can look up — and an undispatchable command means **approved work
                    # never ran**, which is the alert that most needs to be actionable.
                    work_item_id=subject_of(envelope),
                    correlation_id=str(envelope.correlation_id),
                    kind=envelope.kind.value,
                    reason=(
                        f"undispatchable after {attempts} publish attempts; the row is left in "
                        f"place and is never auto-retried past the ceiling ({error!r})"
                    ),
                )
            else:
                failed += 1
                _log.warning(
                    "Outbox row %s failed to publish (attempt %s of %s); it stays undispatched "
                    "and the next pass will try again. correlation=%s",
                    row.outbox_id,
                    attempts,
                    backoff.ceiling,
                    envelope.correlation_id,
                )
            continue

        # Marked only after the transport accepted it. The reverse order would lose a message on a
        # crash in between, and losing beats duplicating in exactly no situation this platform has.
        await outbox.mark_dispatched(row.outbox_id)
        published += 1

    return DispatchResult(published=published, failed=failed, undispatchable=undispatchable)


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, the Service Bus client and the schedule — belongs to the
    deployment that runs this and is wired at Stage 12 alongside the other workers.
    :func:`dispatch_once` is the whole behaviour and is what the tests exercise.
    """
    raise NotImplementedError(
        "dispatch_once is implemented and tested; the worker's process wiring lands with the "
        "other workers at Stage 12 — see specs/001-platform-scaffold/tasks.md"
    )
