"""The classify node — **classification never authorizes** (`FR-AGENT-002`).

This node looks a proposed operation up in the catalogue and reports what it found. That is all it
does, and the distinction between *reporting* and *deciding* is the entire reason it exists as its
own node rather than as the first half of :mod:`ragcore.graph.nodes.governance`.

**Why the platform classifies early at all.** A user who asks for something that will need
somebody's approval should be told so while they are still in the conversation, rather than after a
silence. And the scaffold's own acceptance depends on it: the two human-decided treatments are
**classified** from the catalogue in Stage 12 and their workflows are not built, so classification
is the thing being proven (plan §Stage 12 validation gates, `FR-DEMO-018`).

**Why that is safe.** The treatment written here comes from the catalogue entry, never from the
model — :class:`~ragcore.graph.state.ProposedOperationView` has no ``treatment`` key for a model to
have filled in, so there is nothing to prefer over the catalogue. And nothing downstream reads this
channel to decide anything: :func:`ragcore.governance.gate.evaluate` re-reads the catalogue itself
and assigns the treatment again through
:func:`~ragcore.governance.policy.assign_treatment`. If this node were removed, deleted or made to
lie, the gate's answer would not change.

That redundancy is deliberate. A classification that the gate *trusted* would be an authorization
written by an earlier, cheaper node — and the cheapest node is always the easiest one to reach from
somewhere unexpected.

**The channel it writes carries no authorization either.** See
:class:`~ragcore.graph.state.ClassificationView` for the list of keys it deliberately does not
have.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from ragcore.domain.identifiers import OperationIdentity
from ragcore.governance.policy import assign_treatment
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import treatment_value
from ragcore.graph.state import AgentState, ClassificationView

CLASSIFY = "classify"

__all__ = ["CLASSIFY", "make_classify"]


def make_classify(deps: GraphDependencies) -> GraphNode:
    """Build the ``classify`` node."""

    async def classify(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Report what the catalogue says about the proposed operation.

        Returns:
            The classification channel, or nothing at all when there is no proposal to classify. An
            empty return is correct here rather than a refusal: a conversational turn that proposed
            nothing has nothing to look up, and recording a classification about nothing would put
            a treatment in the trail for an operation nobody proposed.
        """
        proposed = state.get("proposal")
        if proposed is None:
            return {}

        identity = OperationIdentity(proposed["catalogue_id"], proposed["catalogue_version"])
        tenant = runtime.context.tenant

        entry = await deps.catalogue.lookup(tenant, identity)
        is_entitled = await deps.catalogue.is_entitled(tenant, identity.catalogue_id)

        # The SAME deterministic policy the gate uses, over the SAME catalogue data. Not a
        # simplified copy: a second implementation of treatment assignment would eventually
        # disagree with the first, and the disagreement would surface as a user being told one
        # thing and the gate doing another.
        decision = assign_treatment(entry, is_entitled)

        classification: ClassificationView = {
            "catalogue_id": identity.catalogue_id,
            "catalogue_version": identity.version,
            "treatment": treatment_value(decision.treatment),
            # Registration and entitlement are two facts, not one: discovery never confers
            # entitlement (spec FR-EXT-014, FR-EXT-015), and an operator diagnosing a refusal needs
            # to know which of the two is missing.
            "is_registered": entry is not None,
            "is_entitled": is_entitled,
        }
        return {"classification": classification}

    return classify
