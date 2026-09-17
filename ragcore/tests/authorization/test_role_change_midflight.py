"""A role change does not rewrite a recorded decision, and does not cancel authorized work.

`FR-AUTHZ-011` has three clauses and they are easy to collapse into two:

1. Authorization is evaluated against the roles held **at the moment of decision**.
2. That role set is **recorded with the decision**.
3. A later change to a person's roles **neither** retroactively alters the recorded decision **nor**
   by itself cancels work already authorized.

The third clause is the one worth testing, and it cuts both ways. Revoking a role must not
invalidate an approval a technician gave while they held it — the decision was sound when it was
made, and re-deciding it later against a role set nobody had at the time is not a stricter system,
it is a system that cannot say what it authorized. And *granting* a role must not retroactively
make a decision valid that was not.

**The mechanism is that there is nothing to re-resolve.** ``StaffVerdict.roles_held`` is a stored
field, and the gate evaluates set intersection against it rather than against whatever the directory
says now. The tests below drive that by changing the "current" roles and observing that the outcome
does not move — but the last two read the types, because the property is structural: the gate has no
parameter through which a current role set could arrive, and there is no directory it could consult.

**Scope.** These exercise the *gate*, not an approval workflow. No approval or consent workflow
exists in the scaffold (spec FR-DEMO-016), and the decisions here are constructed exactly as
``tests/support/fakes.py`` constructs them — as the approval repository would return them.

Marked ``approval``: *proves binding, expiry, first-valid-verdict-wins*.
"""

from __future__ import annotations

import inspect
from datetime import timedelta
from uuid import uuid4

import pytest

from ragcore.domain.decisions import StaffVerdict
from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import OperationIdentity, PrincipalId
from ragcore.domain.proposal import ProposedOperation
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.work import ApprovalVerdict
from ragcore.governance import gate
from ragcore.governance.catalogue import CatalogueRecord
from ragcore.governance.gate import GateDisposition, GateReason, GateRequest
from tests.support.fakes import FIXED_NOW, admitted_tenant, staff_verdict

pytestmark = pytest.mark.approval

IDENTITY = OperationIdentity("test.staff-operation", 1)


def _entry(accepted: RoleSet) -> CatalogueRecord:
    return CatalogueRecord(
        identity=IDENTITY,
        treatment=ExecutionTreatment.STAFF_APPROVAL,
        accepted_roles=accepted,
        kind=CapabilityKind.ACTION,
        risk_tier=RiskTier.LOW_IMPACT,
        is_reference_fixture=True,
    )


def _request(verdict: StaffVerdict, *, accepted: RoleSet) -> GateRequest:
    return GateRequest(
        tenant=admitted_tenant(),
        proposal=ProposedOperation(identity=IDENTITY),
        entry=_entry(accepted),
        is_entitled=True,
        requester=PrincipalId(uuid4()),
        now=FIXED_NOW + timedelta(minutes=1),
        decision=verdict,
        authorization_expires_at=FIXED_NOW + timedelta(minutes=15),
    )


class TestARevokedRoleDoesNotUnmakeADecision:
    """The decision was sound when it was made, and stays sound."""

    def test_work_approved_by_a_technician_stays_authorized_after_the_role_is_revoked(self) -> None:
        """The person no longer holds ``technician``. The verdict still records that they did.

        Re-resolving here would mean the platform could not answer "what did we authorize, and on
        what basis" — the basis would be whatever the directory says at the moment somebody asks.
        """
        approver = PrincipalId(uuid4())
        verdict = staff_verdict(
            IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN), decided_by=approver
        )

        # The revocation happens here, in the only place it could: the directory. Nothing about
        # the recorded verdict changes, because nothing reads the directory again.
        current_roles_after_revocation = RoleSet()
        assert current_roles_after_revocation.is_empty

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.disposition is GateDisposition.PROCEED
        assert outcome.reason is GateReason.APPROVAL_GRANTED

    def test_the_recorded_role_set_is_what_the_gate_intersected(self) -> None:
        """Not merely that the outcome was right — that it was right *for the stored reason*."""
        verdict = staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN))

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.authorization is not None
        assert outcome.authorization.is_permitted
        assert verdict.roles_held.contains(StaffRole.TECHNICIAN)

    def test_a_verdict_is_immutable(self) -> None:
        """A recorded decision cannot be edited, so it cannot be edited by a role change either."""
        verdict = staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN))

        with pytest.raises((AttributeError, TypeError)):
            verdict.roles_held = RoleSet()  # type: ignore[misc]


class TestAGrantedRoleDoesNotMakeAPastDecisionValid:
    """The other direction, and the one a permissive implementation gets wrong."""

    def test_a_verdict_given_without_an_accepted_role_stays_refused(self) -> None:
        """Somebody who held only ``administrator`` decided. Granting them ``technician`` later
        does not turn that into an approval — the decision recorded what they held at the time.
        """
        verdict = staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.ADMINISTRATOR))

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.APPROVER_HOLDS_NO_ACCEPTED_ROLE

    def test_administrator_still_does_not_imply_technician(self) -> None:
        """Restated here because this is where somebody would be tempted to add the implication.

        The mid-flight scenario — "they are an admin now, surely that covers it" — is exactly the
        argument that introduces a hierarchy (spec FR-AUTHZ-003).
        """
        verdict = staff_verdict(
            IDENTITY, roles=RoleSet.of(StaffRole.ADMINISTRATOR, StaffRole.SENIOR_TECHNICIAN)
        )

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.disposition is GateDisposition.REFUSE


class TestARoleChangeDoesNotCancelAuthorizedWork:
    """Cancellation is an action somebody takes. It is not a side effect of a directory edit."""

    @pytest.mark.parametrize(
        "roles_now",
        [
            RoleSet(),
            RoleSet.of(StaffRole.END_USER),
            RoleSet.of(StaffRole.ADMINISTRATOR),
            RoleSet.of(StaffRole.SENIOR_TECHNICIAN),
        ],
    )
    def test_the_outcome_is_unchanged_whatever_the_approver_holds_now(
        self, roles_now: RoleSet
    ) -> None:
        """The gate is evaluated four times against four different "current" role sets.

        It produces the same answer every time, because the current set is not one of its inputs.
        """
        verdict = staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN))
        del roles_now  # Nothing consumes it. That absence is the assertion.

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.disposition is GateDisposition.PROCEED

    def test_a_rejection_also_stands(self) -> None:
        """Symmetry. A role change does not resurrect work somebody declined."""
        verdict = staff_verdict(
            IDENTITY,
            verdict=ApprovalVerdict.REJECTED,
            roles=RoleSet.of(StaffRole.TECHNICIAN),
        )

        outcome = gate.evaluate(_request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN)))

        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.APPROVAL_REJECTED

    def test_the_window_still_governs_expiry(self) -> None:
        """What *does* end authorized work is time, not a role edit.

        Asserted so the suite above is not read as "nothing ever invalidates an approval".
        """
        verdict = staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN))
        request = _request(verdict, accepted=RoleSet.of(StaffRole.TECHNICIAN))
        expired = GateRequest(
            tenant=request.tenant,
            proposal=request.proposal,
            entry=request.entry,
            is_entitled=True,
            requester=request.requester,
            now=FIXED_NOW + timedelta(minutes=16),
            decision=verdict,
            authorization_expires_at=FIXED_NOW + timedelta(minutes=15),
        )

        outcome = gate.evaluate(expired)

        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.AUTHORIZATION_EXPIRED


class TestTheGateCannotConsultCurrentRolesEvenIfItWantedTo:
    """Structural, and the part that survives a rewrite of everything above."""

    def test_a_gate_request_carries_no_current_role_set(self) -> None:
        """A field for "roles now" is the field a re-resolution would read."""
        fields = set(GateRequest.__dataclass_fields__)

        assert fields.isdisjoint({"roles", "current_roles", "roles_now", "directory"}), (
            f"GateRequest gained {sorted(fields & {'roles', 'current_roles', 'roles_now'})}. "
            f"Authorization is evaluated against the roles held at the moment of decision."
        )

    def test_the_gate_reads_roles_only_from_the_recorded_decision(self) -> None:
        """One call site, and it takes ``decision.roles_held``.

        Read from the source because an implementation could satisfy every behavioural test above
        while also consulting a directory on some branch none of them reaches.
        """
        source = inspect.getsource(gate)

        assert "evaluate_roles(decision.roles_held, entry.accepted_roles)" in source, (
            "the gate no longer intersects the RECORDED role set with the entry's accepted roles"
        )
        assert source.count("evaluate_roles(") == 1, (
            "there is now more than one role evaluation in the gate. Each one is a place the set "
            "could come from somewhere other than the recorded decision."
        )
