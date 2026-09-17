"""T190 — the ``NOT_ALLOWED`` reference operation is refused at the gate, **never surfaced to a
human as an approvable proposal**, and recorded as a denial (`SC-SCOPE-002`, `FR-AUDIT-003`).

The middle clause is the one that needs care. A system that refused an operation *and also* put it
in an approval queue would pass a naive test: the gate said refuse, nothing executed, and the queue
entry looks like diligence. It is not. "Not allowed" means **not askable** — there is no person who
can turn this into a yes, and offering somebody the button implies there is.

So the assertions are:

* the gate refuses, with a reason that names the treatment;
* **no interrupt is raised**, no suspension state is entered, and the disposition is not one of the
  two that would suspend;
* the catalogue entry names no approver, because an entry that named one would be describing
  somebody who could decide;
* nothing executes;
* the refusal is recorded as durably as a permission would have been.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from ragcore.application.audit import AuditWriter
from ragcore.domain.audit import AuditEventKind
from ragcore.domain.governance import ExecutionMethod, ExecutionTreatment
from ragcore.domain.identifiers import WorkItemId
from ragcore.domain.proposal import ProposedOperation
from ragcore.governance.fixtures import WITHHELD
from ragcore.governance.gate import GateDisposition, GateRequest, evaluate
from ragcore.graph.builder import build_graph
from ragcore.graph.state import AgentState, ProposedOperationView
from tests.support.fakes import Harness, build_harness

THREAD: RunnableConfig = {"configurable": {"thread_id": "not-allowed-path"}}


def _compiled(harness: Harness) -> Any:
    return build_graph(harness.deps).compile(checkpointer=InMemorySaver())


def _register_withheld(harness: Harness) -> ProposedOperationView:
    """Register the ``NOT_ALLOWED`` reference fixture and propose it.

    Registered **and entitled**, deliberately. A refusal that came from the operation being absent
    or unentitled would prove a different rule; this one has to be refused because the catalogue
    says ``NOT_ALLOWED``.
    """
    identity = WITHHELD.identity
    harness.catalogue.register(identity.catalogue_id, treatment=ExecutionTreatment.NOT_ALLOWED)
    harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
    return {
        "catalogue_id": identity.catalogue_id,
        "catalogue_version": identity.version,
        "parameters": {},
        "source": "model",
        "rationale": "the reference NOT_ALLOWED operation",
    }


def _start(proposal: ProposedOperationView) -> AgentState:
    return {
        "session_state": "conversational",
        "conversation": [
            {
                "message_id": str(uuid4()),
                "sender": "end_user",
                "content": "please reset the domain administrator password for me",
                "occurred_at": "2026-09-17T12:00:00+00:00",
            }
        ],
        "retrieved": [],
        "proposal": proposal,
    }


class TestItIsRefusedAtTheGate:
    async def test_the_disposition_is_refuse(self) -> None:
        harness = build_harness()
        proposal = _register_withheld(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["governance"]["disposition"] == GateDisposition.REFUSE.value
        assert result["governance"]["reason"] == "treatment_refuses"

    async def test_the_refusal_carries_the_treatment_that_produced_it(self) -> None:
        """A denial without its treatment cannot explain itself.

        "Why was this refused" is the question an audit trail is asked most often, and the answer
        is the treatment.
        """
        harness = build_harness()
        proposal = _register_withheld(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["governance"]["treatment"] == ExecutionTreatment.NOT_ALLOWED.value

    async def test_nothing_executes(self) -> None:
        harness = build_harness()
        proposal = _register_withheld(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert harness.execution.invocations == []


class TestItIsNeverSurfacedAsApprovable:
    """`SC-SCOPE-002`. The clause a naive implementation satisfies while getting it wrong."""

    async def test_no_interrupt_is_raised(self) -> None:
        """A suspension means a decision is pending. No decision is pending here, ever."""
        harness = build_harness()
        proposal = _register_withheld(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result.get("pending_interrupt") is None

    async def test_the_session_does_not_enter_an_awaiting_state(self) -> None:
        harness = build_harness()
        proposal = _register_withheld(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert not str(result.get("session_state", "")).startswith("awaiting_")

    def test_the_gate_outcome_suspends_on_nothing(self) -> None:
        """Asserted on the outcome type directly, so it holds however the graph is wired."""
        harness = build_harness()
        outcome = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=WITHHELD.identity),
                entry=WITHHELD,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )

        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.suspends_on is None
        assert not outcome.is_authorized

    def test_the_catalogue_entry_names_no_approver(self) -> None:
        """An entry naming an approver would describe somebody who could decide.

        The whole point of this treatment is that there is nobody, so the accepted-role set is
        empty — and the gate's approval branch is unreachable for it in any case.
        """
        assert not WITHHELD.accepted_roles.roles

    def test_no_role_can_approve_it(self) -> None:
        """Every staff role, checked against the empty accepted set."""
        from ragcore.domain.roles import RoleSet, StaffRole
        from ragcore.domain.roles import evaluate as evaluate_roles

        for role in StaffRole:
            decision = evaluate_roles(RoleSet.of(role), WITHHELD.accepted_roles)
            assert not decision.is_permitted


class TestTheDenialIsRecorded:
    """`FR-AUDIT-003`: denials are recorded as durably as permissions."""

    async def test_the_audit_record_names_the_refusal_and_its_treatment(self) -> None:
        harness = build_harness()
        outcome = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=WITHHELD.identity),
                entry=WITHHELD,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )

        await AuditWriter(harness.audit).record_gate_outcome(
            harness.tenant,
            harness.run_context().correlation_id,
            outcome,
            harness.requester,
        )

        assert len(harness.audit.events) == 1
        facts = harness.audit.events[0].detail
        assert facts.kind is AuditEventKind.GATE_REFUSED
        assert facts.treatment is ExecutionTreatment.NOT_ALLOWED
        assert facts.outcome == "treatment_refuses"

    async def test_the_actor_chain_records_that_nobody_approved_and_nothing_ran(self) -> None:
        """``approved_by=None`` is the audit answer to "who approved this", not a missing value."""
        harness = build_harness()
        outcome = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=WITHHELD.identity),
                entry=WITHHELD,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )
        captured: list[Any] = []

        class _Sink:
            async def record(
                self,
                tenant: Any,
                event_id: Any,
                correlation_id: Any,
                actor_chain: Any,
                detail: Any,
            ) -> None:
                del tenant, event_id, correlation_id, detail
                captured.append(actor_chain)

        await AuditWriter(_Sink()).record_gate_outcome(
            harness.tenant, harness.run_context().correlation_id, outcome, harness.requester
        )

        chain = captured[0]
        assert chain.approved_by is None
        assert chain.execution_method is ExecutionMethod.NONE
        assert chain.requested_by == harness.requester


class TestTheTwoHumanDecidedTreatmentsAreClassifiedNotAutoApproved:
    """Plan §Stage 12 validation gates, `FR-DEMO-018`.

    Classification is what Stage 12 proves; the workflows are not built. An implementation that
    quietly approved them would pass a test that only looked for "did not execute", because an
    auto-approved operation that then executed would look like the AUTO path succeeding.
    """

    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            ("SELF_SERVICE_NOTE", ExecutionTreatment.END_USER_APPROVAL),
            ("STAFF_NOTE", ExecutionTreatment.STAFF_APPROVAL),
        ],
    )
    async def test_it_is_classified_from_the_catalogue_and_does_not_execute(
        self, fixture_name: str, expected: ExecutionTreatment
    ) -> None:
        from ragcore.governance import fixtures

        entry = getattr(fixtures, fixture_name)
        harness = build_harness()
        harness.catalogue.register(entry.identity.catalogue_id, treatment=expected)
        harness.catalogue.entitle(harness.tenant, entry.identity.catalogue_id)
        proposal: ProposedOperationView = {
            "catalogue_id": entry.identity.catalogue_id,
            "catalogue_version": entry.identity.version,
            "parameters": {},
            "source": "model",
            "rationale": "",
        }
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["classification"]["treatment"] == expected.value
        assert result["governance"]["treatment"] == expected.value
        # Suspended awaiting a human, never auto-approved and never executed.
        assert result["governance"]["disposition"].startswith("suspend_for_")
        assert harness.execution.invocations == []
