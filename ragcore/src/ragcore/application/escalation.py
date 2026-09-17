"""Escalation — hand the request to a person, with everything they need, **and tell the user why**.

Two requirements meet here and neither is satisfied by the other:

* `FR-FALL-002`: the request is placed on the queue in the system of record **with the transcript,
  the retrieved candidates and the reason**. A queue entry saying "the assistant could not help"
  makes a technician start the conversation again, and the person who has already explained their
  problem twice explains it a third time.
* `FR-FALL-010`: the user is told **why**. Not that something went wrong — why. "I could not find
  guidance specific to your organisation" and "this needs an approval I cannot ask for here" lead
  to completely different expectations about what happens next, and a single "a human will help
  you" hides both.

**Escalation is an honest ending, not a failure path.** It is reached when the platform *knows* it
should not proceed — the knowledge condition withheld, the treatment refuses, the operation is out
of scope. Every one of those is the machine working. Nothing here logs an error, nothing retries,
and nothing presents the outcome to the user as a fault of their request.

**The reason is the platform's own, from a closed set.** :class:`EscalationReason` is an enum, not
free text and never a model's explanation. A reason a model wrote would be a reason nobody can
count, alert on, or hold constant between two identical cases — and it would be model output on the
one surface where the user is being told what the platform concluded.

**Escalation carries no authority and creates none.** Handing work to a person does not approve it:
a staff member who picks it up still acts through their own authenticated surface, under their own
roles. Nothing in this module writes an approval, and there is no port here through which it could.

**A transcript is content, and content has a retention class.** What is queued is what the user
wrote and what the platform retrieved — both already inside the organisation's boundary, both
going to that organisation's own case. No credential, no token and no other organisation's material
travels with it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ragcore.application.cases import anchor_key
from ragcore.domain.session_state import transition
from ragcore.domain.work import SessionState

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.audit import AuditWriter
    from ragcore.application.ports import CaseSystemPort, ClockPort, RetrievedChunk
    from ragcore.domain.identifiers import CorrelationId, PrincipalId, SessionId
    from ragcore.domain.tenancy import TenantContext
    from ragcore.graph.state import ConversationTurn

__all__ = [
    "EscalationOutcome",
    "EscalationPath",
    "EscalationReason",
]

MAX_QUEUED_CANDIDATES = 5
"""How many retrieved candidates travel with an escalation.

Enough for a technician to see what the platform looked at and judge whether it looked in the right
place. Bounded because the queue entry is read by a person, and fifty chunks of near-miss evidence
is a wall of text somebody scrolls past — which is the same as sending none.
"""


class EscalationReason(Enum):
    """Why this request is going to a person. **A closed set, in the platform's own words.**

    Each member carries the sentence the user is told, because the requirement is that they are
    told *why* and a reason with no user-facing rendering is a reason that becomes "a human will
    help you" at the first surface that has to display it.
    """

    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"
    """The knowledge condition withheld: there is not enough evidence to act on.

    **Not a refusal of authority.** The operation may be perfectly permitted; what is missing is
    grounding, and no human decision supplies evidence — which is why this escalates rather than
    suspending for an approval (spec FR-AGENT-005, FR-AGENT-006).
    """

    NOT_PERMITTED = "not_permitted"
    """Deterministic governance assigned ``NOT_ALLOWED``.

    The operation is **not askable**: it is never surfaced to a human as an approvable proposal
    (spec SC-SCOPE-002). It still reaches a person — as a request they may act on under their own
    authority — and the distinction is the whole of this member's reason for existing.
    """

    HUMAN_DECISION_REQUIRED = "human_decision_required"
    """The treatment requires a human decision that the scaffold does not collect.

    The two human-decided treatments are **classified** from the catalogue here and their
    workflows are not built (plan §Stage 12 validation gates, `FR-DEMO-018`). Routing to manual
    fallback is the honest outcome; auto-approving would be the dishonest one, and quietly refusing
    would misreport a classification as a denial.
    """

    OUT_OF_SCOPE = "out_of_scope"
    """The request is not an ITSM request the platform serves (spec FR-SCOPE-009)."""

    UNANSWERED_IT_QUESTION = "unanswered_it_question"
    """An IT question inside scope that the platform could not answer (spec FR-SCOPE-010)."""

    EXTERNAL_SYSTEM_UNAVAILABLE = "external_system_unavailable"
    """A system the request depends on could not be reached.

    Told to the user as *temporarily unavailable*, distinctly from *not entitled*, and **never as a
    failure of their request** (spec FR-EXT-022).
    """

    @property
    def explanation(self) -> str:
        """What the user is told. Plain, specific, and about the platform rather than about them."""
        return _EXPLANATIONS[self]


_EXPLANATIONS: dict[EscalationReason, str] = {
    EscalationReason.INSUFFICIENT_KNOWLEDGE: (
        "I could not find guidance specific enough to your organisation to act on, so I have "
        "passed this to the support team with everything you have told me."
    ),
    EscalationReason.NOT_PERMITTED: (
        "This is not something I am permitted to do, so I have passed it to the support team, who "
        "can take it forward."
    ),
    EscalationReason.HUMAN_DECISION_REQUIRED: (
        "This needs a person to decide before anything happens, so I have passed it to the "
        "support team rather than acting on it myself."
    ),
    EscalationReason.OUT_OF_SCOPE: (
        "This is outside what I can help with, so I have passed it to the support team."
    ),
    EscalationReason.UNANSWERED_IT_QUESTION: (
        "I could not answer this one, so I have passed it to the support team with what you have "
        "told me."
    ),
    EscalationReason.EXTERNAL_SYSTEM_UNAVAILABLE: (
        "A system I need is temporarily unavailable, so I have passed this to the support team. "
        "Nothing is wrong with your request."
    ),
}
"""One sentence per reason. Total over the enum, so a new reason cannot ship without its wording."""


@dataclass(frozen=True, slots=True)
class EscalationOutcome:
    """What the escalation did.

    Attributes:
        reason: Why it happened.
        explanation: What the user is told. Carried here rather than looked up again by each
            surface, so the queue entry and the chat message cannot drift apart.
        session_state: ``escalated``. A terminal state, reached through
            :mod:`ragcore.domain.session_state`.
        queued: Whether the system of record held the write for replay rather than accepting it
            (spec FR-EXT-007). The escalation still happened and the user is still told; what is
            not yet known is that the case has it.
    """

    reason: EscalationReason
    explanation: str
    session_state: SessionState
    queued: bool


@dataclass(frozen=True, slots=True)
class EscalationPath:
    """Places a request on the queue and records that it happened.

    Attributes:
        cases: The single owning boundary for system-of-record traffic.
        audit: The audit writer. An escalation is a consequential moment and is recorded as
            durably as a permission (`FR-AUDIT-003`).
        clock: The current instant.
    """

    cases: CaseSystemPort
    audit: AuditWriter
    clock: ClockPort

    async def escalate(
        self,
        tenant: TenantContext,
        session_id: SessionId,
        requester: PrincipalId,
        correlation_id: CorrelationId,
        reason: EscalationReason,
        conversation: Sequence[ConversationTurn],
        candidates: Sequence[RetrievedChunk],
        current_state: SessionState = SessionState.RESOLVING,
    ) -> EscalationOutcome:
        """Hand the request to a person, with the transcript, the candidates and the reason.

        Args:
            tenant: The organisation.
            session_id: The session being escalated. Also the anchor for the case.
            requester: Who asked.
            correlation_id: Carried onto the queue entry and the audit record, so a technician's
                queue item and the platform's own trail join on one identifier.
            reason: Why. From the closed set; never model output.
            conversation: The transcript so far, oldest first. Sent so the person does not start
                the conversation again (`FR-FALL-002`).
            candidates: What retrieval found. Sent so the person can see where the platform looked
                — including when it looked in the wrong place, which is the case this evidence is
                most useful for.
            current_state: Where the session is now.

        Returns:
            The outcome, carrying the explanation the user is owed.

        Raises:
            IllegalSessionTransitionError: When the session cannot legally escalate from where it
                is — a terminal session, for instance. Raised by the state machine, which owns the
                table; escalating a resolved session would restart a retention clock that has
                already started.
        """
        facts = {
            "sessionId": str(session_id),
            "requestedByOid": str(requester),
            "correlationId": str(correlation_id),
            "escalatedAt": self.clock.now().isoformat(),
            # The machine-readable reason and the human one, both. The first is what a report
            # counts; the second is what a technician reads and what the user was told, so the two
            # cannot tell different stories.
            "reason": reason.value,
            "explanation": reason.explanation,
            "transcript": _render_transcript(conversation),
            "candidates": _render_candidates(candidates),
        }

        receipt = await self.cases.record_progress(
            tenant,
            str(session_id),
            facts,
            # The same key as the anchoring write: one session, one case, and an escalation is an
            # update to that case rather than a second one. A fresh key here would post a duplicate
            # into the queue at the exact moment a person is about to read it.
            anchor_key(session_id),
            correlation_id,
        )

        await self.audit.record_escalation(tenant, correlation_id, requester, reason.value)

        return EscalationOutcome(
            reason=reason,
            explanation=reason.explanation,
            session_state=transition(current_state, SessionState.ESCALATED),
            queued=not receipt.committed,
        )


def _render_transcript(conversation: Sequence[ConversationTurn]) -> str:
    """Render the conversation for a person to read.

    Plain text with the sender named on each line. **Data throughout**: this is quoted onto a case
    and never parsed, and nothing reads it back to decide anything.
    """
    return "\n".join(f"{turn['sender']}: {turn['content']}" for turn in conversation)


def _render_candidates(candidates: Sequence[RetrievedChunk]) -> str:
    """Render what retrieval found, bounded by :data:`MAX_QUEUED_CANDIDATES`.

    Each line carries the citation and the score. The score is shown to a technician as the raw
    figure it is — **not a probability**, and never rendered as a percentage or a confidence.
    """
    ordered = sorted(candidates, key=lambda chunk: -float(chunk.score))[:MAX_QUEUED_CANDIDATES]
    return "\n".join(
        f"{chunk.source_reference} (score {chunk.score:.3f}): {chunk.content}" for chunk in ordered
    )
