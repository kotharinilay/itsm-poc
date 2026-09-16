"""Conversation nodes: the turn loop and the clarification interrupt.

Stage 6 is a scaffold. The model is **not** called here — :attr:`GraphDependencies.model` is
declared, bound and unused until a later stage. What is real is the shape: where a turn lands,
which channel it accumulates into, and where the first of the three interrupts suspends.
"""

from __future__ import annotations

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from ragcore.domain.work import InterruptKind, SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode, resume_field
from ragcore.graph.projections import session_state_value
from ragcore.graph.state import AgentState, ConversationTurn

CONVERSE = "converse"
CLARIFY = "clarify"


def make_converse(deps: GraphDependencies) -> GraphNode:
    """Build the ``converse`` node, closed over its dependencies.

    A factory rather than a bare function because LangGraph calls nodes with ``(state, runtime)``
    and has nowhere to pass collaborators. Closing over them keeps injection explicit and leaves
    the node with no global to reach for.
    """

    async def converse(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Advance the conversation by one turn.

        Scaffold behaviour: moves the session into ``resolving`` and writes nothing else. No
        model call and no product behaviour (Stage 6 non-goals).
        """
        del state, runtime
        return {"session_state": session_state_value(SessionState.RESOLVING)}

    return converse


def make_clarify(deps: GraphDependencies) -> GraphNode:
    """Build the ``clarify`` node — interrupt 1 of 3.

    Unlike consent and approval, this interrupt is allowed to act on what it is resumed with,
    because no decision is being made: an answer steers the conversation and nothing else.
    **Chat text cannot grant authority** (spec FR-IDENT-004), and nothing downstream of this node
    reads the answer to decide anything.
    """

    async def clarify(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Suspend and ask the end user a clarifying question.

        **Only the end user of the session may answer** (spec FR-INTR-004). The suspension is
        durable and unbounded (spec FR-INTR-002): nothing here takes a timeout, and losing the
        realtime connection changes nothing.

        The interrupt payload carries a machine-readable ``kind`` and identifiers only, matching
        the SSE ``interrupt`` event — so a client can convey state by more than colour, and so
        the prompt itself carries nothing a client could act on as authority.
        """
        del state

        answer = interrupt(
            {
                "kind": InterruptKind.CLARIFICATION.value,
                "sessionId": str(runtime.context.session_id),
                "correlationId": str(runtime.context.correlation_id),
            }
        )

        turn: ConversationTurn = {
            "message_id": resume_field(answer, "messageId"),
            "sender": "end_user",
            "content": resume_field(answer, "content"),
            "occurred_at": deps.clock.now().isoformat(),
        }
        return {
            "conversation": [turn],
            "pending_interrupt": None,
            "session_state": session_state_value(SessionState.RESOLVING),
        }

    return clarify
