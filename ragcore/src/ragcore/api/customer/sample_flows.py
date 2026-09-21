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

**Nothing here implements, stands in for, or may be counted as a real defined capability**
(`.claude/rules/10-principles.md` H-2). No approval, no consent, no external effect, no model, no
index.

**No endpoint accepts a tenant, role or audience parameter.** The organisation is derived from the
trusted identity the gateway established, and there is nothing a caller could send to influence it.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, status

from ragcore.api.deps import ContainerDep, CorrelationDep, PrincipalDep, TenantDep
from ragcore.api.middleware.problems import (
    UNIVERSAL_PROBLEM_STATUSES,
    ProblemJSONResponse,
    not_implemented,
    problem_responses,
)
from ragcore.api.schemas import ApiModel, ProblemDetails

# EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator publishes
# FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the document
# describes an error body this service never sends.
router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

# The signature every wired-but-inert route carries: the response IS a problem, so it is
# declared as one, at the media type RFC 9457 requires rather than plain `application/json`.
NOT_IMPLEMENTED_ROUTE = {
    "status_code": status.HTTP_501_NOT_IMPLEMENTED,
    "response_model": ProblemDetails,
    "response_class": ProblemJSONResponse,
    "responses": problem_responses(501),
}

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


@router.post("/sample-flows/round-trip", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def begin_round_trip(
    request: Request,
    container: ContainerDep,
    tenant: TenantDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
) -> ProblemDetails:
    """Open the durable record and enqueue its trigger **in one transaction**.

    The two writes share a unit of work, which is the property this endpoint exists to prove: a
    crash between them cannot leave a state change nobody was told about, nor a message for a state
    change that rolled back.

    **Returns 501 until the work-item write lands.** The messaging machinery beneath it —
    :func:`~ragcore.messaging.outbox.enqueue_trigger`, the dispatcher, the consumer — is implemented
    and tested at Stage 8; the durable record this trigger points at is opened by the session and
    work-item write that belongs with the customer surface. Wiring this to create work items now
    would be inventing product behaviour no requirement asks for (P-8) and reporting it as real
    (H-1). The refusal is explicit for that reason. The eventual response is
    :class:`SampleFlowAccepted`.
    """
    del container, tenant, principal, correlation_id
    return not_implemented(request)


@router.get("/sample-flows/round-trip/{workItemId}", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def read_round_trip(
    request: Request,
    work_item_id: WorkItemIdPath,
    tenant: TenantDep,
) -> ProblemDetails:
    """Read the outcome back — **the recovery path for a missed notification**.

    A client that never connected to the realtime channel, or that missed the push, reaches the
    same answer here. That is what keeps the notification a leaf rather than a link.

    Wired by T242, which also declares the eventual response as :class:`SampleFlowState`.
    """
    del work_item_id, tenant
    return not_implemented(request)


@router.post("/sample-flows/service-hop", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def service_hop(
    request: Request,
    tenant: TenantDep,
    correlation_id: CorrelationDep,
) -> ProblemDetails:
    """Reach the workload audience **through the gateway**, and report what it saw.

    **There is no private peer route, and this endpoint must never acquire one.** The call leaves
    through the approved egress path, re-enters at Front Door, is re-authenticated at APIM as an
    app-only principal, and arrives at the workload audience with a fresh identity contract (spec
    §13.4). A direct in-cluster call would be faster and would prove nothing — the identity would be
    whatever this process chose to send.

    Requires the deployed edge, which is why it reports rather than executes here: driving it
    against a locally hosted process would demonstrate the opposite of the property.

    Wired by T246 and T247, which also declare the eventual response as :class:`ServiceHopResult`.
    """
    del tenant, correlation_id
    return not_implemented(request)
