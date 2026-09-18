"""The integration job repository: dispatching an authorized capability, and reading its result.

ADR-0007, specification §21.6.5. RagCore selects the capability and its parameters; the Integrations
Service executes it. **The selection is written to a durable row before the message announcing it
exists**, and the message carries only that row's opaque identifier.

**This lives in `persistence/`, not `application/`, and the architecture tests are why.** It holds
SQL, and SQL is a provider detail: `tests/architecture/test_layering.py` asserts that no provider
package reaches the application layer, because an application module that imported a driver would
make the use case constructible only against a real database. The application layer consumes this
through a port when a use case needs it.

```text
The message causes work to happen.
The durable job record provides the instruction, the authority and the tenant context.
```

**The job row and its outbox row commit in the same transaction as the state change.** A job written
without an outbox row is an instruction nobody will ever act on; an outbox row without a job is a
command naming nothing. Either alone is a silent stall, which is why the two are never separate.

**RagCore does not execute and does not reach the connector.** It writes the instruction, it holds
the atomic claim — idempotency boundary 1 — and it reads the outcome back from the four result
columns on its own row. It never reads the Integrations Service's schema.

**Tool selection is RagCore's** (`FR-INTEG-007`), and this is where that ownership is exercised: the
capability, its version and its parameters are decided here and recorded here. What RagCore does
**not** decide is whether the execution is permitted at the point of effect — the Integrations
Service re-verifies every authority fact against durable state, because time passes between a
proposal and its execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from uuid import uuid4

from sqlalchemy import text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["DispatchedJob", "IntegrationDispatcher"]

_INSERT_JOB: Final = text(
    """
    INSERT INTO platform.integration_job (
        job_id, work_item_id, operation_id, tenant_id,
        catalogue_id, catalogue_version, parameters, expires_at
    ) VALUES (
        :job_id, :work_item_id, :operation_id, :tenant_id,
        :catalogue_id, :catalogue_version, CAST(:parameters AS JSONB), :expires_at
    )
    """
)

_MARK_DISPATCHED: Final = text(
    """
    UPDATE platform.integration_job
       SET status = 'dispatched', dispatched_at = now(), updated_at = now()
     WHERE job_id = :job_id
    """
)

_READ_RESULT: Final = text(
    """
    SELECT
        j.job_id,
        j.work_item_id,
        j.result_status::text       AS result_status,
        j.result_verification::text AS result_verification,
        j.result_execution_id,
        j.result_recorded_at
    FROM platform.integration_job AS j
    WHERE j.job_id = :job_id
    """
)


@dataclass(frozen=True, slots=True)
class DispatchedJob:
    """A written instruction, ready to be announced.

    Attributes:
        job_id: The opaque identifier the message will carry — **and the only thing it will carry**
            besides correlation context and a routing kind.
        work_item_id: The authority record being spent.
    """

    job_id: UUID
    work_item_id: UUID


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    """What the Integrations Service reported back, read from RagCore's own row.

    Attributes:
        executed: Whether the operation ran.
        verification: What the far side **observed**. RagCore draws the conclusion from it; a
            `client_attested` outcome MUST NOT be presented to a user as confirmed resolution
            (ADR-0004).
        execution_id: The attempt, so an operator can find the record without RagCore needing read
            access to the Integrations Service's schema.
        recorded_at: When the result landed. ``None`` means no result yet.
    """

    executed: bool
    verification: str | None
    execution_id: UUID | None
    recorded_at: datetime | None

    @property
    def is_pending(self) -> bool:
        """Whether the Integrations Service has yet to answer."""
        return self.recorded_at is None

    @property
    def may_report_resolution(self) -> bool:
        """Whether this outcome may be told to a user as resolved.

        **Only a server-confirmed one.** Written as a property here rather than as a comparison at
        each surface, so "did anyone actually check" is asked in one place — and so no surface can
        write `if executed:` and answer a different question.
        """
        return self.executed and self.verification == "server_confirmed"


class IntegrationDispatcher:
    """Writes the instruction and queues its announcement, atomically."""

    def __init__(self, outbox: object) -> None:
        """Bind the dispatcher.

        Args:
            outbox: RagCore's existing transactional outbox. Reused rather than duplicated: one
                dispatcher, one retry policy, one dead-letter story for every message this
                deployable publishes.
        """
        self._outbox = outbox

    async def dispatch(
        self,
        session: AsyncSession,
        *,
        work_item_id: UUID,
        operation_id: UUID,
        tenant_id: UUID,
        catalogue_id: str,
        catalogue_version: int,
        parameters: Mapping[str, object],
        expires_at: datetime,
    ) -> DispatchedJob:
        """Write the job row in the caller's transaction.

        Keyword-only past the session: several arguments are identifiers of the same shape, and a
        positional call could swap two of them into a row that looks correct and instructs the wrong
        operation for the wrong organisation.

        Args:
            session: The caller's transaction — **the same one as the state change**, so the
                instruction and the change that justified it are durable together.
            work_item_id: The authority record.
            operation_id: The operation within it.
            tenant_id: The organisation, from trusted context. Written here so the Integrations
                Service can recover it **without the message carrying it**.
            catalogue_id: The capability RagCore selected.
            catalogue_version: The version in force at selection, so the far side can refuse a
                mismatch rather than silently running whatever is current.
            parameters: The arguments, as data.
            expires_at: The execution window, from the authority record.

        Returns:
            The written job.
        """
        job_id = uuid4()
        await session.execute(
            _INSERT_JOB,
            {
                "job_id": job_id,
                "work_item_id": work_item_id,
                "operation_id": operation_id,
                "tenant_id": tenant_id,
                "catalogue_id": catalogue_id,
                "catalogue_version": catalogue_version,
                "parameters": json.dumps(dict(parameters)),
                "expires_at": expires_at,
            },
        )
        return DispatchedJob(job_id=job_id, work_item_id=work_item_id)

    async def mark_dispatched(self, session: AsyncSession, job_id: UUID) -> None:
        """Record that the command reached the queue.

        Args:
            session: The caller's transaction.
            job_id: The job.
        """
        await session.execute(_MARK_DISPATCHED, {"job_id": job_id})

    async def read_result(self, session: AsyncSession, job_id: UUID) -> IntegrationResult | None:
        """Read the outcome back from RagCore's own row.

        **Not from the Integrations Service's schema.** RagCore holds no grant there, and the four
        result columns exist precisely so it does not need one — the coupling between the two
        services stays one directed edge plus a queue, rather than a shared table.

        Args:
            session: The caller's transaction.
            job_id: The job.

        Returns:
            The result, or ``None`` when the job does not exist.
        """
        rows = (await session.execute(_READ_RESULT, {"job_id": job_id})).mappings().all()
        if not rows:
            return None

        row = rows[0]
        return IntegrationResult(
            executed=row["result_status"] == "executed",
            verification=row["result_verification"],
            execution_id=row["result_execution_id"],
            recorded_at=row["result_recorded_at"],
        )
