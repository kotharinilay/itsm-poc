"""Workload audience — the execution leg. App-only authorization.

**The Workload never carries customer-tenant authority.** Its target organisation is resolved only
from the work item (contracts/workload-api.md), which is why no route here takes a tenant and why
:meth:`~ragcore.domain.tenancy.TenantContext.from_work_item` names its provenance.

In this release the Workload principal runs inside the RagCore runtime. That is an accepted and
documented risk, not an oversight (platform specification §18.2, §35.2); the Service Bus seam
exists so splitting it into its own runtime is a deployment change rather than a redesign.

The five rules this audience exists to keep, none of them decided in this file:

1. It never carries customer-tenant authority.
2. It executes only work that is approved, active, unclaimed and unexpired.
3. It claims atomically before acting — idempotency boundary 1.
4. It carries an idempotency key to every external system — idempotency boundary 2.
5. A failed execution does **not** re-fire; it requires fresh human authorization.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, status
from pydantic import Field

from ragcore.api.deps import PrincipalDep
from ragcore.api.middleware.problems import (
    UNIVERSAL_PROBLEM_STATUSES,
    ProblemJSONResponse,
    not_implemented,
    problem_responses,
)
from ragcore.api.schemas import ApiModel, ProblemDetails
from ragcore.domain.governance import VerificationOutcome

# EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator publishes
# FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the document
# describes an error body this service never sends — and a client written against it parses the
# wrong shape on the one path it cannot test against a happy case.
#
# 409 and 410 are declared HERE and on no other audience: the claim is a conditional write
# that a second caller loses, and the execution validity window elapses. Declaring them
# everywhere would describe refusals the other surfaces cannot produce.
router = APIRouter(
    prefix="/api/workload/v1",
    tags=["workload"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES, 409, 410),
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
WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]


class OutcomeRequest(ApiModel):
    """The outcome of one execution attempt.

    ``verification`` is **mandatory and has no default**. That is the whole design of this schema:
    a caller must state what the platform actually knows, and the absence of a default means "we
    did not check" cannot be silently recorded as success.

    A ``client_attested`` outcome MUST NOT be reported to a user or written to the system of
    record as confirmed resolution (ADR-0004). It is a claim; the field name says so.
    """

    status: str
    verification: VerificationOutcome
    detail: dict[str, object] = Field(default_factory=dict)


@router.post("/work/{workItemId}/claim", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def claim_work(
    request: Request, work_item_id: WorkItemIdPath, principal: PrincipalDep
) -> ProblemDetails:
    """Atomically claim a work item. 409 if already claimed, expired, or not authorized.

    **Idempotency boundary 1**, and the one that absorbs at-least-once delivery: a conditional
    update on ``claimed_at IS NULL``, so a duplicate trigger produces exactly one execution.
    Boundary 2 — the idempotency key carried to the external system — protects the far side and
    does not substitute for this.
    """
    del work_item_id, principal
    return not_implemented(request)


@router.post("/work/{workItemId}/outcome", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def record_outcome(
    request: Request, work_item_id: WorkItemIdPath, body: OutcomeRequest, principal: PrincipalDep
) -> ProblemDetails:
    """Record the outcome with its verification result."""
    del work_item_id, body, principal
    return not_implemented(request)
