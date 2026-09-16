"""Deterministic treatment policy: which of the four treatments an operation gets.

Execution treatment is exactly one of ``AUTO``, ``END_USER_APPROVAL``, ``STAFF_APPROVAL`` or
``NOT_ALLOWED``, assigned by deterministic policy from the canonical operation catalogue
(constitution Principle III). **The model MUST NEVER choose, influence or override it.**

**This is a pure function and deliberately not a port.** An injectable treatment policy is an
interface whose implementation could consult a cache, a feature flag or — the real risk — a value
that travelled with the proposal. Ports exist for infrastructure; this is policy over catalogue
data, and :mod:`ragcore.application.ports` says so at the top of the file.

Determinism here means something specific and testable: for the same catalogue entry and the same
entitlement state, the same treatment, every time, with no clock, no randomness, no I/O and no
configuration read. The only inputs are the two arguments.

**Overrides may only narrow.** Policy can make a catalogue default stricter; it can never make one
more permissive. Every rule below routes through :func:`_narrowed`, which checks the move against
:func:`~ragcore.domain.governance.is_narrowing` — the same ordering the graph's governance
reducer uses, so policy and state agree on what a safe re-assignment is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ragcore.application.ports import CatalogueEntry
from ragcore.domain.governance import ExecutionTreatment, is_narrowing


class TreatmentReason(Enum):
    """Why a treatment was assigned. Recorded on the audit trail alongside the treatment itself.

    A treatment without a reason cannot answer "why was this refused", and denials are audited as
    durably as permissions (spec FR-AUDIT-003).
    """

    CATALOGUE_DEFAULT = "catalogue_default"
    """The entry's declared treatment stood. The ordinary case."""

    NOT_IN_CATALOGUE = "not_in_catalogue"
    """No entry exists. A refusal, never a default — discovery is not entitlement."""

    NOT_ENTITLED = "not_entitled"
    """The entry exists but this organisation is not entitled to it. No global toolset."""

    ELEVATION_REFUSED = "elevation_refused"
    """The entry claims it needs elevation. This release permits none (ADR-0004)."""

    NO_ROLE_CAN_APPROVE = "no_role_can_approve"
    """Staff approval is required and the entry accepts no roles, so nobody could ever decide."""


@dataclass(frozen=True, slots=True)
class TreatmentDecision:
    """The assigned treatment and why.

    Attributes:
        treatment: One of exactly four. There is no ``UNKNOWN``, so "we could not determine the
            treatment, carry on" is not expressible.
        reason: The deterministic rule that produced it.
    """

    treatment: ExecutionTreatment
    reason: TreatmentReason


class PolicyWidenedTreatmentError(Exception):
    """A policy rule tried to make a catalogue default more permissive.

    A platform defect rather than a user-facing condition, and raised rather than logged: a
    widening override is exactly the failure this module exists to prevent, and continuing past
    one would execute something the catalogue did not permit.
    """


def _narrowed(default: ExecutionTreatment, override: ExecutionTreatment) -> ExecutionTreatment:
    """Return ``override``, having established it is no more permissive than ``default``.

    Raises:
        PolicyWidenedTreatmentError: When the override would widen.
    """
    if not is_narrowing(default, override):
        raise PolicyWidenedTreatmentError(
            f"policy tried to widen {default.value} to {override.value}; overrides may only narrow"
        )
    return override


def assign_treatment(entry: CatalogueEntry | None, is_entitled: bool) -> TreatmentDecision:
    """Assign the execution treatment for one proposed operation.

    The rules apply in order, and each can only refuse:

    1. **No catalogue entry** — ``NOT_ALLOWED``. A capability advertised by an external or MCP
       server becomes callable only once registered; discovery never confers entitlement
       (spec FR-EXT-014). ``None`` is a refusal, not a default.
    2. **Not entitled to this organisation** — ``NOT_ALLOWED``. There is no global capability
       set; capabilities resolve per organisation, least-privilege (spec FR-EXT-015).
    3. **Claims it requires elevation** — ``NOT_ALLOWED``. This release permits no elevation, and
       a database ``CHECK`` constraint already holds the field false (ADR-0004). Refusing here
       too means a row that somehow got past the constraint still cannot execute.
    4. **Staff approval with an empty accepted-role set** — ``NOT_ALLOWED``. An operation that
       accepts no roles denies every caller (spec FR-AUTHZ-010), so an approval requirement
       nobody can satisfy would otherwise suspend forever rather than refusing honestly.
    5. Otherwise the catalogue's declared treatment stands.

    Args:
        entry: The catalogue entry, or ``None`` when the lookup found nothing.
        is_entitled: Whether this organisation is entitled to the capability, resolved from
            ``tenant_entitlement`` by the caller. A separate argument rather than a property of
            the entry because entitlement is per organisation and the entry is not.

    Returns:
        The treatment and the rule that assigned it.

    Raises:
        PolicyWidenedTreatmentError: When a rule would widen the catalogue default — a defect.
    """
    if entry is None:
        return TreatmentDecision(ExecutionTreatment.NOT_ALLOWED, TreatmentReason.NOT_IN_CATALOGUE)

    default = entry.treatment

    if not is_entitled:
        return TreatmentDecision(
            _narrowed(default, ExecutionTreatment.NOT_ALLOWED), TreatmentReason.NOT_ENTITLED
        )

    if entry.requires_elevation:
        return TreatmentDecision(
            _narrowed(default, ExecutionTreatment.NOT_ALLOWED), TreatmentReason.ELEVATION_REFUSED
        )

    if default is ExecutionTreatment.STAFF_APPROVAL and entry.accepted_roles.is_empty:
        return TreatmentDecision(
            _narrowed(default, ExecutionTreatment.NOT_ALLOWED), TreatmentReason.NO_ROLE_CAN_APPROVE
        )

    return TreatmentDecision(default, TreatmentReason.CATALOGUE_DEFAULT)
