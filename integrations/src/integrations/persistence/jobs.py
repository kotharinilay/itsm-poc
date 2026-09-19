"""The integration job: **where the instruction, the organisation and the authority come from.**

Specification §21.6.5, §18.5, `FR-INTEG-014`, `FR-INTEG-018`. The consumer receives an opaque
identifier and reads everything else here.

**This module is the whole answer to "how does the Integrations Service learn what to do and for
whom".** It reads the durable row RagCore wrote; nothing is taken from the message.

**Authority is re-verified here, not inherited.** The row carries the execution window and the work
item's state, so an authorization that expired, was cancelled, or belongs to an organisation that is
no longer active is refused at this point — after the message arrived and before any effect. Each of
those is ordinary rather than exceptional: time passes between a proposal and its execution.

**Writes are confined to four columns by a database grant**, not by this module's restraint. The
`UPDATE` below names only `result_*` columns because that is all the principal holds; an `UPDATE`
touching `catalogue_id`, `parameters` or `tenant_id` is refused by PostgreSQL with a permission
error. A service that could rewrite its own instruction could execute an operation other than the
one governance authorized.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import text

from integrations.domain.catalogue import CapabilityIdentity

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping
    from datetime import datetime
    from uuid import UUID

    from integrations.domain.execution import ExecutionOutcome, VerificationOutcome
    from integrations.persistence.engine import Database

__all__ = ["JobInstruction", "JobRepository"]

# The work item is joined so the WINDOW and the STATE come from the authority record itself rather
# than from a copy on the job row. A copy could be stale; the authority record cannot be, because it
# is the authority.
_LOAD: Final = text(
    """
    SELECT
        j.job_id,
        j.work_item_id,
        j.operation_id,
        j.tenant_id,
        j.catalogue_id,
        j.catalogue_version,
        j.parameters,
        j.status::text        AS status,
        j.expires_at,
        w.state::text         AS work_state,
        w.approval_state::text AS approval_state,
        w.expires_at          AS work_expires_at,
        t.status::text        AS tenant_status
    FROM platform.integration_job AS j
    JOIN platform.vw_work_item_v1 AS w ON w.work_item_id = j.work_item_id
    JOIN platform.vw_tenant_v1    AS t ON t.tenant_id = j.tenant_id
    WHERE j.job_id = :job_id
    """
)

# ONLY the four result columns. The principal holds `UPDATE` on these and no others, so a statement
# naming any further column is refused by the database before it runs.
_RECORD_RESULT: Final = text(
    """
    UPDATE platform.integration_job
       SET result_status       = CAST(:result_status AS platform.integration_result_status),
           result_verification = CAST(:result_verification AS platform.verification_outcome),
           result_execution_id = :result_execution_id,
           result_recorded_at  = :result_recorded_at
     WHERE job_id = :job_id
    """
)


@dataclass(frozen=True, slots=True)
class JobInstruction:
    """What to do, for whom, and whether it may still be done.

    Attributes:
        job_id: This instruction.
        work_item_id: The authority record being spent.
        operation_id: The operation within it.
        tenant_id: **The organisation. Recovered from here and from nowhere else.**
        identity: The capability and the version RagCore selected.
        parameters: The arguments, as **data**. The destination comes from the connector registry,
            never from these.
        expires_at: The execution window.
        work_state: The authority record's state.
        approval_state: Its approval state.
        tenant_status: The organisation's admission status.
    """

    job_id: UUID
    work_item_id: UUID
    operation_id: UUID
    tenant_id: UUID
    identity: CapabilityIdentity
    parameters: Mapping[str, object]
    expires_at: datetime
    work_state: str
    approval_state: str
    tenant_status: str

    def is_executable_at(self, now: datetime) -> bool:
        """Whether the authority this instruction rests on is still good.

        Four conditions, each from the platform's own rules rather than from the message:

        * the organisation is **active** (`FR-EXEC-003`) — a suspension between proposal and
          execution is ordinary;
        * the work has not reached a terminal state, so it was not cancelled;
        * the approval was granted;
        * `now` is inside the execution window (`FR-EXEC-001`) — expiry is a **normal outcome**,
          not an error, and produces no execution.

        Args:
            now: The current instant, injected rather than read, so expiry is testable.

        Returns:
            Whether execution may proceed.
        """
        return (
            self.tenant_status == "active"
            and self.work_state not in {"cancelled", "expired", "closed", "failed"}
            and self.approval_state in {"approved", "auto_authorized", "consented"}
            and now < self.expires_at
        )


class JobRepository:
    """Reads instructions; writes results, and only results."""

    def __init__(self, database: Database) -> None:
        """Bind the repository.

        Args:
            database: The platform database, reached with a principal that holds `SELECT` on this
                table and `UPDATE` on four of its columns.
        """
        self._database = database

    async def load(self, job_id: UUID) -> JobInstruction | None:
        """Read the instruction the opaque identifier names.

        Args:
            job_id: From the message envelope. It grants nothing; it names a row.

        Returns:
            The instruction, or ``None`` when no such job exists. ``None`` dead-letters: a command
            naming a job that is not there has either outlived its data or come from somewhere it
            should not have, and both want a human.
        """
        rows = await self._database.read(_LOAD, {"job_id": job_id})
        if not rows:
            return None

        row = rows[0]
        return JobInstruction(
            job_id=row["job_id"],
            work_item_id=row["work_item_id"],
            operation_id=row["operation_id"],
            tenant_id=row["tenant_id"],
            identity=CapabilityIdentity(
                catalogue_id=row["catalogue_id"], version=row["catalogue_version"]
            ),
            parameters=dict(row["parameters"] or {}),
            # The WORK ITEM's window, not the job row's, where they differ. The authority record is
            # the authority; a job row's copy is a convenience.
            expires_at=row["work_expires_at"] or row["expires_at"],
            work_state=row["work_state"],
            approval_state=row["approval_state"],
            tenant_status=row["tenant_status"],
        )

    async def record_result(
        self,
        session: Any,  # An AsyncSession; typed loosely to keep this module driver-agnostic
        job_id: UUID,
        result_status: ExecutionOutcome,
        verification: VerificationOutcome,
        execution_id: UUID,
        recorded_at: datetime,
    ) -> None:
        """Write the outcome back, in the caller's transaction.

        Takes a session rather than opening one so the result column write, the execution record and
        the outbox row commit **together or not at all**. A result written outside that transaction
        could survive a crash that lost the evidence behind it.

        Args:
            session: The caller's transaction.
            job_id: The job.
            result_status: Executed or failed. A refusal maps to `failed` — from RagCore's side the
                operation did not happen, and the detail lives on the execution record.
            verification: What was observed. **Reported, not concluded.**
            execution_id: The attempt, so RagCore can find the record without reading this service's
                schema.
            recorded_at: When.
        """
        await session.execute(
            _RECORD_RESULT,
            {
                "job_id": job_id,
                "result_status": "executed" if result_status.value == "succeeded" else "failed",
                "result_verification": verification.value,
                "result_execution_id": execution_id,
                "result_recorded_at": recorded_at,
            },
        )
