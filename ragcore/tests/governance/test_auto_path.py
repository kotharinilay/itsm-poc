"""T189 — the ``AUTO`` reference operation reaches execution **without any human gate**, and with
its treatment taken from the catalogue.

Two properties, and the second is the one that matters. It is easy to build a system where an
``AUTO`` operation runs; the question is *why* it ran. Here the answer must be: because the
catalogue entry says ``AUTO``, assigned by
:func:`~ragcore.governance.policy.assign_treatment` over stored data — and **not** because a model,
a proposal, a resume payload or a state channel said so.

So the tests below assert both directions:

* the operation proceeds, nobody is asked, and no interrupt is raised;
* a proposal that tries to carry its own treatment changes nothing, because there is nowhere on a
  proposal to put one.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import WorkItemId
from ragcore.governance.fixtures import ECHO, REFERENCE_PREFIX, reference_fixtures
from ragcore.graph.builder import build_graph
from ragcore.graph.state import AgentState, ProposedOperationView
from tests.support.fakes import Harness, build_harness

THREAD: RunnableConfig = {"configurable": {"thread_id": "auto-path"}}


def _compiled(harness: Harness) -> Any:
    return build_graph(harness.deps).compile(checkpointer=InMemorySaver())


def _register_echo(harness: Harness) -> ProposedOperationView:
    """Register the ``AUTO`` reference fixture and return a proposal naming it.

    The fixture's own identity is used rather than an invented one, so this test is about the
    operation the specification asks for (`FR-SCOPE-004`) rather than about a convenient stand-in.
    """
    identity = ECHO.identity
    harness.catalogue.register(identity.catalogue_id, treatment=ExecutionTreatment.AUTO)
    harness.catalogue.entitle(harness.tenant, identity.catalogue_id)
    return {
        "catalogue_id": identity.catalogue_id,
        "catalogue_version": identity.version,
        "parameters": {},
        "source": "model",
        "rationale": "the reference AUTO operation",
    }


def _start(proposal: ProposedOperationView) -> AgentState:
    return {
        "session_state": "conversational",
        "conversation": [
            {
                "message_id": str(uuid4()),
                "sender": "end_user",
                "content": "my vpn will not connect from home since the update",
                "occurred_at": "2026-09-17T12:00:00+00:00",
            }
        ],
        "retrieved": [],
        "proposal": proposal,
    }


class TestTheAutoOperationReachesExecution:
    """Propose, gate, execute — with nobody asked."""

    async def test_it_proceeds(self) -> None:
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["governance"]["disposition"] == "proceed"
        assert result["governance"]["reason"] == "auto_treatment"

    async def test_nobody_is_asked(self) -> None:
        """No interrupt, no pending decision, and no approval or consent read as granted.

        ``AUTO`` means no human decision is required. A run that suspended would be asking
        somebody about an operation the catalogue says nobody needs to be asked about.
        """
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result.get("pending_interrupt") is None
        assert result.get("decision") is None

    async def test_the_capability_is_actually_invoked(self) -> None:
        """Reaching ``proceed`` is not reaching execution. This asserts the second."""
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert len(harness.execution.invocations) == 1
        identity, key = harness.execution.invocations[0]
        assert identity.catalogue_id == ECHO.identity.catalogue_id
        assert str(key)

    async def test_the_outcome_is_recorded_as_a_claim_not_a_confirmation(self) -> None:
        """The fixture names no verification tool, because it changes nothing to verify.

        ``client_attested`` MUST NOT be reported to a user or written to the system of record as
        confirmed resolution (ADR-0004), and leaving the fixture unverifiable keeps the scaffold
        honest rather than optimistic.
        """
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["verification"]["outcome"] == "client_attested"
        assert ECHO.verification_tool is None


class TestTheTreatmentComesFromTheCatalogue:
    """`FR-AGENT-004`: never from model output."""

    async def test_the_assigned_treatment_matches_the_catalogue_entry(self) -> None:
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["governance"]["treatment"] == ExecutionTreatment.AUTO.value

    def test_a_proposal_cannot_carry_a_treatment_at_all(self) -> None:
        """The enforcement is an absent field, not a check somebody remembered.

        There is no ``treatment`` key on the channel a model writes to, so a model that decided to
        authorize itself has nowhere to put the claim — and there is no code here to forget.
        """
        from ragcore.graph.state import ProposedOperationView as View

        assert "treatment" not in View.__annotations__
        assert "approved" not in View.__annotations__
        assert "accepted_roles" not in View.__annotations__

    async def test_an_unregistered_operation_does_not_default_to_auto(self) -> None:
        """A catalogue lookup that finds nothing is a refusal, not a default."""
        harness = build_harness()
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))
        proposal: ProposedOperationView = {
            "catalogue_id": f"{REFERENCE_PREFIX}not-registered",
            "catalogue_version": 1,
            "parameters": {},
            "source": "model",
            "rationale": "",
        }

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        assert result["governance"]["treatment"] == ExecutionTreatment.NOT_ALLOWED.value
        assert harness.execution.invocations == []


class TestClassificationIsAReadingNotADecision:
    """`FR-AGENT-002`: classification never authorizes."""

    async def test_the_classification_reports_the_catalogue_treatment(self) -> None:
        harness = build_harness()
        proposal = _register_echo(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_start(proposal), config=THREAD, context=context)

        classification = result["classification"]
        assert classification["treatment"] == ExecutionTreatment.AUTO.value
        assert classification["is_registered"]
        assert classification["is_entitled"]

    def test_the_classification_channel_carries_no_authorization(self) -> None:
        from ragcore.graph.state import ClassificationView

        keys = set(ClassificationView.__annotations__)
        assert not keys & {"approved", "authorized", "accepted_roles", "disposition"}


class TestTheFixtureIsAFixture:
    """`FR-SCOPE-006`, `FR-SCOPE-007` — it is never product capability."""

    def test_it_is_marked_as_a_reference_fixture(self) -> None:
        assert ECHO.is_reference_fixture
        assert ECHO.identity.catalogue_id.startswith(REFERENCE_PREFIX)

    def test_it_is_excluded_from_production(self) -> None:
        from ragcore.governance.fixtures import ReferenceFixtureInProductionError

        with pytest.raises(ReferenceFixtureInProductionError):
            reference_fixtures("production")
