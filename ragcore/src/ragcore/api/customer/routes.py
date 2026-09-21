"""Customer audience — consent, instruction and result. **The routes that stay inert.**

**Every caller here is an ``end_user``, including a Synoptek staff member** (spec FR-SURF-008).
Staff roles are not consulted on this audience and confer nothing, and that is enforced by
:attr:`~ragcore.domain.principal.AuthenticatedPrincipal.authorizable_roles` returning only
``end_user`` for a customer audience — not by any check written in this file.

**Endpoints contain no business policy** (.claude/rules/10-principles.md P-13). Each one below
establishes
context through ``Depends``, hands off, and shapes a response. The decisions live in
:mod:`ragcore.governance.gate` and the application layer.

**What moved out of this module, and why.** Conversation and streaming now live in
:mod:`ragcore.api.customer.sessions`, clarification answers in
:mod:`ragcore.api.customer.answers`, and feedback in :mod:`ragcore.api.customer.feedback` — each
because it acquired real behaviour in Stage 12 and a module of live routes beside inert ones makes
it impossible to tell at a glance which is which.

**What remains here is inert, and deliberately so.** Consent, instruction fetch and result posting
each return 501 rather than a plausible success. Approval and consent workflows are **withdrawn
from the scaffold** (plan §Stage 12 non-goals, `FR-DEMO-016`), and desktop execution is deferred
pending ADR-0004's open items — script signing and the destructive taxonomy. A scaffold that
appears to record a consent is worse than one that says it cannot.
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
from ragcore.domain.work import ConsentVerdict

# EVERY OPERATION DECLARES THE ERROR CONTRACT IT CAN RETURN. Without this the generator publishes
# FastAPI's own `HTTPValidationError` for 422 and nothing at all for the rest, so the document
# describes an error body this service never sends — and a client written against it parses the
# wrong shape on the one path it cannot test against a happy case.
router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
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
WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]


class ConsentRequest(ApiModel):
    """A consent decision — **the only way consent is ever recorded**.

    One field, an enum of two. Deliberately not a boolean: ``consent(True)`` says nothing at a
    call site, and .claude/rules/10-principles.md P-20 prohibits a boolean flag that
    hides behaviour.
    """

    verdict: ConsentVerdict


class ExecutionResultRequest(ApiModel):
    """An execution result posted by the desktop client.

    **A client-reported result is a claim, not proof** (ADR-0004). It becomes a
    ``client_attested`` verification outcome and MUST NOT be reported to a user or written to the
    system of record as confirmed resolution.
    """

    exit_status: int
    detail: str = ""


@router.post("/work/{workItemId}/consent", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def record_consent(
    request: Request, work_item_id: WorkItemIdPath, body: ConsentRequest, principal: PrincipalDep
) -> ProblemDetails:
    """Grant or refuse consent.

    Only the work item's own ``requested_by_oid`` may consent; anyone else receives 403
    (spec FR-INTR-005). That comparison is against the durable record, made in the application
    layer — not here, where the work item has not been loaded.

    Consent does **not** satisfy a ``STAFF_APPROVAL`` requirement (spec FR-INTR-007), which the
    gate enforces by type: it accepts a
    :class:`~ragcore.domain.decisions.StaffVerdict` on that branch and nothing else.
    """
    del work_item_id, body, principal
    return not_implemented(request)


@router.get("/work/{workItemId}/instruction", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def fetch_instruction(
    request: Request, work_item_id: WorkItemIdPath, principal: PrincipalDep
) -> ProblemDetails:
    """Fetch the authorized execution instruction. Desktop only.

    Returns the work identifier, catalogue id, catalogue version, content hash and parameters;
    the client verifies all four before executing and aborts on any mismatch (ADR-0004). Never
    delivered over the realtime channel, and 410 once the validity window has elapsed.

    **In the scaffold the catalogue holds only inert reference fixtures, so no real script is
    ever returned** — and no autonomous ITSM operation is implemented behind this route.
    """
    del work_item_id, principal
    return not_implemented(request)


@router.post("/work/{workItemId}/result", **NOT_IMPLEMENTED_ROUTE)  # type: ignore[arg-type]
async def record_result(
    request: Request,
    work_item_id: WorkItemIdPath,
    body: ExecutionResultRequest,
    principal: PrincipalDep,
) -> ProblemDetails:
    """Post an execution result and exit status. Desktop only."""
    del work_item_id, body, principal
    return not_implemented(request)
