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

from fastapi import APIRouter, Path, status
from pydantic import Field

from ragcore.api.deps import PrincipalDep
from ragcore.api.schemas import ApiModel
from ragcore.domain.governance import VerificationOutcome

router = APIRouter(prefix="/api/workload/v1", tags=["workload"])

# Path parameters are declared with camelCase aliases so the generated OpenAPI document matches
# contracts/ exactly. The wire contract is frozen and shared with the .NET side; a Python-side
# snake_case placeholder would make the two documents disagree over a purely cosmetic difference.
WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]

NOT_IMPLEMENTED = "No product behaviour exists at this stage. The boundary is wired; nothing runs."


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


@router.post("/work/{workItemId}/claim", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def claim_work(work_item_id: WorkItemIdPath, principal: PrincipalDep) -> dict[str, str]:
    """Atomically claim a work item. 409 if already claimed, expired, or not authorized.

    **Idempotency boundary 1**, and the one that absorbs at-least-once delivery: a conditional
    update on ``claimed_at IS NULL``, so a duplicate trigger produces exactly one execution.
    Boundary 2 — the idempotency key carried to the external system — protects the far side and
    does not substitute for this.
    """
    del work_item_id, principal
    return {"detail": NOT_IMPLEMENTED}


@router.post("/work/{workItemId}/outcome", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def record_outcome(
    work_item_id: WorkItemIdPath, body: OutcomeRequest, principal: PrincipalDep
) -> dict[str, str]:
    """Record the outcome with its verification result."""
    del work_item_id, body, principal
    return {"detail": NOT_IMPLEMENTED}
