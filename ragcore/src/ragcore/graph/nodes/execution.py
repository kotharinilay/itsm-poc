"""Execution and verification nodes — the last mile, and the last check.

**The endpoint executes; it MUST NEVER decide** (A3 §6.3). These nodes hold no
policy. :func:`make_execute` re-reads the disposition the gate wrote and refuses to run without
it, then invokes a port that has already been told what to do.

The refusal in :func:`make_execute` is deliberately redundant with the routing in
:func:`~ragcore.graph.nodes.governance.route_after_govern`. Routing decides which node runs next;
this decides whether *this* node does anything. A graph edited to reach execution directly — by a
future change, by a hand-built run, by a resume replaying an unexpected path — still does not
execute, because the check is at the point of effect rather than at the point of routing.

**No autonomous ITSM operation is implemented here.** The node calls
:class:`~ragcore.application.ports.ToolExecutionPort`, and the scaffold binds no adapter to it.
What exists is the boundary and the check that guards it.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from ragcore.domain.governance import ExecutionMethod, VerificationOutcome
from ragcore.domain.identifiers import IdempotencyKey, OperationIdentity
from ragcore.governance.gate import GateDisposition
from ragcore.graph.context import RunContext
from ragcore.graph.dependencies import GraphDependencies
from ragcore.graph.nodes.base import GraphNode
from ragcore.graph.projections import verification_value
from ragcore.graph.state import AgentState, ExecutionRecord, VerificationRecord

EXECUTE = "execute"
VERIFY = "verify"


class UnauthorizedExecutionError(Exception):
    """Execution was attempted without a ``PROCEED`` disposition from the gate.

    A platform defect, not a user-facing condition, and raised rather than returned so it cannot
    be mistaken for a failed execution and retried. Nothing maps this to a problem-details
    response: a user did nothing wrong, and the honest handling is an operational alert.
    """


def make_execute(deps: GraphDependencies) -> GraphNode:
    """Build the ``execute`` node."""

    async def execute(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Invoke the authorized capability, exactly once.

        Raises:
            UnauthorizedExecutionError: When the governance channel is absent or holds anything
                other than ``proceed``. This is the point-of-effect check; see the module
                docstring for why it exists alongside the routing.
            ValueError: When the proposal or the work item is missing. Both are routing defects.
        """
        governance = state.get("governance")
        if governance is None or governance["disposition"] != GateDisposition.PROCEED.value:
            raise UnauthorizedExecutionError(
                "execute reached without a PROCEED disposition. The model proposes; deterministic "
                f"governance authorizes, and it did not. governance={governance!r}"
            )

        proposed = state.get("proposal")
        if proposed is None:
            raise ValueError("execute reached with an empty proposal channel")

        work_item_id = runtime.context.work_item_id
        if work_item_id is None:
            raise ValueError("execute reached with no work item; there is nothing to execute for")

        identity = OperationIdentity(proposed["catalogue_id"], proposed["catalogue_version"])

        # Idempotency boundary 2, protecting the **external** system. Boundary 1 is the atomic
        # claim on the work item, made by the resume worker before the graph is resumed at all.
        # Both are required and neither substitutes for the other.
        idempotency_key = IdempotencyKey(f"{work_item_id}:{identity}")

        result = await deps.execution.invoke(
            runtime.context.tenant,
            identity,
            proposed["parameters"],
            idempotency_key,
            runtime.context.correlation_id,
        )

        record: ExecutionRecord = {
            "status": "executed" if result.succeeded else "failed",
            "idempotency_key": str(idempotency_key),
            "executed_by": ExecutionMethod.WORKLOAD.value,
            "execution_method": ExecutionMethod.WORKLOAD.value,
            "attempted_at": deps.clock.now().isoformat(),
            "detail": {},
        }
        verification: VerificationRecord = {
            "outcome": verification_value(result.verification),
            "verified_by": None,
            "verified_at": deps.clock.now().isoformat(),
        }
        return {"execution": record, "verification": verification}

    return execute


def make_verify(deps: GraphDependencies) -> GraphNode:
    """Build the ``verify`` node — separating what was attempted from what is known."""

    async def verify(state: AgentState, *, runtime: Runtime[RunContext]) -> AgentState:
        """Confirm the effect independently, where a verification tool exists.

        Scaffold behaviour: confirms nothing, and says so. Where a catalogue entry names no
        verification tool the outcome can only ever be ``client_attested`` (ADR-0004), and a
        ``client_attested`` outcome **MUST NOT** be reported to a user or written to the system of
        record as confirmed resolution. Leaving this node inert therefore leaves the platform
        honest rather than optimistic: nothing here can upgrade a claim into a confirmation.

        A failed execution is **not** retried here or anywhere. It requires fresh human
        authorization (spec FR-EXEC-006).
        """
        del state, runtime
        return {}

    return verify


UNVERIFIED = VerificationOutcome.CLIENT_ATTESTED
"""What an outcome is worth with no verification tool: a claim, and the record says so."""
