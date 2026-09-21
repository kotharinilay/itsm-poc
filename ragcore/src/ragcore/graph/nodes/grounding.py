"""Retrieval and proposal nodes: where untrusted content enters, and where a proposal is made.

These two nodes are the entire attack surface for prompt injection, and they are deliberately
adjacent so the containment is visible in one file:

* :func:`make_retrieve` pulls grounding evidence. **Retrieved content cannot grant authority**
  (spec FR-IDENT-004) — it is written to a state channel that nothing downstream consults for a
  decision.
* :func:`make_propose` produces a :class:`~ragcore.graph.state.ProposedOperationView`. **Model
  output cannot grant authority** (spec FR-IDENT-003) — and the channel it writes to has no
  ``treatment`` key, so a model that decided to authorize itself has nowhere to put the claim.

The worst case, end to end: poisoned evidence produces a bad proposal, the gate refuses it, and
the refusal is audited.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.runtime import Runtime

from ragcore.domain.proposal import ProposalSource
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.state import AgentState, GroundingAssessment, RetrievedContext
from ragcore.retrieval.confidence import assess

RETRIEVE = "retrieve"
GROUND = "ground"
PROPOSE = "propose"

RETRIEVAL_LIMIT = 8
"""How many chunks one pass retrieves. A tuning constant, never a security control."""


def make_retrieve(deps: GraphDependencies) -> GraphNode:
    """Build the ``retrieve`` node."""

    async def retrieve(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Fetch grounding evidence, scoped to the organisation.

        The tenant filter is not optional and not defaulted. ``RetrievalPort.search`` takes a
        :class:`~ragcore.domain.tenancy.TenantContext` as its first positional argument, so there
        is no overload to call without one — **a code path able to issue an unfiltered query MUST
        NOT exist** (A1 §4.5, A2 P03).

        The tenant comes from :class:`~ragcore.graph.context.RunContext`, which is run-scoped and
        not checkpointed, so no node can have written it.
        """
        query = _latest_user_content(state)
        if not query:
            return {}

        chunks = await deps.retrieval.search(runtime.context.tenant, query, RETRIEVAL_LIMIT)

        evidence: list[RetrievedContext] = [
            {
                "chunk_id": chunk.source_reference,
                "content": chunk.content,
                "score": chunk.score,
                "source_reference": chunk.source_reference,
            }
            for chunk in chunks
        ]
        return {"retrieved": evidence}

    return retrieve


def make_ground(deps: GraphDependencies) -> GraphNode:
    """Build the ``ground`` node — **the node that may withhold and may never authorize**.

    Sits between retrieval and proposal so the run can report how well grounded it is before it
    suggests anything. The figures come from :mod:`ragcore.retrieval.confidence`, which owns both
    thresholds and their comparison direction; nothing is restated here.

    **What this node cannot do.** It writes a report. It does not gate, does not route and does not
    set a treatment — :func:`ragcore.governance.gate.evaluate` assesses the knowledge condition
    itself from the retrieved channel, and does so **before** the treatment branches so an
    ungrounded proposal cannot be put in front of a human to approve. Removing this node would
    change what a user is told and nothing about what is permitted, which is the property that
    makes it safe to compute early.
    """

    async def ground(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Assess how well grounded this run is.

        Returns:
            The grounding channel. Empty evidence is reported as **not confident** rather than as
            absent: an absence of evidence is not a weak positive, and a surface reading a missing
            channel would have to invent a default — which is the permissive one.
        """
        del runtime

        evidence = state.get("retrieved", [])
        confidence = assess([_Scored(chunk["score"]) for chunk in evidence])

        assessment: GroundingAssessment = {
            "top_score": confidence.top_score,
            "margin": confidence.margin,
            "is_confident": confidence.is_confident,
            # Grounding was sought, so it was required. An operation acting on platform state
            # rather than on retrieved knowledge reports `not_required` at the gate through
            # `KnowledgeCondition.not_required`, which is a different statement from a met
            # condition — evidence not sought is not evidence found.
            "required": True,
        }
        return {"grounding": assessment}

    return ground


@dataclass(frozen=True, slots=True)
class _Scored:
    """A score, shaped for :func:`ragcore.retrieval.confidence.assess`.

    The retrieved channel holds JSON-native ``TypedDict``s, and the confidence module works over
    anything carrying a ``score`` property. This is the two-line adapter between them, kept private
    so no caller starts passing it around as a chunk.
    """

    score: float


def make_propose(deps: GraphDependencies) -> GraphNode:
    """Build the ``propose`` node — where the agent says what it would like to do."""

    async def propose(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Produce a proposed operation, or none.

        Scaffold behaviour: proposes nothing. A proposal in the scaffold arrives from the caller
        seeding the ``proposal`` channel, which is what the golden-path tests do. No model is
        called (Stage 6 non-goals), and no autonomous ITSM operation is proposed or implemented.

        When this node does call the model, its output lands in ``proposal`` — a channel whose
        :class:`~ragcore.graph.state.ProposedOperationView` has no ``treatment``, no ``approved``
        and no ``accepted_roles``. That absence is the enforcement; there is no check here to
        forget, because there is no field to check.
        """
        del state, runtime
        return {}

    return propose


def _latest_user_content(state: AgentState) -> str:
    """The most recent end-user turn, or the empty string.

    Read as a **query**, never as an instruction. What comes back from retrieval is evidence for
    the proposal; nothing here or downstream treats the text as a directive.
    """
    for turn in reversed(state.get("conversation", [])):
        if turn["sender"] == "end_user":
            return turn["content"]
    return ""


PROPOSAL_SOURCE = ProposalSource.MODEL
"""What the scaffold records as the provenance of a proposal. Never consulted by the gate."""
