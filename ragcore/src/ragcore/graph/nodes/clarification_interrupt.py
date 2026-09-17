"""Interrupt 1 of 3 — the clarification, and **what makes it different from the other two**.

`FR-INTR-004`: a clarifying question is answerable only by the end user of the session. The
suspension is durable and unbounded (`FR-INTR-002`): nothing here takes a timeout, and losing the
realtime connection changes nothing.

**This interrupt may act on what it is resumed with. The other two may not.** That asymmetry is the
design, not an inconsistency:

* A clarification answer **steers the conversation**. It changes what is retrieved and what is
  proposed, and it changes nothing about what is permitted. Reading it from the resume payload is
  safe because there is no decision being made.
* Consent and approval **are** decisions, so those nodes re-read the durable record and ignore what
  they were resumed with entirely. Authority lives on a row, never in a message.

The line between the two is `FR-IDENT-004`: **chat text cannot grant authority.** An answer here is
chat text. Nothing downstream reads it to decide anything — which is why the ``conversation``
channel it writes into has no ``is_affirmative`` field for anything to start reading.

**The interrupt payload carries identifiers and a machine-readable ``kind``, and nothing else.** No
approval state, no target, no command content, no disclosure of what would run. That matches the
SSE ``interrupt`` event exactly (contracts/customer-api.md), for two reasons: a client can convey
state by more than colour, and the prompt itself carries nothing a client could act on as
authority.

**Answering rejoins the loop rather than skipping ahead.** The edge from this node goes back to
retrieval, so a clarified request is re-grounded and re-gated. An answer that jumped forward to
execution would be an answer that authorized something, and answers do not.
"""

from __future__ import annotations

from typing import Final

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from ragcore.domain.work import InterruptKind, SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode, resume_field
from ragcore.graph.projections import interrupt_value, session_state_value
from ragcore.graph.state import AgentState, ConversationTurn

CLARIFICATION_INTERRUPT = "clarification_interrupt"

__all__ = [
    "CLARIFICATION_INTERRUPT",
    "MAX_ANSWER_CHARACTERS",
    "clarification_payload",
    "make_clarification_interrupt",
]

MAX_ANSWER_CHARACTERS: Final = 4_000
"""The ceiling on one clarifying answer.

Bounded because the answer becomes part of the next prompt, and an unbounded answer is an unbounded
model call metered against the organisation. Truncation is honest here: a clarification is a
sentence or two, and anything past four thousand characters is not clarifying.
"""


def clarification_payload(runtime: Runtime[RunContext]) -> dict[str, str | None]:
    """Build the interrupt payload a client receives.

    **Identifiers and a kind.** Written as its own function so the contract has one implementation
    and ``tests/unit/test_graph_interrupts.py`` can assert what is absent from it — an assertion
    about absence is worth very little when the absence is spread across a node body.

    Args:
        runtime: The run context, which holds the trusted identifiers.

    Returns:
        The payload. Note what is not in it: no approval state, no target, no parameters, no
        treatment and no disclosure of what would run. A client that needs a disclosure fetches it
        from an authenticated API, where the caller is known.
    """
    return {
        "kind": interrupt_value(InterruptKind.CLARIFICATION),
        "sessionId": str(runtime.context.session_id),
        "workItemId": (
            str(runtime.context.work_item_id) if runtime.context.work_item_id is not None else None
        ),
        "correlationId": str(runtime.context.correlation_id),
    }


def make_clarification_interrupt(deps: GraphDependencies) -> GraphNode:
    """Build the ``clarification_interrupt`` node."""

    async def clarification_interrupt(
        state: AgentState, *, runtime: Runtime[RunContext]
    ) -> AgentState:
        """Suspend durably, ask the end user, and record their answer as a conversation turn.

        The suspension persists indefinitely. There is no clock here, no deadline and no timeout
        parameter — the three ``awaiting_*`` states have no expiry (spec FR-SESS-016), and a node
        able to take a timeout is a node somebody eventually gives one.

        Returns:
            The answer as an ``end_user`` turn, the cleared interrupt, and the session back in
            ``resolving``. The turn is recorded as authored by the end user because they authored
            it — and recording it as anything else would misattribute a sentence somebody may later
            be asked about.
        """
        del state

        answer = interrupt(clarification_payload(runtime))

        turn: ConversationTurn = {
            "message_id": resume_field(answer, "messageId"),
            "sender": "end_user",
            # Bounded, and read as text. `resume_field` already refuses anything that is not a
            # string, which is what stops a structured resume payload arriving where a sentence
            # belongs.
            "content": resume_field(answer, "content")[:MAX_ANSWER_CHARACTERS],
            "occurred_at": deps.clock.now().isoformat(),
        }
        return {
            "conversation": [turn],
            "pending_interrupt": None,
            "session_state": session_state_value(SessionState.RESOLVING),
        }

    return clarification_interrupt
