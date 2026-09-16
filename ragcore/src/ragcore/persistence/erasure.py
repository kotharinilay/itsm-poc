"""Per-organisation erasure. **A hard delete, and that is the requirement** (spec FR-AUDIT-006).

A soft-deleted row is still the organisation's data. Erasure that set a flag would satisfy a query
filter and nothing else — the bytes would still be in the table, in the backups, and in the index —
so no entity in this scaffold carries ``deleted_at`` and this module issues ``DELETE``.

**Three things are removed, and the third is the one that gets forgotten.**

1. *Platform rows*, in foreign-key order, which :func:`erase_tenant` performs.
2. *Derived representations* — the retrieval index. Derived data is still the organisation's data;
   the index being rebuildable makes it cheap to lose, not exempt from erasure.
3. *Cached copies*, including graph checkpoints in the ``langgraph`` schema. Those are working
   state rather than authority, and they are also a verbatim record of a conversation.

**Audit is the named exception, and it is not this module's to make.** The runtime principal holds
no ``DELETE`` on ``audit_event`` (revision ``0019``), so :func:`erase_tenant` physically cannot
remove it and does not try. Erasing the record of what was authorized is a decision with legal
weight; it belongs to a privileged, separately-audited job, and the honest shape of this module is
to say so rather than to quietly widen its own grant.

**Erasure runs in one transaction.** A half-erased organisation is worse than an un-erased one: it
reports success while leaving rows a later query will still return.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.domain.tenancy import TenantContext
from ragcore.persistence import models
from ragcore.persistence.concurrency import rows_affected

ERASURE_ORDER: Final[tuple[str, ...]] = (
    # Children before parents. Several of these would cascade anyway; issuing them explicitly
    # means the order is reviewable here rather than implied by fifteen `ondelete` clauses spread
    # across the model module, and a row that stops cascading still gets deleted.
    "feedback",
    "session_step",
    "message",
    "idempotency_record",
    "operation",
    "approval",
    "consent",
    "work_item",
    "chat_session",
    "outbox_message",
    "ingestion_run",
    "tenant_entitlement",
    "tenant_mapping",
)
"""Every tenant-scoped table, in deletion order.

``audit_event`` is absent by design — see the module docstring. ``governance_record`` is absent
because the catalogue is platform-wide and belongs to no organisation.
"""

UNERASED_BY_DESIGN: Final[frozenset[str]] = frozenset({"audit_event"})
"""What erasure deliberately leaves behind, so a test can assert the decision rather than infer it
from a table that was simply forgotten."""


async def erase_tenant(session: AsyncSession, tenant: TenantContext) -> dict[str, int]:
    """Remove every platform row belonging to one organisation.

    **The caller owns the transaction**, and it must be one transaction: erasure that committed
    per table would leave an organisation half-removed if it failed partway, reporting success for
    the tables it got to.

    This removes platform state only. The derived retrieval index and the ``langgraph`` checkpoints
    are removed by their own owners — the index has no rows here to delete, and the checkpoint
    schema is not Alembic's. A caller performing a complete erasure invokes all three; this
    function is deliberately not the place that reaches across those boundaries, because a
    persistence helper issuing calls to a search service is how a transaction ends up waiting on an
    HTTP timeout.

    Args:
        session: The open transaction.
        tenant: The organisation being erased. A :class:`TenantContext`, so erasure cannot be
            invoked from a tenant identifier that arrived in a request.

    Returns:
        Rows removed per table, for the operator record. The counts are the evidence that erasure
        happened, which is why they are returned rather than logged and discarded.
    """
    removed: dict[str, int] = {}
    for table_name in ERASURE_ORDER:
        table = models.TABLES_BY_NAME[table_name]
        result = await session.execute(
            delete(table).where(table.c.tenant_id == tenant.tenant_id.value)
        )
        removed[table_name] = rows_affected(result)
    return removed
