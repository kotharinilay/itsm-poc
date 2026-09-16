"""Customer audience — conversation, streaming, consent, instruction, result, feedback.

**Every caller here is an ``end_user``, including a Synoptek staff member** (spec FR-SURF-008).
Staff roles are not consulted on this audience and confer nothing, and that is enforced by
:attr:`~ragcore.domain.principal.AuthenticatedPrincipal.authorizable_roles` returning only
``end_user`` for a customer audience — not by any check written in this file.

**Endpoints contain no business policy** (constitution §FastAPI). Each one below establishes
context through ``Depends``, hands off, and shapes a response. The decisions live in
:mod:`ragcore.governance.gate` and the application layer.

Stage 6 wires the surface; the handlers have no product behaviour. Every route that would record
something returns 501 rather than a plausible success, because a scaffold that appears to record
a consent is worse than one that says it cannot.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Path, status
from fastapi.responses import StreamingResponse

from ragcore.api.customer import streaming
from ragcore.api.deps import CorrelationDep, PrincipalDep
from ragcore.api.schemas import ApiModel
from ragcore.domain.work import ConsentVerdict

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])

# Path parameters are declared with camelCase aliases so the generated OpenAPI document matches
# contracts/ exactly. The wire contract is frozen and shared with the .NET side; a Python-side
# snake_case placeholder would make the two documents disagree over a purely cosmetic difference.
SessionIdPath = Annotated[UUID, Path(alias="sessionId", description="The chat session.")]
WorkItemIdPath = Annotated[UUID, Path(alias="workItemId", description="The durable work record.")]
MessageIdPath = Annotated[UUID, Path(alias="messageId", description="An agent-authored message.")]

NOT_IMPLEMENTED = "No product behaviour exists at this stage. The boundary is wired; nothing runs."


class StartSessionResponse(ApiModel):
    """The identifier of a newly started session."""

    session_id: UUID


class SendMessageRequest(ApiModel):
    """One turn of conversation.

    **Chat text cannot grant authority.** An affirmative message is never consent — only
    ``POST /work/{id}/consent`` records that — so there is no ``confirm`` field here for a client
    to set, and nothing downstream reads ``content`` to decide anything.
    """

    content: str


class AnswerRequest(ApiModel):
    """An answer to a pending clarifying question.

    Answerable only by the end user of the session (spec FR-INTR-004). Who that is comes from
    trusted identity, so it is not a field here.
    """

    content: str


class ConsentRequest(ApiModel):
    """A consent decision — **the only way consent is ever recorded**.

    One field, an enum of two. Deliberately not a boolean: ``consent(True)`` says nothing at a
    call site, and the constitution prohibits a boolean flag that hides behaviour.
    """

    verdict: ConsentVerdict


class FeedbackSignal(Enum):
    """A thumbs signal."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class FeedbackRequest(ApiModel):
    """A quality signal against one agent-authored message.

    **Feedback never influences authorization, governance treatment, retrieval scope or
    execution** (spec FR-SESS-013). It is read by reporting and by nothing else.
    """

    signal: FeedbackSignal


class ExecutionResultRequest(ApiModel):
    """An execution result posted by the desktop client.

    **A client-reported result is a claim, not proof** (ADR-0004). It becomes a
    ``client_attested`` verification outcome and MUST NOT be reported to a user or written to the
    system of record as confirmed resolution.
    """

    exit_status: int
    detail: str = ""


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def start_session(principal: PrincipalDep) -> StartSessionResponse:
    """Start a chat session.

    A session is started here; a **work record is not**. One is committed only once the user has
    articulated a genuine request (spec FR-SESS-003), which is a later transition — creating one
    per session would put an authority record behind every "hello".
    """
    del principal
    return StartSessionResponse(session_id=uuid4())


@router.post("/sessions/{sessionId}/messages")
async def send_message(
    session_id: SessionIdPath, principal: PrincipalDep, correlation_id: CorrelationDep
) -> StreamingResponse:
    """Send a message. **Streams the response** as ``text/event-stream``.

    The stream carries no authority. See :mod:`ragcore.api.customer.streaming`.
    """
    del principal
    return StreamingResponse(
        streaming.empty_stream(str(session_id)),
        media_type=streaming.SSE_MEDIA_TYPE,
        headers={**streaming.SSE_HEADERS, "X-Correlation-Id": str(correlation_id)},
    )


@router.post("/sessions/{sessionId}/answers", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def answer_clarification(
    session_id: SessionIdPath, body: AnswerRequest, principal: PrincipalDep
) -> dict[str, str]:
    """Answer a pending clarifying question."""
    del session_id, body, principal
    return {"detail": NOT_IMPLEMENTED}


@router.post("/work/{workItemId}/consent", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def record_consent(
    work_item_id: WorkItemIdPath, body: ConsentRequest, principal: PrincipalDep
) -> dict[str, str]:
    """Grant or refuse consent.

    Only the work item's own ``requested_by_oid`` may consent; anyone else receives 403
    (spec FR-INTR-005). That comparison is against the durable record, made in the application
    layer — not here, where the work item has not been loaded.

    Consent does **not** satisfy a ``STAFF_APPROVAL`` requirement (spec FR-INTR-007), which the
    gate enforces by type: it accepts a
    :class:`~ragcore.domain.decisions.StaffVerdict` on that branch and nothing else.
    """
    del work_item_id, body, principal
    return {"detail": NOT_IMPLEMENTED}


@router.get("/work/{workItemId}/instruction", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def fetch_instruction(
    work_item_id: WorkItemIdPath, principal: PrincipalDep
) -> dict[str, str]:
    """Fetch the authorized execution instruction. Desktop only.

    Returns the work identifier, catalogue id, catalogue version, content hash and parameters;
    the client verifies all four before executing and aborts on any mismatch (ADR-0004). Never
    delivered over the realtime channel, and 410 once the validity window has elapsed.

    **In the scaffold the catalogue holds only inert reference fixtures, so no real script is
    ever returned** — and no autonomous ITSM operation is implemented behind this route.
    """
    del work_item_id, principal
    return {"detail": NOT_IMPLEMENTED}


@router.post("/work/{workItemId}/result", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def record_result(
    work_item_id: WorkItemIdPath, body: ExecutionResultRequest, principal: PrincipalDep
) -> dict[str, str]:
    """Post an execution result and exit status. Desktop only."""
    del work_item_id, body, principal
    return {"detail": NOT_IMPLEMENTED}


@router.put("/messages/{messageId}/feedback", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def record_feedback(
    message_id: MessageIdPath, body: FeedbackRequest, principal: PrincipalDep
) -> dict[str, str]:
    """Record or revise a thumbs signal.

    ``PUT`` because feedback is **revisable**: repeating it replaces the previous signal rather
    than creating a second, which is what the unique constraint on ``(message_id, given_by_oid)``
    enforces underneath.
    """
    del message_id, body, principal
    return {"detail": NOT_IMPLEMENTED}


@router.delete("/messages/{messageId}/feedback", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def withdraw_feedback(message_id: MessageIdPath, principal: PrincipalDep) -> dict[str, str]:
    """Withdraw a previously recorded signal."""
    del message_id, principal
    return {"detail": NOT_IMPLEMENTED}


@router.post("/realtime/negotiate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def negotiate_realtime(principal: PrincipalDep) -> dict[str, str]:
    """Obtain a realtime connection token.

    **Group membership is derived from trusted identity, never requested by the client**
    (contracts/notifications.md). There is no request body here, and that absence is the control:
    a client that could name its group could name somebody else's.
    """
    del principal
    return {"detail": NOT_IMPLEMENTED}
