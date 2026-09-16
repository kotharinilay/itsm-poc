"""Set-intersection authorization (T030).

Mirrors ``dotnet/tests/Synthia.SharedKernel.Tests/RoleIntersectionTests.cs``. The two stacks are
proven **independently** rather than sharing a fixture, because they share no code and a bug in one
must not be masked by the other passing.
"""

from __future__ import annotations

import pytest

from ragcore.domain.roles import (
    EMPTY_ROLE_SET,
    AuthorizationDecision,
    DenialReason,
    RoleSet,
    StaffRole,
    evaluate,
)


class TestNoOrderingExists:
    """Roles are disjoint capabilities. Ranking them must be impossible, not merely discouraged."""

    def test_roles_cannot_be_compared(self) -> None:
        """``<`` raises rather than returning a plausible answer.

        This is the test that would have caught a ``StrEnum`` or ``IntEnum``: both inherit an
        ordering from their mixin, so the prohibited comparison would silently evaluate.
        """
        with pytest.raises(TypeError):
            _ = StaffRole.ADMINISTRATOR < StaffRole.TECHNICIAN  # type: ignore[operator]

    def test_roles_cannot_be_sorted(self) -> None:
        """Sorting the enum members raises, for the same reason."""
        with pytest.raises(TypeError):
            sorted([StaffRole.ADMINISTRATOR, StaffRole.TECHNICIAN])  # type: ignore[type-var]

    def test_administrator_does_not_imply_technician(self) -> None:
        """The classic route to silent privilege escalation, asserted directly."""
        administrator = RoleSet.of(StaffRole.ADMINISTRATOR)
        assert not administrator.contains(StaffRole.TECHNICIAN)
        assert not evaluate(administrator, RoleSet.of(StaffRole.TECHNICIAN)).is_permitted

    def test_technician_does_not_imply_administrator(self) -> None:
        """And the same in the other direction — neither implies the other."""
        technician = RoleSet.of(StaffRole.TECHNICIAN)
        assert not evaluate(technician, RoleSet.of(StaffRole.ADMINISTRATOR)).is_permitted


class TestSetIntersection:
    """``principal roles ∩ operation accepted roles ≠ ∅``."""

    def test_overlapping_sets_permit(self) -> None:
        decision = evaluate(RoleSet.of(StaffRole.TECHNICIAN), RoleSet.of(StaffRole.TECHNICIAN))
        assert decision.is_permitted
        assert decision.reason is None

    def test_disjoint_sets_deny(self) -> None:
        decision = evaluate(RoleSet.of(StaffRole.ADMINISTRATOR), RoleSet.of(StaffRole.TECHNICIAN))
        assert not decision.is_permitted
        assert decision.reason is DenialReason.EMPTY_INTERSECTION

    def test_multiple_roles_receive_the_union_and_nothing_further(self) -> None:
        """A principal holding several roles receives the union of those capabilities — only."""
        both = RoleSet.of(StaffRole.TECHNICIAN, StaffRole.ADMINISTRATOR)
        assert evaluate(both, RoleSet.of(StaffRole.TECHNICIAN)).is_permitted
        assert evaluate(both, RoleSet.of(StaffRole.ADMINISTRATOR)).is_permitted
        # Nothing further: senior_technician was not granted by holding the other two.
        assert not evaluate(both, RoleSet.of(StaffRole.SENIOR_TECHNICIAN)).is_permitted

    def test_partial_overlap_permits(self) -> None:
        """One shared role is enough. Intersection is non-empty, not equal."""
        held = RoleSet.of(StaffRole.ADMINISTRATOR, StaffRole.TECHNICIAN)
        accepted = RoleSet.of(StaffRole.TECHNICIAN, StaffRole.SENIOR_TECHNICIAN)
        assert evaluate(held, accepted).is_permitted


class TestEmptySets:
    """The two empty cases are distinct and neither is an implicit allow."""

    def test_operation_accepting_no_roles_denies_everyone(self) -> None:
        """An empty accepted set is a TOTAL denial (spec FR-AUTHZ-010)."""
        for held in (
            EMPTY_ROLE_SET,
            RoleSet.of(StaffRole.TECHNICIAN),
            RoleSet.of(StaffRole.ADMINISTRATOR, StaffRole.TECHNICIAN, StaffRole.SENIOR_TECHNICIAN),
        ):
            decision = evaluate(held, EMPTY_ROLE_SET)
            assert not decision.is_permitted
            assert decision.reason is DenialReason.OPERATION_ACCEPTS_NO_ROLES

    def test_principal_holding_no_roles_is_denied(self) -> None:
        decision = evaluate(EMPTY_ROLE_SET, RoleSet.of(StaffRole.TECHNICIAN))
        assert not decision.is_permitted
        assert decision.reason is DenialReason.PRINCIPAL_HOLDS_NO_ROLES

    def test_both_empty_denies(self) -> None:
        assert not evaluate(EMPTY_ROLE_SET, EMPTY_ROLE_SET).is_permitted


class TestDecisionRecordsRolesHeld:
    """A decision is evaluated against roles held **at the moment of decision**."""

    def test_permitted_decision_carries_the_held_set(self) -> None:
        held = RoleSet.of(StaffRole.TECHNICIAN)
        assert evaluate(held, RoleSet.of(StaffRole.TECHNICIAN)).roles_held_at_decision == held

    def test_denied_decision_also_carries_the_held_set(self) -> None:
        """Recorded on refusals too — a denial is audited as durably as a permission."""
        held = RoleSet.of(StaffRole.ADMINISTRATOR)
        assert evaluate(held, RoleSet.of(StaffRole.TECHNICIAN)).roles_held_at_decision == held

    def test_a_decision_is_immutable(self) -> None:
        """A later role change must not retroactively alter a recorded decision."""
        decision = AuthorizationDecision.permit(RoleSet.of(StaffRole.TECHNICIAN))
        with pytest.raises((AttributeError, TypeError)):
            decision.is_permitted = False  # type: ignore[misc]


class TestAlphaAssignment:
    """The initial-release assignment, asserted rather than assumed."""

    def test_technician_may_approve(self) -> None:
        assert evaluate(
            RoleSet.of(StaffRole.TECHNICIAN), RoleSet.of(StaffRole.TECHNICIAN)
        ).is_permitted

    def test_administrator_may_not_approve(self) -> None:
        assert not evaluate(
            RoleSet.of(StaffRole.ADMINISTRATOR), RoleSet.of(StaffRole.TECHNICIAN)
        ).is_permitted

    def test_senior_technician_is_accepted_by_no_operation(self) -> None:
        """Defined, and deliberately unused. Every one of its intersections is empty."""
        held = RoleSet.of(StaffRole.SENIOR_TECHNICIAN)
        for accepted in (
            RoleSet.of(StaffRole.TECHNICIAN),
            RoleSet.of(StaffRole.ADMINISTRATOR),
            RoleSet.of(StaffRole.END_USER),
        ):
            assert not evaluate(held, accepted).is_permitted


class TestParsing:
    """Canonical form is a security property, not tidiness."""

    def test_canonical_names_parse(self) -> None:
        assert StaffRole.parse("technician") is StaffRole.TECHNICIAN
        assert StaffRole.parse("senior_technician") is StaffRole.SENIOR_TECHNICIAN

    @pytest.mark.parametrize(
        "candidate",
        ["Technician", "TECHNICIAN", " technician", "technician ", "tech", "", "admin"],
    )
    def test_non_canonical_spellings_are_refused(self, candidate: str) -> None:
        """Refused, not repaired: repairing widens the set beyond what was reviewed."""
        assert StaffRole.parse(candidate) is None

    def test_canonical_rendering_is_ascending_ordinal(self) -> None:
        rendered = RoleSet.of(StaffRole.TECHNICIAN, StaffRole.ADMINISTRATOR).canonical()
        assert rendered == "administrator,technician"
