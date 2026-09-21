"""Marks work non-executable once its window passes with no successful claim.

**Expiry is a normal outcome, not an error** (``contracts/triggers.md``). Work that waited fifteen
minutes for a decision that never came, or for a consumer that never claimed it, has simply run out
of time. Reporting that as a failure would fill an alert channel with events nobody can act on and
train everyone to ignore it.

**Why a sweeper rather than a check at execution time.** A work item that expires while nothing is
looking at it must still *become* expired: the staff portal shows it, the audit record reflects it,
and a late trigger finds a record that already says no. Deciding expiry lazily, at the moment
something happens to look, would mean a work item's state depended on whether anyone asked.

**It never executes anything and holds no authority.** It moves records from "waiting" to "too
late", which is the one transition that can be made without a human — because it grants nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from ragcore.application.ports import WorkItemRepositoryPort
from ragcore.domain.tenancy import TenantContext
from ragcore.domain.work import WorkItemState

_log: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExpirySweepResult:
    """What one organisation's expiry pass changed."""

    tenant_id: str
    expired: int
    contended: int

    @property
    def changed_anything(self) -> bool:
        """Whether this pass had work to do."""
        return self.expired > 0


async def sweep_expired(
    repository: WorkItemRepositoryPort,
    tenant: TenantContext,
    now: datetime,
    *,
    limit: int = 100,
) -> ExpirySweepResult:
    """Expire work whose window has passed with no claim.

    **Optimistic, never locking.** Each transition carries the version it read; a losing transition
    means something else changed the row first — most likely a consumer claiming it a moment before
    the window closed. That is the right answer, and this pass simply leaves it alone rather than
    forcing expiry onto work that is now legitimately executing.

    Args:
        repository: The work item repository, tenant-scoped by its interface.
        tenant: The organisation to sweep.
        now: From the clock port. Never ``datetime.now``.
        limit: Bound on one pass, so a backlog drains in bounded passes.

    Returns:
        What the pass changed.
    """
    candidates: list[Any] = await repository.list_expired(tenant, now, limit)

    expired = contended = 0

    for item in candidates:
        moved = await repository.transition(
            tenant,
            item.work_item_id,
            WorkItemState.EXPIRED,
            expected_version=item.version,
        )
        if moved:
            expired += 1
        else:
            # Lost the race. Someone claimed or cancelled it between the read and the write, and
            # their answer is the newer one. Not an error, and deliberately not retried here.
            contended += 1

    if expired:
        _log.info(
            "Expired %s work item(s) for organisation %s; expiry is a normal outcome.",
            expired,
            tenant.tenant_id,
        )

    return ExpirySweepResult(tenant_id=str(tenant.tenant_id), expired=expired, contended=contended)


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, the organisations to sweep and the schedule — belongs to
    the deployment that runs this and is wired at Stage 12 alongside the other workers.
    :func:`sweep_expired` is the behaviour and is what the tests exercise.
    """
    raise NotImplementedError(
        "sweep_expired is implemented and tested; the worker's process wiring lands with the "
        "other workers."
    )
