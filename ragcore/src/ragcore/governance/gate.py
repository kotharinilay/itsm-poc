"""The control gate: the single place a proposal becomes — or fails to become — authorized work.

Everything upstream of this function is a suggestion. Everything downstream has already been
decided. **Side-effecting tools MUST NOT be reachable from an unconstrained agent loop**
(constitution Principle III), and this module is what stands between the two.

**The gate is a pure function.** No clock, no database, no catalogue lookup, no model call — the
caller resolves all of that and hands it in. Three consequences follow, and all three are the
point:

* It is exhaustively testable. Every combination of treatment, decision and role set is a table
  row rather than an integration test.
* It cannot be influenced by anything it was not given. There is no ambient state to poison.
* It cannot be *partially* applied. A caller that skipped it has no half-evaluated result to
  mistake for a decision.

**The gate never receives a treatment.** :func:`evaluate` derives it from the catalogue through
:func:`~ragcore.governance.policy.assign_treatment`. A ``treatment`` parameter — however carefully
the caller promised to fill it from the catalogue — is the exact hole through which a model-chosen
treatment would arrive, so the parameter does not exist.

The two decision types the gate accepts — :class:`~ragcore.domain.decisions.StaffVerdict` and
:class:`~ragcore.domain.decisions.EndUserConsent` — live in the domain, because the
repositories that return them are declared in :mod:`ragcore.application.ports` and a port
declared in terms of a governance type would invert the dependency direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ragcore.application.ports import CatalogueEntry
from ragcore.domain.decisions import EndUserConsent, RecordedDecision, StaffVerdict
from ragcore.domain.governance import ExecutionTreatment
from ragcore.domain.identifiers import PrincipalId
from ragcore.domain.proposal import ProposedOperation
from ragcore.domain.roles import AuthorizationDecision
from ragcore.domain.roles import evaluate as evaluate_roles
from ragcore.domain.tenancy import TenantContext
from ragcore.domain.work import ApprovalVerdict, ConsentVerdict, InterruptKind
from ragcore.governance.conditions import KnowledgeCondition
from ragcore.governance.policy import TreatmentDecision, TreatmentReason, assign_treatment


class GateDisposition(Enum):
    """What the gate concluded. Exactly one of four, matching the four treatments' outcomes."""

    PROCEED = "proceed"
    """Authorized. Execution may be attempted, inside the validity window."""

    SUSPEND_FOR_CONSENT = "suspend_for_consent"
    """Durably suspend and ask the requester. Persists indefinitely (spec FR-INTR-002)."""

    SUSPEND_FOR_APPROVAL = "suspend_for_approval"
    """Durably suspend and ask staff. Persists indefinitely."""

    REFUSE = "refuse"
    """Not authorized, and not askable. Recorded as a denial, never surfaced as approvable."""


class GateReason(Enum):
    """Why the gate concluded what it did. Every outcome carries one; none is optional."""

    TENANT_NOT_ADMITTED = "tenant_not_admitted"
    """The organisation is suspended or offboarded (spec FR-EXEC-003)."""

    TREATMENT_REFUSES = "treatment_refuses"
    """Deterministic policy assigned ``NOT_ALLOWED``. See the accompanying treatment reason."""

    AUTO_TREATMENT = "auto_treatment"
    """``AUTO``. No human decision is required for this operation."""

    AWAITING_CONSENT = "awaiting_consent"
    """``END_USER_APPROVAL`` with no consent recorded yet."""

    AWAITING_APPROVAL = "awaiting_approval"
    """``STAFF_APPROVAL`` with no verdict recorded yet."""

    CONSENT_GRANTED = "consent_granted"
    """The requester consented, within the window."""

    APPROVAL_GRANTED = "approval_granted"
    """A holder of an accepted role approved, within the window."""

    CONSENT_REFUSED = "consent_refused"
    """The requester refused. The work closes honestly rather than waiting to expire."""

    APPROVAL_REJECTED = "approval_rejected"
    """Staff rejected. The work closes honestly rather than waiting to expire."""

    WRONG_DECISION_KIND = "wrong_decision_kind"
    """A consent was offered against a staff requirement, or the reverse (spec FR-INTR-007)."""

    NOT_THE_REQUESTER = "not_the_requester"
    """Somebody other than the work item's requester tried to consent (spec FR-INTR-005)."""

    APPROVER_HOLDS_NO_ACCEPTED_ROLE = "approver_holds_no_accepted_role"
    """Empty set intersection between roles held and roles the operation accepts."""

    DECISION_BOUND_TO_ANOTHER_VERSION = "decision_bound_to_another_version"
    """The catalogue entry changed after the decision. What was approved is not what would run."""

    AUTHORIZATION_EXPIRED = "authorization_expired"
    """The fifteen-minute window elapsed. A normal outcome, never reported as an error."""

    AUTHORIZATION_WINDOW_MISSING = "authorization_window_missing"
    """A granted decision with no window on the work item. Fails closed rather than assuming one."""

    KNOWLEDGE_WITHHELD = "knowledge_withheld"
    """There is not enough evidence to act on (spec FR-AGENT-005, FR-AGENT-006).

    **A withholding, not a refusal of authority.** The operation may be perfectly permitted; what is
    missing is grounding. Confidence in ability never substitutes for evidence, so this outcome is
    reachable on every path — including one where the treatment is ``AUTO`` and nobody was going to
    be asked anything.
    """


@dataclass(frozen=True, slots=True)
class GateRequest:
    """Everything the gate is allowed to consider. Nothing else is in scope.

    Attributes:
        tenant: Trusted tenant binding. Constructed only through
            :class:`~ragcore.domain.tenancy.TenantContext`'s provenance-named classmethods, so a
            tenant that came from a client field cannot reach here.
        proposal: What the agent suggested. Carries no treatment and no approval.
        entry: The catalogue entry for the proposal, or ``None`` when the lookup found nothing.
        is_entitled: Whether this organisation is entitled to the capability.
        requester: The work item's ``requested_by_oid``. Immutable on the durable record.
        now: The current instant, resolved by the caller from
            :class:`~ragcore.application.ports.ClockPort`. Passed in rather than read so the gate
            stays pure and an expiry test does not have to wait fifteen real minutes.
        decision: The recorded human decision, or ``None`` when none exists yet.
        authorization_expires_at: The work item's execution window. ``None`` until a decision
            sets one.
        knowledge: The knowledge condition, assessed by the caller from what retrieval returned.
            Defaults to :meth:`~ragcore.governance.conditions.KnowledgeCondition.not_required` —
            the honest default for an operation acting on platform state rather than on retrieved
            evidence, and a **safe** one because knowledge can only ever withhold. A default that
            could authorize would be a permissive default; this one cannot be, whatever it holds.
    """

    tenant: TenantContext
    proposal: ProposedOperation
    entry: CatalogueEntry | None
    is_entitled: bool
    requester: PrincipalId
    now: datetime
    decision: RecordedDecision | None = None
    authorization_expires_at: datetime | None = None
    knowledge: KnowledgeCondition = field(default_factory=KnowledgeCondition.not_required)


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """What the gate decided, and everything needed to audit the decision.

    Attributes:
        disposition: What happens next.
        treatment: The treatment deterministic policy assigned. Present on every outcome,
            including refusals — a denial without its treatment cannot explain itself.
        treatment_reason: Which policy rule assigned that treatment.
        reason: Which gate rule produced this disposition.
        authorization: The role evaluation, where one was performed. ``None`` on paths where no
            role question arose — an ``AUTO`` operation, or a suspension before any decision.
    """

    disposition: GateDisposition
    treatment: ExecutionTreatment
    treatment_reason: TreatmentReason
    reason: GateReason
    authorization: AuthorizationDecision | None = None

    @property
    def is_authorized(self) -> bool:
        """Whether execution may be attempted.

        The one question the execution path asks. Deliberately a property of this object rather
        than a boolean anybody can construct: there is no way to hold an ``is_authorized`` of
        ``True`` without holding the gate outcome that produced it.
        """
        return self.disposition is GateDisposition.PROCEED

    @property
    def suspends_on(self) -> InterruptKind | None:
        """Which interrupt this outcome raises, if it suspends."""
        if self.disposition is GateDisposition.SUSPEND_FOR_CONSENT:
            return InterruptKind.CONSENT
        if self.disposition is GateDisposition.SUSPEND_FOR_APPROVAL:
            return InterruptKind.APPROVAL
        return None


def _refuse(treatment: TreatmentDecision, reason: GateReason) -> GateOutcome:
    return GateOutcome(GateDisposition.REFUSE, treatment.treatment, treatment.reason, reason)


def _window_refusal(request: GateRequest) -> GateReason | None:
    """Check the execution validity window.

    Returns:
        The refusal reason, or ``None`` when the window permits execution.
    """
    if request.authorization_expires_at is None:
        return GateReason.AUTHORIZATION_WINDOW_MISSING
    if request.now >= request.authorization_expires_at:
        return GateReason.AUTHORIZATION_EXPIRED
    return None


def _evaluate_consent(request: GateRequest, treatment: TreatmentDecision) -> GateOutcome:
    """The ``END_USER_APPROVAL`` branch. Only an :class:`EndUserConsent` satisfies it."""
    decision = request.decision

    if decision is None:
        return GateOutcome(
            GateDisposition.SUSPEND_FOR_CONSENT,
            treatment.treatment,
            treatment.reason,
            GateReason.AWAITING_CONSENT,
        )

    if not isinstance(decision, EndUserConsent):
        # A staff verdict does not stand in for the requester's own consent. The operation is on
        # that person's account or device, and staff approval answers a different question.
        return _refuse(treatment, GateReason.WRONG_DECISION_KIND)

    if decision.consented_by != request.requester:
        return _refuse(treatment, GateReason.NOT_THE_REQUESTER)

    if decision.bound_to != request.proposal.identity:
        return _refuse(treatment, GateReason.DECISION_BOUND_TO_ANOTHER_VERSION)

    if decision.verdict is ConsentVerdict.REFUSED:
        return _refuse(treatment, GateReason.CONSENT_REFUSED)

    refusal = _window_refusal(request)
    if refusal is not None:
        return _refuse(treatment, refusal)

    return GateOutcome(
        GateDisposition.PROCEED,
        treatment.treatment,
        treatment.reason,
        GateReason.CONSENT_GRANTED,
    )


def _evaluate_approval(
    request: GateRequest, treatment: TreatmentDecision, entry: CatalogueEntry
) -> GateOutcome:
    """The ``STAFF_APPROVAL`` branch. Only a :class:`StaffVerdict` satisfies it."""
    decision = request.decision

    if decision is None:
        return GateOutcome(
            GateDisposition.SUSPEND_FOR_APPROVAL,
            treatment.treatment,
            treatment.reason,
            GateReason.AWAITING_APPROVAL,
        )

    if not isinstance(decision, StaffVerdict):
        # Consent MUST NOT satisfy a requirement for staff approval (spec FR-INTR-007).
        return _refuse(treatment, GateReason.WRONG_DECISION_KIND)

    if decision.bound_to != request.proposal.identity:
        return _refuse(treatment, GateReason.DECISION_BOUND_TO_ANOTHER_VERSION)

    # Set intersection, evaluated against the roles held at decision time. Roles are independent
    # capabilities with no hierarchy: nothing here sorts, ranks or compares them.
    authorization = evaluate_roles(decision.roles_held, entry.accepted_roles)
    if not authorization.is_permitted:
        return GateOutcome(
            GateDisposition.REFUSE,
            treatment.treatment,
            treatment.reason,
            GateReason.APPROVER_HOLDS_NO_ACCEPTED_ROLE,
            authorization,
        )

    if decision.verdict is ApprovalVerdict.REJECTED:
        return GateOutcome(
            GateDisposition.REFUSE,
            treatment.treatment,
            treatment.reason,
            GateReason.APPROVAL_REJECTED,
            authorization,
        )

    refusal = _window_refusal(request)
    if refusal is not None:
        return GateOutcome(
            GateDisposition.REFUSE, treatment.treatment, treatment.reason, refusal, authorization
        )

    return GateOutcome(
        GateDisposition.PROCEED,
        treatment.treatment,
        treatment.reason,
        GateReason.APPROVAL_GRANTED,
        authorization,
    )


def _withhold(treatment: TreatmentDecision) -> GateOutcome:
    """Knowledge withheld. Refuses, and cannot have done anything else.

    Modelled as a refusal rather than a suspension because there is nobody to ask: a suspension
    means a decision is pending, and no human decision supplies missing evidence. The operation is
    routed to manual fallback by the caller, which is the honest outcome for "the platform does not
    know enough to act".
    """
    return _refuse(treatment, GateReason.KNOWLEDGE_WITHHELD)


def evaluate(request: GateRequest) -> GateOutcome:
    """Decide whether a proposed operation may proceed, must be asked about, or is refused.

    The three conditions of `FR-AGENT-005` meet here, and they meet as a **sequence of refusals**
    rather than as a combination:

    * **Security** — tenant admission and the deterministic treatment from the catalogue. The only
      condition that can authorize anything.
    * **Knowledge** — checked below, and able only to remove an outcome. A met knowledge condition
      changes nothing; an unmet one withholds whatever the other two concluded.
    * **Ability** — registration and entitlement, already folded into the treatment by
      :func:`~ragcore.governance.policy.assign_treatment`: an unregistered or unentitled operation
      is ``NOT_ALLOWED`` before this function sees it.

    **Nothing here averages.** There is no score, no weight and no tally — each check either returns
    a refusal or falls through, so a strong result on one condition has no representation in which
    it could compensate for a weak one.

    Args:
        request: Everything the gate may consider.

    Returns:
        The disposition, the treatment that produced it, and the reasons for both.
    """
    treatment = assign_treatment(request.entry, request.is_entitled)

    # Checked at the gate rather than only at admission: a suspension can land between the two
    # (spec FR-EXEC-003).
    if not request.tenant.is_admitted:
        return _refuse(treatment, GateReason.TENANT_NOT_ADMITTED)

    if treatment.treatment is ExecutionTreatment.NOT_ALLOWED:
        return _refuse(treatment, GateReason.TREATMENT_REFUSES)

    # BEFORE the treatment branches, so it applies to all three of them. Placing it inside the AUTO
    # branch would mean an operation requiring approval could be approved on evidence the platform
    # does not have, and a human asked to approve an ungrounded proposal is being asked to supply
    # the grounding.
    if request.knowledge.withholds:
        return _withhold(treatment)

    if treatment.treatment is ExecutionTreatment.AUTO:
        return GateOutcome(
            GateDisposition.PROCEED,
            treatment.treatment,
            treatment.reason,
            GateReason.AUTO_TREATMENT,
        )

    entry = request.entry
    if entry is None:
        # Unreachable: rule 1 of assign_treatment maps a missing entry to NOT_ALLOWED, which
        # returned above. Written as a refusal rather than an assert so that if the two modules
        # ever disagree, the disagreement fails closed instead of raising past the gate.
        return _refuse(treatment, GateReason.TREATMENT_REFUSES)

    if treatment.treatment is ExecutionTreatment.END_USER_APPROVAL:
        return _evaluate_consent(request, treatment)

    return _evaluate_approval(request, treatment, entry)
