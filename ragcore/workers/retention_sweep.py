"""Removes data past its retention window, per class.

**Each class is swept independently**, and that independence is the point: expiring a conversation
must leave every audit record of what was decided in it intact and complete (spec FR-AUDIT-004).
The two clocks are different lengths, start at different moments, and are configured separately.

============================ ======================= ==================================
Class                        Default                 Swept by
============================ ======================= ==================================
Chat content                 90 days from terminal   this worker
Work, operations, approvals  follows audit           this worker, on the audit window
Graph checkpoints            30 days after the work  this worker, through the checkpointer
Audit events                 7 years                 **not this worker** — see below
============================ ======================= ==================================

**Audit is not swept here, and cannot be.** The runtime principal holds ``INSERT`` and ``SELECT`` on
``audit_event`` and neither ``UPDATE`` nor ``DELETE`` (revision ``0019``). Expiring audit past
``retain_until`` is a privileged, separately-audited job; a worker that could do it is a worker that
could be made to do it early.

**Every window resolves from the organisation's overrides, falling back to the platform default**
(spec FR-SESS-008). A missing override never means unbounded retention, which is why
:func:`~ragcore.persistence.retention.window_for` returns a window rather than an optional one.

**The sweep is per organisation.** There is no cross-tenant delete: each pass takes a
:class:`~ragcore.domain.tenancy.TenantContext` and deletes within it, so a defect in the predicate
costs one organisation's data rather than everyone's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.domain.tenancy import TenantContext
from ragcore.domain.work import WorkItemState
from ragcore.persistence import models
from ragcore.persistence.concurrency import rows_affected
from ragcore.persistence.retention import RetentionClass, window_for


class CheckpointPruner(Protocol):
    """The one operation this worker needs from the checkpointer.

    A protocol rather than an import of the saver, for two reasons. It keeps ``langgraph`` out of
    this module — the checkpointer imports it lazily precisely so that nothing else has to — and it
    narrows what this worker can do to the ``langgraph`` schema to exactly one verb. A module
    holding the saver itself could also read, write and set up those tables, and the reason
    checkpoints are pruned *through* the checkpointer rather than with a ``DELETE`` is that this
    worker should not be able to reach that schema any other way.
    """

    async def adelete_thread(self, thread_id: str) -> None:
        """Remove every checkpoint belonging to one thread."""
        ...


@dataclass(frozen=True, slots=True)
class SweepResult:
    """What one organisation's sweep removed.

    Returned rather than logged, so the caller records it and a test can assert on it. A sweeper
    that only logged its effect would be a sweeper nothing could prove had run correctly.

    ``checkpoints_eligible`` and ``checkpoints_pruned`` are both carried, and on a healthy pass they
    are equal. They are separate fields because a divergence is the signal that the checkpointer
    refused a delete, and collapsing them into one number would hide exactly that.
    """

    tenant_id: str
    sessions_removed: int
    checkpoints_eligible: int
    checkpoints_pruned: int

    @property
    def removed_anything(self) -> bool:
        """Whether this pass had work to do."""
        return self.sessions_removed > 0 or self.checkpoints_pruned > 0


async def sweep_chat_content(session: AsyncSession, tenant: TenantContext, now: datetime) -> int:
    """Delete sessions past their content window, and everything that hangs off them.

    **Driven by ``content_expires_at``, not by a duration computed here.** The stamp was written
    when the session reached a terminal state, using the organisation's window as it stood then —
    so shortening a window governs what expires from now on rather than retroactively deleting what
    is already past the new, shorter line.

    Messages, steps and feedback go with the session by ``ON DELETE CASCADE``. That is deliberate:
    three separate deletes would be three chances to add a fourth child table and forget it.

    Returns:
        The number of sessions removed.
    """
    sessions = models.CHAT_SESSION
    result = await session.execute(
        delete(sessions).where(
            sessions.c.tenant_id == tenant.tenant_id.value,
            sessions.c.content_expires_at.isnot(None),
            sessions.c.content_expires_at <= now,
        )
    )
    return rows_affected(result)


COMPLETED_WORK_STATES: Final[tuple[WorkItemState, ...]] = (
    WorkItemState.EXECUTED,
    WorkItemState.FAILED,
    WorkItemState.EXPIRED,
    WorkItemState.CANCELLED,
    WorkItemState.ESCALATED,
)
"""The states that mean the graph will not resume.

An explicit list rather than "anything old enough": a checkpoint for work that might still resume
is live state, not expired state, and the three ``awaiting_*`` suspensions persist indefinitely by
design (spec FR-SESS-016).
"""


async def eligible_checkpoint_threads(
    session: AsyncSession, tenant: TenantContext, now: datetime, overrides: dict[str, Any] | None
) -> list[str]:
    """Identify completed work whose checkpoints may be pruned.

    Returns identifiers rather than deleting, because the checkpoint tables are in the ``langgraph``
    schema and belong to the checkpointer. This worker decides *which* threads are eligible — a
    question only platform state can answer — and the caller prunes them through the checkpointer's
    own surface. A ``DELETE FROM langgraph.*`` issued from here would be Alembic reaching into a
    schema it explicitly does not own.

    Returns:
        The work-item identifiers whose checkpoints are past their window.
    """
    window = window_for(RetentionClass.GRAPH_CHECKPOINT, overrides)
    work = models.WORK_ITEM
    statement = select(work.c.work_item_id).where(
        work.c.tenant_id == tenant.tenant_id.value,
        work.c.state.in_([state.value for state in COMPLETED_WORK_STATES]),
        work.c.updated_at <= now - window.duration,
    )
    rows = (await session.execute(statement)).all()
    return [str(row.work_item_id) for row in rows]


async def prune_checkpoints(pruner: CheckpointPruner, thread_ids: list[str]) -> int:
    """Remove the checkpoints of threads that :func:`eligible_checkpoint_threads` selected.

    **Deleting an already-deleted thread is a no-op, and that is what makes the sweep rerunnable.**
    Eligibility is computed from platform state — a completed work item, old enough — and the work
    item outlives the checkpoint by years, because work follows the audit window rather than the
    chat one. So the same thread is selected on every pass for the rest of its retention, and every
    pass after the first deletes nothing.

    That is wasteful rather than wrong, and it is a deliberate trade. The alternatives were a marker
    column, which is a schema change this task does not own, or probing the ``langgraph`` tables to
    see what still exists, which is the cross-schema reach the whole arrangement avoids. Redundant
    no-op deletes are the cheapest of the three and the only one that keeps the boundary intact.

    Args:
        pruner: The checkpointer, narrowed to its delete verb.
        thread_ids: The eligible threads.

    Returns:
        The number of threads pruned.
    """
    pruned = 0
    for thread_id in thread_ids:
        await pruner.adelete_thread(thread_id)
        pruned += 1
    return pruned


async def sweep_tenant(
    session: AsyncSession,
    pruner: CheckpointPruner,
    tenant: TenantContext,
    now: datetime,
    overrides: dict[str, Any] | None,
) -> SweepResult:
    """Sweep every class this worker may sweep, for one organisation.

    **One organisation per call, and the tenant is an argument rather than a filter applied later.**
    Both queries underneath restrict on it, so a defect in a predicate costs one organisation's data
    instead of everyone's — which is the difference between an incident and a catastrophe.

    **Audit is not swept, and this function has no path that could.** See the module docstring: the
    runtime principal holds no ``DELETE`` on ``audit_event``, so expiring audit is a separately
    privileged job. Chat content and checkpoints expire on their own clocks and leave every audit
    record of what was decided intact (spec FR-AUDIT-004).

    **Safe to rerun.** Nothing here is driven by a cursor, a high-water mark or a swept flag: chat
    is driven by ``content_expires_at``, checkpoints by the owning work item's state and age. A
    second pass over an already-swept organisation deletes nothing and raises nothing.

    Args:
        session: An open session. The caller owns the transaction — a sweeper that committed on its
            own could not be composed into a larger unit of work, and the tests need to observe the
            rows before and after.
        pruner: The checkpointer, narrowed to its delete verb.
        tenant: The organisation to sweep.
        now: The instant to sweep against, from the clock port. Never ``datetime.now``.
        overrides: ``tenant_mapping.retention_overrides`` for this organisation, or ``None``.

    Returns:
        What this pass removed.
    """
    sessions_removed = await sweep_chat_content(session, tenant, now)
    eligible = await eligible_checkpoint_threads(session, tenant, now, overrides)
    pruned = await prune_checkpoints(pruner, eligible)

    return SweepResult(
        tenant_id=str(tenant.tenant_id),
        sessions_removed=sessions_removed,
        checkpoints_eligible=len(eligible),
        checkpoints_pruned=pruned,
    )


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, the checkpointer, the schedule and the list of
    organisations to sweep — belongs to the deployment that runs this, and is wired at Stage 12
    alongside the other workers.

    **The sweep itself is complete.** :func:`sweep_tenant` performs a whole organisation's pass and
    is what the tests exercise; this is only the process boundary. Leaving it honestly unwired is
    better than inventing a configuration story the deployment has not agreed — and a retention
    worker is the worst possible place to guess at one, because the guess would be about which
    organisations get their data deleted and how often.
    """
    raise NotImplementedError(
        "the sweep is implemented and tested — see sweep_tenant; the worker's process wiring "
        "lands with the other workers at Stage 12, see specs/001-platform-scaffold/tasks.md"
    )
