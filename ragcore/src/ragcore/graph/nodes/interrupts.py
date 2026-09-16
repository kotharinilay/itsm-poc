"""The consent and approval interrupts — interrupts 2 and 3 of three.

**These two nodes never read their resume payload.**

That is the whole design. A client resumes a suspended graph by calling ``Command(resume=...)``,
and whatever it passes originates in an HTTP request body. If either node believed that payload,
then "approved" would be a thing a client could say, and the approval gate would be a suggestion.

So the payload is discarded. Both nodes suspend, and when they wake they go and **read the
durable record** through a repository port. The decision they act on is the one that a human made
through an authenticated API and that was written to PostgreSQL — not the one the resume said had
been made.

This is the same rule the resume worker follows for Service Bus triggers: *every trigger is
untrusted; the durable work record provides the authority*. A resume is a trigger by another
transport, and it gets the same treatment.

**Neither node records a decision.** A verdict enters only through the staff API and a consent
only through the customer API (ADR-0002). The graph is a reader here, never a writer, so there is
no path by which a graph could grant itself an approval.
"""

from __future__ import annotations

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from ragcore.domain.decisions import EndUserConsent, StaffVerdict
from ragcore.domain.work import InterruptKind, SessionState
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import session_state_value
from ragcore.graph.state import AgentState, HumanDecisionRecord

AWAIT_CONSENT = "await_consent"
AWAIT_APPROVAL = "await_approval"


def make_await_consent(deps: GraphDependencies) -> GraphNode:
    """Build the ``await_consent`` node — interrupt 2 of 3.

    Reached when deterministic governance assigned ``END_USER_APPROVAL``: an operation on the
    requester's own account or device, which only that person may consent to (spec FR-INTR-005).
    """

    async def await_consent(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Suspend until the requester decides, then read the decision from the durable record.

        The suspension is durable and unbounded (spec FR-INTR-002). ``awaiting_consent`` persists
        indefinitely, and losing the realtime connection changes nothing (spec FR-SESS-016).
        """
        del state

        # The return value is deliberately discarded. See the module docstring: a resume payload
        # is client input, and consent is not a thing a client can assert.
        interrupt(
            {
                "kind": InterruptKind.CONSENT.value,
                "sessionId": str(runtime.context.session_id),
                "workItemId": _work_item_reference(runtime),
                "correlationId": str(runtime.context.correlation_id),
            }
        )

        work_item_id = runtime.context.work_item_id
        if work_item_id is None:
            return _still_awaiting(SessionState.AWAITING_CONSENT)

        consent = await deps.consents.decision_for(runtime.context.tenant, work_item_id)
        if consent is None:
            # Woken with nothing recorded. Not an error and not a denial: the work stays
            # suspended exactly as it was, which is what an unbounded suspension means.
            return _still_awaiting(SessionState.AWAITING_CONSENT)

        return _mirror_consent(consent)

    return await_consent


def make_await_approval(deps: GraphDependencies) -> GraphNode:
    """Build the ``await_approval`` node — interrupt 3 of 3.

    Reached when deterministic governance assigned ``STAFF_APPROVAL``. **Consent MUST NOT satisfy
    this requirement** (spec FR-INTR-007), and it cannot: this node reads the approval repository,
    which returns a :class:`~ragcore.domain.decisions.StaffVerdict` or nothing at all.
    """

    async def await_approval(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Suspend until staff decide, then read the verdict from the durable record.

        There is **no system-generated verdict and no approval by timeout**
        (spec FR-INTR-008). Nothing in this function can produce a verdict: the only way one
        appears is for :meth:`ApprovalRepositoryPort.decision_for` to return one, and the only
        way that happens is for a human to have posted one to the staff API.
        """
        del state

        interrupt(
            {
                "kind": InterruptKind.APPROVAL.value,
                "sessionId": str(runtime.context.session_id),
                "workItemId": _work_item_reference(runtime),
                "correlationId": str(runtime.context.correlation_id),
            }
        )

        work_item_id = runtime.context.work_item_id
        if work_item_id is None:
            return _still_awaiting(SessionState.AWAITING_APPROVAL)

        verdict = await deps.approvals.decision_for(runtime.context.tenant, work_item_id)
        if verdict is None:
            return _still_awaiting(SessionState.AWAITING_APPROVAL)

        return _mirror_verdict(verdict)

    return await_approval


def _work_item_reference(runtime: Runtime[RunContext]) -> str | None:
    """The opaque work identifier for the interrupt payload.

    An identifier and nothing else. The interrupt prompt is delivered over a channel that carries
    no authority, so it carries no approval state, no target and no command content — a client
    fetches the disclosure from an authenticated API instead.
    """
    work_item_id = runtime.context.work_item_id
    return None if work_item_id is None else str(work_item_id)


def _still_awaiting(state: SessionState) -> AgentState:
    """Re-suspend: the graph woke, found no decision, and stays exactly where it was."""
    return {"session_state": session_state_value(state)}


def _mirror_consent(consent: EndUserConsent) -> AgentState:
    """Copy a consent into working state for rendering. **The row remains the authority.**"""
    record: HumanDecisionRecord = {
        "kind": "consent",
        "decision_id": str(consent.consent_id),
        "decided_by": str(consent.consented_by),
        "verdict": consent.verdict.value,
        "decided_at": consent.decided_at.isoformat(),
        "expires_at": None,
    }
    return {"decision": record, "pending_interrupt": None}


def _mirror_verdict(verdict: StaffVerdict) -> AgentState:
    """Copy a staff verdict into working state for rendering. **The row remains the authority.**

    Note what is not copied: ``roles_held``. The roles a person held at decision time are an
    authority fact, they are already on the approval row, and the gate re-evaluates the set
    intersection against the row. Mirroring them into a checkpoint would create a second copy
    that could drift from the first — and the drifting copy would be the one in reach of the
    agent loop.
    """
    record: HumanDecisionRecord = {
        "kind": "approval",
        "decision_id": str(verdict.approval_id),
        "decided_by": str(verdict.decided_by),
        "verdict": verdict.verdict.value,
        "decided_at": verdict.decided_at.isoformat(),
        "expires_at": None,
    }
    return {"decision": record, "pending_interrupt": None}
