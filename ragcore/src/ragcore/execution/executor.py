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

**Verification is a separate call to a separate tool, and it is the catalogue that names it.** Not
the model, not the proposal, not the executing adapter. An adapter that could nominate its own
verifier could nominate itself, and "the thing that acted says it worked" is exactly what
``client_attested`` means — so the platform would be relabelling an attestation as a confirmation.
Where an entry names no verification tool the outcome can only ever be ``client_attested``, and
:func:`verify` says so rather than optimistically defaulting.

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
from typing import TYPE_CHECKING, Protocol

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

__all__ = [
    "ExecutionLeg",
    "ExecutionReport",
    "UnauthorizedExecutionError",
    "VerificationPort",
    "verify",
]


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


class VerificationPort(Protocol):
    """A **server-side read** that confirms or contradicts a claimed effect.

    Declared here because this module is the consumer. Deliberately read-shaped: it observes state
    and returns whether the claim holds. There is no verb on it that changes anything, so a
    verification step cannot become a second execution — which is what "verify by re-running it"
    would quietly be.
    """

    async def observe(
        self,
        tenant: TenantContext,
        tool: str,
        identity: OperationIdentity,
        parameters: Mapping[str, object],
        correlation_id: CorrelationId,
    ) -> bool:
        """Read the real state and report whether the intended effect is present.

        Returns:
            ``True`` when the effect is observed. ``False`` means observed-and-absent, which is a
            contradiction — an implementation that cannot reach the system raises rather than
            returning ``False``, because "I could not look" and "I looked and it is not there" must
            not become the same answer.
        """
        ...


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """What happened, and separately, what the platform knows about it.

    Attributes:
        succeeded: Whether the invocation itself completed. **Not** proof of the effect.
        verification: What the platform knows. The only field a user-facing message may be derived
            from, and only when it is ``SERVER_CONFIRMED``.
        idempotency_key: The derived key the invocation carried, for the audit record.
        method: By what means the effect was performed. Recorded distinctly from the actor (§28.4).
        verified_by: The verification tool the catalogue named, where one ran. ``None`` when the
            entry named none — which is why the outcome is an attestation.
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


async def verify(
    verifier: VerificationPort | None,
    tenant: TenantContext,
    verification_tool: str | None,
    identity: OperationIdentity,
    parameters: Mapping[str, object],
    correlation_id: CorrelationId,
) -> tuple[VerificationOutcome, str | None]:
    """Confirm the effect independently, where the catalogue names a tool to confirm it with.

    Args:
        verifier: The server-side read port, or ``None`` when the platform has none bound.
        tenant: The organisation.
        verification_tool: The tool named **by the catalogue entry**. ``None`` is the ordinary case
            in the scaffold: the reference fixtures change nothing, so there is nothing to observe,
            and naming a tool would claim a confirmation the platform cannot perform.
        identity: What ran.
        parameters: What it ran with. Passed so the observation is of *this* effect rather than of
            the system in general.
        correlation_id: The journey.

    Returns:
        The outcome and the tool that produced it. ``(CLIENT_ATTESTED, None)`` when no tool is
        named or none is bound — an honest statement that nobody checked, never an optimistic
        default.
    """
    if verification_tool is None or verifier is None:
        return VerificationOutcome.CLIENT_ATTESTED, None

    observed = await verifier.observe(
        tenant, verification_tool, identity, parameters, correlation_id
    )
    outcome = VerificationOutcome.SERVER_CONFIRMED if observed else VerificationOutcome.CONTRADICTED
    return outcome, verification_tool


@dataclass(frozen=True, slots=True)
class ExecutionLeg:
    """Invokes an authorized capability exactly once and establishes what is known about it.

    Attributes:
        tools: Invocation of a governed capability. Reached only past the gate.
        clock: The current instant.
        verifier: The server-side read used for verification, where one is bound. ``None`` in the
            scaffold, which is why every outcome here is an attestation and says so.
    """

    tools: ToolExecutionPort
    clock: ClockPort
    verifier: VerificationPort | None = None

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
        """Execute, then verify. In that order, and both exactly once.

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
            verification_tool: The tool the **catalogue entry** names, or ``None``.
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

        verification, verified_by = await verify(
            self.verifier, tenant, verification_tool, identity, parameters, correlation_id
        )

        return ExecutionReport(
            succeeded=True,
            verification=verification,
            idempotency_key=str(key),
            method=method,
            verified_by=verified_by,
        )
