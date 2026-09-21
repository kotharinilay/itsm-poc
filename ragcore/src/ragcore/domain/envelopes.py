"""Asynchronous trigger and realtime notification envelopes.

Both are defined here, in the pure domain, because both are governed by a rule about what they
may **not** carry — and that rule is domain policy, not transport detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ragcore.domain.identifiers import (
    CorrelationId,
    IntegrationJobId,
    SessionId,
    WorkItemId,
)


class TriggerKind(Enum):
    """What made a work item resumable (contracts/triggers.md).

    A **routing hint only**. The consumer reads authority from the durable work record either
    way, and a consumer that decides anything from ``kind`` is defective.
    """

    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    CONSENT_GRANTED = "consent.granted"
    CONSENT_REFUSED = "consent.refused"

    SAMPLE_FLOW = "sample.flow"
    """The scaffold's inert platform demonstration. **Never a product capability.**

    It exists so the outbox-to-bus-to-consumer seam can be proven end to end before any governed
    operation runs across it, and it resumes to an execution that reaches no external system
    (spec FR-DEMO-007, FR-DEMO-014). The four kinds above are the real ones; their handlers are
    deferred (spec FR-DEMO-016), and an unhandled kind dead-letters rather than proceeding.
    """

    @property
    def resumes_to_execution(self) -> bool:
        """Whether this kind can lead to execution, or only to honest closure."""
        return self in _GRANTING_TRIGGER_KINDS


_GRANTING_TRIGGER_KINDS = frozenset(
    {TriggerKind.APPROVAL_GRANTED, TriggerKind.CONSENT_GRANTED, TriggerKind.SAMPLE_FLOW}
)
"""Kinds that resume towards execution rather than to closure.

``SAMPLE_FLOW`` is here because the seam it proves is the one that ends in execution — but what it
executes is an inert reference fixture, so "resumes to execution" and "has an effect" remain
different statements. The refusal kinds resume too; they just resume to honest closure.
"""


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


class IntegrationMessageKind(Enum):
    """The closed kind set for the integration seam (``contracts/triggers.md``, ADR-0007).

    **A separate enum from :class:`TriggerKind`, and that separation is structural rather than
    tidiness.** The two travel on different queues, carry different identifiers and have different
    lifecycles. Merging them would make
    :class:`~ragcore.domain.envelopes.TriggerEnvelope` constructible with an integration kind — and
    that envelope carries ``workItemId``, so the resulting message would name the wrong row and be
    refused by a consumer that expects ``jobId``.

    A **routing hint only**, exactly as ``TriggerKind`` is. The consumer reads authority from the
    durable record either way, and a consumer that decided anything from ``kind`` is defective.
    """

    EXECUTE = "integration.execute"
    """RagCore has an authorized capability to run. Consumed by the Integrations Service."""

    COMPLETED = "integration.completed"
    """An execution finished and its outcome is durable. Consumed by RagCore."""

    FAILED = "integration.failed"
    """An execution did not complete. Consumed by RagCore, **never as a re-dispatch**."""

    @property
    def is_outbound(self) -> bool:
        """Whether RagCore publishes this kind, rather than consuming it.

        Exists so the dispatcher can refuse to publish a result kind. RagCore holds **no Sender
        role on the results queue** (``build/infra/messaging/queues.json``), so publishing one
        would fail at the platform anyway — but failing here names the defect instead of surfacing
        it as an authorization error against a queue nobody expected this process to write to.
        """
        return self is IntegrationMessageKind.EXECUTE


@dataclass(frozen=True, slots=True)
class IntegrationCommandEnvelope:
    """The entire command message. Three fields, and **nothing authority-bearing**.

    `FR-INTEG-014`. Explicitly absent, and never to be added: tenant, requester, roles, action,
    target, parameters, treatment, approval state, expiry, command content or credentials. The
    organisation, the capability, its version and its authority all come from the durable
    ``integration_job`` row that :attr:`job_id` names.

    ```text
    The message causes work to happen.
    The durable job record provides the instruction, the authority and the tenant context.
    ```

    **The mirror of this type lives in the Integrations Service**
    (``integrations.messaging.envelope.MessageEnvelope``) and the duplication is deliberate
    (.claude/rules/10-principles.md P-6). Two deployables that shared this class would share a
    package, and
    the wire contract — three named fields — is cheap enough to state twice and expensive enough to
    couple over. Each side refuses what it does not recognise, which is what makes the contract hold
    without a shared library to enforce it.
    """

    job_id: IntegrationJobId
    correlation_id: CorrelationId
    kind: IntegrationMessageKind


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
