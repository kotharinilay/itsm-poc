"""The governance catalogue: the one shape a catalogue entry takes once governance can see it.

**Treatment is assigned from the catalogue, never from model output** (spec FR-AGENT-004,
constitution Principle III). :mod:`ragcore.governance.policy` makes that assignment; this module is
what guarantees the thing it is handed really is a catalogue entry.

**Why a type rather than a row.** ``OperationCatalogue.lookup`` selects columns from
``governance_record`` and returns a database row. A row is structurally whatever the query said:
its treatment column is called ``default_treatment``, its roles are an array of strings, and
nothing about it is checked. Policy reads ``entry.treatment`` and ``entry.accepted_roles``, so a
row reaching it directly fails at the attribute rather than at the boundary — and a *differently
shaped* row would fail later still, or not at all. :class:`CatalogueRecord` is where a row becomes
a catalogue entry, with every invariant checked once, at the edge, in one place.

**The invariants are refusals, not corrections.** A record that cannot be built is not a record
that gets a default. ``requires_elevation`` is already held false by a database ``CHECK``
constraint (ADR-0004); it is checked again here, because a row that somehow got past the
constraint — a restored dump, a manual insert, a future migration that dropped it — must still be
unable to become an executable operation. Two independent refusals for one rule is the intent.

Nothing here performs I/O or reads a clock. The catalogue is platform-wide; *entitlement* is the
tenant-scoped half and is resolved separately, because a capability is callable only when
registered **and** entitled and collapsing the two would make discovery an entitlement
(spec FR-EXT-014).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from ragcore.domain.governance import (
    CapabilityKind,
    ExecutionTreatment,
    RiskTier,
)
from ragcore.domain.identifiers import OperationIdentity
from ragcore.domain.roles import RoleSet, StaffRole

FIRST_VERSION: Final = 1
"""Catalogue versions start at one, matching the ``catalogue_versions_start_at_one`` constraint."""


class CatalogueRecordError(ValueError):
    """A row or declaration that cannot be a catalogue entry.

    A platform defect rather than a user-facing condition. Raised rather than returned because
    there is no degraded catalogue entry: a caller holding one of these has nothing it could safely
    do with a partially valid alternative.
    """


class ElevationNotPermittedError(CatalogueRecordError):
    """An entry claims it requires elevation. This release permits none (ADR-0004).

    Distinct from the general error so a test can name the rule it is asserting, and so an operator
    reading a stack trace sees the decision rather than a validation failure.
    """


@dataclass(frozen=True, slots=True)
class CatalogueRecord:
    """One catalogue entry, validated. Satisfies :class:`~ragcore.application.ports.CatalogueEntry`.

    Attributes:
        identity: Catalogue key plus the version in force. The version is part of the identity
            because an approval binds the version it was granted against.
        treatment: The entry's declared treatment. Deterministic policy reads this and may narrow
            it; **no model output ever writes it**.
        accepted_roles: The roles this operation accepts, as a set. **Empty denies everyone**
            (spec FR-AUTHZ-010) — which is the correct reading of an entry whose roles nobody has
            declared, and is why the field has no permissive default.
        kind: Whether this reads state or changes it.
        risk_tier: How much damage the operation could do. Describes the *operation*; treatment
            describes *how a human is involved*, and collapsing them would let a risk
            reclassification silently change who approves.
        is_reference_fixture: Whether this is an inert scaffold fixture. Never counted as, and
            never allowed to become, one of UC-01..UC-12 (spec FR-SCOPE-007).
        requires_elevation: Always ``False``. Constructing one with ``True`` raises.
        commands: The command set, disclosed **in full** to an approver. An approver who cannot see
            the commands is not approving the commands.
        content_hash: Binds what was approved to what executes, so a catalogue edit between the two
            cannot silently change it.
        verification_tool: The server-side read that confirms the effect. ``None`` means the best
            outcome available is ``client_attested`` — a claim, not confirmed resolution
            (ADR-0004).
    """

    identity: OperationIdentity
    treatment: ExecutionTreatment
    accepted_roles: RoleSet
    kind: CapabilityKind
    risk_tier: RiskTier
    is_reference_fixture: bool
    requires_elevation: bool = False
    commands: Mapping[str, Any] | None = None
    content_hash: str | None = None
    verification_tool: str | None = None

    def __post_init__(self) -> None:
        """Refuse anything that is not a catalogue entry.

        Raises:
            ElevationNotPermittedError: When the entry claims it needs elevation.
            CatalogueRecordError: When the identity is malformed.
        """
        if self.requires_elevation:
            raise ElevationNotPermittedError(
                f"{self.identity} declares requires_elevation; this release permits no elevation "
                f"(ADR-0004). The database holds the column false, and this refusal is the second "
                f"of two so a row that got past the constraint still cannot execute."
            )

        if not self.identity.catalogue_id:
            raise CatalogueRecordError("a catalogue entry has a non-empty catalogue_id")

        if self.identity.version < FIRST_VERSION:
            raise CatalogueRecordError(
                f"{self.identity} has version {self.identity.version}; versions start at "
                f"{FIRST_VERSION}"
            )

    @property
    def is_consequential(self) -> bool:
        """Whether executing this changes state somewhere outside the platform.

        The question the execution path asks before it records an audit event with a full actor
        chain. Derived from :attr:`kind` rather than from the treatment: an ``AUTO`` action is
        still consequential, and an operation that reads is not consequential however much
        approval it happens to require.
        """
        return self.kind is CapabilityKind.ACTION

    @property
    def can_be_server_confirmed(self) -> bool:
        """Whether a server-side read exists to verify the outcome.

        ``False`` means an execution of this operation can at best be ``client_attested``, and
        **MUST NOT** be presented as confirmed resolution (constitution Principle VIII).
        """
        return self.verification_tool is not None


def _roles_from(raw: Iterable[str] | RoleSet | None) -> RoleSet:
    """Build a role set from whatever the store holds.

    ``governance_record.accepted_roles`` is an array of text, and every value in it must be a role
    this platform defines. An unrecognised role is refused rather than dropped: silently discarding
    it would turn an entry that accepts one unknown role into an entry that accepts nobody, which
    denies quietly — and quiet denial is how a control stops being exercised.

    Raises:
        CatalogueRecordError: When a value is not a defined role.
    """
    if raw is None:
        return RoleSet()
    if isinstance(raw, RoleSet):
        return raw

    known = {role.value: role for role in StaffRole}
    roles: list[StaffRole] = []

    for value in raw:
        role = known.get(str(value))
        if role is None:
            raise CatalogueRecordError(
                f"accepted_roles holds {value!r}, which is not a defined staff role. Dropping it "
                f"would silently narrow the entry to accept nobody."
            )
        roles.append(role)

    return RoleSet.of(*roles)


def _member(enumeration: type[Any], value: Any) -> Any:  # Generic over enums
    """Resolve an enum member from a stored value, or refuse."""
    if isinstance(value, enumeration):
        return value
    try:
        return enumeration(value)
    except ValueError as error:
        raise CatalogueRecordError(
            f"{value!r} is not a member of {enumeration.__name__}"
        ) from error


def record_from_row(row: Any) -> CatalogueRecord:  # A database row
    """Turn a ``governance_record`` row into a validated catalogue entry.

    **This is the only place a stored row becomes something governance will act on.** The column is
    called ``default_treatment`` and the field policy reads is called ``treatment``; the rename
    happens here, once, rather than at each call site where getting it wrong would be an
    ``AttributeError`` in the execution path instead of a refusal at the boundary.

    Args:
        row: A row carrying the columns ``OperationCatalogue.lookup`` selects.

    Returns:
        The validated entry.

    Raises:
        CatalogueRecordError: When the row is not a usable catalogue entry.
        ElevationNotPermittedError: When the row claims it requires elevation.
    """
    try:
        return CatalogueRecord(
            identity=OperationIdentity(str(row.catalogue_id), int(row.version)),
            treatment=_member(ExecutionTreatment, row.default_treatment),
            accepted_roles=_roles_from(row.accepted_roles),
            kind=_member(CapabilityKind, row.kind),
            risk_tier=_member(RiskTier, row.risk_tier),
            is_reference_fixture=bool(row.is_reference_fixture),
            requires_elevation=bool(row.requires_elevation),
            commands=getattr(row, "commands", None),
            content_hash=getattr(row, "content_hash", None),
            verification_tool=getattr(row, "verification_tool", None),
        )
    except AttributeError as error:
        raise CatalogueRecordError(
            f"the catalogue row is missing a column governance requires: {error}"
        ) from error


@dataclass(frozen=True, slots=True)
class Catalogue:
    """A resolved set of catalogue entries, keyed by identity.

    Used where the entries are known in advance — the reference fixtures, and tests. The
    production path resolves entries from ``governance_record`` through
    :class:`~ragcore.persistence.repositories.OperationCatalogue`; this is not a second store and
    holds nothing the database does not.

    **A lookup miss returns ``None``, and ``None`` is a refusal.** There is no fallback entry and
    no permissive default, because an operation nobody registered is not an operation this platform
    performs (spec FR-EXT-014).
    """

    entries: Mapping[tuple[str, int], CatalogueRecord] = field(default_factory=dict)

    @classmethod
    def of(cls, *records: CatalogueRecord) -> Catalogue:
        """Build a catalogue from records, refusing a duplicate identity.

        Raises:
            CatalogueRecordError: When two records share one ``(catalogue_id, version)``. A
                catalogue entry is never edited in place — a change is a new version — so two
                records at one identity means one of them is describing an operation that no
                longer exists, and there is no way to tell which.
        """
        entries: dict[tuple[str, int], CatalogueRecord] = {}

        for record in records:
            key = (record.identity.catalogue_id, record.identity.version)
            if key in entries:
                raise CatalogueRecordError(
                    f"two catalogue records share the identity {record.identity}"
                )
            entries[key] = record

        return cls(entries)

    def find(self, identity: OperationIdentity) -> CatalogueRecord | None:
        """Resolve one entry, or ``None`` — a refusal, never a default."""
        return self.entries.get((identity.catalogue_id, identity.version))

    def __iter__(self) -> Iterator[CatalogueRecord]:
        """Iterate the records, in catalogue-id then version order.

        Ordered so that anything built from a catalogue — a report, a fixture loader, a test
        table — is stable across runs rather than dependent on insertion order.
        """
        return iter(sorted(self.entries.values(), key=lambda record: str(record.identity)))
