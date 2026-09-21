"""Audit writing — **requester, approver, executor, method, organisation and result, every time**.

`FR-AUDIT-001` names six things every consequential record must carry, and `FR-AUDIT-003` says
denials, expiries and escalations are recorded as durably as permissions. This module is where a
platform event becomes a record with all six on it.

**Why a writer rather than "call the sink".** :class:`~ragcore.application.ports.AuditSinkPort` can
append anything it is handed, which means "every audit record names by what means" would be a rule
each call site honours. The constructors below take the facts of a *moment* — a gate refusal, an
execution attempt, an escalation — and assemble the chain from them, so a caller cannot record a
gate refusal without its treatment or an execution without its method. The absent field is a
missing argument rather than a missing column.

**The chain's three actors are three facts, and ``None`` is one of the answers.**
``approved_by=None`` on an ``AUTO`` execution is not a gap: it is the audit trail stating that
nobody approved it, which is exactly what an auditor asking "who signed this off" needs to be told.
The same goes for ``execution_method=NONE`` on a refusal — something was decided and nothing ran.

**What the platform knows is recorded separately from what it attempted.** An execution record
carries its :class:`~ragcore.domain.governance.VerificationOutcome`, and a ``client_attested``
outcome is written as a claim. Nothing here can upgrade one into a confirmation, because the
outcome arrives from the verification stage and this module has no arithmetic that touches it
(ADR-0004).

**Telemetry MUST NEVER answer an audit question** (A2 §8.1, spec FR-OPS-004).
This module writes to the audit sink and to nothing else — it has no logger, and the absence is
deliberate: a writer that also logged would be one somebody could later "simplify" into logging
only.

**Credentials never appear.** Every actor is a stable principal identifier or a platform-owned
mechanism name. There is no free-text field on :class:`~ragcore.domain.audit.AuditFacts` through
which a provider's error string — which can carry a URL, a header or a token — could reach the
record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from ragcore.domain.audit import ActorChain, AuditEventKind, AuditFacts
from ragcore.domain.governance import ExecutionMethod
from ragcore.domain.identifiers import AuditEventId

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import AuditSinkPort
    from ragcore.domain.governance import ExecutionTreatment, VerificationOutcome
    from ragcore.domain.identifiers import CorrelationId, PrincipalId
    from ragcore.domain.tenancy import TenantContext
    from ragcore.governance.gate import GateOutcome

__all__ = ["AuditWriter"]


@dataclass(frozen=True, slots=True)
class AuditWriter:
    """Writes the consequential moments of one flow.

    Frozen and slotted: the sink is chosen in the composition root, and a writer whose sink could
    be replaced mid-flow is one whose records for a single correlation identifier could land in two
    places.

    Attributes:
        sink: The durable, append-only audit store. Separate from telemetry, separately retained.
    """

    sink: AuditSinkPort

    async def record_gate_outcome(
        self,
        tenant: TenantContext,
        correlation_id: CorrelationId,
        outcome: GateOutcome,
        requester: PrincipalId,
        approver: PrincipalId | None = None,
    ) -> None:
        """Record what deterministic governance decided.

        **A refusal is recorded exactly as durably as a permission** (`FR-AUDIT-003`), and it
        carries its treatment: a denial without the treatment that produced it cannot explain
        itself, and "why was this refused" is the question an audit trail is most often asked.

        Args:
            tenant: The organisation.
            correlation_id: The journey this decision belongs to.
            outcome: The gate's own conclusion. Taken whole rather than as separate arguments, so
                a caller cannot record a disposition from one evaluation beside a treatment from
                another.
            requester: Who asked.
            approver: Who decided, where a human did. ``None`` for ``AUTO`` — and that ``None`` is
                the audit answer to "who approved this", not an omission.
        """
        await self._append(
            tenant,
            correlation_id,
            ActorChain(
                # Nothing executed: a gate decision is a decision. Recording the workload here
                # would put an executor on a record where nothing was executed.
                executed_by="none",
                execution_method=ExecutionMethod.NONE,
                requested_by=requester,
                approved_by=approver,
            ),
            AuditFacts(
                kind=(
                    AuditEventKind.GATE_REFUSED
                    if not outcome.is_authorized
                    else AuditEventKind.TREATMENT_ASSIGNED
                ),
                outcome=outcome.reason.value,
                treatment=outcome.treatment,
            ),
        )

    async def record_execution(
        self,
        tenant: TenantContext,
        correlation_id: CorrelationId,
        *,
        requester: PrincipalId,
        approver: PrincipalId | None,
        executed_by: str,
        method: ExecutionMethod,
        treatment: ExecutionTreatment,
        verification: VerificationOutcome,
        outcome: str,
    ) -> None:
        """Record an execution and what the platform actually knows about its effect.

        Keyword-only past the correlation identifier, and every argument required. Several are the
        same type — two principals, two strings — and a positional call could swap them silently,
        putting the executor in the requester's place on a record nobody will re-derive.

        Args:
            tenant: The organisation.
            correlation_id: The journey.
            requester: Who asked.
            approver: Who approved, or ``None`` where the treatment was ``AUTO``.
            executed_by: A stable identifier for whatever performed the effect. Deliberately
                polymorphic (§28.3): a human, the Workload principal, or an endpoint.
            method: By what means. Recorded distinctly from the actor, because the same principal
                acting through two mechanisms is two different facts (§28.4).
            treatment: The treatment in force.
            verification: What the platform **knows**, as distinct from what it attempted. A
                ``client_attested`` outcome is a claim and is recorded as one.
            outcome: The platform's own word for what happened. Never a provider's error string.
        """
        await self._append(
            tenant,
            correlation_id,
            ActorChain(
                executed_by=executed_by,
                execution_method=method,
                requested_by=requester,
                approved_by=approver,
            ),
            AuditFacts(
                kind=AuditEventKind.EXECUTION_RECORDED,
                outcome=outcome,
                treatment=treatment,
                verification=verification,
            ),
        )

    async def record_escalation(
        self,
        tenant: TenantContext,
        correlation_id: CorrelationId,
        requester: PrincipalId,
        reason: str,
    ) -> None:
        """Record that work left the automated path for a person.

        An escalation is a consequential moment (`FR-AUDIT-003`): something the platform was asked
        to do is now somebody's job, and the record of *why* is what stops a queue of escalations
        being a mystery.

        Args:
            tenant: The organisation.
            correlation_id: The journey, carried onto the queued request as well so the two join.
            requester: Who asked.
            reason: The platform's own reason, in the vocabulary of
                :class:`~ragcore.application.escalation.EscalationReason`.
        """
        await self._append(
            tenant,
            correlation_id,
            ActorChain(
                executed_by="none",
                execution_method=ExecutionMethod.NONE,
                requested_by=requester,
            ),
            AuditFacts(kind=AuditEventKind.WORK_ESCALATED, outcome=reason),
        )

    async def _append(
        self,
        tenant: TenantContext,
        correlation_id: CorrelationId,
        chain: ActorChain,
        facts: AuditFacts,
    ) -> None:
        """Append one event.

        The event identifier is minted here rather than taken from a caller. A caller-supplied
        identifier is one two records could share, and an append-only store with two records under
        one identifier cannot be read back in order.
        """
        await self.sink.record(tenant, AuditEventId(uuid4()), correlation_id, chain, facts)
