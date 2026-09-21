"""Staff roles and the one authorization primitive: set intersection.

Mirrors ``Synthia.SharedKernel.Authorization`` in the .NET stack. The two are proven independently
by their own tests rather than sharing code, because the deployables have no application-level
dependency in either direction (ADR-0001) — duplication across that boundary is cheaper than a
false shared contract (.claude/rules/10-principles.md P-6).

Imports nothing outside the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class StaffRole(Enum):
    """A staff capability. Roles are **disjoint capability sets, never a hierarchy**.

    This is a plain :class:`~enum.Enum`, deliberately **not** ``StrEnum`` or ``IntEnum``. Both of
    those inherit an ordering from their mixin, so ``ADMINISTRATOR > TECHNICIAN``
    would evaluate rather than raise — exactly the ranking the identity plane prohibits
    (A1 §6). A plain ``Enum`` raises ``TypeError`` on ``<``, so the prohibited comparison
    fails loudly at the first attempt instead of quietly returning a plausible answer.

    ``administrator`` does NOT imply ``technician``.
    """

    END_USER = "end_user"
    """Any person acting on a customer surface, including staff doing so."""

    TECHNICIAN = "technician"
    """The role that may approve in the initial release."""

    SENIOR_TECHNICIAN = "senior_technician"
    """A defined role that no operation accepts in the initial release (spec FR-AUTHZ-008).

    Its presence is what keeps the no-hierarchy rule honest: a set with a member that grants
    nothing cannot be quietly reimplemented as a rank.
    """

    ADMINISTRATOR = "administrator"
    """Platform administration. Does NOT imply :attr:`TECHNICIAN`."""

    NONE = "none"
    """The sentinel carried by an app-only (Workload) credential."""

    @classmethod
    def parse(cls, name: str) -> StaffRole | None:
        """Parse a canonical role name from the Gateway-derived header contract.

        Matching is exact and case-sensitive. The specification makes the canonical form a security
        property rather than tidiness: accepting ``Administrator`` would mean the set of accepted
        spellings is larger than the set that was reviewed.

        Args:
            name: The candidate role name.

        Returns:
            The role, or ``None`` when the name is not canonical.
        """
        for role in cls:
            if role.value == name:
                return role
        return None


SENTINEL_ROLES: Final[frozenset[StaffRole]] = frozenset({StaffRole.END_USER, StaffRole.NONE})
"""Roles that are single-member sets and never combine with anything."""


@dataclass(frozen=True, slots=True)
class RoleSet:
    """The roles a principal holds, or the roles an operation accepts.

    A set, not a list: order carries no meaning and duplicates say nothing. The type exposes
    :meth:`intersects` and nothing that could be mistaken for a ranking.
    """

    roles: frozenset[StaffRole] = frozenset()

    @classmethod
    def of(cls, *roles: StaffRole) -> RoleSet:
        """Build a set from the given roles, discarding duplicates.

        Args:
            *roles: The roles to include.

        Returns:
            The resulting set.
        """
        return cls(frozenset(roles))

    @property
    def is_empty(self) -> bool:
        """Whether the set holds no roles."""
        return not self.roles

    def contains(self, role: StaffRole) -> bool:
        """Whether this set holds ``role``.

        Args:
            role: The role to look for.

        Returns:
            ``True`` when present.
        """
        return role in self.roles

    def intersects(self, other: RoleSet) -> bool:
        """Whether this set shares at least one role with ``other``.

        Args:
            other: The set to intersect with.

        Returns:
            ``True`` when the intersection is non-empty.
        """
        return bool(self.roles & other.roles)

    def canonical(self) -> str:
        """Render in canonical order — lowercase, comma-separated, ascending ordinal.

        Canonical ordering is a security property, not tidiness: it makes "array order never
        decides anything" checkable at the boundary rather than trusted.

        Returns:
            The canonical header form.
        """
        return ",".join(sorted(role.value for role in self.roles))


EMPTY_ROLE_SET: Final = RoleSet()
"""An operation accepting this denies everyone."""


class DenialReason(Enum):
    """Why an authorization attempt was refused.

    Never surfaced verbatim to a caller — a refusal reason is operational and audit detail, not a
    client contract.
    """

    EMPTY_INTERSECTION = "empty_intersection"
    """The principal holds no role the operation accepts."""

    OPERATION_ACCEPTS_NO_ROLES = "operation_accepts_no_roles"
    """The operation declares no accepted roles, so it denies everyone."""

    PRINCIPAL_HOLDS_NO_ROLES = "principal_holds_no_roles"
    """The principal holds no roles at all."""


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """The outcome of one authorization evaluation.

    Carries the role set held **at the moment of decision**, because a later role change must not
    retroactively alter a recorded decision (spec FR-AUTHZ-011).
    """

    is_permitted: bool
    roles_held_at_decision: RoleSet
    reason: DenialReason | None = None

    @classmethod
    def permit(cls, roles_held: RoleSet) -> AuthorizationDecision:
        """Record a permitted decision.

        Args:
            roles_held: The roles held at decision time.

        Returns:
            The decision.
        """
        return cls(is_permitted=True, roles_held_at_decision=roles_held, reason=None)

    @classmethod
    def deny(cls, roles_held: RoleSet, reason: DenialReason) -> AuthorizationDecision:
        """Record a refusal.

        Args:
            roles_held: The roles held at decision time.
            reason: Why the attempt was refused.

        Returns:
            The decision.
        """
        return cls(is_permitted=False, roles_held_at_decision=roles_held, reason=reason)


def evaluate(principal_roles: RoleSet, operation_accepted_roles: RoleSet) -> AuthorizationDecision:
    """Decide whether a principal may perform an operation.

    ``principal roles ∩ operation accepted roles ≠ ∅``

    There is no other way to decide a staff operation. No ranking, no precedence, no implied
    capability. An empty intersection denies, and an operation that accepts no roles denies
    everyone — the second is not a special case of the first, so both are named explicitly and
    tested separately.

    This is a pure function, not a port: it needs no database, no clock and no configuration, so
    anything that appears to require those to authorize is doing something else.

    Args:
        principal_roles: The roles the principal holds.
        operation_accepted_roles: The roles the operation accepts, declared explicitly.

    Returns:
        The decision, carrying the role set held at decision time.
    """
    if operation_accepted_roles.is_empty:
        # A TOTAL denial, never an implicit allow (spec FR-AUTHZ-010). The failure mode where
        # "no roles configured" silently means "anyone" is what this branch exists to prevent.
        return AuthorizationDecision.deny(principal_roles, DenialReason.OPERATION_ACCEPTS_NO_ROLES)

    if principal_roles.is_empty:
        return AuthorizationDecision.deny(principal_roles, DenialReason.PRINCIPAL_HOLDS_NO_ROLES)

    if principal_roles.intersects(operation_accepted_roles):
        return AuthorizationDecision.permit(principal_roles)

    return AuthorizationDecision.deny(principal_roles, DenialReason.EMPTY_INTERSECTION)
