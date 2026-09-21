"""The authority boundary.

**MODEL MAY PROPOSE. MODEL MAY NOT AUTHORIZE.**

Everything in this file exists to make that sentence fail loudly if it stops being true. The
tests fall into four groups, in increasing order of how much they would hurt to lose:

1. **Classification** — every source the platform reads is classified, and the untrusted ones
   cannot grant authority. Exhaustive over both enumerations, so a new member added without a
   classification fails here.
2. **Structural impossibility** — the types themselves have no field through which an
   authorization could arrive. These are the tests that would survive a rewrite of the gate.
3. **Determinism** — the same catalogue state produces the same treatment, every time, and policy
   overrides only ever narrow.
4. **The gate** — every treatment reaches its correct disposition, and the specific substitutions
   the specification forbids are each refused.

Marked ``governance`` per ``pyproject.toml``: *proves treatment comes from the catalogue, never
from model output*.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime

from ragcore.application.ports import CatalogueEntry
from ragcore.domain.authority import (
    AUTHORITY_SOURCES,
    NON_AUTHORITY_SOURCES,
    AuthorityAssertionError,
    AuthoritySource,
    UntrustedContent,
    may_grant_authority,
    require_authority_source,
)
from ragcore.domain.decisions import RecordedDecision
from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import OperationIdentity, PrincipalId, WorkItemId
from ragcore.domain.proposal import ProposalSource, ProposedOperation
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.tenancy import TenantStatus
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict
from ragcore.governance import gate, policy
from ragcore.governance.gate import GateDisposition, GateReason, GateRequest
from ragcore.governance.policy import TreatmentReason, assign_treatment
from ragcore.graph.context import RunContext
from ragcore.graph.state import AgentState, GovernanceResult
from tests.support.fakes import (
    FIXED_NOW,
    FakeCatalogue,
    FakeCatalogueEntry,
    admitted_tenant,
    build_harness,
    end_user_consent,
    staff_verdict,
)

pytestmark = pytest.mark.governance

WINDOW = timedelta(minutes=15)
"""The execution validity window. Fifteen minutes, per A3 §8.5."""

# Bound to typed names rather than inlined into ``parametrize``, whose parameter type is
# ``Iterable[object]`` and would erase the enum type the sort key needs.
UNTRUSTED: list[UntrustedContent] = sorted(UntrustedContent, key=lambda member: member.value)
AUTHORITATIVE: list[AuthoritySource] = sorted(AuthoritySource, key=lambda member: member.value)


# ---------------------------------------------------------------------------
# 1. Classification — exhaustive over every source that exists
# ---------------------------------------------------------------------------


class TestEverySourceIsClassified:
    """Every source the platform reads is on exactly one side of the boundary."""

    @pytest.mark.parametrize("source", UNTRUSTED)
    def test_untrusted_content_cannot_grant_authority(self, source: UntrustedContent) -> None:
        """Retrieved, fetched, model and chat content confer nothing (spec FR-IDENT-003, -004)."""
        assert may_grant_authority(source) is False

    @pytest.mark.parametrize("source", AUTHORITATIVE)
    def test_authority_sources_may_grant_authority(self, source: AuthoritySource) -> None:
        """Durable records and authenticated human decisions are where authority comes from."""
        assert may_grant_authority(source) is True

    def test_the_four_named_prohibitions_are_each_represented(self) -> None:
        """The prompt's four prohibitions map onto members that exist and are refused.

        Named individually rather than covered by the parametrized sweep above, because the
        sweep passes trivially if somebody deletes a member. This fails if one goes missing.
        """
        for member in (
            UntrustedContent.MODEL_OUTPUT,
            UntrustedContent.RETRIEVED_CONTENT,
            UntrustedContent.VENDOR_RESPONSE,
            UntrustedContent.CHAT_TEXT,
        ):
            assert may_grant_authority(member) is False

    def test_the_two_enumerations_are_disjoint(self) -> None:
        """No value is both. A source that could be either is a source nobody has classified."""
        assert not {s.value for s in AUTHORITY_SOURCES} & {s.value for s in NON_AUTHORITY_SOURCES}

    def test_an_unclassified_source_raises_rather_than_defaulting(self) -> None:
        """A new content class must be classified, not silently absorbed as merely unauthorized.

        ``False`` would be the safe answer and the wrong behaviour: it would let a new source be
        added, quietly refused everywhere, and never noticed until somebody wonders why the
        feature does not work.
        """
        with pytest.raises(TypeError):
            may_grant_authority("a string somebody passed")  # type: ignore[arg-type]

    def test_require_authority_source_narrows_or_refuses(self) -> None:
        """The call-site assertion admits an authority source and refuses untrusted content."""
        assert (
            require_authority_source(AuthoritySource.DURABLE_WORK_RECORD)
            is AuthoritySource.DURABLE_WORK_RECORD
        )
        with pytest.raises(AuthorityAssertionError):
            require_authority_source(UntrustedContent.MODEL_OUTPUT)


# ---------------------------------------------------------------------------
# 2. Structural impossibility — no field through which authority could arrive
# ---------------------------------------------------------------------------


class TestAProposalCannotCarryAuthority:
    """The strongest guarantees here are absences, so they are asserted as absences."""

    FORBIDDEN_FIELDS = (
        "treatment",
        "approved",
        "authorized",
        "accepted_roles",
        "roles",
        "tenant_id",
        "tenant",
        "requires_approval",
        "auto",
    )

    def test_proposed_operation_declares_no_authority_field(self) -> None:
        """A model filling in a proposal has nowhere to write a decision."""
        assert is_dataclass(ProposedOperation)
        present = {f.name for f in fields(ProposedOperation)}
        for forbidden in self.FORBIDDEN_FIELDS:
            assert forbidden not in present, (
                f"ProposedOperation gained a {forbidden!r} field. The model fills this type in; "
                "a field it can write that governance then reads is the whole failure mode."
            )

    def test_the_graph_proposal_channel_declares_no_authority_field(self) -> None:
        """Same rule, restated for the checkpointed view the model actually writes."""
        from ragcore.graph.state import ProposedOperationView

        present = set(ProposedOperationView.__annotations__)
        for forbidden in self.FORBIDDEN_FIELDS:
            assert forbidden not in present

    def test_proposal_parameters_cannot_be_mutated_after_construction(self) -> None:
        """An approval binds what was disclosed; the parameters cannot change underneath it."""
        mutable = {"target": "original"}
        proposal = ProposedOperation(OperationIdentity("op", 1), mutable)

        mutable["target"] = "swapped"

        assert proposal.parameters["target"] == "original"
        with pytest.raises(TypeError):
            proposal.parameters["target"] = "swapped"  # type: ignore[index]

    def test_proposal_source_does_not_change_the_outcome(self) -> None:
        """A 'trustworthy' proposal is still only a proposal.

        If provenance could relax the gate, the promotion path would be to claim better
        provenance. Every source lands on the identical refusal.
        """
        catalogue = FakeCatalogue()
        identity = catalogue.register("unentitled.op", treatment=ExecutionTreatment.AUTO)
        outcomes = set()

        for source in ProposalSource:
            request = _request(
                identity=identity,
                entry=None,
                is_entitled=False,
                proposal_source=source,
            )
            outcomes.add(gate.evaluate(request).disposition)

        assert outcomes == {GateDisposition.REFUSE}


class TestTheGateCannotBeToldATreatment:
    """The gate derives the treatment. It never accepts one."""

    def test_gate_request_has_no_treatment_parameter(self) -> None:
        """A ``treatment`` field on the request is the hole a model-chosen treatment arrives by."""
        present = {f.name for f in fields(GateRequest)}
        assert "treatment" not in present
        assert "disposition" not in present
        assert "is_authorized" not in present

    def test_evaluate_takes_exactly_one_argument(self) -> None:
        """One argument means one place to look for everything the decision considered."""
        signature = inspect.signature(gate.evaluate)
        assert list(signature.parameters) == ["request"]

    def test_gate_and_policy_perform_no_io(self) -> None:
        """Purity, asserted statically rather than trusted.

        A gate that could reach a database could be handed a different catalogue than the one
        the caller read. This walks the AST because an ``await`` added inside a rarely-taken
        branch would not show up in any test that merely calls the function.
        """
        for module in (gate, policy):
            source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
            tree = ast.parse(source)
            offenders = [
                type(node).__name__
                for node in ast.walk(tree)
                if isinstance(node, ast.Await | ast.AsyncFunctionDef | ast.AsyncWith)
            ]
            assert not offenders, f"{module.__name__} became asynchronous: {offenders}"

    def test_governance_imports_no_provider_package(self) -> None:
        """Deterministic policy stays free of infrastructure it could be influenced through."""
        forbidden = {"httpx", "sqlalchemy", "asyncpg", "langgraph", "langchain", "fastapi", "mcp"}
        for module in (gate, policy):
            tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
            roots = {
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert not roots & forbidden


# ---------------------------------------------------------------------------
# 3. Determinism — the same inputs, the same treatment, every time
# ---------------------------------------------------------------------------


class TestTreatmentIsDeterministic:
    """Deterministic governance decides. Determinism is a property worth checking directly."""

    @pytest.mark.parametrize("treatment", list(ExecutionTreatment))
    def test_the_catalogue_default_stands_for_an_entitled_operation(
        self, treatment: ExecutionTreatment
    ) -> None:
        """All four treatments are assignable, and each comes straight from the catalogue."""
        entry = _entry(treatment=treatment)
        decision = assign_treatment(entry, is_entitled=True)
        assert decision.treatment is treatment

    def test_repeated_evaluation_returns_the_identical_decision(self) -> None:
        """No clock, no randomness, no I/O — so a hundred calls agree."""
        entry = _entry(treatment=ExecutionTreatment.STAFF_APPROVAL)
        decisions = {assign_treatment(entry, is_entitled=True) for _ in range(100)}
        assert len(decisions) == 1

    def test_a_missing_catalogue_entry_is_refused_not_defaulted(self) -> None:
        """Discovery is not entitlement (spec FR-EXT-014). ``None`` is a refusal."""
        decision = assign_treatment(None, is_entitled=True)
        assert decision.treatment is ExecutionTreatment.NOT_ALLOWED
        assert decision.reason is TreatmentReason.NOT_IN_CATALOGUE

    def test_an_unentitled_organisation_is_refused(self) -> None:
        """There is no global toolset; capabilities resolve per organisation (FR-EXT-015)."""
        decision = assign_treatment(_entry(treatment=ExecutionTreatment.AUTO), is_entitled=False)
        assert decision.treatment is ExecutionTreatment.NOT_ALLOWED
        assert decision.reason is TreatmentReason.NOT_ENTITLED

    def test_an_entry_claiming_elevation_is_refused(self) -> None:
        """This release permits no elevation (ADR-0004), belt as well as CHECK constraint."""
        entry = _entry(treatment=ExecutionTreatment.AUTO, requires_elevation=True)
        decision = assign_treatment(entry, is_entitled=True)
        assert decision.treatment is ExecutionTreatment.NOT_ALLOWED
        assert decision.reason is TreatmentReason.ELEVATION_REFUSED

    def test_staff_approval_with_no_accepted_role_is_refused_rather_than_unanswerable(
        self,
    ) -> None:
        """An operation accepting no roles denies everyone (FR-AUTHZ-010).

        The alternative — suspending on an approval nobody can give — would leave work pending
        forever and look like a stuck queue rather than a refusal.
        """
        entry = _entry(treatment=ExecutionTreatment.STAFF_APPROVAL, accepted_roles=RoleSet.of())
        decision = assign_treatment(entry, is_entitled=True)
        assert decision.treatment is ExecutionTreatment.NOT_ALLOWED
        assert decision.reason is TreatmentReason.NO_ROLE_CAN_APPROVE

    def test_policy_overrides_may_only_narrow(self) -> None:
        """A widening override is a defect and raises rather than shipping."""
        with pytest.raises(policy.PolicyWidenedTreatmentError):
            policy._narrowed(ExecutionTreatment.STAFF_APPROVAL, ExecutionTreatment.AUTO)

        assert (
            policy._narrowed(ExecutionTreatment.AUTO, ExecutionTreatment.NOT_ALLOWED)
            is ExecutionTreatment.NOT_ALLOWED
        )

    def test_there_is_no_treatment_for_undetermined(self) -> None:
        """No ``UNKNOWN`` member, so "carry on, we could not tell" is inexpressible."""
        assert {t.name for t in ExecutionTreatment} == {
            "AUTO",
            "END_USER_APPROVAL",
            "STAFF_APPROVAL",
            "NOT_ALLOWED",
        }


# ---------------------------------------------------------------------------
# 4. The gate — every treatment reaches its correct disposition
# ---------------------------------------------------------------------------


class TestTheGateAssignsTheRightDisposition:
    """The four treatments, and what each one does."""

    def test_auto_proceeds_without_a_human(self) -> None:
        request = _request(entry=_entry(treatment=ExecutionTreatment.AUTO), is_entitled=True)
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.PROCEED
        assert outcome.reason is GateReason.AUTO_TREATMENT
        assert outcome.is_authorized is True

    def test_not_allowed_refuses_and_is_never_askable(self) -> None:
        """A refused operation is never surfaced as an approvable proposal."""
        request = _request(entry=_entry(treatment=ExecutionTreatment.NOT_ALLOWED), is_entitled=True)
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.suspends_on is None
        assert outcome.is_authorized is False

    def test_end_user_approval_suspends_for_consent(self) -> None:
        request = _request(
            entry=_entry(treatment=ExecutionTreatment.END_USER_APPROVAL), is_entitled=True
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.SUSPEND_FOR_CONSENT
        assert outcome.is_authorized is False

    def test_staff_approval_suspends_for_approval(self) -> None:
        request = _request(
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL), is_entitled=True
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.SUSPEND_FOR_APPROVAL
        assert outcome.is_authorized is False

    def test_every_outcome_carries_its_treatment_and_reasons(self) -> None:
        """A denial that cannot explain itself cannot be audited (spec FR-AUDIT-003)."""
        for treatment in ExecutionTreatment:
            outcome = gate.evaluate(_request(entry=_entry(treatment=treatment), is_entitled=True))
            assert outcome.treatment is not None
            assert outcome.treatment_reason is not None
            assert outcome.reason is not None


class TestTheSubstitutionsTheSpecificationForbids:
    """Each of these is a specific way somebody could get authority they were not given."""

    def test_consent_does_not_satisfy_staff_approval(self) -> None:
        """Spec FR-INTR-007. The requester agreeing is not a staff verdict."""
        identity = OperationIdentity("op.needing.staff", 1)
        requester = PrincipalId(uuid4())
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
            is_entitled=True,
            requester=requester,
            decision=end_user_consent(identity, requester),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.WRONG_DECISION_KIND

    def test_a_staff_verdict_does_not_stand_in_for_the_requesters_consent(self) -> None:
        """The mirror case. The operation is on that person's own account or device."""
        identity = OperationIdentity("op.on.my.device", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.END_USER_APPROVAL, identity=identity),
            is_entitled=True,
            decision=staff_verdict(identity),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.WRONG_DECISION_KIND

    def test_only_the_requester_may_consent(self) -> None:
        """Spec FR-INTR-005. Somebody else's consent is not consent."""
        identity = OperationIdentity("op.on.my.device", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.END_USER_APPROVAL, identity=identity),
            is_entitled=True,
            requester=PrincipalId(uuid4()),
            decision=end_user_consent(identity, PrincipalId(uuid4())),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.NOT_THE_REQUESTER

    def test_an_approver_holding_no_accepted_role_is_denied(self) -> None:
        """Set intersection, and an empty one denies (spec FR-AUTHZ-004)."""
        identity = OperationIdentity("op.for.technicians", 1)
        request = _request(
            identity=identity,
            entry=_entry(
                treatment=ExecutionTreatment.STAFF_APPROVAL,
                identity=identity,
                accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
            ),
            is_entitled=True,
            decision=staff_verdict(identity, roles=RoleSet.of(StaffRole.ADMINISTRATOR)),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.APPROVER_HOLDS_NO_ACCEPTED_ROLE

    def test_administrator_does_not_imply_technician(self) -> None:
        """Roles are independent capabilities with no hierarchy (spec FR-AUTHZ-003).

        The same assertion as above from the other direction, and worth stating separately: the
        tempting 'admins can do anything' shortcut is exactly what this forbids.
        """
        identity = OperationIdentity("op.for.technicians", 1)
        approved = staff_verdict(identity, roles=RoleSet.of(StaffRole.ADMINISTRATOR))
        request = _request(
            identity=identity,
            entry=_entry(
                treatment=ExecutionTreatment.STAFF_APPROVAL,
                identity=identity,
                accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
            ),
            is_entitled=True,
            decision=approved,
            expires_at=FIXED_NOW + WINDOW,
        )
        assert gate.evaluate(request).is_authorized is False

    def test_a_decision_bound_to_another_catalogue_version_is_refused(self) -> None:
        """A catalogue edit between approval and execution changes what would run."""
        approved_version = OperationIdentity("op.v1", 1)
        proposed_version = OperationIdentity("op.v1", 2)
        request = _request(
            identity=proposed_version,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=proposed_version),
            is_entitled=True,
            decision=staff_verdict(approved_version),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.reason is GateReason.DECISION_BOUND_TO_ANOTHER_VERSION

    def test_a_suspended_organisation_cannot_execute_approved_work(self) -> None:
        """Spec FR-EXEC-003. A suspension can land between admission and execution."""
        identity = OperationIdentity("op", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.AUTO, identity=identity),
            is_entitled=True,
            tenant_status=TenantStatus.SUSPENDED,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.TENANT_NOT_ADMITTED


class TestTheExecutionWindow:
    """Fifteen minutes, and what happens on either side of it."""

    def test_an_approval_inside_the_window_proceeds(self) -> None:
        identity = OperationIdentity("op", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
            is_entitled=True,
            decision=staff_verdict(identity),
            expires_at=FIXED_NOW + WINDOW,
        )
        assert gate.evaluate(request).disposition is GateDisposition.PROCEED

    def test_an_expired_approval_does_not_execute(self) -> None:
        """Expiry is a normal outcome, never reported as an error (spec FR-EXEC-001)."""
        identity = OperationIdentity("op", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
            is_entitled=True,
            decision=staff_verdict(identity),
            expires_at=FIXED_NOW - timedelta(seconds=1),
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.AUTHORIZATION_EXPIRED

    def test_a_granted_decision_with_no_window_fails_closed(self) -> None:
        """A missing window is not an unlimited one."""
        identity = OperationIdentity("op", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
            is_entitled=True,
            decision=staff_verdict(identity),
            expires_at=None,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.AUTHORIZATION_WINDOW_MISSING

    def test_a_rejection_closes_rather_than_waiting_to_expire(self) -> None:
        """A declined decision closes the work honestly (contracts/triggers.md)."""
        identity = OperationIdentity("op", 1)
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
            is_entitled=True,
            decision=staff_verdict(identity, verdict=ApprovalVerdict.REJECTED),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.APPROVAL_REJECTED

    def test_a_refused_consent_closes_the_same_way(self) -> None:
        identity = OperationIdentity("op", 1)
        requester = PrincipalId(uuid4())
        request = _request(
            identity=identity,
            entry=_entry(treatment=ExecutionTreatment.END_USER_APPROVAL, identity=identity),
            is_entitled=True,
            requester=requester,
            decision=end_user_consent(identity, requester, verdict=ConsentVerdict.REFUSED),
            expires_at=FIXED_NOW + WINDOW,
        )
        outcome = gate.evaluate(request)
        assert outcome.disposition is GateDisposition.REFUSE
        assert outcome.reason is GateReason.CONSENT_REFUSED

    def test_there_is_no_approval_by_timeout(self) -> None:
        """Spec FR-INTR-008. Waiting produces a suspension forever, never an approval."""
        identity = OperationIdentity("op", 1)
        harness = build_harness()
        for minutes in (0, 15, 60, 60 * 24 * 365):
            harness.clock.advance(minutes=minutes)
            request = _request(
                identity=identity,
                entry=_entry(treatment=ExecutionTreatment.STAFF_APPROVAL, identity=identity),
                is_entitled=True,
                now_offset=timedelta(minutes=minutes),
            )
            assert gate.evaluate(request).disposition is GateDisposition.SUSPEND_FOR_APPROVAL


class TestTheGraphCannotAuthorizeItself:
    """The last mile: even past routing, execution re-checks the gate's own verdict."""

    def test_execute_refuses_without_a_proceed_disposition(self) -> None:
        """A graph reaching execution some other way still does not execute."""
        import asyncio

        from ragcore.graph.nodes.execution import UnauthorizedExecutionError, make_execute

        harness = build_harness()
        node = make_execute(harness.deps)

        suspended: GovernanceResult = {
            "treatment": "STAFF_APPROVAL",
            "treatment_reason": "catalogue_default",
            "disposition": "suspend_for_approval",
            "reason": "awaiting_approval",
            "decided_at": FIXED_NOW.isoformat(),
        }
        refused: GovernanceResult = {
            "treatment": "NOT_ALLOWED",
            "treatment_reason": "not_in_catalogue",
            "disposition": "refuse",
            "reason": "treatment_refuses",
            "decided_at": FIXED_NOW.isoformat(),
        }
        states: tuple[AgentState, ...] = (
            {},
            {"governance": suspended},
            {"governance": refused},
        )

        for state in states:
            with pytest.raises(UnauthorizedExecutionError):
                asyncio.run(
                    node(
                        state,
                        runtime=_runtime(harness.run_context(work_item_id=WorkItemId(uuid4()))),
                    )
                )

        assert harness.execution.invocations == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    *,
    treatment: ExecutionTreatment,
    identity: OperationIdentity | None = None,
    accepted_roles: RoleSet | None = None,
    requires_elevation: bool = False,
) -> CatalogueEntry:
    """A catalogue entry, without going through the async catalogue port."""
    return FakeCatalogueEntry(
        identity=identity if identity is not None else OperationIdentity("op", 1),
        treatment=treatment,
        accepted_roles=accepted_roles
        if accepted_roles is not None
        else RoleSet.of(StaffRole.TECHNICIAN),
        requires_elevation=requires_elevation,
    )


def _request(  # noqa: PLR0913 — a gate request has this many parts; naming each beats a dict
    *,
    entry: CatalogueEntry | None = None,
    is_entitled: bool = True,
    identity: OperationIdentity | None = None,
    requester: PrincipalId | None = None,
    decision: RecordedDecision | None = None,
    expires_at: datetime | None = None,
    tenant_status: TenantStatus = TenantStatus.ACTIVE,
    proposal_source: ProposalSource = ProposalSource.MODEL,
    now_offset: timedelta = timedelta(0),
) -> GateRequest:
    """Assemble a gate request with sensible defaults for whatever the test is not about."""
    resolved_identity = identity if identity is not None else OperationIdentity("op", 1)
    return GateRequest(
        tenant=admitted_tenant(tenant_status),
        proposal=ProposedOperation(resolved_identity, {}, proposal_source),
        entry=entry,
        is_entitled=is_entitled,
        requester=requester if requester is not None else PrincipalId(uuid4()),
        now=FIXED_NOW + now_offset,
        decision=decision,
        authorization_expires_at=expires_at,
    )


def _runtime(context: RunContext) -> Runtime[RunContext]:
    """A real ``Runtime`` carrying only the run context.

    The real type rather than a stand-in: a hand-rolled double with a ``context`` attribute would
    keep passing if LangGraph changed how a node receives its context, and the node under test
    would then be exercised through an interface nothing uses.
    """
    return Runtime(context=context)
