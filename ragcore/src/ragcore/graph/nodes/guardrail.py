"""The scope guardrail — decline what is not ITSM, and route what it cannot answer.

Two requirements, two outcomes, and the difference between them matters to the person asking:

* `FR-SCOPE-009`: a request that is **not an ITSM request** is declined. The platform is an IT
  service desk, and answering a question about annual leave, a supplier invoice or the weather
  would be the platform pretending to a competence it does not have — and doing so in a channel
  the organisation has told its people to trust for IT.
* `FR-SCOPE-010`: an IT question that is **in scope but unanswered** is routed to vendor fallback.
  The platform could not help; a person can. That is an escalation, not a decline.

**Declining and escalating are not the same outcome and are not rendered the same way.** A decline
ends the session honestly — nobody is going to pick it up, and saying "I have passed this to the
support team" when nothing was passed would be a lie a user only discovers by waiting. An
escalation says a person now has it, and a person does.

**The guardrail withholds; it never permits.** Every outcome is *decline*, *escalate* or *continue*,
and ``continue`` means "carry on to the gate" rather than "this is allowed" — the gate is still
ahead, and an in-scope request for a forbidden operation is still refused there. Nothing in this
module can shorten that path: there is no outcome here that skips governance.

**Scope classification is deterministic and reads only the user's own words.** It never reads
retrieved content — content is data, never instruction (spec FR-IDENT-004) — so a poisoned document
cannot talk the guardrail into declaring something in scope. Being deterministic also means the
same request is classified the same way twice, which is what makes a decline explainable to the
person who received it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from langgraph.runtime import Runtime

from ragcore.application.escalation import EscalationReason
from ragcore.domain.work import SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import session_state_value
from ragcore.graph.state import AgentState

GUARDRAIL = "guardrail"

__all__ = [
    "GUARDRAIL",
    "IT_VOCABULARY",
    "OUT_OF_SCOPE_VOCABULARY",
    "ScopeDecision",
    "ScopeOutcome",
    "classify_scope",
    "make_guardrail",
]

IT_VOCABULARY: Final[frozenset[str]] = frozenset(
    {
        "access",
        "account",
        "application",
        "browser",
        "certificate",
        "computer",
        "connect",
        "crash",
        "device",
        "disk",
        "email",
        "error",
        "install",
        "laptop",
        "licence",
        "license",
        "login",
        "mailbox",
        "network",
        "outlook",
        "password",
        "permission",
        "printer",
        "reset",
        "server",
        "software",
        "teams",
        "update",
        "vpn",
        "wifi",
        "windows",
    }
)
"""Vocabulary that marks a request as plausibly IT.

A **word list, and not the control.** It exists to keep obviously-unrelated requests out of the
resolution loop, and it is wrong at the edges by construction. What makes being wrong survivable is
what sits behind it: an in-scope classification permits nothing, because the gate is still ahead.
A guardrail that *granted* anything would need to be right.
"""

OUT_OF_SCOPE_VOCABULARY: Final[frozenset[str]] = frozenset(
    {
        "appraisal",
        "bonus",
        "expenses",
        "grievance",
        "holiday",
        "invoice",
        "maternity",
        "payroll",
        "payslip",
        "pension",
        "recruitment",
        "resignation",
        "salary",
        "sickness",
        "timesheet",
    }
)
"""Vocabulary that marks a request as somebody else's to answer — HR, finance, facilities.

Listed explicitly rather than inferred from the absence of IT vocabulary, because the two are
different questions. "My laptop is slow" has no word from either list and is plainly IT; "when is
my payslip due" is plainly not. An absence of evidence would classify both the same way.
"""


class ScopeOutcome(Enum):
    """What the guardrail concluded. Three members, and all three withhold or pass through."""

    CONTINUE = "continue"
    """Plausibly an IT service request. **Carry on to the gate** — which is still ahead."""

    DECLINE = "decline"
    """Not an ITSM request (`FR-SCOPE-009`). The session closes honestly; nobody picks it up."""

    ESCALATE = "escalate"
    """In scope, unanswered (`FR-SCOPE-010`). Routed to vendor fallback; a person picks it up."""


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    """The guardrail's conclusion and what the user is told.

    Attributes:
        outcome: What happens next.
        explanation: The sentence the user sees. Written here rather than at each surface, so the
            reason a session ended and the reason recorded against it cannot drift apart.
        escalation_reason: Which escalation reason applies, when the outcome escalates. ``None``
            otherwise — a decline is not an escalation with a different label.
    """

    outcome: ScopeOutcome
    explanation: str
    escalation_reason: EscalationReason | None = None


DECLINED_EXPLANATION: Final = (
    "This is not something the IT service desk handles, so I have not passed it on — somebody "
    "would have to raise it with the right team directly. I can help with IT accounts, devices, "
    "software and access."
)
"""What a declined user is told. **Says explicitly that nothing was passed on.**

The tempting wording — "I have passed this to the right team" — is softer and untrue, and its
untruth is discovered by waiting for a reply that never comes.
"""


def classify_scope(text: str, *, grounded: bool) -> ScopeDecision:
    """Classify one request against the platform's scope.

    Args:
        text: The user's own words. **Never retrieved content and never model output** — both are
            data, and a scope classification derived from either would be a scope classification an
            attacker could write.
        grounded: Whether the knowledge condition was met, as
            :mod:`ragcore.retrieval.confidence` assessed it. An in-scope request the platform
            cannot ground is the `FR-SCOPE-010` case.

    Returns:
        The decision. An empty request is treated as in-scope-and-unanswerable rather than
        declined: the platform has been given nothing to judge, and declining on no evidence is a
        decline the user cannot argue with.
    """
    words = {word.strip(".,!?;:'\"").lower() for word in text.split()}

    # Checked first. A request mentioning both — "I cannot open my payslip in Outlook" — is an IT
    # request about a payslip, and declining it would send somebody to HR about a mail client.
    if words & IT_VOCABULARY:
        return _in_scope(grounded)

    if words & OUT_OF_SCOPE_VOCABULARY:
        return ScopeDecision(ScopeOutcome.DECLINE, DECLINED_EXPLANATION)

    return _in_scope(grounded)


def _in_scope(grounded: bool) -> ScopeDecision:
    """The outcome for a request the platform will serve: continue, or hand it to a person."""
    if grounded:
        return ScopeDecision(ScopeOutcome.CONTINUE, "")

    return ScopeDecision(
        ScopeOutcome.ESCALATE,
        EscalationReason.UNANSWERED_IT_QUESTION.explanation,
        EscalationReason.UNANSWERED_IT_QUESTION,
    )


def make_guardrail(deps: GraphDependencies) -> GraphNode:
    """Build the ``guardrail`` node."""

    async def guardrail(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Decline what is out of scope, and route what is in scope but unanswered.

        Returns:
            The session state where the guardrail ends the run, and nothing where it continues —
            an empty return is how a node says "I changed nothing", and a guardrail that always
            wrote a channel would be one with an opinion on every turn.
        """
        del runtime

        grounding = state.get("grounding")
        decision = classify_scope(
            _latest_user_content(state),
            # Two ways a turn can be answerable, and both count. Either the platform found evidence
            # it is confident in, or it has an operation to propose — an operation acting on
            # platform state needs no retrieved knowledge, which is exactly what the gate's
            # `KnowledgeCondition.not_required` says. Requiring grounding for both would withhold
            # every operational request on the grounds that no article described it.
            grounded=(grounding is not None and grounding["is_confident"])
            or state.get("proposal") is not None,
        )

        if decision.outcome is ScopeOutcome.DECLINE:
            return {"session_state": session_state_value(SessionState.CLOSED_DECLINED)}
        if decision.outcome is ScopeOutcome.ESCALATE:
            return {"session_state": session_state_value(SessionState.ESCALATED)}
        return {}

    return guardrail


def _latest_user_content(state: AgentState) -> str:
    """The most recent end-user turn, or the empty string.

    **The end user's own turn, specifically.** A staff turn in a taken-over session is not the
    request being classified, and an agent turn is model output — classifying scope from either
    would be classifying it from something other than what was asked.
    """
    for turn in reversed(state.get("conversation", [])):
        if turn["sender"] == "end_user":
            return turn["content"]
    return ""
