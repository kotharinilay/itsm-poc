"""Dead-lettering, and why nothing here replays.

**A dead-lettered message is never automatically replayed.** It surfaces for operational handling
and stops. For a trigger that carried a granted decision, recovery is *fresh authorization* — a
human deciding again — never a redelivery of the original message (``contracts/triggers.md``).

The reason is that a replay is indistinguishable, from inside, from the original: same work item,
same correlation, same authority on the record. So a replay of an approved trigger is a second
authorized execution of an action a human approved just once. The queue cannot tell the difference,
the consumer cannot tell the difference, and by the time anyone can, the external system has acted
twice.

**Approved-but-not-executed is a governance failure, not an operational one.** It means a human
authorized work that never happened. That is why the classification below is by *what was granted*
rather than by what broke: the two refusal kinds dead-lettering is an alert and nothing more,
because no authority was granted and nothing can execute on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Final

from ragcore.domain.envelopes import TriggerKind

_log: Final = logging.getLogger(__name__)


class DeadLetterSeverity(Enum):
    """How a dead-lettered trigger must be handled."""

    GOVERNANCE = "governance"
    """A granted decision never executed. Surfaces as approved-but-not-executed, plus an alert."""

    OPERATIONAL = "operational"
    """No authority was granted. An alert; the work stays suspended until cancelled or expired."""


@dataclass(frozen=True, slots=True)
class DeadLetterReport:
    """What is recorded when a trigger is dead-lettered.

    **Carries no payload and no authority-bearing value** — the work identifier and the correlation
    identifier are enough to find everything else, and a report that embedded the message body would
    be a second copy of authority-adjacent data living somewhere with different retention.
    """

    work_item_id: str
    correlation_id: str
    kind: str
    reason: str
    severity: DeadLetterSeverity

    @property
    def requires_fresh_authorization(self) -> bool:
        """Whether recovery needs a human to decide again rather than a replay."""
        return self.severity is DeadLetterSeverity.GOVERNANCE


def severity_for(kind: TriggerKind) -> DeadLetterSeverity:
    """Classify a dead-lettered trigger by what it granted.

    An **unknown or unhandled** kind is operational, never governance, and never a reason to
    proceed. The scaffold wires only ``sample.flow``; the four decision kinds' handlers are deferred
    (spec FR-DEMO-016), and one arriving now dead-letters rather than being treated as authorization
    (spec FR-DEMO-018).

    Args:
        kind: The trigger kind.

    Returns:
        The severity.
    """
    if kind.resumes_to_execution and kind is not TriggerKind.SAMPLE_FLOW:
        return DeadLetterSeverity.GOVERNANCE
    return DeadLetterSeverity.OPERATIONAL


def report_dead_letter(
    *, work_item_id: str, correlation_id: str, kind: str, reason: str
) -> DeadLetterReport:
    """Record a dead-lettered trigger and raise the appropriate alert.

    Returns the report rather than only logging it, so the caller can surface it and a test can
    assert on it. A dead-letter path that only logged would be one nothing could prove had fired.

    Args:
        work_item_id: The opaque work identifier from the message.
        correlation_id: The journey identifier, so the whole story is recoverable.
        kind: The trigger kind, as a string — it may be one this build does not know.
        reason: Why it was dead-lettered, in platform vocabulary.

    Returns:
        The report.
    """
    try:
        severity = severity_for(TriggerKind(kind))
    except ValueError:
        # A kind this build does not know. Operational, and explicitly not a reason to proceed:
        # an unrecognised kind is the one case where "carry on" would mean acting on authority
        # nobody in this process can verify.
        severity = DeadLetterSeverity.OPERATIONAL

    report = DeadLetterReport(
        work_item_id=work_item_id,
        correlation_id=correlation_id,
        kind=kind,
        reason=reason,
        severity=severity,
    )

    if report.severity is DeadLetterSeverity.GOVERNANCE:
        _log.error(
            "Dead-lettered a granted trigger: work %s is approved but not executed. Recovery is "
            "fresh authorization, never replay. kind=%s correlation=%s reason=%s",
            work_item_id,
            kind,
            correlation_id,
            reason,
        )
    else:
        _log.warning(
            "Dead-lettered a trigger. No authority was granted, so nothing can execute on it. "
            "kind=%s work=%s correlation=%s reason=%s",
            kind,
            work_item_id,
            correlation_id,
            reason,
        )

    return report
