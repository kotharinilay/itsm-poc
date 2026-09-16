"""The audit record's domain shape: the actor chain and what a recordable event is.

**Telemetry MUST NEVER answer an audit question** (constitution Principle VIII, spec FR-OPS-004).
That is why this lives in the domain with its own types and its own port
(:class:`~ragcore.application.ports.AuditSinkPort`) rather than as a structured log field: a
logger with an ``audit=True`` flag is one sampling configuration away from losing the record.

Two rules shape everything here:

* **Denials, expiries and escalations are recorded as durably as permissions**
  (spec FR-AUDIT-003). A sink that only sees the happy path cannot answer "why was this refused".
* **Credentials never appear** — only stable principal identifiers and non-secret references.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ragcore.domain.governance import ExecutionMethod, ExecutionTreatment, VerificationOutcome
from ragcore.domain.identifiers import PrincipalId


class AuditEventKind(Enum):
    """The consequential moments that MUST leave a record.

    100% audit coverage of consequential actions is a non-functional commitment, so this set is
    closed and adding to it is a deliberate change rather than an incidental one.
    """

    TENANT_ADMITTED = "tenant.admitted"
    TENANT_REFUSED = "tenant.refused"
    OPERATION_PROPOSED = "operation.proposed"
    TREATMENT_ASSIGNED = "treatment.assigned"
    GATE_REFUSED = "gate.refused"
    CONSENT_RECORDED = "consent.recorded"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    AUTHORIZATION_EXPIRED = "authorization.expired"
    WORK_CLAIMED = "work.claimed"
    EXECUTION_ATTEMPTED = "execution.attempted"
    EXECUTION_RECORDED = "execution.recorded"
    SESSION_TAKEN_OVER = "session.taken_over"
    WORK_CANCELLED = "work.cancelled"
    WORK_ESCALATED = "work.escalated"


@dataclass(frozen=True, slots=True)
class ActorChain:
    """Who asked, who approved, and who actually did it (data-model.md §Audit event).

    Three distinct facts that a single ``user_id`` column cannot hold. §28.3 makes
    ``executed_by`` deliberately polymorphic — a human, the Workload principal, or an endpoint
    running a signed script are different answers to "who did it" — and pairs it with
    :class:`~ragcore.domain.governance.ExecutionMethod` so "by what means" is answerable too.

    Attributes:
        requested_by: The end user whose request started this. ``None`` for platform-initiated
            work such as a sweep.
        approved_by: The staff principal who decided, or the requester who consented. ``None``
            where the treatment was ``AUTO`` — and that ``None`` is itself the audit answer to
            "who approved this", not a missing value.
        executed_by: A stable identifier for whatever performed the effect. Text rather than a
            :class:`~ragcore.domain.identifiers.PrincipalId` because it is not always a
            directory principal.
        execution_method: The mechanism. ``NONE`` where nothing executed — a refusal, an
            expiry, a denial — which are recorded just as durably.
    """

    executed_by: str
    execution_method: ExecutionMethod
    requested_by: PrincipalId | None = None
    approved_by: PrincipalId | None = None


@dataclass(frozen=True, slots=True)
class AuditFacts:
    """The governance facts one audit event carries, beyond its actor chain.

    Attributes:
        kind: Which consequential moment this is.
        outcome: What happened, in the platform's own vocabulary. Never a provider error string.
        treatment: The treatment in force, where one had been assigned. Present on a denial as
            well as a permission, because ``NOT_ALLOWED`` is the answer to why it was refused.
        verification: What the platform actually **knows** about the effect. A
            ``CLIENT_ATTESTED`` outcome is a claim, and the audit record says so rather than
            recording it as confirmed resolution (ADR-0004).
    """

    kind: AuditEventKind
    outcome: str
    treatment: ExecutionTreatment | None = None
    verification: VerificationOutcome | None = None
