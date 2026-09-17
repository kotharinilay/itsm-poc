"""The intake node — where a turn becomes conversation, and where the triage gate sits.

`FR-SESS-003`: a work record is committed only when a genuine problem has been articulated. This is
the node that asks, and :mod:`ragcore.application.sessions` is where the asking lives — the node
records the turn and applies the answer, and holds no triage rule of its own. A rule implemented in
a node is a rule that can only be tested through a graph.

**The triage verdict is deterministic and is not a model call.** A model-decided triage gate would
mean model output decides when an authority record comes into existence, and model output creates
no authority (constitution Principle III). See :func:`~ragcore.application.sessions.assess_triage`
for why the heuristic is deliberately crude.

**Intake writes no authority.** It appends a conversation turn and, at most, reports the work item
the application layer committed. It cannot set a treatment, cannot set an approval and cannot
change which organisation the run belongs to — the tenant lives in run context, which no node can
write (``tests/governance/test_authority_boundary.py``).
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from ragcore.application.sessions import SessionTurn, assess_triage
from ragcore.domain.work import SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import session_state_value
from ragcore.graph.state import AgentState

INTAKE = "intake"

__all__ = ["INTAKE", "make_intake"]


def make_intake(deps: GraphDependencies) -> GraphNode:
    """Build the ``intake`` node, closed over its dependencies."""

    async def intake(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Apply the triage gate to the conversation so far.

        Reads the conversation channel and reports where the session should be. It does **not**
        create the work item itself: the durable record is committed by the application layer
        through a transactional boundary, and a node that wrote it would be writing an authority
        record from inside a checkpointed graph — which is the confusion data-model.md §Graph
        checkpoint forbids.

        Returns:
            The session state after triage. ``resolving`` once a request has been articulated,
            ``conversational`` until then — and the difference is visible to the user, which is the
            point: a session that has not opened a work record should not look like one that has.
        """
        turns = [
            SessionTurn(content=turn["content"], sender_is_end_user=turn["sender"] == "end_user")
            for turn in state.get("conversation", [])
        ]
        assessment = assess_triage(turns)

        state_after = (
            SessionState.RESOLVING if assessment.commits_work else SessionState.CONVERSATIONAL
        )
        return {
            "session_state": session_state_value(state_after),
            # Reported honestly: a run that has articulated nothing has no work item, and `None`
            # here is the answer rather than a value not yet filled in.
            "work_item_id": (
                str(runtime.context.work_item_id)
                if runtime.context.work_item_id is not None
                else None
            ),
        }

    return intake
