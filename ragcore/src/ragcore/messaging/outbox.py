"""The transactional outbox writer — **durability before publication**.

The state change and the message announcing it become durable in the **same transaction**, so a
crash between them loses neither and duplicates neither (research R-017). That is the whole reason
the outbox table exists rather than a publish call at the end of the handler.

**Why not just publish after committing?** Because there is no instant at which that is safe:

- Publish before commit, and a rolled-back transaction has already told the world something
  happened. The consumer wakes, loads a work item that does not exist, and dead-letters.
- Publish after commit, and a process that dies in between has changed the state and told nobody.
  The work is approved and nothing will ever execute it — the approved-but-not-executed condition,
  which is a governance failure rather than a lost message.

The outbox makes the second case recoverable: the row is already durable, so a dispatcher publishes
it whenever it next runs, even after a restart. Duplicates are the accepted cost, and the atomic
claim absorbs them.

**This module writes; it never publishes.** Publication is
:mod:`ragcore.workers.outbox_dispatch`, deliberately in a different process. A writer that could
publish would be one tempted to publish inside the transaction — which is the first bullet above.
"""

from __future__ import annotations

from ragcore.application.ports import OutboxPort
from ragcore.domain.envelopes import TriggerEnvelope, TriggerKind
from ragcore.domain.identifiers import CorrelationId, WorkItemId
from ragcore.domain.tenancy import TenantContext
from ragcore.messaging.tracecontext import TraceContext, current_trace_context


async def enqueue_trigger(
    outbox: OutboxPort,
    tenant: TenantContext,
    work_item_id: WorkItemId,
    kind: TriggerKind,
    *,
    correlation_id: CorrelationId | None = None,
) -> TriggerEnvelope:
    """Write a trigger to the outbox, inside the caller's transaction.

    **The caller owns the transaction, and that is the contract.** This function opens none and
    commits none. Calling it inside ``async with uow:`` alongside the state change is what makes
    the two atomic; calling it outside would produce a durable message for a state change that may
    yet roll back.

    Args:
        outbox: The outbox port.
        tenant: The organisation, from trusted context.
        work_item_id: The durable authority record the trigger points at.
        kind: The trigger kind, from the closed set.
        correlation_id: The journey identifier. Taken from the ambient context when omitted, which
            is what keeps one journey identifiable across the hop.

    Returns:
        The envelope that was written, so the caller can assert on it or log it.
    """
    trace: TraceContext = current_trace_context()
    resolved = correlation_id if correlation_id is not None else CorrelationId(trace.correlation_id)

    envelope = TriggerEnvelope(
        work_item_id=work_item_id,
        correlation_id=resolved,
        kind=kind,
    )

    await outbox.enqueue(tenant, envelope)
    return envelope
