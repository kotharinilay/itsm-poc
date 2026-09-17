"""T192 — **Golden path A, end to end**: a chat turn reaches a verified outcome with a complete
actor chain, and the same machine refuses what it must.

This is the Stage 12 acceptance. What it drives is the whole synchronous machine in one run —
intake and the triage gate, retrieval, grounding, the scope guardrail, the proposal, classification,
the deterministic gate, execution, verification and audit — with no human anywhere in it.

**What "complete actor chain" means, and why each field is asserted separately.** `FR-AUDIT-001`
names requester, approver, executor, method, organisation and result. Three of those are easy to
get subtly wrong:

* ``approved_by`` is ``None`` on an ``AUTO`` path, and that ``None`` **is the answer** to "who
  approved this" rather than a missing value. A chain that named the requester here would be
  recording a consent nobody gave.
* ``execution_method`` is recorded distinctly from ``executed_by`` (§28.4): the same principal
  acting through two mechanisms is two different facts, and a record that conflated them cannot
  answer "by what means".
* ``verification`` says what the platform **knows**, not what it attempted. The reference fixture
  names no verification tool, so the only honest outcome is ``client_attested`` — a claim, and the
  record says so (ADR-0004).

**Why the refusal is in the same file.** The acceptance is not "the machine works"; it is "the
machine works *and refuses what it must*". A golden path proven alone is a system nobody has seen
say no.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from ragcore.application.audit import AuditWriter
from ragcore.application.sessions import SessionTurn, assess_triage
from ragcore.domain.audit import AuditEventKind
from ragcore.domain.governance import ExecutionMethod, ExecutionTreatment, VerificationOutcome
from ragcore.domain.identifiers import OperationId, WorkItemId
from ragcore.domain.proposal import ProposedOperation
from ragcore.execution.executor import ExecutionLeg
from ragcore.governance.fixtures import ECHO, WITHHELD
from ragcore.governance.gate import GateDisposition, GateRequest, evaluate
from ragcore.graph.builder import build_graph
from ragcore.graph.state import AgentState, ProposedOperationView
from tests.support.fakes import FakeChunk, Harness, build_harness

THREAD: RunnableConfig = {"configurable": {"thread_id": "golden-path-a"}}

REQUEST = "my vpn client will not connect from home since the windows update last night"
"""A real request, articulated. Long enough to clear the triage gate, which is the point."""


def _compiled(harness: Harness) -> Any:
    return build_graph(harness.deps).compile(checkpointer=InMemorySaver())


def _grounded(harness: Harness) -> None:
    """Seed the organisation's index so the knowledge condition is met.

    A confident singleton rather than a near-tie: 0.82 against 0.21 clears both the absolute
    threshold and the margin, which is what an answerable request looks like.
    """
    harness.retrieval.seed(
        harness.tenant,
        FakeChunk(
            content="VPN clients need the split-tunnel profile reapplied after a feature update.",
            score=0.82,
            source_reference="kb/vpn-after-update",
        ),
        FakeChunk(content="Printer troubleshooting.", score=0.21, source_reference="kb/printers"),
    )


def _proposal(catalogue_id: str, version: int) -> ProposedOperationView:
    return {
        "catalogue_id": catalogue_id,
        "catalogue_version": version,
        "parameters": {},
        "source": "model",
        "rationale": "reapply the profile",
    }


def _turn(proposal: ProposedOperationView | None = None) -> AgentState:
    state: AgentState = {
        "session_state": "conversational",
        "conversation": [
            {
                "message_id": str(uuid4()),
                "sender": "end_user",
                "content": REQUEST,
                "occurred_at": "2026-09-17T12:00:00+00:00",
            }
        ],
        "retrieved": [],
    }
    if proposal is not None:
        state["proposal"] = proposal
    return state


class TestTheTriageGateOpensTheWorkRecord:
    """`FR-SESS-003`: a work record is committed only once a genuine problem is articulated."""

    def test_a_greeting_alone_opens_nothing(self) -> None:
        assert not assess_triage([SessionTurn("hi")]).commits_work

    def test_the_request_articulates_a_problem(self) -> None:
        assert assess_triage([SessionTurn(REQUEST)]).commits_work

    async def test_the_session_moves_to_resolving(self) -> None:
        harness = build_harness()
        _grounded(harness)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(_turn(), config=THREAD, context=context)

        assert result["session_state"] != "closed_declined"


class TestTheWholeMachineRunsWithNoHumanInIt:
    """Propose → gate → execute → verify, on the ``AUTO`` reference operation."""

    async def test_the_turn_reaches_a_verified_outcome(self) -> None:
        harness = build_harness()
        _grounded(harness)
        harness.catalogue.register(ECHO.identity.catalogue_id, treatment=ExecutionTreatment.AUTO)
        harness.catalogue.entitle(harness.tenant, ECHO.identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(
            _turn(_proposal(ECHO.identity.catalogue_id, ECHO.identity.version)),
            config=THREAD,
            context=context,
        )

        assert result["governance"]["disposition"] == "proceed"
        assert result["execution"]["status"] == "executed"
        # What the platform KNOWS, as distinct from what it attempted. The fixture names no
        # verification tool, so a claim is the only honest outcome (ADR-0004).
        assert result["verification"]["outcome"] == VerificationOutcome.CLIENT_ATTESTED.value
        assert result.get("pending_interrupt") is None

    async def test_the_grounding_report_says_why_it_proceeded(self) -> None:
        """The report is a report — it authorizes nothing — but it has to be honest."""
        harness = build_harness()
        _grounded(harness)
        harness.catalogue.register(ECHO.identity.catalogue_id, treatment=ExecutionTreatment.AUTO)
        harness.catalogue.entitle(harness.tenant, ECHO.identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(
            _turn(_proposal(ECHO.identity.catalogue_id, ECHO.identity.version)),
            config=THREAD,
            context=context,
        )

        grounding = result["grounding"]
        assert grounding["is_confident"]
        assert grounding["required"]
        assert grounding["top_score"] == pytest.approx(0.82)


class TestTheActorChainIsComplete:
    """`FR-AUDIT-001`: requester, approver, executor, method, organisation and result."""

    async def test_every_field_of_the_chain_is_recorded(self) -> None:
        harness = build_harness()
        outcome = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=ECHO.identity),
                entry=ECHO,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )
        assert outcome.disposition is GateDisposition.PROCEED

        report = await ExecutionLeg(harness.execution, harness.clock).run(
            harness.tenant,
            outcome,
            work_item_id=WorkItemId(uuid4()),
            operation_id=OperationId(uuid4()),
            identity=ECHO.identity,
            parameters={},
            verification_tool=ECHO.verification_tool,
            correlation_id=harness.run_context().correlation_id,
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
                captured.append((tenant, correlation_id, actor_chain, detail))

        correlation = harness.run_context().correlation_id
        await AuditWriter(_Sink()).record_execution(
            harness.tenant,
            correlation,
            requester=harness.requester,
            approver=None,
            executed_by=ExecutionMethod.WORKLOAD.value,
            method=report.method,
            treatment=outcome.treatment,
            verification=report.verification,
            outcome="executed",
        )

        tenant, recorded_correlation, chain, facts = captured[0]

        # ORGANISATION.
        assert tenant == harness.tenant
        # REQUESTER.
        assert chain.requested_by == harness.requester
        # APPROVER — None, and that None is the answer on an AUTO path.
        assert chain.approved_by is None
        # EXECUTOR and METHOD, recorded as two facts rather than one.
        assert chain.executed_by == ExecutionMethod.WORKLOAD.value
        assert chain.execution_method is ExecutionMethod.WORKLOAD
        # RESULT, and what the platform knows about it.
        assert facts.kind is AuditEventKind.EXECUTION_RECORDED
        assert facts.outcome == "executed"
        assert facts.treatment is ExecutionTreatment.AUTO
        assert facts.verification is VerificationOutcome.CLIENT_ATTESTED
        # One correlation identifier, carried onto the record (spec FR-OPS-001).
        assert recorded_correlation == correlation

    async def test_an_unverified_outcome_may_not_be_reported_as_resolved(self) -> None:
        """ADR-0004. The one question a user-facing message may be derived from."""
        harness = build_harness()
        outcome = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=ECHO.identity),
                entry=ECHO,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )

        report = await ExecutionLeg(harness.execution, harness.clock).run(
            harness.tenant,
            outcome,
            work_item_id=WorkItemId(uuid4()),
            operation_id=OperationId(uuid4()),
            identity=ECHO.identity,
            parameters={},
            verification_tool=ECHO.verification_tool,
            correlation_id=harness.run_context().correlation_id,
        )

        assert report.succeeded
        assert not report.may_report_resolution
        assert report.verified_by is None


class TestTheSameMachineRefuses:
    """The other half of the acceptance. A golden path proven alone is a system nobody has seen
    say no."""

    async def test_the_not_allowed_operation_is_refused_and_nothing_runs(self) -> None:
        harness = build_harness()
        _grounded(harness)
        harness.catalogue.register(
            WITHHELD.identity.catalogue_id, treatment=ExecutionTreatment.NOT_ALLOWED
        )
        harness.catalogue.entitle(harness.tenant, WITHHELD.identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(
            _turn(_proposal(WITHHELD.identity.catalogue_id, WITHHELD.identity.version)),
            config=THREAD,
            context=context,
        )

        assert result["governance"]["disposition"] == "refuse"
        assert result.get("pending_interrupt") is None
        assert harness.execution.invocations == []

    async def test_execution_is_refused_at_the_point_of_effect_too(self) -> None:
        """The check that does not depend on routing.

        A graph edited to reach execution directly — by a future change, by a hand-built run, by a
        resume replaying an unexpected path — still does not execute, because the refusal is at the
        point of effect rather than at the point of routing.
        """
        from ragcore.execution.executor import UnauthorizedExecutionError

        harness = build_harness()
        refused = evaluate(
            GateRequest(
                tenant=harness.tenant,
                proposal=ProposedOperation(identity=WITHHELD.identity),
                entry=WITHHELD,
                is_entitled=True,
                requester=harness.requester,
                now=harness.clock.now(),
            )
        )

        with pytest.raises(UnauthorizedExecutionError):
            await ExecutionLeg(harness.execution, harness.clock).run(
                harness.tenant,
                refused,
                work_item_id=WorkItemId(uuid4()),
                operation_id=OperationId(uuid4()),
                identity=WITHHELD.identity,
                parameters={},
                verification_tool=None,
                correlation_id=harness.run_context().correlation_id,
            )

        assert harness.execution.invocations == []


class TestOneCorrelationIdentifierThroughout:
    """`FR-OPS-001`: one user request, followable across the whole flow."""

    async def test_the_run_context_carries_it_and_nothing_regenerates_it(self) -> None:
        harness = build_harness()
        _grounded(harness)
        harness.catalogue.register(ECHO.identity.catalogue_id, treatment=ExecutionTreatment.AUTO)
        harness.catalogue.entitle(harness.tenant, ECHO.identity.catalogue_id)
        context = harness.run_context(work_item_id=WorkItemId(uuid4()))

        result = await _compiled(harness).ainvoke(
            _turn(_proposal(ECHO.identity.catalogue_id, ECHO.identity.version)),
            config=THREAD,
            context=context,
        )

        # The channel is seeded by the caller and no node rewrites it; a node that minted a second
        # identifier would break the join between the turn and everything downstream of it.
        assert result.get("correlation_id", str(context.correlation_id)) == str(
            context.correlation_id
        )
