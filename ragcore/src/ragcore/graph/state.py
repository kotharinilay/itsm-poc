"""The LangGraph state: explicitly typed, JSON-native, and structurally unable to hold authority.

Seven channels the platform specification names — conversation, retrieved context, proposed
operation, governance result, approval, execution and verification — plus the identifiers that
bind a run to its durable records.

**Why every channel is JSON-native.** A checkpoint is written to PostgreSQL by
``langgraph-checkpoint-postgres`` and read back, possibly by a different process at a different
revision. Domain objects do round-trip through the serializer, but only by registering each type
in a msgpack allowlist that then has to stay correct across every deployment. Primitives,
``TypedDict`` and ``Literal`` carry the same information with no allowlist, no version coupling
and no way for a checkpoint written last month to fail to load. The node boundary converts.

**Why the ``Literal`` types are not hand-maintained.** Each one below mirrors a domain enum's
values, and ``tests/unit/test_graph_state.py`` asserts the two match exactly. Adding a member to
the enum without adding it here fails that test rather than producing a state channel that
silently cannot represent the new case.

**What the state cannot say.** There is no ``authorized`` flag, no ``roles`` channel and no
``tenant_override``; the assigned treatment is sealed once governance writes it; and the
execution and verification channels are write-once. The checkpoint is **working state, never an
authority record** (data-model.md §Graph checkpoint): the graph reads authority from the work
item and cannot rewrite it, which is the structural reason a misbehaving agent cannot retarget
approved work.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from ragcore.domain.governance import ExecutionTreatment, is_narrowing

__all__ = [
    "AgentState",
    "ClassificationView",
    "ConversationTurn",
    "ExecutionRecord",
    "GovernanceResult",
    "GroundingAssessment",
    "HumanDecisionRecord",
    "ProposedOperationView",
    "RetrievedContext",
    "VerificationRecord",
    "seal_execution",
    "seal_governance",
    "seal_human_decision",
    "seal_verification",
]


# ---------------------------------------------------------------------------
# Literal mirrors of the domain enums. Kept honest by test_graph_state.py.
# ---------------------------------------------------------------------------

TreatmentValue = Literal["AUTO", "END_USER_APPROVAL", "STAFF_APPROVAL", "NOT_ALLOWED"]
"""Mirrors :class:`~ragcore.domain.governance.ExecutionTreatment`. Exactly four, no ``UNKNOWN``."""

DispositionValue = Literal["proceed", "suspend_for_consent", "suspend_for_approval", "refuse"]
"""Mirrors :class:`~ragcore.governance.gate.GateDisposition`."""

InterruptValue = Literal["clarification", "consent", "approval"]
"""Mirrors :class:`~ragcore.domain.work.InterruptKind`. The three interruption types."""

SessionStateValue = Literal[
    "conversational",
    "resolving",
    "awaiting_user",
    "awaiting_consent",
    "awaiting_approval",
    "staff_controlled",
    "resolved",
    "escalated",
    "closed_declined",
]
"""Mirrors :class:`~ragcore.domain.work.SessionState`. The nine states."""

SenderValue = Literal["end_user", "agent", "staff"]
"""Mirrors ``message.sender_kind`` in data-model.md."""

VerificationValue = Literal["server_confirmed", "client_attested", "contradicted"]
"""Mirrors :class:`~ragcore.domain.governance.VerificationOutcome`."""

ExecutionStatusValue = Literal["executed", "failed"]
"""Mirrors the workload outcome contract. There is no ``partial``: a claim is made or it is not."""


# ---------------------------------------------------------------------------
# Channel payloads
# ---------------------------------------------------------------------------


class ConversationTurn(TypedDict):
    """One turn of the conversation.

    **Chat text cannot grant authority** (spec FR-IDENT-004). An affirmative message is never
    consent — only ``POST /api/customer/v1/work/{id}/consent`` records that — so nothing
    downstream reads ``content`` to decide anything, and there is no ``is_affirmative`` field for
    somebody to start reading.
    """

    message_id: str
    sender: SenderValue
    content: str
    occurred_at: str


class RetrievedContext(TypedDict):
    """One piece of grounding evidence from the derived index.

    **Retrieved content cannot grant authority** (spec FR-IDENT-004). It is cited, shown and
    reasoned over; it is never obeyed. A successful injection here can at most produce a bad
    proposal, which then meets the same gate as every other proposal.

    ``score`` is a raw relevance score and **is not a probability** — nothing may present it as a
    confidence figure to a user.
    """

    chunk_id: str
    content: str
    score: float
    source_reference: str


class GroundingAssessment(TypedDict):
    """What the ``ground`` node concluded about the evidence it has.

    Mirrors :class:`~ragcore.retrieval.confidence.Confidence` plus whether grounding was required
    at all. Written so the step trail and the audit record can say *why* the run continued or
    withheld, rather than only that it did.

    **This channel cannot authorize anything.** There is no ``sufficient_to_execute`` key and no
    treatment: grounding may withhold and may never authorize (spec FR-AGENT-005), and the gate
    re-assesses the condition itself from the retrieved evidence rather than reading this. What
    lives here is a *report*, and a report nothing consults for permission is a report nothing can
    be tricked into consulting.

    ``top_score`` and ``margin`` are raw figures and **are not probabilities** — nothing may
    present either to a user as a confidence.
    """

    top_score: float
    margin: float
    is_confident: bool
    required: bool


class ClassificationView(TypedDict):
    """What the ``classify`` node read out of the catalogue. **A reading, never a decision.**

    Deliberately absent, and never to be added: ``approved``, ``authorized``, ``accepted_roles``
    and anything a downstream node could read as permission. Classification looks an operation up
    and reports what the catalogue says about it; :mod:`ragcore.governance.gate` is what decides,
    and it re-reads the catalogue itself rather than trusting this channel (spec FR-AGENT-002).

    ``treatment`` is here because a user is owed an honest early answer — a request that will need
    somebody's approval should not be described as being in progress — and because the two
    human-decided treatments are **classified** in this scaffold while their workflows are not
    built (plan §Stage 12). It is the catalogue's value, copied; it is never the model's, and
    nothing executes on the strength of it.
    """

    catalogue_id: str
    catalogue_version: int
    treatment: TreatmentValue
    is_registered: bool
    is_entitled: bool


class ProposedOperationView(TypedDict):
    """What the agent suggested doing. **A proposal, not a decision.**

    Mirrors :class:`~ragcore.domain.proposal.ProposedOperation` and shares its central property:
    there is no ``treatment`` key, no ``approved`` key and no ``accepted_roles`` key. The model
    fills this channel; it has nowhere to write an authorization.
    """

    catalogue_id: str
    catalogue_version: int
    parameters: dict[str, object]
    source: str
    rationale: str


class GovernanceResult(TypedDict):
    """What deterministic governance decided.

    Mirrors :class:`~ragcore.governance.gate.GateOutcome`. The reducer for this channel
    (:func:`seal_governance`) seals ``treatment`` while letting the rest advance — see there for
    why those are two different rules.
    """

    treatment: TreatmentValue
    treatment_reason: str
    disposition: DispositionValue
    reason: str
    decided_at: str


class HumanDecisionRecord(TypedDict):
    """A human decision, mirrored into working state after it was read from the durable record.

    **This channel is a copy, never the original.** Authority lives on the approval or consent
    row; this exists so a resumed graph can render what happened without re-reading. Anything
    about to cause an effect reads the durable record, not this.

    ``kind`` distinguishes the two because consent MUST NOT satisfy a staff-approval requirement
    (spec FR-INTR-007), and :func:`seal_human_decision` keeps the **first** decision: the first
    valid verdict wins, and a later one is recorded elsewhere but changes nothing
    (spec FR-INTR-010).
    """

    kind: Literal["consent", "approval"]
    decision_id: str
    decided_by: str
    verdict: str
    decided_at: str
    expires_at: str | None


class ExecutionRecord(TypedDict):
    """What the execution leg attempted and what came back.

    Sealed by :func:`seal_execution`. **A failed authorized action MUST NOT re-fire**
    (spec FR-EXEC-006): a second, differing write to this channel is a re-attempt, and the reducer
    refuses it rather than letting the graph quietly try again.
    """

    status: ExecutionStatusValue
    idempotency_key: str
    executed_by: str
    execution_method: str
    attempted_at: str
    detail: dict[str, object]


class VerificationRecord(TypedDict):
    """What the platform actually **knows** about the effect, as opposed to what it attempted.

    ``client_attested`` is a claim, not proof, and MUST NOT be reported to a user or written to
    the system of record as confirmed resolution (ADR-0004). Kept as its own channel rather than a
    field on :class:`ExecutionRecord` so that "the call succeeded" and "the effect is confirmed"
    can never be read as the same fact.
    """

    outcome: VerificationValue
    verified_by: str | None
    verified_at: str


# ---------------------------------------------------------------------------
# Reducers
# ---------------------------------------------------------------------------


class StateChannelSealedError(Exception):
    """A node tried to overwrite a channel that records a decision already made.

    A platform defect, not a user-facing condition. Raised rather than logged because the
    alternative — accepting the write — is how an authorization gets revised after the fact.
    """

    def __init__(self, channel: str, existing: object, update: object) -> None:
        super().__init__(
            f"the {channel!r} channel is write-once and already holds a different value. "
            f"existing={existing!r} update={update!r}. A decision that has been made is not "
            "revisable from inside the graph; a new decision needs a new authorization."
        )
        self.channel = channel


def _append[T](existing: list[T] | None, update: list[T] | None) -> list[T]:
    """Accumulate. Used for the channels that are a growing record rather than a current value."""
    return (existing or []) + (update or [])


def _seal[T](channel: str, existing: T | None, update: T | None) -> T | None:
    """Write-once with idempotent replay.

    LangGraph replays pending writes when a run resumes from a checkpoint, so an identical
    second write is normal and must be accepted. A *differing* second write is not a replay — it
    is a revision — and that is what this refuses.
    """
    if update is None:
        return existing
    if existing is None or existing == update:
        return update
    raise StateChannelSealedError(channel, existing, update)


class TreatmentWidenedError(Exception):
    """A second governance evaluation made the treatment **more permissive**.

    Its own type because it is the failure the whole gate exists to prevent, and an operator
    reading a stack trace should not have to work out which channel was involved.
    """

    def __init__(self, before: str, after: str) -> None:
        super().__init__(
            f"governance re-evaluated {before} as {after}, which demands less human decision "
            "than the assignment already in force. A treatment may become stricter — an "
            "organisation can be suspended or a capability de-entitled while work waits — but it "
            "may never become more permissive."
        )
        self.before = before
        self.after = after


def seal_governance(
    existing: GovernanceResult | None, update: GovernanceResult | None
) -> GovernanceResult | None:
    """Reducer for :attr:`AgentState.governance`. **The treatment is sealed; the rest advances.**

    Two rules, and the distinction between them is the design:

    * ``treatment`` may only ever become **stricter**, never more permissive
      (:func:`~ragcore.domain.governance.is_narrowing`). Equality would be too strict: a
      capability can be de-entitled, or an organisation suspended, while work waits — and the
      correct outcome of either is ``NOT_ALLOWED`` on the next evaluation, which is a refusal
      rather than a defect.
    * Everything else **must** be free to change, because the gate is deliberately re-evaluated
      after a suspension. ``await_approval`` routes back to ``govern``, not forward to
      ``execute``, so a resumed run re-reads the durable decision and re-runs the gate against
      the current tenant status and clock. That re-run is precisely how ``suspend_for_approval``
      becomes ``proceed``.

    Sealing the whole channel would have made the second rule impossible and the resume path
    unreachable.

    Raises:
        TreatmentWidenedError: When a second evaluation demands less human decision than the
            assignment already in force.
    """
    if update is None:
        return existing
    if existing is None:
        return update

    before = ExecutionTreatment(existing["treatment"])
    after = ExecutionTreatment(update["treatment"])
    if not is_narrowing(before, after):
        raise TreatmentWidenedError(before.value, after.value)
    return update


def seal_human_decision(
    existing: HumanDecisionRecord | None, update: HumanDecisionRecord | None
) -> HumanDecisionRecord | None:
    """Reducer for :attr:`AgentState.decision`. **First valid decision wins** (spec FR-INTR-010).

    Unlike the other sealed channels this does not raise on a differing second write. A second
    verdict arriving is a legitimate race — two staff can open the same queue item — and the
    specification says the later one is *recorded* but changes nothing. It is recorded on the
    durable approval row; here it is simply dropped.
    """
    if existing is not None:
        return existing
    return update


def seal_execution(
    existing: ExecutionRecord | None, update: ExecutionRecord | None
) -> ExecutionRecord | None:
    """Reducer for :attr:`AgentState.execution`. One authorization, at most one execution."""
    return _seal("execution", existing, update)


def seal_verification(
    existing: VerificationRecord | None, update: VerificationRecord | None
) -> VerificationRecord | None:
    """Reducer for :attr:`AgentState.verification`."""
    return _seal("verification", existing, update)


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class AgentState(TypedDict, total=False):
    """The complete, explicitly typed graph state.

    ``total=False`` because a run starts with only its identifiers and fills the rest in as it
    goes; a node that has not run has not written its channel, and ``None`` for "not yet" is
    honest where a required key holding an empty value would not be.

    Attributes:
        tenant_id: The platform tenant, derived from trusted identity or from the work item.
            Present so nodes can pass it to tenant-scoped ports — **not** so anything can set it.
            A node that writes this is changing which organisation's data a run touches, which is
            why ``tests/governance/test_authority_boundary.py`` asserts no node does.
        session_id: The chat session. 1:1 with the work item (spec FR-SESS-004).
        work_item_id: The durable authority record. The graph reads authority from it and
            cannot rewrite it.
        correlation_id: Originates at the public edge, carried onto every log, span, trigger,
            notification and audit record (spec FR-OPS-001).
        session_state: Where the session is among its nine states. Moved through
            :mod:`ragcore.domain.session_state`, which is the only place transition rules live.
        pending_interrupt: Which of the three interruptions the run is suspended on, or ``None``.
            The three ``awaiting_*`` states persist indefinitely; nothing here expires.
        conversation: The turns so far. Accumulates.
        retrieved: Grounding evidence for this run. Accumulates. Data, never instruction.
        grounding: What the ``ground`` node concluded about that evidence. A report; it authorizes
            nothing, and the gate assesses the knowledge condition itself rather than reading it.
        classification: What the catalogue says about the proposed operation. A reading of stored
            data, never a decision — see :class:`ClassificationView`.
        proposal: What the agent suggested. Last write wins — the agent may revise its own
            proposal freely, right up until the gate reads it.
        governance: What deterministic governance decided. **Write-once.**
        decision: The human decision, mirrored from the durable record. **First one wins.**
        execution: What the execution leg attempted. **Write-once.**
        verification: What the platform knows about the effect. **Write-once.**
    """

    tenant_id: str
    session_id: str
    work_item_id: str | None
    correlation_id: str

    session_state: SessionStateValue
    pending_interrupt: InterruptValue | None

    conversation: Annotated[list[ConversationTurn], _append]
    retrieved: Annotated[list[RetrievedContext], _append]
    grounding: GroundingAssessment | None
    classification: ClassificationView | None

    proposal: ProposedOperationView | None
    governance: Annotated[GovernanceResult | None, seal_governance]
    decision: Annotated[HumanDecisionRecord | None, seal_human_decision]
    execution: Annotated[ExecutionRecord | None, seal_execution]
    verification: Annotated[VerificationRecord | None, seal_verification]
