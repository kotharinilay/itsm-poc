"""The execution leg. **Recovers, re-verifies, executes once, records whole.**

The order below is the design, and each step exists because skipping it has a specific consequence:

```text
1. load the instruction from the durable job row      ← not from the message
2. re-verify authority against durable state          ← prior gating is not standing permission
3. re-verify access and policy facts                  ← entitlement can be revoked meanwhile
4. derive the idempotency key from the RECOVERED org  ← never from anything a caller supplied
5. invoke                                             ← once, never retried
6. record the attempt and queue the result, atomically
```

**This module executes; it MUST NEVER decide** (constitution Principle III). It re-verifies *facts*
and originates no authorization: it assigns no treatment and performs no role intersection, and
there is no code path here that could.

**A failed authorized action does not re-fire** (`FR-EXEC-006`). There is no retry loop: a failure
needs fresh human authorization, and a loop would spend one authority record more than once.

**Verification is reported, not concluded.** This service says what it observed —
`server_confirmed`, `client_attested` or `contradicted`. Whether a user may be told the issue is
resolved is RagCore's conclusion (`FR-INTEG-009`). A service that both acted and judged its own
success would be relabelling an attestation as a confirmation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from integrations.domain.catalogue import AccessRefusal, IdempotencyPolicy
from integrations.domain.execution import (
    ExecutionOutcome,
    ExecutionRecord,
    VerificationOutcome,
)
from integrations.egress.http import EgressError
from integrations.execution.idempotency import derive_key
from integrations.execution.normalization import BoundaryValidationError
from integrations.messaging.envelope import MessageKind

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

    from integrations.application.ports import ConnectorInvocationPort
    from integrations.observability.telemetry import ConnectorMetrics
    from integrations.persistence.audit import AuditWriter
    from integrations.persistence.engine import Database
    from integrations.persistence.executions import ExecutionRepository
    from integrations.persistence.jobs import JobInstruction, JobRepository
    from integrations.policy.checks import AccessPolicy

__all__ = ["ExecutionLeg", "ExecutionReport"]

logger = logging.getLogger(__name__)

# A refusal maps to the outcome an operator can act on. Kept as data rather than a chain of `if`s so
# that adding a refusal reason to the domain forces a decision here rather than silently falling
# through to a generic failure.
_REFUSAL_OUTCOME = {
    AccessRefusal.NOT_ENTITLED: ExecutionOutcome.REFUSED_UNENTITLED,
    AccessRefusal.NOT_REGISTERED: ExecutionOutcome.REFUSED_UNREGISTERED,
    AccessRefusal.VERSION_MISMATCH: ExecutionOutcome.REFUSED_VERSION,
    AccessRefusal.NO_BINDING: ExecutionOutcome.REFUSED_UNREGISTERED,
}


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """What the consumer needs to know about one delivery.

    Attributes:
        executed: Whether this delivery produced an attempt. ``False`` for a duplicate the derived
            key suppressed — which is a **success of the idempotency boundary**, not a failure.
        outcome: What happened, where an attempt was made.
        dead_letter: Whether the message should dead-letter rather than complete. Reserved for a
            command that cannot be interpreted at all; an ordinary refusal completes, because the
            refusal is itself the durable answer.
    """

    executed: bool
    outcome: ExecutionOutcome | None
    dead_letter: bool = False


class ExecutionLeg:
    """Turns one opaque command into at most one external effect."""

    def __init__(
        self,
        database: Database,
        jobs: JobRepository,
        policy: AccessPolicy,
        executions: ExecutionRepository,
        audit: AuditWriter,
        invoker: ConnectorInvocationPort,
        metrics: ConnectorMetrics,
    ) -> None:
        """Bind the leg.

        Args:
            database: The transaction the four writes share. Injected rather than reached
                through a repository, so the unit of work is visible at the composition root
                instead of being an implementation detail two collaborators happen to agree on.
            jobs: Where the instruction, organisation and authority come from.
            policy: The execution-time re-check.
            executions: Durable records and the result outbox.
            audit: The governance record, appended to the **one** audit store. A separate
                collaborator from `executions` because the two answer different questions and are
                retained on different schedules — merging them would force one retention policy
                and one access grant onto both.
            invoker: The connector invocation port — the MCP client or a native adapter. A **port**,
                not a union, because this module must not know the difference: a branch on connector
                kind here would be a second dispatch point competing with the registry.
            metrics: Attempts, outcomes and duration.
        """
        self._database = database
        self._jobs = jobs
        self._policy = policy
        self._executions = executions
        self._audit = audit
        self._invoker = invoker
        self._metrics = metrics

    async def run(self, job_id: UUID, correlation_id: str) -> ExecutionReport:
        """Execute one command.

        Args:
            job_id: The opaque identifier from the envelope. It names a row; it grants nothing.
            correlation_id: The journey, carried onto the outbound call, the execution record and
                the result announcement.

        Returns:
            What happened, and whether the message should dead-letter.
        """
        instruction = await self._jobs.load(job_id)
        if instruction is None:
            # A command naming a job that is not there has either outlived its data or come from
            # somewhere it should not have. Neither is recoverable by retrying.
            logger.warning(
                "Integration command names no known job",
                extra={"correlationId": correlation_id},
            )
            return ExecutionReport(executed=False, outcome=None, dead_letter=True)

        now = datetime.now(UTC)

        if not instruction.is_executable_at(now):
            # EXPIRY IS A NORMAL OUTCOME, NOT AN ERROR (spec §29.5), and so is a cancellation or a
            # deactivated organisation. Recorded rather than dead-lettered: the refusal IS the
            # answer, and RagCore needs to receive it so the work closes honestly instead of
            # hanging until somebody notices.
            return await self._record(
                instruction,
                connector_id="",
                outcome=ExecutionOutcome.REFUSED_WINDOW,
                verification=VerificationOutcome.CLIENT_ATTESTED,
                correlation_id=correlation_id,
                attempted_at=now,
            )

        decision = await self._policy.evaluate(instruction.tenant_id, instruction.identity)
        if not decision.permitted:
            refusal = decision.refusal
            return await self._record(
                instruction,
                connector_id="",
                outcome=_REFUSAL_OUTCOME.get(refusal, ExecutionOutcome.FAILED)
                if refusal
                else ExecutionOutcome.FAILED,
                verification=VerificationOutcome.CLIENT_ATTESTED,
                correlation_id=correlation_id,
                attempted_at=now,
            )

        binding = decision.binding
        assert binding is not None  # noqa: S101 — `permitted` guarantees it; narrows for the type checker

        # DERIVED FROM THE RECOVERED ORGANISATION, not from anything that arrived. A key derived
        # from a caller-supplied organisation would be a key an attacker could steer, which would
        # let one organisation's retry collide with another's first attempt.
        key = (
            derive_key(instruction.tenant_id, instruction.work_item_id, instruction.operation_id)
            if binding.idempotency_policy is IdempotencyPolicy.DERIVED_KEY
            else None
        )

        # Asked BEFORE invoking. The unique constraint would catch a duplicate afterwards, but only
        # after the external effect had already happened a second time — which is precisely what
        # boundary 2 exists to prevent.
        if key is not None and await self._executions.execution_for_key(key) is not None:
            logger.info(
                "Duplicate integration command suppressed before invocation",
                extra={"correlationId": correlation_id},
            )
            return ExecutionReport(executed=False, outcome=None)

        started = datetime.now(UTC)
        try:
            result = await self._invoker.invoke(
                binding,
                instruction.tenant_id,
                instruction.parameters,
                key,
                correlation_id,
            )
        except (EgressError, BoundaryValidationError):
            # UNREACHABLE, reported distinctly from not-entitled (spec FR-EXT-022) and never
            # re-fired. The effect MAY have happened — the transport failed, which says nothing
            # about the far side — so recovery reads real state rather than retrying.
            self._metrics.record(
                connector_id=binding.connector_id,
                outcome=ExecutionOutcome.UNREACHABLE.value,
                duration_ms=self._elapsed_ms(started),
            )
            return await self._record(
                instruction,
                connector_id=binding.connector_id,
                outcome=ExecutionOutcome.UNREACHABLE,
                verification=VerificationOutcome.CLIENT_ATTESTED,
                correlation_id=correlation_id,
                attempted_at=started,
            )

        outcome = ExecutionOutcome.SUCCEEDED if result.succeeded else ExecutionOutcome.FAILED
        self._metrics.record(
            connector_id=binding.connector_id,
            outcome=outcome.value,
            duration_ms=self._elapsed_ms(started),
        )

        return await self._record(
            instruction,
            connector_id=binding.connector_id,
            outcome=outcome,
            # CLIENT_ATTESTED, NOT SERVER_CONFIRMED. Nobody has read the real state: the call said
            # it worked. Reporting a confirmation here is exactly the relabelling ADR-0004 forbids,
            # and the verification stage that could upgrade this runs in RagCore.
            verification=VerificationOutcome.CLIENT_ATTESTED,
            correlation_id=correlation_id,
            attempted_at=started,
            external_reference=result.external_reference,
            normalized_result=result.payload,
            key=key,
        )

    async def _record(
        self,
        instruction: JobInstruction,
        *,
        connector_id: str,
        outcome: ExecutionOutcome,
        verification: VerificationOutcome,
        correlation_id: str,
        attempted_at: datetime,
        external_reference: str | None = None,
        normalized_result: object = None,
        key: str | None = None,
    ) -> ExecutionReport:
        """Write the attempt, the audit record, the result columns and the outbox row in **one**
        transaction.

        All four together or none. Each pairing matters for its own reason:

        * a result column set without an execution record claims an attempt with no evidence;
        * an execution record without an outbox row leaves an external effect nobody hears about;
        * an **audit record that committed separately** could survive a rolled-back execution —
          asserting in the governance store that an effect happened when it did not — or be lost
          while the effect persisted. Neither is recoverable after the fact, which is why the audit
          write joins this transaction rather than following it.
        """
        derived = key or derive_key(
            instruction.tenant_id, instruction.work_item_id, instruction.operation_id
        )
        completed = datetime.now(UTC)

        record = ExecutionRecord(
            job_id=instruction.job_id,
            tenant_id=instruction.tenant_id,
            connector_id=connector_id or "none",
            catalogue_id=instruction.identity.catalogue_id,
            catalogue_version=instruction.identity.version,
            idempotency_key=derived,
            outcome=outcome,
            verification=verification,
            correlation_id=correlation_id,
            attempted_at=attempted_at,
            external_reference=external_reference,
            normalized_result=normalized_result,  # type: ignore[arg-type]
            completed_at=completed,
        )

        kind = (
            MessageKind.COMPLETED if outcome is ExecutionOutcome.SUCCEEDED else MessageKind.FAILED
        )

        async for session in self._database.session():
            written = await self._executions.record(session, record, kind)
            if not written:
                # The unique constraint won the race with a concurrent replica. No second effect
                # and no second announcement.
                await session.rollback()
                return ExecutionReport(executed=False, outcome=None)

            # THE GOVERNANCE RECORD, in the one audit store (`FR-INTEG-024`). Distinct from the
            # execution record written above: that one says what was attempted against which
            # connector, this one says who did it, by what means, against which organisation and
            # with what result. Different questions, different retention, different readers.
            #
            # `requested_by_oid` and `approved_by_oid` are written NULL by this writer: they live on
            # `work_item` and `approval`, which this principal cannot read and must not be granted
            # (T327 carries the residual).
            await self._audit.record(
                session,
                record,
                work_item_id=instruction.work_item_id,
                occurred_at=attempted_at,
            )

            await self._jobs.record_result(
                session,
                instruction.job_id,
                outcome,
                verification,
                record.execution_id,
                completed,
            )
            await session.commit()

        return ExecutionReport(executed=True, outcome=outcome)

    @staticmethod
    def _elapsed_ms(started: datetime) -> float:
        """Milliseconds since `started`."""
        return (datetime.now(UTC) - started).total_seconds() * 1000.0
