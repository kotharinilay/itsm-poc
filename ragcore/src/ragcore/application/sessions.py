"""The session lifecycle, and **the triage gate that decides when a work record exists**.

`FR-SESS-003`: a work record is committed only when a genuine problem has been articulated. Not on
the first message, not when a session opens, and not because a session has been going for a while.

**Why the gate exists at all.** A work item is the platform's durable *authority* record — it is
what an approval binds to, what execution claims, what audit joins on, and what retention and
erasure are keyed by. Creating one per session would mean a "hello" produces an authority record
with no request in it, and every downstream count, queue and report would then be measuring
greetings. It would also mean the one artefact that exists to say *this was asked for* would exist
before anything was asked for.

**What "articulated" means here, precisely, and why it is not a model call.**
:func:`assess_triage` is a deterministic function over the conversation. It asks whether the user
has said something with enough shape to be worked on: enough substance, and not merely a greeting
or an acknowledgement. It does **not** ask the model, and the reason is not cost. A model-decided
triage gate would mean the model decides when an authority record comes into existence, and the
one rule this platform does not bend is that model output creates no authority (constitution
Principle III). The heuristic is deliberately crude and deliberately visible: it can be wrong, and
being wrong means one more turn of conversation, which is a conversation problem rather than a
governance one.

**The gate can only ever withhold commitment.** There is no path here that skips it, and no
parameter that forces a commit — :class:`SessionLifecycle` has one entry point, and the triage
assessment is computed inside it rather than passed in. A caller cannot supply a verdict.

**Nothing here authorizes anything.** Committing a work item records that somebody asked for
something. What may then be done about it is decided by :mod:`ragcore.governance.gate`, later, from
the catalogue — and a work item in ``OPEN`` is as far from authorized as a work item can be.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final, Protocol

from ragcore.domain.session_state import transition
from ragcore.domain.work import SessionState

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import ClockPort
    from ragcore.domain.identifiers import CorrelationId, PrincipalId, SessionId, WorkItemId
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "MINIMUM_ARTICULATED_CHARACTERS",
    "MINIMUM_ARTICULATED_WORDS",
    "SessionLifecycle",
    "SessionTurn",
    "TriageAssessment",
    "TriageOutcome",
    "TurnResult",
    "WorkItemFactory",
    "assess_triage",
]

MINIMUM_ARTICULATED_WORDS: Final = 4
"""How many words a turn needs before it can be a request.

Low on purpose. This is a floor that excludes "hi", "thanks", "ok then" and "are you there" — not a
quality bar. Set high enough to be a quality bar it would start withholding work records from
people who write tersely, and terse is not the same as vague.
"""

MINIMUM_ARTICULATED_CHARACTERS: Final = 15
"""How much text a turn needs, alongside the word count.

Both are required because each misses what the other catches: "a b c d e" clears the word count and
says nothing, and a single long token clears the character count and says nothing either.
"""

ACKNOWLEDGEMENTS: Final[frozenset[str]] = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "no",
        "sure",
        "please",
        "help",
        "good morning",
        "good afternoon",
        "are you there",
    }
)
"""Turns that are never, on their own, a request.

Note ``yes`` and ``no``. They are here for the ordinary reason — an acknowledgement is not a
request — and they are worth reading twice for a second one: **an affirmative message is never
consent** (spec FR-IDENT-004). Nothing downstream reads a turn's content to decide anything, so
this set is not load-bearing for that rule; it simply avoids opening a work record because somebody
said "yes" to a clarifying question.
"""


class TriageOutcome(Enum):
    """Whether a work record should exist yet. Two members; there is no "maybe".

    A third member would need a caller to decide what to do about it, and the two possible
    decisions are the two members already here.
    """

    ARTICULATED = "articulated"
    """A genuine problem has been stated. A work record is committed."""

    CONVERSATIONAL = "conversational"
    """Nothing has been asked for yet. The session stays a conversation."""


@dataclass(frozen=True, slots=True)
class TriageAssessment:
    """The triage verdict and the reason for it.

    Attributes:
        outcome: Whether to commit a work record.
        reason: Why, in the platform's own words, for the step trail and the audit record. Never a
            model's explanation — this assessment is not made by a model.
    """

    outcome: TriageOutcome
    reason: str

    @property
    def commits_work(self) -> bool:
        """Whether this assessment causes a work record to exist."""
        return self.outcome is TriageOutcome.ARTICULATED


@dataclass(frozen=True, slots=True)
class SessionTurn:
    """One inbound turn, as the transport boundary validated it.

    Attributes:
        content: What the user wrote. **Read as text, never as an instruction and never as an
            authorization.** The triage assessment reads its shape — length, word count — and not
            its meaning.
        sender_is_end_user: Whether the session's own user wrote it. A staff member speaking into a
            taken-over session never triggers triage: take-over transfers no requester authority
            (spec FR-SURF-009), and a work record opened on a staff turn would record the wrong
            person as having asked.
    """

    content: str
    sender_is_end_user: bool = True


def assess_triage(turns: Sequence[SessionTurn]) -> TriageAssessment:
    """Decide whether a genuine problem has been articulated.

    Deterministic, pure, and total. Given the same conversation it returns the same verdict on
    every machine and in every process — which is what makes "when does a work record exist"
    answerable from the transcript rather than from a model's mood.

    Args:
        turns: The conversation so far, oldest first.

    Returns:
        The assessment. The reason is written for a step trail a user may read, so it says what is
        missing rather than scoring what was said.
    """
    for turn in turns:
        if not turn.sender_is_end_user:
            continue

        text = turn.content.strip()
        if text.lower().rstrip("!.?") in ACKNOWLEDGEMENTS:
            continue

        if len(text) >= MINIMUM_ARTICULATED_CHARACTERS and len(text.split()) >= (
            MINIMUM_ARTICULATED_WORDS
        ):
            return TriageAssessment(
                TriageOutcome.ARTICULATED,
                "the request has been described in enough detail to be worked on",
            )

    return TriageAssessment(
        TriageOutcome.CONVERSATIONAL,
        "no request has been described yet, so no work record has been opened",
    )


class WorkItemFactory(Protocol):
    """Commits the durable authority record.

    Declared here because this module is the consumer. Deliberately narrow: it creates a work item
    in its initial state and returns its identifier. It cannot set a treatment, cannot set an
    approval state and cannot set an expiry — all three are decided elsewhere, and a factory able
    to set them is a factory through which a caller could create pre-authorized work.
    """

    async def open_work_item(
        self,
        tenant: TenantContext,
        session_id: SessionId,
        requested_by: PrincipalId,
        correlation_id: CorrelationId,
    ) -> WorkItemId:
        """Commit a work item in ``OPEN``, bound 1:1 to the session (spec FR-SESS-004)."""
        ...


@dataclass(frozen=True, slots=True)
class TurnResult:
    """What one turn did to the session.

    Attributes:
        state: The session state after the turn, moved through
            :mod:`ragcore.domain.session_state` — the only place transition rules live.
        work_item_id: The work record, once the triage gate has committed one. ``None`` while the
            session is still a conversation, and that ``None`` is the honest answer rather than a
            missing value.
        triage: The assessment, carried out so the step trail can say why a work record does or
            does not exist.
    """

    state: SessionState
    work_item_id: WorkItemId | None
    triage: TriageAssessment


@dataclass(frozen=True, slots=True)
class SessionLifecycle:
    """Advances a session by one turn, committing a work record at the triage gate and not before.

    Attributes:
        work_items: Commits the authority record. See :class:`WorkItemFactory` for what it cannot
            do.
        clock: The current instant. A port so nothing here calls ``datetime.now``.
    """

    work_items: WorkItemFactory
    clock: ClockPort

    async def advance(
        self,
        tenant: TenantContext,
        session_id: SessionId,
        requester: PrincipalId,
        correlation_id: CorrelationId,
        turns: Sequence[SessionTurn],
        current_state: SessionState = SessionState.CONVERSATIONAL,
        work_item_id: WorkItemId | None = None,
    ) -> TurnResult:
        """Advance the session, committing a work record if and only if triage says to.

        Args:
            tenant: The organisation, from trusted identity. Never from a client field.
            session_id: The session.
            requester: The end user the session belongs to. What a committed work item records as
                having asked, and what consent is later compared against (spec FR-INTR-005).
            correlation_id: Carried onto the work record and everything that follows it.
            turns: The conversation so far, oldest first.
            current_state: Where the session is now.
            work_item_id: The existing work record, when one has already been committed.

        Returns:
            The new state, the work record where one exists, and the triage assessment.

        Raises:
            IllegalSessionTransitionError: When the move is not legal for the current state. Raised
                by :func:`~ragcore.domain.session_state.transition`, which owns the table.
        """
        triage = assess_triage(turns)

        # ALREADY COMMITTED: triage is not re-run for effect. A work item is 1:1 with its session
        # (spec FR-SESS-004), so a second commit would be a second authority record for one
        # conversation — and the second would be the one nothing points at.
        if work_item_id is not None:
            return TurnResult(state=current_state, work_item_id=work_item_id, triage=triage)

        if not triage.commits_work:
            # Stays where it is. A conversational turn is not a state change, and moving to
            # `resolving` before there is anything to resolve would put the session in a state its
            # own name contradicts.
            return TurnResult(state=current_state, work_item_id=None, triage=triage)

        committed = await self.work_items.open_work_item(
            tenant, session_id, requester, correlation_id
        )

        # `transition` refuses a move from a state to itself, deliberately: a no-op transition
        # hides a caller that did not know where it was. A session already in `resolving` is such
        # a caller only if it reached here with no work item, which the branch above excludes — so
        # the guard is for the legitimate case where triage commits on a turn that did not move
        # the session, and it stays out of the state machine's table.
        state = (
            current_state
            if current_state is SessionState.RESOLVING
            else transition(current_state, SessionState.RESOLVING)
        )
        return TurnResult(state=state, work_item_id=committed, triage=triage)
