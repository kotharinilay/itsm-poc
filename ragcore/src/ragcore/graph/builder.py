"""The graph: nodes, edges, and the three interrupt points.

One shape, built once, compiled against whichever checkpointer the caller supplies. The build and
the checkpointer are separate on purpose — see :mod:`ragcore.graph.checkpointer` — so a test can
compile the same graph against an in-memory saver without an in-memory saver existing anywhere on
a production path.

**The three interrupts** (spec FR-INTR-001), each a node that suspends durably and indefinitely:

============ ================================ ==========================================
Node         Kind                             Who may answer
============ ================================ ==========================================
``clarify``  ``clarification``                the end user of the session (FR-INTR-004)
``await_consent``  ``consent``                the work item's own requester (FR-INTR-005)
``await_approval`` ``approval``               a staff holder of an accepted role
============ ================================ ==========================================

**The shape of the graph is the control.** There is exactly one edge into ``execute``, and it
comes from :func:`~ragcore.graph.nodes.governance.route_after_govern`. Nothing routes from
``retrieve`` or ``propose`` to ``execute``, so a side-effecting capability is not reachable from
an unconstrained agent loop (constitution Principle III) — not because a check forbids it, but
because no edge goes there.

The two suspension nodes route back through ``govern`` rather than forward to ``execute``. That
matters: a resumed run re-reads the durable decision and re-evaluates the gate, so a consent that
arrived after the organisation was suspended, or after the window elapsed, still does not execute.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes import (
    classify,
    closure,
    conversation,
    execution,
    governance,
    grounding,
    guardrail,
    intake,
    interrupts,
)
from ragcore.graph.state import AgentState

__all__ = ["build_graph"]


def build_graph(
    deps: GraphDependencies,
) -> StateGraph[AgentState, RunContext, AgentState, AgentState]:
    """Assemble the graph.

    Args:
        deps: The collaborators every node is bound to. Passed explicitly and closed over by the
            node factories; there is no container for a node to consult at runtime.

    Returns:
        The uncompiled graph. The caller compiles it with a checkpointer, which is what decides
        whether suspensions survive a process restart — so that choice is never made here.
    """
    graph: StateGraph[AgentState, RunContext, AgentState, AgentState] = StateGraph(
        AgentState, context_schema=RunContext
    )

    graph.add_node(intake.INTAKE, intake.make_intake(deps))
    graph.add_node(conversation.CONVERSE, conversation.make_converse(deps))
    graph.add_node(conversation.CLARIFY, conversation.make_clarify(deps))
    graph.add_node(grounding.RETRIEVE, grounding.make_retrieve(deps))
    graph.add_node(grounding.GROUND, grounding.make_ground(deps))
    graph.add_node(guardrail.GUARDRAIL, guardrail.make_guardrail(deps))
    graph.add_node(grounding.PROPOSE, grounding.make_propose(deps))
    graph.add_node(classify.CLASSIFY, classify.make_classify(deps))
    graph.add_node(governance.GOVERN, governance.make_govern(deps))
    graph.add_node(interrupts.AWAIT_CONSENT, interrupts.make_await_consent(deps))
    graph.add_node(interrupts.AWAIT_APPROVAL, interrupts.make_await_approval(deps))
    graph.add_node(execution.EXECUTE, execution.make_execute(deps))
    graph.add_node(execution.VERIFY, execution.make_verify(deps))
    graph.add_node(closure.CLOSE, closure.make_close(deps))

    # Intake first, because the triage gate decides whether this turn is a conversation or a
    # request — and a work record that does not exist yet is not something the rest of the graph
    # should be reasoning about.
    graph.add_edge(START, intake.INTAKE)
    graph.add_edge(intake.INTAKE, conversation.CONVERSE)
    graph.add_edge(conversation.CONVERSE, grounding.RETRIEVE)

    # Interrupt 1. An answered clarification rejoins the loop rather than skipping ahead: the
    # answer may change what is retrieved, and it must not change what is authorized.
    graph.add_edge(conversation.CLARIFY, grounding.RETRIEVE)

    # Retrieve, then assess how well grounded the run is, then decide whether the request is one
    # the platform serves at all. The guardrail reads the grounding assessment, so it runs after it
    # — an in-scope request the platform cannot ground is FR-SCOPE-010's case and needs both facts.
    graph.add_edge(grounding.RETRIEVE, grounding.GROUND)
    graph.add_edge(grounding.GROUND, guardrail.GUARDRAIL)
    graph.add_conditional_edges(
        guardrail.GUARDRAIL,
        _route_after_guardrail,
        {grounding.PROPOSE: grounding.PROPOSE, closure.CLOSE: closure.CLOSE},
    )

    # Classification sits between the proposal and the gate, and it is a READING rather than a
    # decision: the gate re-reads the catalogue itself, so removing this node would change what a
    # user is told and nothing about what is permitted (see nodes/classify.py).
    graph.add_edge(grounding.PROPOSE, classify.CLASSIFY)
    graph.add_conditional_edges(
        classify.CLASSIFY,
        _route_after_propose,
        {governance.GOVERN: governance.GOVERN, END: END},
    )

    # The only edge into execute, and the only branch that reads a governance outcome.
    graph.add_conditional_edges(
        governance.GOVERN,
        governance.route_after_govern,
        {
            execution.EXECUTE: execution.EXECUTE,
            interrupts.AWAIT_CONSENT: interrupts.AWAIT_CONSENT,
            interrupts.AWAIT_APPROVAL: interrupts.AWAIT_APPROVAL,
            closure.CLOSE: closure.CLOSE,
        },
    )

    # Interrupts 2 and 3. Both return to the gate, never to execution: the decision is re-read
    # from the durable record and the gate runs again against the current tenant status and clock.
    graph.add_edge(interrupts.AWAIT_CONSENT, governance.GOVERN)
    graph.add_edge(interrupts.AWAIT_APPROVAL, governance.GOVERN)

    graph.add_edge(execution.EXECUTE, execution.VERIFY)
    graph.add_edge(execution.VERIFY, END)
    graph.add_edge(closure.CLOSE, END)

    return graph


def _route_after_guardrail(state: AgentState) -> str:
    """Close the session where the guardrail ended it, and otherwise carry on to the proposal.

    Routes on the **session state the guardrail wrote**, not on the request text: the classification
    happens once, in one place, and this reads its result. A second reading of the text here would
    be a second scope decision, and the two would eventually disagree.

    Note what this cannot route to. There is no branch from here to ``execute`` and none to
    ``govern`` — a request that clears the guardrail still meets the gate, because clearing the
    guardrail is not permission.
    """
    session_state = state.get("session_state")
    if session_state in ("closed_declined", "escalated"):
        return "close"
    return "propose"


def _route_after_propose(state: AgentState) -> str:
    """End the turn when there is nothing to govern.

    A conversational turn that proposes no operation is complete. It does **not** fall through to
    the gate, because a gate evaluation with no proposal would have to invent something to
    evaluate, and whatever it invented would be a governance record about nothing.
    """
    return "govern" if state.get("proposal") is not None else END
