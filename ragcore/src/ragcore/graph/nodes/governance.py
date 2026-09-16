"""The governance node: the graph's single call into the deterministic gate.

This is the only node that writes the ``governance`` channel, and that channel is write-once
(:func:`~ragcore.graph.state.seal_governance`). Between the two facts, a treatment assigned here
cannot be revised by anything that runs afterwards — including the agent loop.

**Everything the gate needs is resolved here and handed in.** The node reads the catalogue,
reads entitlement, reads the clock and reads any recorded decision, then calls a pure function.
The gate itself touches no infrastructure, so there is no ambient state for a compromised
retrieval or model call to have poisoned.
"""

from __future__ import annotations

from datetime import datetime

from langgraph.runtime import Runtime

from ragcore.domain.decisions import RecordedDecision
from ragcore.domain.identifiers import OperationIdentity
from ragcore.domain.proposal import ProposedOperation
from ragcore.governance.gate import GateDisposition, GateRequest, evaluate
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import (
    disposition_value,
    interrupt_value,
    treatment_value,
)
from ragcore.graph.state import AgentState, GovernanceResult

GOVERN = "govern"


def make_govern(deps: GraphDependencies) -> GraphNode:
    """Build the ``govern`` node."""

    async def govern(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Assign a treatment and decide the disposition.

        Raises:
            ValueError: When reached with no proposal. Not a refusal — a refusal is a governance
                outcome about a real proposal, and recording one here would put a denial in the
                audit trail for something nobody proposed. An empty ``proposal`` channel at this
                point is a routing defect, and it fails loudly rather than being absorbed.
        """
        proposed = state.get("proposal")
        if proposed is None:
            raise ValueError(
                "the govern node was reached with an empty proposal channel; routing should not "
                "reach the gate before a proposal exists"
            )

        identity = OperationIdentity(proposed["catalogue_id"], proposed["catalogue_version"])
        tenant = runtime.context.tenant

        entry = await deps.catalogue.lookup(tenant, identity)
        is_entitled = await deps.catalogue.is_entitled(tenant, identity.catalogue_id)
        decision = await _recorded_decision(deps, runtime, state)

        outcome = evaluate(
            GateRequest(
                tenant=tenant,
                proposal=ProposedOperation(
                    identity=identity,
                    parameters=proposed["parameters"],
                    rationale=proposed["rationale"],
                ),
                entry=entry,
                is_entitled=is_entitled,
                requester=runtime.context.requester,
                now=deps.clock.now(),
                decision=decision,
                authorization_expires_at=_expiry(decision),
            )
        )

        result: GovernanceResult = {
            "treatment": treatment_value(outcome.treatment),
            "treatment_reason": outcome.treatment_reason.value,
            "disposition": disposition_value(outcome.disposition),
            "reason": outcome.reason.value,
            "decided_at": deps.clock.now().isoformat(),
        }

        pending = outcome.suspends_on
        return {
            "governance": result,
            "pending_interrupt": interrupt_value(pending) if pending is not None else None,
        }

    return govern


async def _recorded_decision(
    deps: GraphDependencies, runtime: Runtime[RunContext], state: AgentState
) -> RecordedDecision | None:
    """Read back whatever human decision actually stands for this work item.

    **Read from the durable record, never from the graph state.** The ``decision`` channel holds
    a mirror of the decision for rendering; this reads the row. A graph that authorized itself
    from its own checkpoint would be reading working state as an authority record, which is
    precisely the confusion data-model.md §Graph checkpoint forbids.

    Returns:
        The standing verdict or consent, or ``None`` when neither has been recorded. ``None``
        means *undecided* and produces a suspension, never a proceed.
    """
    del state
    work_item_id = runtime.context.work_item_id
    if work_item_id is None:
        return None

    verdict = await deps.approvals.decision_for(runtime.context.tenant, work_item_id)
    if verdict is not None:
        return verdict
    return await deps.consents.decision_for(runtime.context.tenant, work_item_id)


def _expiry(decision: RecordedDecision | None) -> datetime | None:
    """The execution validity window, resolved from the durable decision record.

    The gate takes exactly one window, so resolving it is this node's job rather than the gate's.
    Both decision types carry ``expires_at`` as their repository read it — ``approval.expires_at``
    for a verdict, the work item's window for a consent — so there is one value and one origin.

    ``None`` when nothing has been decided, which is correct rather than a stub: no decision means
    no window, and :class:`~ragcore.governance.gate.GateReason.AUTHORIZATION_WINDOW_MISSING` makes
    a granted decision with no window **fail closed** instead of treating it as unlimited.
    """
    return None if decision is None else decision.expires_at


def route_after_govern(state: AgentState) -> str:
    """Route on the gate's disposition.

    The only place in the graph that branches on a governance outcome, and it branches on the
    ``disposition`` the gate wrote — never on the proposal, the conversation or the evidence.

    Raises:
        ValueError: When the governance channel is empty. Unreachable via the built graph; kept
            so a hand-constructed run fails rather than falling through to execution.
    """
    governance = state.get("governance")
    if governance is None:
        raise ValueError("route_after_govern reached with an empty governance channel")

    disposition = governance["disposition"]
    if disposition == GateDisposition.PROCEED.value:
        return "execute"
    if disposition == GateDisposition.SUSPEND_FOR_CONSENT.value:
        return "await_consent"
    if disposition == GateDisposition.SUSPEND_FOR_APPROVAL.value:
        return "await_approval"
    return "close"
