"""The LangGraph state: explicitly typed, and typed *consistently* with the domain.

Two jobs here.

**Keeping the mirrors honest.** ``state.py`` describes a checkpoint in terms a checkpoint can
hold — ``Literal`` strings rather than enums — and ``projections.py`` converts. Both duplicate
information the domain already owns. These tests make that duplication safe: add an enum member
without adding it to the mirror and the test fails, rather than a run reaching the one path that
needs the missing case and raising a ``KeyError`` in production.

**Proving the reducers.** A reducer is invoked by the framework, not by any code a reader can
follow, so its rules are worth asserting directly.
"""

from __future__ import annotations

from typing import get_args, get_type_hints

import pytest

from ragcore.domain.governance import ExecutionTreatment, VerificationOutcome, is_narrowing
from ragcore.domain.work import InterruptKind, SessionState
from ragcore.governance.gate import GateDisposition
from ragcore.graph import projections, state
from ragcore.graph.state import (
    AgentState,
    ExecutionRecord,
    GovernanceResult,
    HumanDecisionRecord,
    StateChannelSealedError,
    TreatmentWidenedError,
    VerificationRecord,
    seal_execution,
    seal_governance,
    seal_human_decision,
    seal_verification,
)


class TestTheLiteralMirrorsMatchTheDomain:
    """Every ``Literal`` in ``state.py`` covers exactly its enum, no more and no less."""

    @pytest.mark.parametrize(
        ("literal", "enum"),
        [
            (state.TreatmentValue, ExecutionTreatment),
            (state.DispositionValue, GateDisposition),
            (state.InterruptValue, InterruptKind),
            (state.SessionStateValue, SessionState),
            (state.VerificationValue, VerificationOutcome),
        ],
    )
    def test_literal_arguments_equal_enum_values(
        self, literal: object, enum: type[ExecutionTreatment]
    ) -> None:
        assert set(get_args(literal)) == {member.value for member in enum}

    @pytest.mark.parametrize(
        ("mapping", "enum"),
        [
            (projections.TREATMENT_VALUES, ExecutionTreatment),
            (projections.DISPOSITION_VALUES, GateDisposition),
            (projections.INTERRUPT_VALUES, InterruptKind),
            (projections.SESSION_STATE_VALUES, SessionState),
            (projections.VERIFICATION_VALUES, VerificationOutcome),
        ],
    )
    def test_every_projection_is_total_over_its_enum(
        self, mapping: dict[ExecutionTreatment, str], enum: type[ExecutionTreatment]
    ) -> None:
        """A partial mapping raises ``KeyError`` on whichever case nobody tested."""
        assert set(mapping) == set(enum)

    def test_projections_round_trip(self) -> None:
        """The projected literal is the enum's own value, not a second vocabulary."""
        for treatment in ExecutionTreatment:
            assert projections.treatment_value(treatment) == treatment.value
        for disposition in GateDisposition:
            assert projections.disposition_value(disposition) == disposition.value


class TestTheStateCannotHoldAuthority:
    """Absences, asserted as absences."""

    def test_there_is_no_authorized_channel(self) -> None:
        """No boolean a node could set to mean 'this may run'."""
        channels = set(AgentState.__annotations__)
        for forbidden in ("authorized", "approved", "roles", "is_authorized", "tenant_override"):
            assert forbidden not in channels

    def test_the_seven_specified_channels_are_present(self) -> None:
        """The seven the specification names, each a channel rather than a derived value."""
        channels = set(AgentState.__annotations__)
        for required in (
            "conversation",
            "retrieved",
            "proposal",
            "governance",
            "decision",
            "execution",
            "verification",
        ):
            assert required in channels

    def test_the_tenant_is_carried_as_run_context_not_as_a_domain_object(self) -> None:
        """A checkpointed tenant would have to be rebuilt from a value with no provenance.

        ``RunContext`` holds the real :class:`~ragcore.domain.tenancy.TenantContext`; the state
        holds an opaque identifier for correlation and nothing a port would accept.
        """
        from ragcore.graph.context import RunContext

        assert "tenant" in RunContext.__annotations__
        assert get_type_hints(AgentState)["tenant_id"] is str


class TestTheGovernanceReducer:
    """The treatment may become stricter. It may never become more permissive."""

    def test_the_first_assignment_is_accepted(self) -> None:
        assert seal_governance(None, _governance("STAFF_APPROVAL", "suspend_for_approval")) is not (
            None
        )

    def test_the_disposition_may_advance(self) -> None:
        """Otherwise a suspended run could never resume — the gate re-runs on every resume."""
        before = _governance("STAFF_APPROVAL", "suspend_for_approval")
        after = _governance("STAFF_APPROVAL", "proceed")
        result = seal_governance(before, after)
        assert result is not None
        assert result["disposition"] == "proceed"

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            ("AUTO", "END_USER_APPROVAL"),
            ("AUTO", "STAFF_APPROVAL"),
            ("AUTO", "NOT_ALLOWED"),
            ("END_USER_APPROVAL", "STAFF_APPROVAL"),
            ("END_USER_APPROVAL", "NOT_ALLOWED"),
            ("STAFF_APPROVAL", "NOT_ALLOWED"),
        ],
    )
    def test_a_stricter_treatment_is_accepted(self, before: str, after: str) -> None:
        """De-entitlement and suspension both land here, and both are correct outcomes."""
        result = seal_governance(_governance(before, "refuse"), _governance(after, "refuse"))
        assert result is not None
        assert result["treatment"] == after

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            ("NOT_ALLOWED", "STAFF_APPROVAL"),
            ("NOT_ALLOWED", "AUTO"),
            ("STAFF_APPROVAL", "END_USER_APPROVAL"),
            ("STAFF_APPROVAL", "AUTO"),
            ("END_USER_APPROVAL", "AUTO"),
        ],
    )
    def test_a_more_permissive_treatment_is_refused(self, before: str, after: str) -> None:
        """The failure the gate exists to prevent, whatever produced it."""
        with pytest.raises(TreatmentWidenedError):
            seal_governance(_governance(before, "proceed"), _governance(after, "proceed"))

    def test_narrowing_agrees_with_the_policy_module(self) -> None:
        """One ordering, shared, so policy and state cannot disagree about what is safe."""
        for before in ExecutionTreatment:
            for after in ExecutionTreatment:
                widened = False
                try:
                    seal_governance(
                        _governance(before.value, "proceed"), _governance(after.value, "proceed")
                    )
                except TreatmentWidenedError:
                    widened = True
                assert widened is not is_narrowing(before, after)


class TestTheDecisionReducer:
    """First valid decision wins (spec FR-INTR-010)."""

    def test_the_first_decision_is_kept(self) -> None:
        first = _decision("approval", "approved")
        second = _decision("approval", "rejected")
        assert seal_human_decision(first, second) == first

    def test_a_second_decision_does_not_raise(self) -> None:
        """Two staff opening the same queue item is a race, not a defect.

        The later verdict is recorded on the durable approval row, where the audit trail needs
        it. Here it is simply dropped, because it changed nothing.
        """
        assert seal_human_decision(_decision("approval", "approved"), None) is not None


class TestTheExecutionAndVerificationReducers:
    """One authorization, at most one execution (spec FR-EXEC-004, FR-EXEC-006)."""

    def test_an_identical_replay_is_accepted(self) -> None:
        """LangGraph replays pending writes on resume; an identical write is normal."""
        record = _execution("executed")
        assert seal_execution(record, dict(record)) == record  # type: ignore[arg-type]

    def test_a_differing_second_execution_is_refused(self) -> None:
        """A failed authorized action does not re-fire; it needs fresh human authorization."""
        with pytest.raises(StateChannelSealedError):
            seal_execution(_execution("failed"), _execution("executed"))

    def test_a_differing_second_verification_is_refused(self) -> None:
        """What the platform knows is not revisable by a later pass through the graph."""
        with pytest.raises(StateChannelSealedError):
            seal_verification(_verification("client_attested"), _verification("server_confirmed"))


def _governance(treatment: str, disposition: str) -> GovernanceResult:
    return {
        "treatment": treatment,  # type: ignore[typeddict-item]
        "treatment_reason": "catalogue_default",
        "disposition": disposition,  # type: ignore[typeddict-item]
        "reason": "test",
        "decided_at": "2026-09-16T12:00:00+00:00",
    }


def _decision(kind: str, verdict: str) -> HumanDecisionRecord:
    return {
        "kind": kind,  # type: ignore[typeddict-item]
        "decision_id": "d1",
        "decided_by": "p1",
        "verdict": verdict,
        "decided_at": "2026-09-16T12:00:00+00:00",
        "expires_at": None,
    }


def _execution(status: str) -> ExecutionRecord:
    return {
        "status": status,  # type: ignore[typeddict-item]
        "idempotency_key": "k1",
        "executed_by": "workload",
        "execution_method": "workload",
        "attempted_at": "2026-09-16T12:00:00+00:00",
        "detail": {},
    }


def _verification(outcome: str) -> VerificationRecord:
    return {
        "outcome": outcome,  # type: ignore[typeddict-item]
        "verified_by": None,
        "verified_at": "2026-09-16T12:00:00+00:00",
    }
