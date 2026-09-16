"""Asynchronous trigger and realtime notification envelopes.

Both are defined here, in the pure domain, because both are governed by a rule about what they
may **not** carry — and that rule is domain policy, not transport detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ragcore.domain.identifiers import CorrelationId, SessionId, WorkItemId


class TriggerKind(Enum):
    """What made a work item resumable (contracts/triggers.md).

    A **routing hint only**. The consumer reads authority from the durable work record either
    way, and a consumer that decides anything from ``kind`` is defective.
    """

    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    CONSENT_GRANTED = "consent.granted"
    CONSENT_REFUSED = "consent.refused"

    @property
    def resumes_to_execution(self) -> bool:
        """Whether this kind can lead to execution, or only to honest closure."""
        return self in _GRANTING_TRIGGER_KINDS


_GRANTING_TRIGGER_KINDS = frozenset({TriggerKind.APPROVAL_GRANTED, TriggerKind.CONSENT_GRANTED})


@dataclass(frozen=True, slots=True)
class TriggerEnvelope:
    """The entire Service Bus message. It carries — and may carry — **nothing else**.

    **Every trigger is untrusted.** The event causes work to happen; the durable work record
    provides the authority and the tenant context.

    Explicitly absent, and never to be added: tenant, requester, roles, action, target,
    approval state, expiry, command content, credentials, or any other authority-bearing value.
    """

    work_item_id: WorkItemId
    correlation_id: CorrelationId
    kind: TriggerKind


class NotificationKind(Enum):
    """Realtime event kinds (contracts/notifications.md)."""

    INTERRUPT_PENDING = "interrupt.pending"
    APPROVAL_DECIDED = "approval.decided"
    WORK_PROGRESSED = "work.progressed"
    WORK_COMPLETED = "work.completed"
    WORK_FAILED = "work.failed"
    INSTRUCTION_READY = "instruction.ready"
    SESSION_TAKEN_OVER = "session.taken_over"


@dataclass(frozen=True, slots=True)
class NotificationEnvelope:
    """What the realtime channel may carry.

    **SignalR is a leaf on every consequential path, never a link.** It may tell a client that
    something exists or has changed. It may never carry, imply or trigger a decision.

    The envelope carries no authority-bearing value — no tenant, no role, no approval state, no
    target, no command content. A consumer that reads authority from a notification is
    defective regardless of where the message came from.
    """

    kind: NotificationKind
    occurred_at: datetime
    correlation_id: CorrelationId
    session_id: SessionId | None = None
    work_item_id: WorkItemId | None = None
