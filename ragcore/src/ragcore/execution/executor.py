"""The execution leg and the verification stage — **what was attempted, and what is known**.

Two stages, two records, and keeping them apart is the whole design. "The call returned 200" and
"the effect happened" are different facts, and a system that stores one field for both will report
the first as the second on the day they differ — which is the day it matters.

`FR-AGENT-008` names the three things the platform may conclude:

* ``server_confirmed`` — a **server-side read** against the real state agreed. The only outcome
  reportable to a user as resolved.
* ``client_attested`` — nobody checked. The call said it worked. **MUST NOT** be reported to a user
  or written to the system of record as confirmed resolution (ADR-0004).
* ``contradicted`` — a server-side read disagreed with the claim. Treated as a failure, because a
  claim the platform has actively disproved is worse than one it never checked.

**The verification workflow is split, and the split is the control** (constitution Principle III,
`FR-INTEG-009`, T295). Verification is a **server-side read against the external system**, so the
call belongs to the Integrations Service along with every other external call. What stays here is
the **conclusion**: whether the platform may tell a user the issue is resolved.

That division is not bureaucratic. A service that both acted and judged its own success would be
reporting an attestation as a confirmation, which is precisely what ``client_attested`` exists to
name. And putting the verification call back in RagCore would hand the orchestrator the external
access ADR-0007 removed from it — so each half is where it is because the other place is worse.

:attr:`ExecutionReport.verification` is therefore **received, not computed**. It arrives on the
result of the invocation, and this module's job is to carry it faithfully into
:attr:`ExecutionReport.may_report_resolution` without upgrading it.

**This module executes; it MUST NEVER decide** (constitution Principle III). :func:`execute` takes
a :class:`~ragcore.governance.gate.GateOutcome` and refuses to run without ``PROCEED``. That check
is deliberately redundant with the graph's routing: routing decides which node runs, this decides
whether the effect happens, and the check sits at the point of effect so a path that reached here
another way still does nothing.

**A failed authorized action does not re-fire** (`FR-EXEC-006`). There is no retry here and none
elsewhere: a failure needs fresh human authorization, and a loop that retried would be an authority
record being spent more than once.

**Idempotency boundary 2 protects the external system** (:mod:`ragcore.execution.idempotency`). The
key is derived, never random, so a repeat of the same logical action is recognised as a repeat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ragcore.domain.governance import ExecutionMethod, VerificationOutcome
from ragcore.execution.idempotency import derive_key
from ragcore.governance.gate import GateDisposition

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping

    from ragcore.application.ports import ClockPort, ToolExecutionPort
    from ragcore.domain.identifiers import (
        CorrelationId,
        OperationId,
        OperationIdentity,
        WorkItemId,
    )
    from ragcore.domain.tenancy import TenantContext
    from ragcore.governance.gate import GateOutcome

__all__ = ["ExecutionLeg", "ExecutionReport", "UnauthorizedExecutionError"]


class UnauthorizedExecutionError(Exception):
    """Execution was attempted without a ``PROCEED`` disposition from the gate.

    A **platform defect**, not a user-facing condition, and raised rather than returned so it
    cannot be mistaken for a failed execution and retried. Nothing maps this to a problem-details
    response: the user did nothing wrong, and the honest handling is an operational alert.
    """

    def __init__(self, disposition: GateDisposition) -> None:
        super().__init__(
            f"execution was attempted on a {disposition.value} disposition. The model proposes; "
            "deterministic governance authorizes, and it did not."
        )
        self.disposition = disposition


# `VerificationPort` AND `verify()` STOOD HERE AND ARE GONE (T295).
#
# They declared a server-side read and performed it — an outbound call to the system the effect
# landed in. That is an external call, and RagCore makes none: the port and its one implementation
# moved to the Integrations Service, which reports what it observed on the result of the invocation.
#
# **What did not move is the sentence below**, :attr:`ExecutionReport.may_report_resolution`. The
# observation is the far side's to make and the conclusion is RagCore's, and keeping the two in
# different deployables is what stops the service that acted from grading its own work.


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """What happened, and separately, what the platform knows about it.

    Attributes:
        succeeded: Whether the invocation itself completed. **Not** proof of the effect.
        verification: What the platform knows. **Reported by the Integrations Service, never
            computed here** (T295) — this module carries it and must not upgrade it. The only field
            a user-facing message may be derived from, and only when it is ``SERVER_CONFIRMED``.
        idempotency_key: The derived key the invocation carried, for the audit record.
        method: By what means the effect was performed. Recorded distinctly from the actor (§28.4).
        verified_by: The verification tool the catalogue named, where one ran, as reported back.
            ``None`` when the entry named none — which is why the outcome is an attestation.
    """

    succeeded: bool
    verification: VerificationOutcome
    idempotency_key: str
    method: ExecutionMethod
    verified_by: str | None = None

    @property
    def may_report_resolution(self) -> bool:
        """Whether this outcome may be reported to a user as resolved.

        Only a server-confirmed one. Written as a property here rather than as a comparison at each
        surface, so "did the platform actually check" is asked in one place — and so there is no
        ``if succeeded:`` at a surface that would answer a different question.
        """
        return self.verification is VerificationOutcome.SERVER_CONFIRMED


@dataclass(frozen=True, slots=True)
class ExecutionLeg:
    """Invokes an authorized capability exactly once and establishes what is known about it.

    Attributes:
        tools: Invocation of a governed capability. Reached only past the gate. In a deployed
            process this dispatches to the Integrations Service; **there is no in-process
            implementation of it and there must not be one** (T296).
        clock: The current instant.
    """

    tools: ToolExecutionPort
    clock: ClockPort

    async def run(
        self,
        tenant: TenantContext,
        outcome: GateOutcome,
        *,
        work_item_id: WorkItemId,
        operation_id: OperationId,
        identity: OperationIdentity,
        parameters: Mapping[str, object],
        verification_tool: str | None,
        correlation_id: CorrelationId,
        method: ExecutionMethod = ExecutionMethod.WORKLOAD,
    ) -> ExecutionReport:
        """Execute once, and record what the far side reported about the effect.

        **No longer "execute, then verify".** Both halves happen on the other side of the boundary
        now, and this method's remaining job is the one thing that must not: deciding what the
        reported outcome entitles the platform to say.

        Keyword-only past the gate outcome: several arguments are identifiers of the same shape,
        and a positional call could swap two of them into a key that looks derived and correlates
        nothing.

        Args:
            tenant: The organisation, resolved from the durable work record.
            outcome: The gate's conclusion. Taken whole rather than as a boolean, because there is
                no way to hold a ``PROCEED`` without holding the evaluation that produced it.
            work_item_id: The authority record this execution is spending.
            operation_id: The operation within it.
            identity: The catalogue entry and version being invoked.
            parameters: The arguments, as the proposal disclosed them. **Data**: the destination of
                the outbound call comes from the catalogue entry, never from here
                (spec FR-EXT-018).
            verification_tool: The tool the **catalogue entry** names, or ``None``. Passed
                through to the far side, which performs the read; it is **not** consulted here, and
                a ``None`` no longer implies the outcome — the reported verification does.
            correlation_id: The journey.
            method: By what means. Defaults to the workload principal acting directly, which is the
                only mechanism the scaffold implements — desktop execution is deferred.

        Returns:
            The report: what was attempted, and separately what is known.

        Raises:
            UnauthorizedExecutionError: When the disposition is anything but ``PROCEED``.
        """
        if outcome.disposition is not GateDisposition.PROCEED:
            raise UnauthorizedExecutionError(outcome.disposition)

        key = derive_key(tenant, work_item_id, operation_id)

        result = await self.tools.invoke(tenant, identity, parameters, key, correlation_id)

        # NOT RETRIED, here or anywhere. A failed authorized action requires fresh human
        # authorization (spec FR-EXEC-006); a retry would spend one authority record twice.
        if not result.succeeded:
            return ExecutionReport(
                succeeded=False,
                # A failed call has nothing to verify. Reported as an attestation of failure rather
                # than as a contradiction: `contradicted` means a server-side read disagreed with a
                # claim, and no claim was made.
                verification=VerificationOutcome.CLIENT_ATTESTED,
                idempotency_key=str(key),
                method=method,
            )

        # TAKEN FROM THE RESULT, NOT DERIVED HERE. The far side looked, or did not; either way it
        # says which. A local default at this point — optimistic or pessimistic — would be RagCore
        # asserting a fact about an external system it cannot reach.
        return ExecutionReport(
            succeeded=True,
            verification=result.verification,
            idempotency_key=str(key),
            method=method,
            verified_by=verification_tool,
        )
