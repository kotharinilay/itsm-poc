"""Idempotency boundary 1 — the atomic claim, which absorbs duplicate delivery.

At-least-once means a duplicate trigger is **routine, not exceptional**. This is what makes that
harmless: a conditional update on ``claimed_at IS NULL``, so two consumers racing the same work item
produce exactly one winner and one loser that stops.

**The database decides, not the application.** A read-then-write — "is it claimed? no? claim it" —
has a window between the two statements in which both consumers read ``NULL``. The conditional
update has no such window because PostgreSQL evaluates the predicate and applies the change in one
statement, and the loser learns it lost from the row count.

**This boundary protects the platform. It does not protect the external system**, which is a
different problem with a different answer: :mod:`ragcore.execution.idempotency`. A claim stops a
second *execution attempt*; the idempotency key stops a second *effect* if the first attempt already
reached the far side before failing. Neither substitutes for the other.

No lock is taken anywhere here, and none may be. The loser returns promptly with a ``False`` rather
than waiting for a winner it cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ragcore.application.ports import WorkItemRepositoryPort
from ragcore.domain.identifiers import WorkItemId
from ragcore.domain.tenancy import TenantContext


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    """Whether this consumer may proceed, and why not when it may not."""

    won: bool
    claimed_by: str

    @property
    def should_stop(self) -> bool:
        """Whether this consumer must stop without executing.

        Losing is a **normal outcome, not an error**. Another consumer holds the work and will
        execute it exactly once; treating this as a failure would turn routine duplicate delivery
        into a stream of alerts nobody can act on.
        """
        return not self.won


async def claim_for_execution(
    repository: WorkItemRepositoryPort,
    tenant: TenantContext,
    work_item_id: WorkItemId,
    *,
    claimed_by: str,
    now: datetime,
) -> ClaimOutcome:
    """Attempt the atomic claim.

    Args:
        repository: The work item repository. Tenant-scoped by its own interface — there is no
            overload that omits the tenant, so this function cannot claim across organisations even
            by mistake.
        tenant: The organisation, resolved from the durable work record rather than from the
            message that woke this consumer.
        work_item_id: The work to claim.
        claimed_by: Who is claiming — the workload principal, for the audit trail. A claim with no
            claimant is one nobody can attribute afterwards.
        now: From the clock port. Never ``datetime.now``.

    Returns:
        The outcome. ``won=False`` means another consumer has it; stop, and do not treat it as an
        error.
    """
    won = await repository.claim(tenant, work_item_id, claimed_by, now)
    return ClaimOutcome(won=won, claimed_by=claimed_by)
