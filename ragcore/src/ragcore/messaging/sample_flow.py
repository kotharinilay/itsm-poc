"""The inert sample flow — **platform plumbing, proven; product behaviour, absent**.

One journey, crossing every seam the scaffold exists to demonstrate:

.. code-block:: text

    Customer API
      -> state change + outbox row   (one PostgreSQL transaction)
        -> dispatcher -> Service Bus  (at-least-once)
          -> resume consumer          (load, verify, claim, execute, record)
            -> PostgreSQL result
              -> SignalR notification (a leaf; the client may ignore it)

**Nothing here is a product capability, and nothing here may become one.** The execution is a
reference fixture: it reaches no external system, modifies no account, device or record, and calls
no model, index or cache. It MUST NOT implement, stand in for, or be counted as any of UC-01 through
UC-12 (spec FR-DEMO-014, FR-DEMO-015, FR-SCOPE-007).

**It is not an approval, and it grants nothing.** The ``sample.flow`` kind exists because the seam
needs exercising before a governed operation crosses it. No human decided anything, so there is no
authority to carry — which is also why it is safe to run it in a scaffold where the approval and
consent handlers are deliberately unbuilt (spec FR-DEMO-016).

**What it actually proves.** That a state change and its message are durable together; that a
duplicate delivery produces exactly one effect; that authority is read from PostgreSQL and never
from the message; that one correlation identifier survives the asynchronous hop; and that the
outcome is identical whether or not a client is listening.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from ragcore.application.ports import (
    IdempotencyStorePort,
    NotificationPort,
    OutboxPort,
    WorkItemRepositoryPort,
)
from ragcore.domain.envelopes import (
    NotificationEnvelope,
    NotificationKind,
    TriggerEnvelope,
    TriggerKind,
)
from ragcore.domain.identifiers import OperationId, PrincipalId, WorkItemId
from ragcore.domain.tenancy import TenantContext
from ragcore.execution.claim import claim_for_execution
from ragcore.execution.idempotency import begin_effect, complete_effect, derive_key
from ragcore.messaging.outbox import enqueue_trigger

SAMPLE_OPERATION_ID: Final = "sample.round-trip"
"""The inert reference operation this flow acts on.

A constant rather than a catalogue lookup at this stage, and named so that it is obviously not an
ITSM capability. ``tests/e2e/test_sample_flows_are_inert.py`` is what keeps it that way.
"""

WORKLOAD_PRINCIPAL: Final = "workload"
"""Who claims the work. A machine identity, never a human one."""


@dataclass(frozen=True, slots=True)
class SampleFlowResult:
    """What one consumption of a sample-flow trigger did.

    ``executed`` and ``replayed`` are both carried because the interesting cases are the ones where
    they differ: a duplicate delivery that lost the claim did neither, and a retry after a partial
    failure replayed without executing.
    """

    work_item_id: str
    executed: bool
    replayed: bool
    claim_won: bool

    @property
    def had_effect(self) -> bool:
        """Whether this consumption produced the (inert) effect. Exactly one delivery may."""
        return self.executed and not self.replayed


async def begin_sample_flow(
    outbox: OutboxPort,
    tenant: TenantContext,
    work_item_id: WorkItemId,
) -> TriggerEnvelope:
    """The API half: enqueue the trigger **inside the caller's transaction**.

    The caller has already made its state change in the same unit of work. That co-location is the
    property being demonstrated — call this outside the transaction and the demonstration is of
    something else.

    Args:
        outbox: The outbox port.
        tenant: The organisation, from trusted context.
        work_item_id: The durable record the trigger points at.

    Returns:
        The envelope written.
    """
    return await enqueue_trigger(outbox, tenant, work_item_id, TriggerKind.SAMPLE_FLOW)


async def execute_sample_flow(
    *,
    work_items: WorkItemRepositoryPort,
    idempotency: IdempotencyStorePort,
    notifications: NotificationPort | None,
    tenant: TenantContext,
    work_item_id: WorkItemId,
    operation_id: OperationId,
    requester: PrincipalId,
    correlation_id: str,
    now: datetime,
) -> SampleFlowResult:
    """The consumer half: claim, act inertly, record, notify.

    The order is the contract (``contracts/triggers.md`` §Consumer obligations), and each step is
    here because skipping it breaks a property the flow exists to prove:

    1. **Claim atomically.** Losing means a duplicate arrived and another consumer has it. Stop —
       this is the routine case, not an error.
    2. **Check the idempotency key.** Protects the external system in the case the claim cannot:
       an earlier attempt that acted and then died before recording.
    3. **Act.** Inertly. There is no external call here and there may never be one.
    4. **Record the outcome**, so a repeat replays rather than acts again.
    5. **Notify.** Last, and failure-tolerant — the notification is a leaf.

    **Tenant and authority come from the caller's resolution of the durable record**, never from the
    message. The message carried three fields and none of them was a tenant.

    Args:
        work_items: The work item repository.
        idempotency: The idempotency store.
        notifications: The realtime channel, or ``None`` when unconfigured — in which case the flow
            reaches an identical outcome, which is the property being demonstrated.
        tenant: The organisation, loaded from PostgreSQL.
        work_item_id: The work to execute.
        operation_id: The operation within it.
        requester: Who to notify. From the durable record, never from the message.
        correlation_id: The journey identifier, restored from the message's trace context.
        now: From the clock port.

    Returns:
        What this consumption did.
    """
    claim = await claim_for_execution(
        work_items, tenant, work_item_id, claimed_by=WORKLOAD_PRINCIPAL, now=now
    )

    if claim.should_stop:
        # A duplicate delivery whose twin is already executing. Absorbed, and not an error:
        # at-least-once means this is expected traffic.
        return SampleFlowResult(
            work_item_id=str(work_item_id), executed=False, replayed=False, claim_won=False
        )

    key = derive_key(tenant, work_item_id, operation_id)
    decision = await begin_effect(idempotency, tenant, key)

    if not decision.should_execute:
        return SampleFlowResult(
            work_item_id=str(work_item_id), executed=False, replayed=True, claim_won=True
        )

    outcome: dict[str, Any] = _perform_inert_operation(work_item_id, correlation_id)
    await complete_effect(idempotency, tenant, key, operation_id, outcome)

    if notifications is not None:
        await notifications.notify_user(
            requester,
            NotificationEnvelope(
                kind=NotificationKind.WORK_COMPLETED,
                occurred_at=now,
                correlation_id=correlation_id,  # type: ignore[arg-type]
                work_item_id=work_item_id,
            ),
        )

    return SampleFlowResult(
        work_item_id=str(work_item_id), executed=True, replayed=False, claim_won=True
    )


def _perform_inert_operation(work_item_id: WorkItemId, correlation_id: str) -> dict[str, Any]:
    """The 'execution'. It does nothing, and that is the specification.

    **No external system, no model, no retrieval index, no cache, no device, no account.** It
    returns a record that the seam was traversed, which is the only thing the scaffold is entitled
    to demonstrate at this stage.

    If this function ever acquires a dependency, the sample flow has stopped being a sample flow —
    and ``tests/e2e/test_sample_flows_are_inert.py`` is what will say so.
    """
    return {
        "operation": SAMPLE_OPERATION_ID,
        "workItemId": str(work_item_id),
        "correlationId": correlation_id,
        "effect": "none",
    }
