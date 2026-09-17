"""Staff audience — approval verdict, take-over, cancellation.

**The target organisation is always derived from the platform object being operated on, never
supplied by the caller** (contracts/staff-api.md). A staff token's ``tid`` is the Operator tenant
and is never the customer target, which is why no route here takes a tenant and why
:meth:`~ragcore.domain.tenancy.TenantContext.from_platform_object` exists as a separate
constructor with its provenance in its name.

**Roles are independent capabilities with no hierarchy** (spec FR-AUTHZ-003). Authorization is set
intersection, and ``administrator`` does not imply ``technician``. Any implementation that sorts,
ranks or compares roles is a defect — so nothing here does, and the evaluation lives in
:func:`ragcore.domain.roles.evaluate`, which has no ordering to consult.

**Absent by design**: there is no endpoint on this audience to start a chat session or raise a
request. Staff needing their own support use a customer surface, as an end user.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, status

from ragcore.api.deps import PrincipalDep
from ragcore.api.middleware.problems import (
    UNIVERSAL_PROBLEM_STATUSES,
    ProblemJSONResponse,
    not_implemented,
    problem_responses,
)
from ragcore.api.schemas import ApiModel, ProblemDetails
from ragcore.domain.work import ApprovalVerdict

# EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator publishes
# FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the document
# describes an error body this service never sends — and a client written against it parses the
# wrong shape on the one path it cannot test against a happy case.
router = APIRouter(
    prefix="/api/staff/v1",
    tags=["staff"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

# The signature every wired-but-inert route carries: the response IS a problem, so it is declared
# as one, at the media type RFC 9457 requires rather than plain `application/json`.
NOT_IMPLEMENTED_ROUTE = {
    "status_code": status.HTTP_501_NOT_IMPLEMENTED,
    "response_model": ProblemDetails,
    "response_class": ProblemJSONResponse,
    "responses": problem_responses(501),
}


# Path parameters are declared with camelCase aliases so the generated OpenAPI document matches
# contracts/ exactly. The wire contract is frozen and shared with the .NET side; a Python-side
# snake_case placeholder would make the two documents disagree over a purely cosmetic difference.
ApprovalIdPath = Annotated[
    UUID, Path(alias="approvalId", description="The approval being decided.")
]
SessionIdPath = Annotated[
    UUID, Path(alias="sessionId", description="The session being operated on.")
]
WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]


class VerdictRequest(ApiModel):
    """A staff decision on one approval.

    ``verdict`` is :class:`~ragcore.domain.work.ApprovalVerdict` — **two members**. There is no
    ``expired`` to send, so a system-synthesized verdict is unrepresentable on this contract
    rather than merely prohibited by it (spec FR-INTR-008).

    Deliberately absent: ``decidedBy``, ``roles``, ``tenantId``, ``expiresAt``. The approver is
    the authenticated caller, the roles are the ones they hold at this moment, the organisation
    comes from the approval's own work item, and the window is computed server-side as
    ``decided_at`` plus fifteen minutes. Every one of those is authority, and none of them is a
    thing a request may assert.
    """

    verdict: ApprovalVerdict
    note: str = ""


class StaffMessageRequest(ApiModel):
    """A message sent into a taken-over session."""

    content: str


@router.post("/approvals/{approvalId}/verdict", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def record_verdict(
    request: Request, approval_id: ApprovalIdPath, body: VerdictRequest, principal: PrincipalDep
) -> ProblemDetails:
    """Approve or reject. Accepts ``technician``.

    Three properties this route commits to, all enforced below it rather than here:

    * **First valid verdict wins.** A later one is recorded but does not change the outcome
      (spec FR-INTR-010), which the repository's conditional write decides — two staff opening
      the same queue item is a race, not an error.
    * **Approval never executes.** On approval the window is set and a trigger is published, and
      **the request returns before execution runs**. A response reporting success would be
      reporting something that has not happened.
    * **No approval by timeout.** Nothing anywhere produces a verdict except this route.
    """
    del approval_id, body, principal
    return not_implemented(request)


@router.post("/sessions/{sessionId}/takeover", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def take_over_session(
    request: Request, session_id: SessionIdPath, principal: PrincipalDep
) -> ProblemDetails:
    """Transition a session to staff-controlled. Accepts ``technician``.

    An authenticated state transition, not a socket message, and a **single** transition: where
    two staff attempt it concurrently one wins and the other is told (spec FR-INTR-013).

    It does **not** transfer requester authority. Consent for that user's own account or device
    still belongs to the original end user, so a taken-over session does not become a route by
    which staff consent on somebody's behalf.
    """
    del session_id, principal
    return not_implemented(request)


@router.post("/sessions/{sessionId}/messages", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def send_staff_message(
    request: Request, session_id: SessionIdPath, body: StaffMessageRequest, principal: PrincipalDep
) -> ProblemDetails:
    """Send a message into a taken-over session. Accepts ``technician``."""
    del session_id, body, principal
    return not_implemented(request)


@router.post("/work/{workItemId}/cancel", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def cancel_work(
    request: Request, work_item_id: WorkItemIdPath, principal: PrincipalDep
) -> ProblemDetails:
    """Cancel before execution is claimed. Accepts ``technician``.

    Permitted before the claim. After the claim, execution completes and the outcome is recorded
    normally (spec FR-EXEC-009) — a half-cancelled side effect is worse than a completed one that
    is honestly reported.
    """
    del work_item_id, principal
    return not_implemented(request)
