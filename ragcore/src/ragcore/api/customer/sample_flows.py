"""The sample flow's API surface — **inert, and never a product capability**.

Three endpoints, each proving one seam and nothing more:

``POST /sample-flows/round-trip``
    Opens a durable record **and** writes its outbox row in one transaction, then returns the
    correlation identifier. This is the whole point of the outbox: the state change and the message
    announcing it are durable together or not at all.

``GET  /sample-flows/round-trip/{id}``
    Reads back the outcome. This is what makes the realtime notification a **leaf** rather than a
    link — a client that never connects, or misses the push entirely, reaches the same answer here.

``POST /sample-flows/service-hop``
    Demonstrates Customer API → Workload API **through the gateway**, app-only, and reports what the
    callee saw about the caller. There is no private peer route (spec §13.4).

**Nothing here implements, stands in for, or may be counted as any of UC-01 through UC-12**
(spec FR-DEMO-014, FR-DEMO-015). No approval, no consent, no external effect, no model, no index.

**No endpoint accepts a tenant, role or audience parameter.** The organisation is derived from the
trusted identity the gateway established, and there is nothing a caller could send to influence it.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status

from ragcore.api.deps import ContainerDep, CorrelationDep, PrincipalDep, TenantDep
from ragcore.api.schemas import ApiModel

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])

WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]


class SampleFlowAccepted(ApiModel):
    """What the round-trip endpoint returns.

    Carries the identifiers a caller needs to follow its own request and **nothing else** — no
    tenant, no role, no approval state. The correlation identifier is the one a user would quote in
    a support request.
    """

    work_item_id: UUID
    correlation_id: str
    operation: str


class SampleFlowState(ApiModel):
    """The readable outcome of a sample flow.

    **This is the recovery path for a missed notification.** Whatever the realtime channel did or
    did not deliver, the answer is here, read under the caller's own identity.
    """

    work_item_id: UUID
    status: str
    effect: str


class ServiceHopResult(ApiModel):
    """What the workload leg reported about its caller.

    Deliberately descriptive rather than authoritative: it says which audience and credential class
    the callee observed, which is the thing being demonstrated. It confers nothing.
    """

    reached_audience: str
    credential_class: str
    via_gateway: bool
    correlation_id: str


@router.post(
    "/sample-flows/round-trip",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def begin_round_trip(
    container: ContainerDep,
    tenant: TenantDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
) -> dict[str, str]:
    """Open the durable record and enqueue its trigger **in one transaction**.

    The two writes share a unit of work, which is the property this endpoint exists to prove: a
    crash between them cannot leave a state change nobody was told about, nor a message for a state
    change that rolled back.

    **Returns 501 until the work-item write lands.** The messaging machinery beneath it —
    :func:`~ragcore.messaging.outbox.enqueue_trigger`, the dispatcher, the consumer — is implemented
    and tested at Stage 8; the durable record this trigger points at is opened by the session and
    work-item write that belongs with the customer surface. Wiring this to create work items now
    would be inventing product behaviour the scaffold is specifically not allowed to have.
    """
    del container, tenant, principal, correlation_id
    return {
        "detail": (
            "The Stage 8 messaging seam is implemented and tested; this endpoint is wired when the "
            "customer surface opens durable work. See specs/001-platform-scaffold/tasks.md T241."
        )
    }


@router.get(
    "/sample-flows/round-trip/{workItemId}",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def read_round_trip(
    work_item_id: WorkItemIdPath,
    tenant: TenantDep,
) -> dict[str, str]:
    """Read the outcome back — **the recovery path for a missed notification**.

    A client that never connected to the realtime channel, or that missed the push, reaches the
    same answer here. That is what keeps the notification a leaf rather than a link.
    """
    del work_item_id, tenant
    return {
        "detail": (
            "Returns the outcome the workload leg persisted, once the durable record is opened. "
            "See specs/001-platform-scaffold/tasks.md T242."
        )
    }


@router.post(
    "/sample-flows/service-hop",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def service_hop(
    tenant: TenantDep,
    correlation_id: CorrelationDep,
) -> dict[str, str]:
    """Reach the workload audience **through the gateway**, and report what it saw.

    **There is no private peer route, and this endpoint must never acquire one.** The call leaves
    through the approved egress path, re-enters at Front Door, is re-authenticated at APIM as an
    app-only principal, and arrives at the workload audience with a fresh identity contract (spec
    §13.4). A direct in-cluster call would be faster and would prove nothing — the identity would be
    whatever this process chose to send.

    Requires the deployed edge, which is why it reports rather than executes here: driving it
    against a locally hosted process would demonstrate the opposite of the property.
    """
    del tenant, correlation_id
    return {
        "detail": (
            "Routes Customer -> Workload through Front Door and APIM; the callee reports the "
            "audience and credential class it observed. Requires the deployed edge. See "
            "specs/001-platform-scaffold/tasks.md T246 and T247."
        )
    }
