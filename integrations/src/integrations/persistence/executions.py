"""Execution records and the result outbox. **Both written in one transaction.**

Two things become durable together, and the atomicity is the point: the record of what was attempted
and the row that will tell RagCore about it. A crash between them would leave an external effect
nobody ever hears about, or a result announcing an attempt with no evidence behind it.

**The unique constraint on `idempotency_key` is consulted by INSERT, not by a prior SELECT.** A
check-then-act is two statements two replicas can both pass; letting the insert fail is one
statement the database arbitrates. :meth:`ExecutionRepository.record` returns whether it won, so a
redelivered command can be recognised as a duplicate rather than retried.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

    from integrations.domain.execution import ExecutionRecord
    from integrations.messaging.envelope import MessageKind

__all__ = ["ExecutionRepository"]

logger = logging.getLogger(__name__)

_INSERT_EXECUTION: Final = text(
    """
    INSERT INTO integration.execution_record (
        execution_id, job_id, tenant_id, connector_id,
        catalogue_id, catalogue_version, idempotency_key,
        external_reference, outcome, verification, normalized_result,
        correlation_id, attempted_at, completed_at
    ) VALUES (
        :execution_id, :job_id, :tenant_id, :connector_id,
        :catalogue_id, :catalogue_version, :idempotency_key,
        :external_reference,
        CAST(:outcome AS integration.execution_outcome),
        CAST(:verification AS platform.verification_outcome),
        CAST(:normalized_result AS JSONB),
        :correlation_id, :attempted_at, :completed_at
    )
    """
)

_INSERT_OUTBOX: Final = text(
    """
    INSERT INTO integration.outbox_message (message_id, job_id, kind, correlation_id)
    VALUES (:message_id, :job_id, :kind, :correlation_id)
    """
)

# FOR UPDATE SKIP LOCKED: several dispatcher replicas may run, and each takes rows nobody else
# holds rather than queueing behind a peer. Without SKIP LOCKED a second replica blocks on the
# first's rows and adds no throughput while looking busy.
_CLAIM_PENDING: Final = text(
    """
    SELECT message_id, job_id, kind, correlation_id, attempts
    FROM integration.outbox_message
    WHERE dispatched_at IS NULL AND undispatchable IS FALSE
    ORDER BY created_at
    LIMIT :limit
    FOR UPDATE SKIP LOCKED
    """
)

_MARK_DISPATCHED: Final = text(
    """
    UPDATE integration.outbox_message
       SET dispatched_at = now(), updated_at = now()
     WHERE message_id = :message_id
    """
)

# The ceiling is enforced here as well as by the CHECK constraint, because what matters is not only
# that `attempts` stays in range but that reaching the ceiling FLIPS the row to undispatchable in
# the same statement — a row that merely stopped incrementing would be retried forever.
_RECORD_FAILURE: Final = text(
    """
    UPDATE integration.outbox_message
       SET attempts = attempts + 1,
           undispatchable = (attempts + 1 >= 10),
           updated_at = now()
     WHERE message_id = :message_id
    """
)

_HAS_EXECUTION_FOR_KEY: Final = text(
    """
    SELECT execution_id
    FROM integration.execution_record
    WHERE idempotency_key = :idempotency_key
    """
)


class ExecutionRepository:
    """Durable execution records and the outbox that announces them."""

    def __init__(self, database: Any) -> None:  # Database; loose to stay driver-agnostic
        """Bind the repository.

        Args:
            database: The database. Its `integration` schema is this service's to write.
        """
        self._database = database

    async def record(
        self,
        session: Any,  # An AsyncSession
        record: ExecutionRecord,
        result_kind: MessageKind,
    ) -> bool:
        """Write the attempt and queue its result announcement, atomically.

        Args:
            session: The caller's transaction. Both writes join it, so they are durable together or
                not at all.
            record: What was attempted and what is known.
            result_kind: `integration.completed` or `integration.failed`.

        Returns:
            ``True`` when this attempt was recorded. ``False`` when the derived key was **already
            present** — which means a previous delivery of the same command already executed, so
            this one is a duplicate and MUST NOT produce a second effect or a second announcement.

        Note:
            The duplicate is detected by letting the `INSERT` fail rather than by a prior `SELECT`.
            A check-then-act is two statements that two replicas can both pass between; the unique
            constraint is one statement the database arbitrates.
        """
        import json

        try:
            await session.execute(
                _INSERT_EXECUTION,
                {
                    "execution_id": record.execution_id,
                    "job_id": record.job_id,
                    "tenant_id": record.tenant_id,
                    "connector_id": record.connector_id,
                    "catalogue_id": record.catalogue_id,
                    "catalogue_version": record.catalogue_version,
                    "idempotency_key": record.idempotency_key,
                    "external_reference": record.external_reference,
                    "outcome": record.outcome.value,
                    "verification": record.verification.value,
                    "normalized_result": json.dumps(dict(record.normalized_result))
                    if record.normalized_result is not None
                    else None,
                    "correlation_id": record.correlation_id,
                    "attempted_at": record.attempted_at,
                    "completed_at": record.completed_at,
                },
            )
        except IntegrityError:
            # IDEMPOTENCY BOUNDARY 2 DOING ITS JOB. Logged at info, not warning: a duplicate
            # delivery is expected under at-least-once semantics, and a warning here would train
            # operators to ignore the channel.
            logger.info(
                "Duplicate execution suppressed by the derived key",
                extra={"correlationId": record.correlation_id},
            )
            return False

        await session.execute(
            _INSERT_OUTBOX,
            {
                "message_id": uuid4(),
                "job_id": record.job_id,
                "kind": result_kind.value,
                "correlation_id": record.correlation_id,
            },
        )
        return True

    async def execution_for_key(self, idempotency_key: str) -> UUID | None:
        """The attempt a derived key already names, if any.

        Used by the consumer to answer "has this exact command already run" without attempting a
        second effect.

        Args:
            idempotency_key: The derived key.

        Returns:
            The execution identifier, or ``None``.
        """
        rows = await self._database.read(
            _HAS_EXECUTION_FOR_KEY, {"idempotency_key": idempotency_key}
        )
        return rows[0]["execution_id"] if rows else None

    async def claim_pending(self, session: Any, limit: int) -> list[Any]:
        """Take undispatched rows nobody else holds.

        Args:
            session: The caller's transaction. The lock lives as long as it does.
            limit: How many to take.

        Returns:
            The claimed rows.
        """
        result = await session.execute(_CLAIM_PENDING, {"limit": limit})
        return list(result.mappings().all())

    async def mark_dispatched(self, session: Any, message_id: UUID) -> None:
        """Record that a row reached the queue.

        Args:
            session: The caller's transaction.
            message_id: The row.
        """
        await session.execute(_MARK_DISPATCHED, {"message_id": message_id})

    async def record_dispatch_failure(self, session: Any, message_id: UUID) -> None:
        """Increment the attempt count and retire the row at the ceiling.

        **Why a ceiling rather than indefinite retry.** The execution window is fifteen minutes. A
        row that cannot publish within it can no longer lead to a valid resume, so retrying past
        that point creates the illusion of pending work that can never complete. Marking it
        undispatchable and surfacing it to a human is the honest outcome — and where the row
        announced an execution that already happened, it is a governance failure rather than an
        operational one.

        Args:
            session: The caller's transaction.
            message_id: The row.
        """
        await session.execute(_RECORD_FAILURE, {"message_id": message_id})
