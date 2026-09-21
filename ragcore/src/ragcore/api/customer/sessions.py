"""``POST /sessions`` and ``POST /sessions/{sessionId}/messages`` — the conversation surface.

Two endpoints, and the second one streams.

**Starting a session does not commit a work record.** `FR-SESS-003` puts that at the triage gate,
which the graph applies on the first turn (:mod:`ragcore.graph.nodes.intake`). A session per
"hello" is fine; an authority record per "hello" is not, because a work item is what an approval
binds to, what execution claims and what audit joins on — and one of those existing before anybody
asked for anything makes every downstream count a count of greetings.

**The message endpoint responds ``text/event-stream``.** It renders what
:class:`~ragcore.graph.host.RunHost` reports; it holds no orchestration policy of its own, which is
what keeps the endpoint free of business policy (.claude/rules/10-principles.md P-13).

**The stream carries no authority.** An ``interrupt`` frame tells a client that a decision is
needed. It does not ask for one and cannot receive one: the decision is made by calling the consent
or answer endpoint, authenticated, where it is recorded durably. **The stream ending is not a
decision** — a dropped connection leaves the work suspended, indefinitely.

**Accessibility reaches into this contract** (contracts/customer-api.md). ``token`` frames carry
incremental text so assistive technology can announce what arrived without re-reading what it has
already announced, and every ``interrupt`` carries a machine-readable ``kind`` so a client can
convey state by more than colour. The scaffold emits no ``token`` frames, because it makes no model
call — and emitting an empty one to look busy would be the platform claiming to be doing something
it is not.

**No request here carries a tenant, a role or an audience.** All three are derived from the
Gateway-established identity, so there is no field through which a caller could widen its own
reach.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import StreamingResponse

from ragcore.api.customer import streaming
from ragcore.api.deps import ContainerDep, CorrelationDep, PrincipalDep, TenantDep
from ragcore.api.middleware.problems import UNIVERSAL_PROBLEM_STATUSES, problem_responses
from ragcore.api.schemas import ApiModel
from ragcore.domain.identifiers import CorrelationId, SessionId
from ragcore.domain.principal import AuthenticatedPrincipal
from ragcore.domain.tenancy import TenantContext
from ragcore.graph.context import RunContext
from ragcore.graph.host import RunHost, TurnEventKind
from ragcore.graph.state import AgentState, ConversationTurn

router = APIRouter(
    prefix="/api/customer/v1",
    tags=["customer"],
    responses=problem_responses(*UNIVERSAL_PROBLEM_STATUSES),
)

SessionIdPath = Annotated[UUID, Path(alias="sessionId", description="The chat session.")]

MAX_MESSAGE_CHARACTERS = 8_000
"""The ceiling on one inbound turn.

Bounded because the turn becomes part of the next prompt, and an unbounded turn is an unbounded
model call metered against the organisation — on a field the user controls the length of.
"""


class StartSessionResponse(ApiModel):
    """The identifier of a newly started session."""

    session_id: UUID


class SendMessageRequest(ApiModel):
    """One turn of conversation.

    **Chat text cannot grant authority** (spec FR-IDENT-004). An affirmative message is never
    consent — only ``POST /work/{id}/consent`` records that — so there is no ``confirm`` field here
    for a client to set, and nothing downstream reads ``content`` to decide anything.
    """

    content: str


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def start_session(principal: PrincipalDep, tenant: TenantDep) -> StartSessionResponse:
    """Start a chat session.

    A session is started here; a **work record is not**. One is committed only once the user has
    articulated a genuine request (spec FR-SESS-003), which the triage gate decides on the first
    turn — creating one per session would put an authority record behind every "hello".
    """
    del principal, tenant
    return StartSessionResponse(session_id=uuid4())


# The response is a stream, and the document has to say so. A route whose success body is declared
# `application/json` when the service sends `text/event-stream` misdescribes the one response a
# client cannot discover by trying it — the connection stays open and nothing parses.
#
# The event kinds are read off `StreamEventKind` rather than restated, so adding one cannot leave
# the published description behind.
SSE_RESPONSE: dict[int | str, dict[str, object]] = {
    200: {
        "description": (
            "Server-sent events. Event kinds: "
            + ", ".join(kind.value for kind in streaming.StreamEventKind)
            + ". The stream carries no authority: an interrupt event reports that a decision is "
            "needed and cannot receive one."
        ),
        "content": {streaming.SSE_MEDIA_TYPE: {"schema": {"type": "string"}}},
    }
}


@router.post(
    "/sessions/{sessionId}/messages",
    response_class=StreamingResponse,
    responses=SSE_RESPONSE,
)
async def send_message(
    request: Request,
    session_id: SessionIdPath,
    body: SendMessageRequest,
    principal: PrincipalDep,
    tenant: TenantDep,
    container: ContainerDep,
    correlation_id: CorrelationDep,
) -> StreamingResponse:
    """Send a message. **Streams the response** as ``text/event-stream``.

    The turn runs through the compiled graph when this process hosts one. A process built without
    persistence — a contract emission, a schema test — has no run host, and the stream then reports
    only that the turn completed rather than inventing progress it did not make.

    Args:
        request: For the run host held on application state.
        session_id: The session. The checkpointer thread is derived from it, which is what stops
            one session resuming another's suspended run.
        body: The turn. **Text**, bounded, and never read to decide anything.
        principal: The caller, from trusted identity. Becomes the requester on the run context.
        tenant: The admitted organisation, from trusted identity plus registry state.
        correlation_id: Carried onto every log, span, trigger, notification and audit record this
            turn produces (spec FR-OPS-001).

    Returns:
        The stream.
    """
    host = getattr(request.app.state, "run_host", None)
    context = _run_context(tenant, principal, correlation_id, SessionId(session_id))
    turn = _initial_state(
        context, body.content[:MAX_MESSAGE_CHARACTERS], container.clock.now().isoformat()
    )

    frames = (
        _render(host, context, turn)
        if isinstance(host, RunHost)
        else streaming.empty_stream(str(session_id))
    )

    return StreamingResponse(
        frames,
        media_type=streaming.SSE_MEDIA_TYPE,
        headers={**streaming.SSE_HEADERS, "X-Correlation-Id": str(correlation_id)},
    )


def _run_context(
    tenant: TenantContext,
    principal: AuthenticatedPrincipal,
    correlation_id: CorrelationId,
    session_id: SessionId,
) -> RunContext:
    """Build the trusted bindings for one invocation.

    Every field comes from something the Gateway established or the registry admitted. **Nothing
    comes from the request body**, which is why the tenant binding can be re-established on every
    invocation rather than travelling in the checkpoint — see :mod:`ragcore.graph.context`.

    ``work_item_id`` is ``None``: a work record exists only once the triage gate has committed one,
    and starting a turn by asserting one would be creating authority for a request nobody has made
    yet.
    """
    return RunContext(
        tenant=tenant,
        requester=principal.identity.principal_id,
        correlation_id=correlation_id,
        session_id=session_id,
        work_item_id=None,
    )


def _initial_state(context: RunContext, content: str, occurred_at: str) -> AgentState:
    """The state one turn starts from.

    Carries the conversation turn and the identifiers, and **nothing else**. In particular it seeds
    no ``proposal``, no ``governance`` and no ``classification``: a turn that began with a
    governance outcome already in its state would be a turn whose gate had been decided by its
    caller.
    """
    turn: ConversationTurn = {
        "message_id": str(uuid4()),
        "sender": "end_user",
        "content": content,
        # From the platform's clock port rather than from a client field: a client-supplied
        # timestamp is a client-ordered conversation.
        "occurred_at": occurred_at,
    }
    return {
        "tenant_id": str(context.tenant.tenant_id),
        "session_id": str(context.session_id),
        "correlation_id": str(context.correlation_id),
        "conversation": [turn],
    }


async def _render(host: RunHost, context: RunContext, turn: AgentState) -> AsyncIterator[str]:
    """Render the host's events as SSE frames.

    The one place :class:`~ragcore.graph.host.TurnEvent` becomes wire format. Kept as a function
    rather than folded into the endpoint so the mapping is testable without a running application,
    and so a new event kind is a change in one place.

    **Cancellation-safe.** A client disconnect cancels the consuming task and the
    ``CancelledError`` is raised at the ``yield``; nothing here catches it.
    """
    async for event in host.stream_turn(context, turn):
        if event.kind is TurnEventKind.STEP:
            yield streaming.step(event.name, event.label)
        elif event.kind is TurnEventKind.INTERRUPT:
            yield streaming.interrupt(
                event.name,
                str(context.session_id),
                str(context.work_item_id) if context.work_item_id is not None else None,
                str(context.correlation_id),
            )
        elif event.kind is TurnEventKind.ERROR:
            yield streaming.error(str(context.correlation_id))
        else:
            yield streaming.done(str(context.session_id))


def rendered_kinds() -> set[str]:
    """Every SSE kind this module can emit.

    Exposed so ``tests/unit/test_run_host.py`` can assert the host's event kinds and the
    transport's frame kinds agree without importing one into the other.
    """
    return {kind.value for kind in TurnEventKind}
