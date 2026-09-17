"""An unexercised gate **refuses**. It never permits.

`FR-DEMO-018`: the absence of an approval or consent workflow MUST NOT be implemented as a
permissive default. Where the gate is not yet exercised, an operation requiring a human decision
MUST be refused or routed to manual fallback — never auto-approved, and never allowed to proceed
because nothing was there to stop it. `SC-DEMO-014` puts a number on it: refused or routed in 100%
of cases, auto-approved in 0.

**This is the requirement that covers a gap rather than a feature**, which is why it needs its own
file. The approval and consent workflows are deliberately absent from this release
(spec FR-DEMO-016, and the retired-task table in ``tasks.md``), and an absence is exactly the kind
of thing that is easy to implement as "nothing stopped it". Four independent things would each have
to go wrong for that to happen here, and each is asserted separately:

1. **The gate suspends rather than proceeding.** ``STAFF_APPROVAL`` and ``END_USER_APPROVAL`` with
   no recorded decision are ``SUSPEND_*``, never ``PROCEED`` — and suspension persists indefinitely
   rather than timing out into a default.
2. **Nothing can manufacture a decision.** A decision is only ever read back from its durable row,
   and the endpoints that would record one return 501. A gate that suspends correctly beside a
   process that fabricates a verdict is the same failure with more steps.
3. **No verdict can be synthesized by the type system.** ``ApprovalVerdict`` has two members, so
   there is no ``EXPIRED`` and no ``AUTO_APPROVED`` to pass.
4. **An unhandled resume trigger dead-letters.** A decision kind arriving with no handler is refused
   with an alert, never treated as authorization to proceed.

**And the scaffold routes every action to manual resolution** (`FR-FALL-009`), which is the "or
routed to manual fallback" half of the requirement: refusal and fallback are both acceptable
outcomes, and auto-approval is not either of them.

Marked ``governance``: *proves treatment comes from the catalogue, never from model output*.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from workers import resume_worker

from ragcore.domain.decisions import EndUserConsent, StaffVerdict
from ragcore.domain.envelopes import TriggerEnvelope, TriggerKind
from ragcore.domain.governance import CapabilityKind, ExecutionTreatment, RiskTier
from ragcore.domain.identifiers import CorrelationId, OperationIdentity, PrincipalId, WorkItemId
from ragcore.domain.proposal import ProposedOperation
from ragcore.domain.roles import RoleSet, StaffRole
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, InterruptKind
from ragcore.governance import gate
from ragcore.governance.catalogue import CatalogueRecord
from ragcore.governance.fixtures import REFERENCE_FIXTURES
from ragcore.governance.gate import GateDisposition, GateReason, GateRequest
from ragcore.messaging.tracecontext import TraceContext
from tests.support.fakes import FIXED_NOW, admitted_tenant

pytestmark = pytest.mark.governance

SRC = Path(inspect.getsourcefile(gate) or "").resolve().parents[1]

REQUIRE_A_HUMAN = (ExecutionTreatment.STAFF_APPROVAL, ExecutionTreatment.END_USER_APPROVAL)
"""The two treatments whose workflow does not exist in this release."""

IDENTITY = OperationIdentity("test.requires-a-human", 1)


def _entry(treatment: ExecutionTreatment) -> CatalogueRecord:
    return CatalogueRecord(
        identity=IDENTITY,
        treatment=treatment,
        accepted_roles=RoleSet.of(StaffRole.TECHNICIAN),
        kind=CapabilityKind.ACTION,
        risk_tier=RiskTier.LOW_IMPACT,
        is_reference_fixture=True,
    )


def _request(treatment: ExecutionTreatment, **overrides: object) -> GateRequest:
    base: dict[str, object] = {
        "tenant": admitted_tenant(),
        "proposal": ProposedOperation(identity=IDENTITY),
        "entry": _entry(treatment),
        "is_entitled": True,
        "requester": PrincipalId(uuid4()),
        "now": FIXED_NOW,
        "decision": None,
        "authorization_expires_at": None,
    }
    base.update(overrides)
    return GateRequest(**base)  # type: ignore[arg-type]


class TestTheGateSuspendsRatherThanProceeding:
    """The first of the four, and the only one most people would think to write."""

    @pytest.mark.parametrize("treatment", REQUIRE_A_HUMAN)
    def test_no_recorded_decision_never_proceeds(self, treatment: ExecutionTreatment) -> None:
        outcome = gate.evaluate(_request(treatment))

        assert outcome.disposition is not GateDisposition.PROCEED
        assert not outcome.is_authorized

    @pytest.mark.parametrize("treatment", REQUIRE_A_HUMAN)
    def test_it_suspends_for_the_right_kind_of_decision(
        self, treatment: ExecutionTreatment
    ) -> None:
        """Suspending for the *wrong* kind would put the case in front of the wrong person."""
        outcome = gate.evaluate(_request(treatment))

        expected = (
            InterruptKind.APPROVAL
            if treatment is ExecutionTreatment.STAFF_APPROVAL
            else InterruptKind.CONSENT
        )
        assert outcome.suspends_on is expected

    @pytest.mark.parametrize("treatment", REQUIRE_A_HUMAN)
    def test_time_passing_does_not_turn_a_suspension_into_an_approval(
        self, treatment: ExecutionTreatment
    ) -> None:
        """The three ``awaiting_*`` states have **no expiry** (spec FR-INTR-002).

        A closed laptop, a timeout or a dropped connection leaves the work exactly where it was. The
        failure this guards against is the opposite of an expiry bug: a suspension that resolves
        itself into a permission because a timer fired.
        """
        for elapsed in (timedelta(minutes=16), timedelta(days=1), timedelta(days=400)):
            outcome = gate.evaluate(_request(treatment, now=FIXED_NOW + elapsed))

            assert outcome.disposition is not GateDisposition.PROCEED
            assert outcome.reason in {
                GateReason.AWAITING_APPROVAL,
                GateReason.AWAITING_CONSENT,
            }

    @pytest.mark.parametrize("treatment", REQUIRE_A_HUMAN)
    def test_an_expired_window_with_no_decision_still_does_not_proceed(
        self, treatment: ExecutionTreatment
    ) -> None:
        """A window without a decision is not a decision that expired into a yes."""
        outcome = gate.evaluate(
            _request(
                treatment,
                now=FIXED_NOW + timedelta(hours=1),
                authorization_expires_at=FIXED_NOW + timedelta(minutes=15),
            )
        )

        assert not outcome.is_authorized

    def test_the_reference_fixtures_behave_the_same_way(self) -> None:
        """The catalogue the scaffold actually ships, not a constructed entry.

        Two of the four fixtures require a human, and neither proceeds.
        """
        for record in REFERENCE_FIXTURES:
            if record.treatment not in REQUIRE_A_HUMAN:
                continue

            outcome = gate.evaluate(
                GateRequest(
                    tenant=admitted_tenant(),
                    proposal=ProposedOperation(identity=record.identity),
                    entry=record,
                    is_entitled=True,
                    requester=PrincipalId(uuid4()),
                    now=FIXED_NOW,
                )
            )

            assert not outcome.is_authorized, f"{record.identity} auto-approved"


class TestNothingCanManufactureADecision:
    """A gate that suspends correctly, beside a process that fabricates a verdict, is the same
    failure with more steps.
    """

    @pytest.mark.parametrize("decision_type", [StaffVerdict, EndUserConsent])
    def test_a_decision_is_only_ever_read_back_from_the_durable_record(
        self, decision_type: type
    ) -> None:
        """The one legitimate construction site is a repository **read**.

        Not "nothing constructs one" — the repositories must, because a recorded decision is read
        back from its row and handed to the gate. The rule is that it is constructed *there and
        nowhere else*, and only inside a method that selects: any other site would be a decision
        assembled from something that is not the durable record.

        Read with ``ast`` rather than by substring, so a mention in a docstring or a type
        annotation — both correct and common here — is not a finding. Only a *call* is.
        """
        name = decision_type.__name__
        sites: list[tuple[str, str]] = []

        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for function in ast.walk(tree):
                if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                for node in ast.walk(function):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == name
                    ):
                        sites.append((str(path.relative_to(SRC)), str(function.name)))

        assert sites, f"{name} is never constructed. It has to be read back from its row somewhere."

        for module, where in sites:
            assert module == str(Path("persistence") / "repositories.py"), (
                f"{name} is constructed in {module}.{where}. Outside the repository it would be a "
                f"decision assembled from something other than the durable record."
            )
            assert where == "decision_for", (
                f"{name} is constructed in {where}, which is not the read path."
            )

    @pytest.mark.parametrize(
        ("receiver", "method"),
        [("approvals", "record_verdict"), ("consents", "record")],
    )
    def test_nothing_in_this_build_calls_the_write_path(self, receiver: str, method: str) -> None:
        """The adapter can write a decision. **Nothing reaches it.**

        The repository methods and their ports exist — they are the Stage 7 persistence work, and
        deleting them would make the deferred workflow harder to land honestly later. What must not
        exist is a caller, because a caller is how a decision gets into the store without a human
        having made one.

        Matched on the **receiver as well as the method**, because ``record`` is an ordinary verb:
        an OpenTelemetry instrument has one, and a check on the name alone would flag a metric
        write and teach the next person to widen the exclusion list until it flagged nothing.

        The staff endpoint named ``record_verdict`` is the 501 placeholder and is a function
        definition rather than a call, so it is not matched; the test above asserts it returns a
        problem document rather than writing.
        """
        callers: list[str] = []

        for path in SRC.rglob("*.py"):
            if path.name in {"repositories.py", "ports.py"}:
                continue

            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr != method:
                    continue

                target = node.func.value
                name = (
                    target.id
                    if isinstance(target, ast.Name)
                    else target.attr
                    if isinstance(target, ast.Attribute)
                    else ""
                )
                if receiver in name.lower():
                    callers.append(f"{path.relative_to(SRC)}:{node.lineno}")

        assert not callers, (
            f"something calls {receiver}.{method}() at {callers}. The approval and consent "
            f"workflows are deferred (spec FR-DEMO-016); a decision reaching the store in this "
            f"build is one nobody made."
        )

    @pytest.mark.parametrize(
        "route",
        [
            "record_verdict",
            "record_consent",
        ],
    )
    def test_the_endpoint_that_would_record_one_returns_501(self, route: str) -> None:
        """Wired, and honestly inert. A 200 here would be a recorded decision nobody made."""
        from ragcore.api.customer import routes as customer_routes
        from ragcore.api.staff import routes as staff_routes

        handler = getattr(staff_routes, route, None) or getattr(customer_routes, route)
        source = inspect.getsource(handler)

        assert "not_implemented(request)" in source, (
            f"{route} no longer returns a 501 problem document. Recording a decision is the one "
            f"thing this build must not do."
        )

    def test_neither_endpoint_writes_to_a_repository(self) -> None:
        """A 501 that had already written a row would be worse than a 200."""
        from ragcore.api.customer import routes as customer_routes
        from ragcore.api.staff import routes as staff_routes

        for module in (staff_routes, customer_routes):
            source = inspect.getsource(module)
            assert "ApprovalRepository" not in source
            assert "ConsentRepository" not in source


class TestNoVerdictCanBeSynthesized:
    """The type system's contribution, and the one that survives a rewrite."""

    def test_an_approval_verdict_has_exactly_two_members(self) -> None:
        """No ``EXPIRED``, so a system-synthesized verdict is unrepresentable rather than merely
        prohibited (spec FR-INTR-008). No timeout, no auto-reject, no auto-approve.
        """
        assert {member.name for member in ApprovalVerdict} == {"APPROVED", "REJECTED"}

    def test_a_consent_verdict_has_exactly_two_members(self) -> None:
        assert {member.name for member in ConsentVerdict} == {"GRANTED", "REFUSED"}

    def test_no_member_is_named_for_an_automatic_outcome(self) -> None:
        """A guard against the member somebody would add to make an integration test pass."""
        for enumeration in (ApprovalVerdict, ConsentVerdict):
            for member in enumeration:
                assert not any(
                    word in member.name.lower()
                    for word in ("auto", "default", "implied", "assumed", "timeout", "expired")
                ), f"{enumeration.__name__}.{member.name} names an outcome nobody decided"

    def test_a_decision_is_immutable_once_recorded(self) -> None:
        """So a later process cannot edit a refusal into a grant."""
        for decision_type in (StaffVerdict, EndUserConsent):
            assert is_dataclass(decision_type)
            # Asserted behaviourally rather than by reading the dataclass machinery: what matters
            # is that an assignment raises, and `frozen=True` is only how that happens today.
            fields_of = {field.name for field in dataclass_fields(decision_type)}
            assert fields_of, f"{decision_type.__name__} declares no fields"

            with pytest.raises((AttributeError, TypeError)):
                setattr(decision_type.__new__(decision_type), next(iter(fields_of)), None)


class TestAnUnhandledResumeTriggerDoesNotProceed:
    """The last door: a decision kind arriving on the bus with no handler behind it."""

    def test_only_the_sample_flow_kind_is_handled_in_this_build(self) -> None:
        assert frozenset({TriggerKind.SAMPLE_FLOW}) == resume_worker.HANDLED_KINDS

    @pytest.mark.parametrize(
        "kind",
        [
            TriggerKind.APPROVAL_GRANTED,
            TriggerKind.APPROVAL_REJECTED,
            TriggerKind.CONSENT_GRANTED,
            TriggerKind.CONSENT_REFUSED,
        ],
    )
    def test_every_decision_kind_is_dead_lettered_rather_than_executed(
        self, kind: TriggerKind
    ) -> None:
        """Including ``APPROVAL_GRANTED``, which is the one a permissive build would let through."""
        assert kind not in resume_worker.HANDLED_KINDS

        report = resume_worker.refuse_unhandled_kind(
            resume_worker.ConsumedTrigger(
                envelope=TriggerEnvelope(
                    work_item_id=WorkItemId(uuid4()),
                    correlation_id=CorrelationId(str(uuid4())),
                    kind=kind,
                ),
                trace=TraceContext(correlation_id=str(uuid4()), traceparent="", tracestate=""),
            )
        )

        assert report.kind == kind.value
        assert "never authorization" in report.reason

    def test_the_dispatch_is_an_allow_list_rather_than_a_fallthrough(self) -> None:
        """An explicit set, so a new kind is unhandled until somebody handles it.

        A ``match`` with a final ``case _`` would send an unrecognised kind into whatever the last
        branch happened to be — which is how "nothing stopped it" gets implemented.
        """
        source = inspect.getsource(resume_worker)

        assert "HANDLED_KINDS" in source
        assert "case _:" not in source


class TestTheScaffoldRoutesActionsToManualResolution:
    """The other acceptable outcome. Refusal and fallback; auto-approval is neither."""

    def test_no_use_case_is_defined_for_an_action_to_resolve_to(self) -> None:
        """`FR-FALL-009`: because UC-01..UC-12 are undefined, every request requiring an action
        routes to manual resolution. The catalogue holding only inert fixtures is what makes that
        true rather than asserted.
        """
        for record in REFERENCE_FIXTURES:
            assert record.is_reference_fixture, (
                f"{record.identity} is in the shipped catalogue and is not a fixture. The scaffold "
                f"has no product operation to resolve a request to."
            )

    def test_a_refusal_carries_the_reason_it_could_not_proceed(self) -> None:
        """`FR-FALL-010`: a fallback says **why**, not only that it could not.

        Every gate outcome carries a reason and a treatment reason; neither is optional, so a
        refusal that cannot explain itself is unrepresentable.
        """
        outcome = gate.evaluate(_request(ExecutionTreatment.STAFF_APPROVAL))

        assert outcome.reason is not None
        assert outcome.treatment_reason is not None
        assert outcome.treatment is ExecutionTreatment.STAFF_APPROVAL


class TestTheNegativeHalf:
    """A gate that refused everything would pass every test above and be useless."""

    def test_an_auto_operation_still_proceeds(self) -> None:
        """Proving the suspensions above are about the treatment, not about a gate that is off."""
        outcome = gate.evaluate(_request(ExecutionTreatment.AUTO))

        assert outcome.disposition is GateDisposition.PROCEED
        assert outcome.reason is GateReason.AUTO_TREATMENT

    def test_a_decision_that_does_exist_is_still_honoured(self) -> None:
        """The workflow is unbuilt, not broken. When a verdict exists, the gate accepts it.

        Constructed here as the approval repository would return it — which is exactly what the
        suite above proves nothing in ``src/`` can do.
        """
        from tests.support.fakes import staff_verdict

        outcome = gate.evaluate(
            _request(
                ExecutionTreatment.STAFF_APPROVAL,
                decision=staff_verdict(IDENTITY, roles=RoleSet.of(StaffRole.TECHNICIAN)),
                now=FIXED_NOW + timedelta(minutes=1),
                authorization_expires_at=FIXED_NOW + timedelta(minutes=15),
            )
        )

        assert outcome.disposition is GateDisposition.PROCEED
