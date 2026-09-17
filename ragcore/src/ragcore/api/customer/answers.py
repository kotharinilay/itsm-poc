"""``POST /api/customer/v1/sessions/{sessionId}/answers`` — answering a clarifying question.

`FR-INTR-004`: **only the end user of the session may answer.** Who that is comes from trusted
identity, so it is not a field on the request — there is nothing here a client could send to answer
on somebody else's behalf, which is a stronger statement than a check that compares two values the
client supplied.

**An answer resumes a run; it does not decide anything.** The graph node it resumes
(:mod:`ragcore.graph.nodes.clarification_interrupt`) writes the answer into the conversation
channel and routes back to retrieval. Nothing downstream reads it to authorize: **chat text cannot
grant authority** (`FR-IDENT-004`), and an affirmative answer here is not consent — only
``POST /work/{id}/consent`` records that.

That is why this endpoint exists separately from the consent endpoint rather than as a mode of it.
Two endpoints with two names make "I said yes in the chat" and "I granted consent" two different
events in the audit trail, which is exactly what they are.

**A session that is not the caller's own returns 404.** Existence is tenant-scoped information, and
a 403 would confirm that the session exists.

**Answering twice is not an error the second time.** The interrupt is consumed when the run
resumes; a second answer arrives at a run that is no longer suspended and is reported as 404 for
the same reason — there is no pending question to answer, and inventing a conflict status for it
would give clients a third branch for a state that is simply gone.
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
from ragcore.graph.nodes.clarification_interrupt import MAX_ANSWER_CHARACTERS

router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

SessionIdPath = Annotated[UUID, Path(alias="sessionId", description="The chat session.")]


class AnswerRequest(ApiModel):
    """An answer to a pending clarifying question.

    One field. Note the three that are absent and will not be added: no ``sessionOwner``, because
    the answerer comes from trusted identity; no ``confirm``, because an affirmative answer is not
    consent; and no ``workItemId``, because an answer does not target a decision.

    ``content`` is bounded at :data:`~ragcore.graph.nodes.clarification_interrupt.
    MAX_ANSWER_CHARACTERS`. The answer becomes part of the next prompt, and an unbounded answer is
    an unbounded model call metered against the organisation.
    """

    content: Annotated[str, ...] = ""

    def bounded(self) -> str:
        """The answer, truncated to the platform ceiling.

        Truncation rather than rejection: a long answer is somebody being thorough, and refusing it
        would lose what they wrote. The ceiling itself lives with the node that consumes it, so
        there is one figure rather than an API-side copy that drifts.
        """
        return self.content[:MAX_ANSWER_CHARACTERS]


@router.post(
    "/sessions/{sessionId}/answers",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    response_model=ProblemDetails,
    response_class=ProblemJSONResponse,
    responses=problem_responses(501),
)
async def answer_clarification(
    request: Request,
    session_id: SessionIdPath,
    body: AnswerRequest,
    principal: PrincipalDep,
    tenant: TenantDep,
    container: ContainerDep,
    correlation_id: CorrelationDep,
) -> ProblemDetails:
    """Answer a pending clarifying question.

    **Returns 501 until the run loop is hosted.** The interrupt node, its payload contract and the
    bounded answer are implemented and unit-tested; what is missing is the process that holds a
    compiled graph and resumes it, which is the run host — not this endpoint. Wiring a resume here
    against a graph nobody compiled would be a route that appears to work and silently drops the
    answer, which is worse than one that says it is not there.

    What this signature already fixes, and what a later wiring cannot therefore get wrong: the
    answerer comes from ``principal`` and the organisation from ``tenant``, both derived from
    trusted identity; neither is a parameter a client can supply.
    """
    del session_id, body, principal, tenant, container, correlation_id
    return not_implemented(request)
