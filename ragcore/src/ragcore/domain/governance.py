"""Execution treatment, capability kind, and verification outcome."""

from __future__ import annotations

from enum import Enum


class ExecutionTreatment(Enum):
    """How an operation may proceed. Exactly one of four.

    **The model MUST NEVER choose, influence or override this** (A3 §6.3).
    There is deliberately no ``UNKNOWN`` member: a missing treatment is not a state this type
    can represent, so "we could not determine the treatment, carry on" cannot be expressed. A
    catalogue lookup that finds nothing is a refusal, not a default.
    """

    AUTO = "AUTO"
    """Proceeds without a human decision."""

    END_USER_APPROVAL = "END_USER_APPROVAL"
    """Requires the requester's consent, for an operation on their own account or device."""

    STAFF_APPROVAL = "STAFF_APPROVAL"
    """Requires a staff verdict from a principal holding a role the operation accepts."""

    NOT_ALLOWED = "NOT_ALLOWED"
    """Refused at the gate. Never surfaced as an approvable proposal; recorded as a denial."""

    @property
    def strictness(self) -> int:
        """How much human decision this treatment demands.

        **Not a hierarchy that permits substitution.** Consent MUST NOT satisfy a requirement for
        staff approval (spec FR-INTR-007), and nothing here lets it: this ordering exists solely
        so :func:`is_narrowing` can tell a safe re-assignment from a dangerous one. It is also
        unrelated to staff roles, which have no hierarchy, ranking or precedence
        (spec FR-AUTHZ-003).
        """
        return _STRICTNESS[self]


_STRICTNESS: dict[ExecutionTreatment, int] = {
    ExecutionTreatment.AUTO: 0,
    ExecutionTreatment.END_USER_APPROVAL: 1,
    ExecutionTreatment.STAFF_APPROVAL: 2,
    ExecutionTreatment.NOT_ALLOWED: 3,
}


def is_narrowing(before: ExecutionTreatment, after: ExecutionTreatment) -> bool:
    """Whether re-assigning ``before`` to ``after`` demands at least as much human decision.

    **The one direction a treatment is allowed to move.** Re-evaluation happens for real: the
    gate runs again every time a suspended run resumes, and between the two evaluations an
    organisation can be suspended or a capability de-entitled. Both make the treatment stricter,
    both are the correct outcome, and both must be permitted.

    What must never happen is the reverse. A treatment that became *more* permissive between the
    evaluation a human saw and the one that executes is the failure the gate exists to prevent —
    whether it came from a policy bug or from something that reached the state channel.

    Args:
        before: The treatment already assigned.
        after: The treatment a later evaluation produced.

    Returns:
        ``True`` when ``after`` is the same or stricter.
    """
    return after.strictness >= before.strictness


class CapabilityKind(Enum):
    """Whether a capability reads state or changes it.

    An ``ACTION`` capability MUST NOT be callable directly from the agent loop and passes
    through deterministic governance and, where required, human approval (spec FR-EXT-013).
    """

    READ = "read"
    ACTION = "action"


class ExecutionMethod(Enum):
    """The mechanism by which a consequential action was performed.

    §28.3 makes ``executed_by`` deliberately polymorphic and requires the execution *mechanism* to
    be recorded distinctly from the *actor*: the same Workload principal acting through Graph and
    through an MCP tool are different facts, and an audit record that conflates them cannot answer
    "by what means" (§28.4).

    Mirrors ``data-model.md`` ``audit_event.execution_method``.
    """

    WORKLOAD = "workload"
    """The Workload principal acted directly, app-only, tenant resolved from the work item."""

    DESKTOP_SCRIPT = "desktop_script"
    """The end user's endpoint ran a predefined, versioned, platform-owned script.

    The endpoint executes; it never decides. Deferred in this release pending ADR-0004's open
    items — script signing and the destructive taxonomy.
    """

    NONE = "none"
    """No execution occurred. The operation was refused, expired, or cancelled before claim."""


class IntegrationJobStatus(Enum):
    """The lifecycle of one instruction handed to the Integrations Service (ADR-0007).

    **Not an authority state.** The authority lives on the work item; this only tracks where the
    instruction has got to, so an operator can tell a job that never left from one whose result
    never came back — two stalls with different causes and different fixes.
    """

    CREATED = "created"
    """Written, not yet announced. A job stuck here means the outbox never dispatched."""

    DISPATCHED = "dispatched"
    """Announced. A job stuck here means the far side never answered."""

    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    """The execution window elapsed. A **normal outcome**, not an error (spec §29.5)."""


class IntegrationResultStatus(Enum):
    """Whether the operation ran, as RagCore records it on its own job row.

    Deliberately coarser than the Integrations Service's own outcome enum. RagCore needs to know
    *did this happen*; the detail — unentitled, unregistered, unreachable — belongs on the execution
    record, and duplicating it here would create a second place the same fact is stated and a second
    place it can be stated differently.
    """

    EXECUTED = "executed"
    FAILED = "failed"


class VerificationOutcome(Enum):
    """What the platform actually knows about an execution's outcome.

    A client-reported result is a claim, not proof. The platform MUST NOT claim to know more
    than it does (ADR-0004).
    """

    SERVER_CONFIRMED = "server_confirmed"
    """A server-side read tool confirmed the effect. Reported as resolved."""

    CLIENT_ATTESTED = "client_attested"
    """No server-side read path exists. MUST NOT be presented as confirmed resolution."""

    CONTRADICTED = "contradicted"
    """A server-side read disagreed with the claim. Treated as a failure."""


class RiskTier(Enum):
    """How much damage an operation could do if it went wrong.

    **The scaffold registers non-destructive tiers only.** The destructive taxonomy is an open
    ADR-0004 item, and a tier that named destruction before that taxonomy existed would be a
    label with no agreed meaning attached to it. The two members below are the ones the catalogue
    may hold today; a third arrives with the taxonomy, not before it.

    Distinct from :class:`ExecutionTreatment` on purpose. Risk describes the *operation*;
    treatment describes *how a human is involved*. Collapsing them would mean a catalogue edit
    that reclassified risk silently changed who has to approve.
    """

    INFORMATIONAL = "informational"
    """Reads state and changes nothing. A failed call leaves the external system as it was."""

    LOW_IMPACT = "low_impact"
    """Changes state reversibly, within the requester's own account or device."""
