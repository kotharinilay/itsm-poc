"""The closure node: where refused, rejected and declined work ends honestly.

A refusal is an outcome, not an absence of one. The two refusal trigger kinds exist precisely so
a declined decision **closes the work honestly** rather than leaving it suspended until it expires
(contracts/triggers.md), and this node is where that lands inside the graph.

Denials, expiries and escalations are audited as durably as permissions (spec FR-AUDIT-003), so
nothing here is a quiet return.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from ragcore.domain.work import SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import session_state_value
from ragcore.graph.state import AgentState

CLOSE = "close"


def make_close(deps: GraphDependencies) -> GraphNode:
    """Build the ``close`` node."""

    async def close(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Close the session without execution.

        Moves to ``closed_declined``, which is terminal and therefore starts the content
        retention clock (spec FR-SESS-020). Audit records are **not** affected by that clock:
        expiring chat content leaves the audit trail intact and complete (spec FR-AUDIT-004).
        """
        del state, runtime
        return {
            "session_state": session_state_value(SessionState.CLOSED_DECLINED),
            "pending_interrupt": None,
        }

    return close
