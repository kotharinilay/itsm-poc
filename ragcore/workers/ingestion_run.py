"""Opens an ingestion run and records its watermark and terminal state.

**No acquisition, no chunking, no embedding.** This worker manages the *run record* and nothing
else (`.claude/rules/10-principles.md` P-8, H-1). The twelfth bounded context exists as a process
boundary and a durable record of what has been ingested; inventing the acquisition behaviour before
a source has been specified would be speculative capability no requirement needs, reported as
though it were real.

**Runs are idempotent** (research R-021). Re-running from a watermark MUST NOT duplicate documents,
which is why the run record holds a resume point rather than a cursor into a stream: a crashed run
is re-run from its last watermark, not resumed from the middle of one.

**The index is derived.** A lost retrieval index is rebuilt by re-running ingestion, not restored
from backup. That is the whole reason this record is in PostgreSQL and the documents are not.

**Ingestion never writes authority.** Nothing in this module touches a work item, an approval or a
consent, and nothing here can: the run row has no foreign key that reaches one.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import func

from ragcore.domain.ingestion import IngestionRunState
from ragcore.domain.tenancy import TenantContext
from ragcore.persistence import models
from ragcore.persistence.concurrency import rows_affected


async def open_run(
    session: AsyncSession, tenant: TenantContext, source: str, watermark: str | None
) -> UUID:
    """Record the start of a run and return its identifier.

    Args:
        session: The caller's open transaction.
        tenant: The organisation being ingested for. **Every ingested record is tenant-stamped**,
            and so is the run that produced it.
        source: The knowledge source.
        watermark: The resume point from the previous successful run, or ``None`` on a first pass.
            ``None`` means *start from the beginning*, not *nothing to do*.

    Returns:
        The run identifier.
    """
    table = models.INGESTION_RUN
    run_id = uuid4()
    await session.execute(
        insert(table).values(
            run_id=run_id,
            tenant_id=tenant.tenant_id.value,
            source=source,
            watermark=watermark,
            state=IngestionRunState.RUNNING.value,
            started_at=func.now(),
        )
    )
    return run_id


async def close_run(
    session: AsyncSession,
    tenant: TenantContext,
    run_id: UUID,
    state: IngestionRunState,
    watermark: str | None,
    document_count: int,
    expected_version: int,
) -> bool:
    """Record a run's terminal state and the watermark it reached.

    The watermark is written **with** the terminal state, in one statement. Writing it separately
    would leave a window in which a run had advanced its position but not recorded that it
    finished — and the next run would resume from a point no completed run had reached.

    Args:
        state: Must be terminal. A run does not close as ``running``.
        expected_version: Optimistic concurrency. A second writer loses and re-reads; nothing
            blocks.

    Returns:
        ``True`` when this writer closed the run, ``False`` when another already had.

    Raises:
        ValueError: When ``state`` is not terminal.
    """
    if not state.is_terminal:
        raise ValueError(f"a run cannot close as {state.value!r}; it is not a terminal state")

    table = models.INGESTION_RUN
    result = await session.execute(
        update(table)
        .where(
            table.c.tenant_id == tenant.tenant_id.value,
            table.c.run_id == run_id,
            table.c.version == expected_version,
        )
        .values(
            state=state.value,
            watermark=watermark,
            document_count=document_count,
            completed_at=func.now(),
            updated_at=func.now(),
            version=table.c.version + 1,
        )
    )
    return rows_affected(result) == 1


def main() -> None:
    """Worker entry point.

    The run record is implemented above and is what the tests exercise. Acquisition itself is
    deliberately absent — see the module docstring — and the process wiring lands with the other
    workers.
    """
    raise NotImplementedError(
        "the run record is implemented; acquisition is deliberately not scaffolded, and the "
        "worker's process wiring lands with the other workers."
    )


__all__ = ["close_run", "main", "open_run"]
