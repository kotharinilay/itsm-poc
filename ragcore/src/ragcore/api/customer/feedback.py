"""Message feedback — an idempotent, owner-scoped, **decision-free** quality signal.

Three requirements, and each one shows up in this file as a shape rather than as a check somebody
remembered:

* `FR-SESS-009`, `FR-SESS-010`: feedback is **revisable**. ``PUT`` replaces; it does not append.
  The unique constraint on ``(message_id, given_by_oid)`` is where that is true, and the repository
  writes through it with ``ON CONFLICT DO UPDATE`` — so two tabs revising one signal produce one
  signal rather than one error and one lost revision.
* `FR-SESS-011`: **owner-scoped**. Only the session's own user may record, and only against an
  agent-authored message in their own session. Ownership is resolved from the durable record in the
  same transaction as the write, never from the route — a message identifier carries no ownership,
  and a path parameter is client input.
* `FR-SESS-013`: feedback reaches **no authorization, no governance treatment, no retrieval scope
  and no execution path**. Nothing in this module returns a signal to the platform's own code, and
  :class:`~ragcore.application.ports.FeedbackRepositoryPort` has no reader for one to come back
  through. ``tests/governance/test_feedback_no_influence.py`` asserts it.

**A message that is not the caller's returns 404, not 403** (contracts/customer-api.md). Existence
is itself tenant-scoped information: a 403 would confirm that the message exists and belongs to
somebody, which is precisely what a caller probing identifiers is trying to learn.

**Withdrawal is idempotent.** Withdrawing a signal that is already withdrawn is a success, because
the caller's intent — "there should be no signal from me on this message" — holds either way, and
a 404 would send a client into a retry loop over a state it has already reached.

**No content is written.** A signal is one of two enum values. There is no free-text comment field
here, and its absence is deliberate: a comment box on an agent message is an unmoderated content
surface attached to a record with organisation-wide read access.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, Response, status

from ragcore.api.deps import ContainerDep, CorrelationDep, PrincipalDep, TenantDep
from ragcore.api.middleware.problems import (
    PROBLEM_BASE,
    UNIVERSAL_PROBLEM_STATUSES,
    ProblemJSONResponse,
    problem_responses,
)
from ragcore.api.schemas import ApiModel, ProblemDetails
from ragcore.application.ports import FeedbackRepositoryPort
from ragcore.config.composition import Container
from ragcore.domain.identifiers import MessageId
from ragcore.domain.work import FeedbackSignal

router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

MessageIdPath = Annotated[UUID, Path(alias="messageId", description="An agent-authored message.")]


class FeedbackRequest(ApiModel):
    """A quality signal against one agent-authored message.

    One field, an enum of two. Deliberately not a boolean — ``feedback(True)`` says nothing at a
    call site — and deliberately without a comment field; see the module docstring.

    **Feedback never influences authorization, governance treatment, retrieval scope or
    execution** (spec FR-SESS-013). It is read by reporting and by nothing else.
    """

    signal: FeedbackSignal


NOT_FOUND = problem_responses(404)


@router.put(
    "/messages/{messageId}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, 204: {"description": "The signal was recorded or replaced."}},
)
async def record_feedback(
    request: Request,
    message_id: MessageIdPath,
    body: FeedbackRequest,
    principal: PrincipalDep,
    tenant: TenantDep,
    container: ContainerDep,
    correlation_id: CorrelationDep,
) -> Response:
    """Record or revise a thumbs signal.

    ``PUT`` because feedback is revisable: repeating it replaces the previous signal rather than
    creating a second.

    Returns:
        204 on success — there is no body, because there is nothing to return that the client did
        not just send, and an echoed signal is a second source of truth for a value the client
        already holds.

    Raises:
        HTTPException: Never raised here. A message that is not an agent-authored message in the
            caller's own session is reported as **404** through the problem contract, because
            existence is tenant-scoped information.
    """
    repository = _repository(container)

    async with container.unit_of_work():
        recorded = await repository.record(
            tenant,
            MessageId(message_id),
            # From trusted identity, never from the body. There is no `givenBy` field on
            # FeedbackRequest, so there is nothing for a client to record feedback *as*.
            principal.identity.principal_id,
            body.signal,
        )

    if not recorded:
        return _not_found(request, correlation_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/messages/{messageId}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, 204: {"description": "No signal from this caller remains."}},
)
async def withdraw_feedback(
    request: Request,
    message_id: MessageIdPath,
    principal: PrincipalDep,
    tenant: TenantDep,
    container: ContainerDep,
    correlation_id: CorrelationDep,
) -> Response:
    """Withdraw a previously recorded signal.

    Idempotent: withdrawing when nothing is recorded succeeds, because the caller's intent holds
    either way and a 404 would send a client into a retry loop over a state it has reached.

    Returns:
        204 when no signal from this caller remains on the message. 404 when the message is not
        theirs.
    """
    repository = _repository(container)

    async with container.unit_of_work():
        owned = await repository.withdraw(
            tenant, MessageId(message_id), principal.identity.principal_id
        )

    if not owned:
        return _not_found(request, correlation_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _not_found(request: Request, correlation_id: object) -> ProblemJSONResponse:
    """404 for a message that is not the caller's own agent-authored message.

    **Not 403.** A 403 would confirm the message exists, which is the fact a caller enumerating
    identifiers is trying to establish.
    """
    return ProblemJSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ProblemDetails(
            type=f"{PROBLEM_BASE}/not-found",
            title="Not found",
            status=404,
            detail="No such message, or it is not one you may record feedback against.",
            instance=request.url.path,
            correlation_id=str(correlation_id),
        ).model_dump(by_alias=True),
    )


def _repository(container: Container) -> FeedbackRepositoryPort:
    """The feedback repository, or a loud failure.

    Raises:
        RuntimeError: When the container was built without persistence. Surfaced by the catch-all
            handler as a 500, which is the honest status: the caller did nothing wrong and their
            signal was never storable. A 404 here would tell them their message does not exist,
            which is a different and untrue statement.
    """
    repository = container.feedback
    if repository is None:  # pragma: no cover — a container built without persistence
        raise RuntimeError(
            "no feedback repository is bound; this process cannot record a quality signal."
        )
    return repository
