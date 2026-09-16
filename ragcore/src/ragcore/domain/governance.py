"""Execution treatment, capability kind, and verification outcome."""

from __future__ import annotations

from enum import Enum


class ExecutionTreatment(Enum):
    """How an operation may proceed. Exactly one of four.

    **The model MUST NEVER choose, influence or override this** (constitution Principle III).
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


class VerificationOutcome(Enum):
    """What the platform actually knows about an execution's outcome.

    A client-reported result is a claim, not proof. The platform MUST NOT claim to know more
    than it does (constitution Principle VIII, ADR-0004).
    """

    SERVER_CONFIRMED = "server_confirmed"
    """A server-side read tool confirmed the effect. Reported as resolved."""

    CLIENT_ATTESTED = "client_attested"
    """No server-side read path exists. MUST NOT be presented as confirmed resolution."""

    CONTRADICTED = "contradicted"
    """A server-side read disagreed with the claim. Treated as a failure."""
