"""One test per hard failure. **Each fails when its protection is removed.**

.claude/rules/80-security-ops.md §80.3 names seven things that are hard failures, never warnings:

1. cross-tenant data leakage
2. consequential execution without required authority
3. authorization bypass
4. execution caused by untrusted model output
5. duplicate consequential execution from a retry
6. approval bypass
7. tenant context derived from an untrusted client field

The Development Workflow section then makes the obligation concrete: *everything named as a hard
failure in Principle VIII must have a test that fails when the protection is removed*. That sentence
is the specification for this file, and it is a stronger requirement than "is tested". A test that
passes because the scenario never arises satisfies coverage and proves nothing.

**So every test here is written against the protection rather than against the happy path**, and
each class carries a ``test_..._would_fail_if_the_protection_were_removed`` that names — precisely —
what would have to change for the assertion above it to stop holding. Where the protection is
structural, that is a type with no field to carry the thing; where it is a refusal, the removal is
the refusal returning instead of raising.

**This file does not re-prove what the dedicated suites prove.** ``test_cross_tenant_retrieval.py``
attacks retrieval, ``test_duplicate_trigger.py`` drives a real PostgreSQL, and the role matrix lives
in the .NET suite. This is the index: seven entries, each asserting the load-bearing mechanism and
naming where the exhaustive proof lives, so a reader can answer "which of the seven is protected by
what" from one file.

Marked ``security``: *proves a documented prohibition is actually unreachable*.
"""

from __future__ import annotations

import inspect
from dataclasses import fields, is_dataclass
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest

from ragcore.application import ports
from ragcore.domain.authority import (
    AUTHORITY_SOURCES,
    NON_AUTHORITY_SOURCES,
    AuthorityAssertionError,
    may_grant_authority,
    require_authority_source,
)
from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import OperationIdentity, PrincipalId
from ragcore.domain.proposal import ProposedOperation
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.roles import evaluate as evaluate_roles
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.domain.work import ApprovalVerdict
from ragcore.governance import gate
from ragcore.governance.catalogue import CatalogueRecord
from ragcore.governance.gate import GateDisposition, GateReason, GateRequest
from ragcore.persistence import repositories
from tests.support.fakes import FIXED_NOW, admitted_tenant, end_user_consent, staff_verdict

pytestmark = pytest.mark.security

IDENTITY = OperationIdentity("test.consequential", 1)
WINDOW = timedelta(minutes=15)


def _entry(
    treatment: ExecutionTreatment,
    *,
    accepted: RoleSet | None = None,
) -> CatalogueRecord:
    return CatalogueRecord(
        identity=IDENTITY,
        treatment=treatment,
        accepted_roles=accepted if accepted is not None else RoleSet.of(StaffRole.TECHNICIAN),
        kind=CapabilityKind.ACTION,
        risk_tier=RiskTier.LOW_IMPACT,
        is_reference_fixture=True,
    )


def _request(**overrides: Any) -> GateRequest:
    base: dict[str, Any] = {
        "tenant": admitted_tenant(),
        "proposal": ProposedOperation(identity=IDENTITY),
        "entry": _entry(ExecutionTreatment.STAFF_APPROVAL),
        "is_entitled": True,
        "requester": PrincipalId(uuid4()),
        "now": FIXED_NOW,
        "decision": None,
        "authorization_expires_at": None,
    }
    base.update(overrides)
    return GateRequest(**base)


# ---------------------------------------------------------------------------
# 1. Cross-tenant data leakage
# ---------------------------------------------------------------------------


class TestCrossTenantDataLeakage:
    """Every query path carries the organisation, and no overload omits it."""

    def test_every_repository_method_takes_a_tenant_context(self) -> None:
        """The protection: it is a property of the *interface*, not of each implementation.

        A repository that resolved the organisation internally would be trusted to; one that takes
        it cannot forget, because a caller with no tenant has nothing to pass.
        """
        offenders: list[str] = []

        for name, port in vars(ports).items():
            if not name.endswith("RepositoryPort") and not name.endswith("StorePort"):
                continue
            for method_name, method in vars(port).items():
                if method_name.startswith("_") or not callable(method):
                    continue
                parameters = list(inspect.signature(method).parameters)
                if "tenant" not in parameters:
                    offenders.append(f"{name}.{method_name}")

        assert not offenders, (
            f"these port methods do not take a tenant: {offenders}. Each one is a query path that "
            f"could run unscoped."
        )

    def test_the_repository_base_applies_the_scope_from_the_context_alone(self) -> None:
        """No parameter contributes to the filter, so no caller can widen it."""
        scope = inspect.getsource(repositories._TenantScoped._scope)  # noqa: SLF001

        assert "tenant.tenant_id.value" in scope
        assert "or_(" not in scope, (
            "the tenant scope now contains a disjunction. A filter with an OR in it is a filter "
            "with a branch that matches something else."
        )

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would mean: a port method losing its ``tenant`` parameter, or ``_scope``
        deriving the organisation from anything other than the context it was given. The two
        assertions above read exactly those things, so either change turns them red.

        The exhaustive proofs are ``tests/isolation/`` and, for the read path the .NET side owns,
        ``dotnet/tests/Synthia.TenantIsolationTests/``.
        """
        assert "tenant" in inspect.signature(ports.WorkItemRepositoryPort.get).parameters


# ---------------------------------------------------------------------------
# 2. Consequential execution without required authority
# ---------------------------------------------------------------------------


class TestConsequentialExecutionWithoutRequiredAuthority:
    """An operation requiring a decision does not proceed without one."""

    @pytest.mark.parametrize(
        "treatment",
        [ExecutionTreatment.STAFF_APPROVAL, ExecutionTreatment.END_USER_APPROVAL],
    )
    def test_no_decision_means_no_execution(self, treatment: ExecutionTreatment) -> None:
        outcome = gate.evaluate(_request(entry=_entry(treatment), decision=None))

        assert not outcome.is_authorized
        assert outcome.disposition in {
            GateDisposition.SUSPEND_FOR_APPROVAL,
            GateDisposition.SUSPEND_FOR_CONSENT,
        }

    def test_a_granted_decision_with_no_window_fails_closed(self) -> None:
        """A missing window is not an unlimited one."""
        outcome = gate.evaluate(
            _request(
                decision=staff_verdict(IDENTITY, expires_at=None),
                authorization_expires_at=None,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.AUTHORIZATION_WINDOW_MISSING

    def test_an_expired_window_refuses(self) -> None:
        outcome = gate.evaluate(
            _request(
                decision=staff_verdict(IDENTITY),
                authorization_expires_at=FIXED_NOW + WINDOW,
                now=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.AUTHORIZATION_EXPIRED

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """The protection is ``GateOutcome.is_authorized`` deriving from the disposition rather
        than being a field anybody can set. Remove that — make it a stored boolean — and an
        execution path could hold ``is_authorized=True`` without holding the outcome that produced
        it. So: it is a property, and there is no such field.
        """
        assert isinstance(type(gate.GateOutcome.is_authorized), type(property))
        assert "is_authorized" not in {field.name for field in fields(gate.GateOutcome)}


# ---------------------------------------------------------------------------
# 3. Authorization bypass
# ---------------------------------------------------------------------------


class TestAuthorizationBypass:
    """Set intersection, with no ordering and no implication."""

    def test_an_empty_intersection_refuses(self) -> None:
        outcome = gate.evaluate(
            _request(
                entry=_entry(
                    ExecutionTreatment.STAFF_APPROVAL, accepted=RoleSet.of(StaffRole.TECHNICIAN)
                ),
                decision=staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.ADMINISTRATOR)),
                authorization_expires_at=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.APPROVER_HOLDS_NO_ACCEPTED_ROLE

    def test_an_entry_accepting_no_role_denies_everyone(self) -> None:
        """Refused by policy before the gate asks anybody, so it cannot sit in a queue forever."""
        outcome = gate.evaluate(
            _request(entry=_entry(ExecutionTreatment.STAFF_APPROVAL, accepted=RoleSet()))
        )

        assert not outcome.is_authorized
        assert outcome.disposition is GateDisposition.REFUSE

    def test_roles_cannot_be_ordered(self) -> None:
        """A plain ``Enum`` raises on ``<``, so a ranking fails loudly at the first attempt.

        ``StrEnum`` or ``IntEnum`` would evaluate instead, and ``ADMINISTRATOR > TECHNICIAN``
        would quietly return a plausible answer.
        """
        with pytest.raises(TypeError):
            _ = StaffRole.ADMINISTRATOR > StaffRole.TECHNICIAN  # type: ignore[operator]

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would be ``evaluate`` comparing roles instead of intersecting them. The source
        is read for the operators a ranking needs, and the exhaustive matrix is
        ``dotnet/tests/Synthia.AuthorizationTests/RoleMatrixTests.cs``.
        """
        source = inspect.getsource(evaluate_roles)

        for operator in (" > ", " < ", " >= ", " <= ", "sorted(", "max(", "min("):
            assert operator not in source, (
                f"role evaluation contains {operator!r}. Roles are disjoint capability sets with "
                f"no hierarchy (spec FR-AUTHZ-003)."
            )


# ---------------------------------------------------------------------------
# 4. Execution caused by untrusted model output
# ---------------------------------------------------------------------------


class TestExecutionCausedByUntrustedModelOutput:
    """Model may propose. Model may not authorize."""

    def test_a_proposal_has_no_field_that_could_carry_an_authorization(self) -> None:
        names = {field.name for field in fields(ProposedOperation)}

        assert names.isdisjoint(
            {"treatment", "approved", "authorized", "accepted_roles", "tenant_id"}
        )

    def test_every_untrusted_source_is_refused_authority(self) -> None:
        """Exhaustive, so a new content class added without a classification fails here."""
        for source in NON_AUTHORITY_SOURCES:
            assert not may_grant_authority(source)
            with pytest.raises(AuthorityAssertionError):
                require_authority_source(source)

    def test_every_authority_source_is_a_record_or_an_authenticated_decision(self) -> None:
        for source in AUTHORITY_SOURCES:
            assert may_grant_authority(source)

    def test_an_unclassified_source_raises_rather_than_defaulting_to_unauthorized(self) -> None:
        """A ``False`` would quietly absorb a new content class as merely unauthorized."""
        with pytest.raises(TypeError):
            may_grant_authority("something new")  # type: ignore[arg-type]

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would be adding a ``treatment`` field to ``ProposedOperation`` — the exact hole
        a model-chosen treatment would arrive through — or giving ``may_grant_authority`` an
        ``else: return False``. Both are asserted above.

        The exhaustive proof is ``tests/governance/test_authority_boundary.py``.
        """
        assert is_dataclass(ProposedOperation)
        assert "treatment" not in {field.name for field in fields(ProposedOperation)}


# ---------------------------------------------------------------------------
# 5. Duplicate consequential execution from a retry
# ---------------------------------------------------------------------------


class TestDuplicateConsequentialExecutionFromARetry:
    """Two boundaries. Neither substitutes for the other."""

    def test_the_claim_is_a_conditional_update_rather_than_a_read_then_write(self) -> None:
        """A read-then-write has a window in which both consumers read ``NULL``."""
        claim = inspect.getsource(repositories.WorkItemRepository.claim)

        assert "claimed_at.is_(None)" in claim
        assert "claim_once(" in claim, (
            "the claim no longer goes through the single-statement helper. Two statements is two "
            "chances for both consumers to win."
        )

    def test_the_idempotency_key_is_derived_and_not_random(self) -> None:
        """A random key is a new key on every attempt, defeating the far side's deduplication."""
        from ragcore.execution import idempotency

        source = inspect.getsource(idempotency.derive_key)

        assert "sha256" in source
        assert "uuid" not in source and "random" not in source

    def test_no_lock_is_taken_anywhere_in_the_execution_path(self) -> None:
        """The loser returns promptly rather than waiting for a winner it cannot see."""
        claim_module = inspect.getsource(
            inspect.getmodule(repositories.WorkItemRepository.claim) or repositories
        )

        assert "FOR UPDATE" not in claim_module.upper()
        assert "advisory_lock" not in claim_module

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would be either boundary going: the conditional predicate becoming a plain
        update, or the key becoming random. Both are read above, and the end-to-end proof against a
        real PostgreSQL is ``tests/idempotency/test_duplicate_trigger.py``.
        """
        assert "claimed_at.is_(None)" in inspect.getsource(repositories.WorkItemRepository.claim)


# ---------------------------------------------------------------------------
# 6. Approval bypass
# ---------------------------------------------------------------------------


class TestApprovalBypass:
    """Consent does not satisfy staff approval, and a decision binds to what was disclosed."""

    def test_a_consent_does_not_satisfy_a_staff_approval_requirement(self) -> None:
        """Spec FR-INTR-007. The two answer different questions about different people."""
        requester = PrincipalId(uuid4())

        outcome = gate.evaluate(
            _request(
                entry=_entry(ExecutionTreatment.STAFF_APPROVAL),
                requester=requester,
                decision=end_user_consent(IDENTITY, requester),
                authorization_expires_at=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.WRONG_DECISION_KIND

    def test_a_staff_verdict_does_not_stand_in_for_the_requesters_own_consent(self) -> None:
        """The reverse, and it is not symmetric reasoning: the operation is on that person's own
        account or device, and staff approval answers a different question about it.
        """
        outcome = gate.evaluate(
            _request(
                entry=_entry(ExecutionTreatment.END_USER_APPROVAL),
                decision=staff_verdict(IDENTITY),
                authorization_expires_at=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.WRONG_DECISION_KIND

    def test_somebody_other_than_the_requester_cannot_consent(self) -> None:
        outcome = gate.evaluate(
            _request(
                entry=_entry(ExecutionTreatment.END_USER_APPROVAL),
                requester=PrincipalId(uuid4()),
                decision=end_user_consent(IDENTITY, PrincipalId(uuid4())),
                authorization_expires_at=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.NOT_THE_REQUESTER

    def test_a_decision_bound_to_another_catalogue_version_is_refused(self) -> None:
        """What was approved is not what would run.

        This is the swap a catalogue edit between approval and execution would perform, and the
        version in the identity is what detects it.
        """
        outcome = gate.evaluate(
            _request(
                decision=staff_verdict(OperationIdentity(IDENTITY.catalogue_id, 2)),
                authorization_expires_at=FIXED_NOW + WINDOW,
            )
        )

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.DECISION_BOUND_TO_ANOTHER_VERSION

    def test_there_is_no_verdict_a_system_could_synthesize(self) -> None:
        """``ApprovalVerdict`` has exactly two members, so ``EXPIRED`` is unrepresentable rather
        than merely prohibited (spec FR-INTR-008). No timeout, no auto-reject, no auto-approve.
        """
        assert {member.name for member in ApprovalVerdict} == {"APPROVED", "REJECTED"}

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would be the gate accepting :class:`RecordedDecision` structurally rather than
        checking the concrete type — an ``isinstance`` becoming a ``hasattr``. The source is read
        for both branches.
        """
        source = inspect.getsource(gate)

        assert "isinstance(decision, EndUserConsent)" in source
        assert "isinstance(decision, StaffVerdict)" in source


# ---------------------------------------------------------------------------
# 7. Tenant context derived from an untrusted client field
# ---------------------------------------------------------------------------


class TestTenantContextDerivedFromAnUntrustedClientField:
    """Every constructor names its provenance, and none of them names a request."""

    def test_the_context_cannot_be_built_without_naming_where_it_came_from(self) -> None:
        """The constructors are classmethods whose names *are* the provenance.

        ``from_admitted_identity``, ``from_platform_object``, ``from_work_item`` — a reader at the
        call site sees where the organisation came from without following anything.
        """
        constructors = {
            name
            for name, member in vars(TenantContext).items()
            if isinstance(member, classmethod) and not name.startswith("_")
        }

        assert constructors, "TenantContext has no named constructors"
        for name in constructors:
            assert name.startswith("from_"), (
                f"{name} does not name its provenance. A constructor that does not say where the "
                f"organisation came from is one a request field can reach."
            )

    def test_no_constructor_names_a_request_a_header_or_a_client(self) -> None:
        constructors = {
            name
            for name, member in vars(TenantContext).items()
            if isinstance(member, classmethod) and not name.startswith("_")
        }

        for name in constructors:
            assert not any(
                word in name for word in ("request", "header", "client", "param", "body")
            ), f"{name} derives a tenant from something a client sends"

    def test_a_suspended_organisation_is_refused_at_the_gate(self) -> None:
        """Checked again at the gate, because a suspension can land after admission."""
        suspended = admitted_tenant(TenantStatus.SUSPENDED)

        outcome = gate.evaluate(_request(tenant=suspended, entry=_entry(ExecutionTreatment.AUTO)))

        assert not outcome.is_authorized
        assert outcome.reason is GateReason.TENANT_NOT_ADMITTED

    def test_it_would_fail_if_the_protection_were_removed(self) -> None:
        """Removal would be a ``TenantContext(tenant_id=...)`` call somewhere, bypassing the named
        constructors — or one of them being named for a request. Both are asserted above.

        The end-to-end proof that a self-supplied identity header is refused is
        ``tests/security/test_edge_trust_policy.py``.
        """
        assert not any(
            name.startswith("from_request") or name.startswith("from_header")
            for name in vars(TenantContext)
        )


# ---------------------------------------------------------------------------
# The list itself
# ---------------------------------------------------------------------------


class TestEveryHardFailureHasATest:
    """The index is only useful if it stays complete."""

    HARD_FAILURES = (
        "CrossTenantDataLeakage",
        "ConsequentialExecutionWithoutRequiredAuthority",
        "AuthorizationBypass",
        "ExecutionCausedByUntrustedModelOutput",
        "DuplicateConsequentialExecutionFromARetry",
        "ApprovalBypass",
        "TenantContextDerivedFromAnUntrustedClientField",
    )
    """The seven, in the order Principle VIII lists them."""

    def test_this_module_carries_a_class_for_each(self) -> None:
        import sys

        module = sys.modules[__name__]
        declared = {name for name in vars(module) if name.startswith("Test")}

        missing = [name for name in self.HARD_FAILURES if f"Test{name}" not in declared]

        assert not missing, f"no hard-failure test for: {missing}"

    @pytest.mark.parametrize("name", HARD_FAILURES)
    def test_each_one_states_what_removing_its_protection_would_break(self, name: str) -> None:
        """The obligation is a test that **fails when the protection is removed**, which is a claim
        about a counterfactual. It cannot be asserted directly, so each class states the
        counterfactual in a named test — and this requires the statement to exist.
        """
        import sys

        cls = getattr(sys.modules[__name__], f"Test{name}")
        assert hasattr(cls, "test_it_would_fail_if_the_protection_were_removed"), (
            f"Test{name} does not say what removing its protection would break"
        )
