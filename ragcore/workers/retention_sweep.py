"""Removes data past its retention window, per class.

**Each class is swept independently**, and that independence is the point: expiring a conversation
must leave every audit record of what was decided in it intact and complete (spec FR-AUDIT-004).
The two clocks are different lengths, start at different moments, and are configured separately.

============================ ======================= ==================================
Class                        Default                 Swept by
============================ ======================= ==================================
Chat content                 90 days from terminal   this worker
Work, operations, approvals  follows audit           this worker, on the audit window
Graph checkpoints            30 days after the work  this worker, in ``langgraph``
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
from typing import Any, Final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.domain.tenancy import TenantContext
from ragcore.domain.work import WorkItemState
from ragcore.persistence import models
from ragcore.persistence.concurrency import rows_affected
from ragcore.persistence.retention import RetentionClass, window_for


@dataclass(frozen=True, slots=True)
class SweepResult:
    """What one organisation's sweep removed.

    Returned rather than logged, so the caller records it and a test can assert on it. A sweeper
    that only logged its effect would be a sweeper nothing could prove had run correctly.
    """

    tenant_id: str
    sessions_removed: int
    checkpoints_eligible: int

    @property
    def removed_anything(self) -> bool:
        """Whether this pass had work to do."""
        return self.sessions_removed > 0


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


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, the tenant list to sweep — belongs to the deployment
    that runs this, and is wired at Stage 12 alongside the other workers. The sweep functions above
    are complete and are what the tests exercise; this is the process boundary, and leaving it
    honestly unwired is better than inventing a configuration story the deployment has not agreed.
    """
    raise NotImplementedError(
        "the sweep functions in this module are implemented and tested; the worker's process "
        "wiring lands with the other workers — see specs/001-platform-scaffold/tasks.md"
    )
