"""Verdict and status types (contract-freeze findings F-1, F-2, F-6, F-7).

These exist because the first version of ``ApprovalRepositoryPort.record_verdict`` took
``ApprovalState`` — the work item's field, which also carries ``pending`` and ``expired``. That
signature made ``record_verdict(state=ApprovalState.EXPIRED)`` type-check: a system-synthesized
verdict, which §17.7 and FR-INTR-008 prohibit outright.

The narrower type is what makes the prohibited call unrepresentable rather than merely forbidden.
These tests are what stop the two types being merged back together by someone tidying up.
"""

from __future__ import annotations

import inspect

import pytest

from ragcore.application.ports import ApprovalRepositoryPort, ConsentRepositoryPort
from ragcore.domain.governance import ExecutionMethod
from ragcore.domain.work import (
    ApprovalState,
    ApprovalVerdict,
    ConsentVerdict,
    OperationStatus,
    WorkItemState,
)


class TestApprovalVerdictCannotExpressASynthesizedVerdict:
    """F-1. The whole point of the type."""

    def test_has_exactly_two_members(self) -> None:
        assert {v.value for v in ApprovalVerdict} == {"approved", "rejected"}

    @pytest.mark.parametrize("forbidden", ["expired", "pending", "none", "timeout", "auto"])
    def test_carries_no_member_that_would_be_a_synthesized_verdict(self, forbidden: str) -> None:
        """§17.7: no timeout, no auto-reject, no system-synthesized verdict."""
        assert forbidden not in {v.value for v in ApprovalVerdict}

    def test_the_work_item_state_still_carries_what_a_verdict_must_not(self) -> None:
        """Merging the two enums is the regression this file exists to catch.

        Identity (``is not``) would be statically decidable and prove nothing. What matters is
        that the value sets stay different: ``ApprovalState`` legitimately carries ``pending`` and
        ``expired``, and a verdict must carry neither.
        """
        state_values = {s.value for s in ApprovalState}
        verdict_values = {v.value for v in ApprovalVerdict}

        assert {"pending", "expired"} <= state_values
        assert not ({"pending", "expired"} & verdict_values)

    def test_the_port_takes_a_verdict_not_a_state(self) -> None:
        """Asserts the signature, because the type only helps if the port actually uses it."""
        signature = inspect.signature(ApprovalRepositoryPort.record_verdict)
        annotation = signature.parameters["verdict"].annotation
        assert "ApprovalVerdict" in str(annotation)
        assert "ApprovalState" not in str(annotation)

    def test_no_expired_member_to_pass(self) -> None:
        """The prohibited call has nothing to pass. That is the guarantee."""
        assert not hasattr(ApprovalVerdict, "EXPIRED")
        assert not hasattr(ApprovalVerdict, "PENDING")


class TestConsentVerdictIsNotABoolean:
    """F-2. Principle VI: no boolean parameter flag that hides behaviour."""

    def test_has_exactly_two_named_members(self) -> None:
        assert {v.value for v in ConsentVerdict} == {"granted", "refused"}

    def test_the_port_takes_a_verdict_not_a_bool(self) -> None:
        signature = inspect.signature(ConsentRepositoryPort.record)
        annotation = str(signature.parameters["verdict"].annotation)
        assert "ConsentVerdict" in annotation
        assert annotation != "bool"

    def test_mirrors_the_two_consent_trigger_kinds(self) -> None:
        """The database enum, the trigger kinds and this type must not drift apart."""
        from ragcore.domain.envelopes import TriggerKind

        consent_kinds = {
            k.value.split(".", 1)[1] for k in TriggerKind if k.value.startswith("consent.")
        }
        assert consent_kinds == {v.value for v in ConsentVerdict}


class TestOperationStatus:
    """F-6. Present because ``gated`` and ``refused`` are not expressible anywhere else."""

    def test_matches_the_data_model(self) -> None:
        assert {s.value for s in OperationStatus} == {
            "proposed",
            "gated",
            "authorized",
            "executed",
            "failed",
            "refused",
        }

    def test_refused_exists_so_a_denial_is_recordable(self) -> None:
        """FR-AUDIT-003: decisions that deny are recorded as durably as decisions that permit."""
        assert OperationStatus.REFUSED.value == "refused"

    def test_carries_states_the_work_item_does_not(self) -> None:
        """A work item is the authority record; an operation is one action within it.

        ``gated`` and ``proposed`` exist only here — which is the reason the type is needed
        rather than folding the operation lifecycle into the work item.
        """
        assert {"gated", "proposed"} <= {s.value for s in OperationStatus}
        assert not ({"gated", "proposed"} & {s.value for s in WorkItemState})


class TestExecutionMethod:
    """F-7. §28.3 separates the execution mechanism from the execution actor."""

    def test_matches_the_data_model(self) -> None:
        assert {m.value for m in ExecutionMethod} == {"workload", "desktop_script", "none"}

    def test_none_exists_so_a_non_execution_is_recordable(self) -> None:
        """Refused, expired or cancelled work still produces an audit record."""
        assert ExecutionMethod.NONE.value == "none"


class TestNoneOfTheseOrder:
    """Every one of these is a plain Enum, for the same reason StaffRole is."""

    @pytest.mark.parametrize(
        "enum_type",
        [ApprovalVerdict, ConsentVerdict, OperationStatus, ExecutionMethod],
    )
    def test_members_cannot_be_compared(self, enum_type: type) -> None:
        members = list(enum_type)  # type: ignore[call-overload]
        with pytest.raises(TypeError):
            _ = members[0] < members[1]
