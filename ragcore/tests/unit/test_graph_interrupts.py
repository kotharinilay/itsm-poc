"""The graph suspends and resumes at all three interrupt points — the Stage 6 gate.

Run against ``InMemorySaver``. That is the one place an in-memory checkpointer is legitimate, and
``tests/checkpoint/test_durable_checkpointer.py`` asserts it appears nowhere else.

**What each test actually proves.** Suspending is easy; the interesting property is that the
graph comes back to the *same* run — same thread, same accumulated state — and that what it
comes back to is not whatever the resume payload said.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import WorkItemId
from ragcore.domain.tenancy import TenantStatus
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, InterruptKind
from ragcore.graph.builder import build_graph
from ragcore.graph.state import AgentState, ProposedOperationView
from tests.support.fakes import (
    Harness,
    build_harness,
    end_user_consent,
    staff_verdict,
)

pytestmark = pytest.mark.asyncio

THREAD: RunnableConfig = {"configurable": {"thread_id": "test-thread"}}

WAKE: Command[None] = Command(resume={"acknowledged": True})
"""What a client sends to wake a suspended run.

Deliberately meaningless. The consent and approval nodes discard it and read the durable record
instead, so the only thing this payload has to be is **non-empty**: LangGraph reads an empty dict
as an empty resume *map* — a mapping of interrupt id to value — and resumes nothing at all.
"""


def _compiled(harness: Harness) -> Any:
    """Compile the graph against an in-memory saver. Tests only."""
    return build_graph(harness.deps).compile(checkpointer=InMemorySaver())


def _proposal(catalogue_id: str, version: int = 1) -> ProposedOperationView:
    """A seeded proposal, standing in for one the model would make."""
    return {
        "catalogue_id": catalogue_id,
        "catalogue_version": version,
        "parameters": {},
        "source": "model",
        "rationale": "",
    }


def _start(proposal: ProposedOperationView | None = None) -> AgentState:
    state: AgentState = {
        "session_state": "conversational",
        "conversation": [],
        "retrieved": [],
    }
    if proposal is not None:
        state["proposal"] = proposal
    return state


class TestInterruptOneClarification:
    """``clarification`` — answerable only by the end user of the session (FR-INTR-004)."""

    async def test_the_clarify_node_suspends_and_resumes_in_memory(self) -> None:
        """Driven directly: the built graph does not route here in the scaffold.

        The node is wired and reachable — ``build_graph`` adds it and an edge out of it — but
        ``converse`` never asks a question yet, so a run through the whole graph would not reach
        it. Compiling a one-node graph exercises the suspend/resume mechanics the wiring depends
        on without pretending the scaffold asks questions it does not ask.
        """
        from langgraph.graph import END, START, StateGraph

        from ragcore.graph.context import RunContext
        from ragcore.graph.nodes.conversation import CLARIFY, make_clarify

        harness = build_harness()
        graph: StateGraph[AgentState, RunContext, AgentState, AgentState] = StateGraph(
            AgentState, context_schema=RunContext
        )
        graph.add_node(CLARIFY, make_clarify(harness.deps))
        graph.add_edge(START, CLARIFY)
        graph.add_edge(CLARIFY, END)
        compiled = graph.compile(checkpointer=InMemorySaver())

        context = harness.run_context()
        result = await compiled.ainvoke(_start(), config=THREAD, context=context)

        assert "__interrupt__" in result
        prompt = result["__interrupt__"][0].value
        assert prompt["kind"] == InterruptKind.CLARIFICATION.value

        resumed = await compiled.ainvoke(
            Command(resume={"messageId": "m1", "content": "the printer on floor 3"}),
            config=THREAD,
            context=context,
        )

        assert resumed["session_state"] == "resolving"
        assert resumed["conversation"][-1]["content"] == "the printer on floor 3"
        assert resumed["pending_interrupt"] is None


class TestInterruptTwoConsent:
    """``consent`` — given only by the work item's own requester (FR-INTR-005)."""

    async def test_end_user_approval_suspends_then_proceeds_on_a_recorded_consent(self) -> None:
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.reset.my.own.thing", treatment=ExecutionTreatment.END_USER_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        suspended = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        assert suspended["governance"]["disposition"] == "suspend_for_consent"
        assert suspended["governance"]["treatment"] == "END_USER_APPROVAL"
        assert suspended["__interrupt__"][0].value["kind"] == InterruptKind.CONSENT.value
        assert harness.execution.invocations == []

        # The decision arrives the only way it can: recorded through the authenticated customer
        # API. The resume merely wakes the graph.
        harness.consents.seed(work_item_id, end_user_consent(identity, harness.requester))
        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed["decision"]["kind"] == "consent"
        assert resumed["decision"]["verdict"] == ConsentVerdict.GRANTED.value
        # The gate re-ran on resume and advanced from suspension to authorization. The treatment
        # is unchanged — that is the part that may never move — while the disposition did.
        assert resumed["governance"]["treatment"] == "END_USER_APPROVAL"
        assert resumed["governance"]["disposition"] == "proceed"
        assert len(harness.execution.invocations) == 1

    async def test_a_resume_claiming_consent_grants_nothing(self) -> None:
        """**Chat text and client payloads cannot grant authority.**

        The resume says the work is consented. Nothing was recorded. The graph re-suspends,
        exactly where it was, and nothing executes.
        """
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.reset.my.own.thing", treatment=ExecutionTreatment.END_USER_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        resumed = await compiled.ainvoke(
            Command(
                resume={
                    "verdict": "granted",
                    "approved": True,
                    "consent": "granted",
                    "treatment": "AUTO",
                }
            ),
            config=THREAD,
            context=context,
        )

        assert resumed.get("decision") is None
        assert resumed["session_state"] == "awaiting_consent"
        assert harness.execution.invocations == []


class TestInterruptThreeApproval:
    """``approval`` — a human staff decision, and nothing else (FR-INTR-008)."""

    async def test_staff_approval_suspends_then_proceeds_on_a_recorded_verdict(self) -> None:
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        suspended = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        assert suspended["governance"]["disposition"] == "suspend_for_approval"
        assert suspended["__interrupt__"][0].value["kind"] == InterruptKind.APPROVAL.value

        harness.approvals.seed(work_item_id, staff_verdict(identity))
        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed["decision"]["kind"] == "approval"
        assert resumed["decision"]["verdict"] == ApprovalVerdict.APPROVED.value
        assert resumed["governance"]["treatment"] == "STAFF_APPROVAL"
        assert resumed["governance"]["disposition"] == "proceed"
        assert len(harness.execution.invocations) == 1

    async def test_a_consent_does_not_wake_an_approval_into_proceeding(self) -> None:
        """Consent MUST NOT satisfy staff approval (FR-INTR-007), end to end through the graph."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        harness.consents.seed(work_item_id, end_user_consent(identity, harness.requester))
        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed.get("decision") is None
        assert harness.execution.invocations == []

    async def test_waiting_never_becomes_an_approval(self) -> None:
        """There is no approval by timeout. A year of waiting is still a suspension."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )
        harness.clock.advance(minutes=60 * 24 * 365)
        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed["session_state"] == "awaiting_approval"
        assert harness.execution.invocations == []


class TestRefusalClosesHonestly:
    """A refused operation ends, rather than suspending until it expires."""

    async def test_an_uncatalogued_operation_closes_without_asking_anybody(self) -> None:
        """Discovery is not entitlement. Nobody is asked to approve something unregistered."""
        harness = build_harness()
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        result = await compiled.ainvoke(
            _start(_proposal("never.registered")), config=THREAD, context=context
        )

        assert result["governance"]["treatment"] == "NOT_ALLOWED"
        assert result["governance"]["treatment_reason"] == "not_in_catalogue"
        assert result["session_state"] == "closed_declined"
        assert "__interrupt__" not in result
        assert harness.execution.invocations == []

    async def test_an_unentitled_organisation_closes_the_same_way(self) -> None:
        """Registered but not entitled: there is no global toolset."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.registered.not.entitled", treatment=ExecutionTreatment.AUTO
        )
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        result = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        assert result["governance"]["treatment_reason"] == "not_entitled"
        assert harness.execution.invocations == []


class TestTheAutoPath:
    """``AUTO`` reaches execution without a human — the only treatment that does."""

    async def test_auto_proceeds_to_execution(self) -> None:
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.read.only.thing", treatment=ExecutionTreatment.AUTO
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        result = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        assert result["governance"]["disposition"] == "proceed"
        assert result["execution"]["status"] == "executed"
        assert len(harness.execution.invocations) == 1

    async def test_execution_carries_an_idempotency_key(self) -> None:
        """Idempotency boundary 2, protecting the external system."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.read.only.thing", treatment=ExecutionTreatment.AUTO
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        _, key = harness.execution.invocations[0]
        assert str(key)

    async def test_an_unverified_outcome_is_recorded_as_a_claim(self) -> None:
        """``client_attested`` is never presented as confirmed resolution (ADR-0004)."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.read.only.thing", treatment=ExecutionTreatment.AUTO
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        compiled = _compiled(harness)

        result = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )

        assert result["verification"]["outcome"] == "client_attested"


class TestATurnWithNoProposal:
    """A conversation that proposes nothing does not reach the gate."""

    async def test_no_proposal_means_no_governance_record(self) -> None:
        """A governance record about nothing would be a denial nobody caused."""
        harness = build_harness()
        context = harness.run_context()
        compiled = _compiled(harness)

        result = await compiled.ainvoke(_start(), config=THREAD, context=context)

        assert result.get("governance") is None
        assert harness.execution.invocations == []


class TestTheTreatmentIsSealedAcrossASuspension:
    """A suspension re-runs the gate. What may move, and what may not."""

    async def test_the_disposition_advances_but_the_treatment_does_not(self) -> None:
        """Both halves of :func:`~ragcore.graph.state.seal_governance`, in one run.

        The disposition has to move — that is what a human decision is *for*, and sealing the
        whole channel would have made resume unreachable. The treatment must not, because it came
        from the catalogue and nothing downstream may reassign it.
        """
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        first = await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )
        harness.approvals.seed(work_item_id, staff_verdict(identity))
        second = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert first["governance"]["disposition"] != second["governance"]["disposition"]
        assert first["governance"]["treatment"] == second["governance"]["treatment"]

    async def test_an_approval_that_expired_while_suspended_does_not_execute(self) -> None:
        """Spec FR-EXEC-001. The gate re-runs against the clock as it is now, not as it was."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )
        harness.approvals.seed(work_item_id, staff_verdict(identity))
        harness.clock.advance(minutes=16)
        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed["governance"]["reason"] == "authorization_expired"
        assert resumed["session_state"] == "closed_declined"
        assert harness.execution.invocations == []

    async def test_an_organisation_suspended_while_waiting_does_not_execute(self) -> None:
        """Spec FR-EXEC-003. A suspension can land between the decision and the execution."""
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)),
            config=THREAD,
            context=harness.run_context(work_item_id=work_item_id),
        )
        harness.approvals.seed(work_item_id, staff_verdict(identity))

        # The *same* organisation, now suspended. Swapping in a different tenant would also
        # refuse, but for the wrong reason — it would be unentitled, not suspended — and the test
        # would pass without exercising the rule it names.
        suspended = replace(harness.tenant, status=TenantStatus.SUSPENDED)
        resumed = await compiled.ainvoke(
            WAKE,
            config=THREAD,
            context=replace(harness, tenant=suspended).run_context(work_item_id=work_item_id),
        )

        assert resumed["governance"]["reason"] == "tenant_not_admitted"
        assert resumed["governance"]["disposition"] == "refuse"
        # The treatment is unchanged, and that is right: it is a property of the operation and
        # the catalogue, not of the organisation's admission state. Suspension refuses at the
        # gate without rewriting what the operation would have required.
        assert resumed["governance"]["treatment"] == "STAFF_APPROVAL"
        assert harness.execution.invocations == []

    async def test_a_capability_de_entitled_while_waiting_refuses_rather_than_erroring(
        self,
    ) -> None:
        """Narrowing to ``NOT_ALLOWED`` mid-suspension is a refusal, not a defect.

        The reducer permits a treatment to become stricter for exactly this case. An equality
        seal would have raised here, turning a correct governance outcome into a crash.
        """
        harness = build_harness()
        identity = harness.catalogue.register(
            "fixture.governed.action", treatment=ExecutionTreatment.STAFF_APPROVAL
        )
        harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
        work_item_id = WorkItemId(uuid4())
        context = harness.run_context(work_item_id=work_item_id)
        compiled = _compiled(harness)

        await compiled.ainvoke(
            _start(_proposal(identity.catalogue_id)), config=THREAD, context=context
        )
        harness.approvals.seed(work_item_id, staff_verdict(identity))
        harness.catalogue.revoke(harness.tenant, identity.catalogue_id)

        resumed = await compiled.ainvoke(WAKE, config=THREAD, context=context)

        assert resumed["governance"]["treatment"] == "NOT_ALLOWED"
        assert resumed["governance"]["treatment_reason"] == "not_entitled"
        assert resumed["session_state"] == "closed_declined"
        assert harness.execution.invocations == []
