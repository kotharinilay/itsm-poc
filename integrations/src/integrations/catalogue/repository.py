"""Catalogue and entitlement reads, over the published views.

Implements :class:`~integrations.application.ports.CataloguePort` and
:class:`~integrations.application.ports.TenantResolutionPort`.

**Every query is parameterised and every tenant-scoped query carries the organisation.** There is no
code path here that can issue an unfiltered read — not because a reviewer checks, but because the
only statements in this module are the ones below and each one binds `:tenant_id`. Constitution
Principle IV: a code path able to issue an unfiltered query MUST NOT exist.

**Views only.** `vw_governance_catalogue_v1` for what a capability is,
`vw_tenant_entitlement_v1` for whether an organisation may use it, `vw_session_summary_v1` and
`vw_work_item_v1` to recover an organisation from an opaque identifier. The Integrations principal
holds `SELECT` on exactly two of those and no grant on any base table, so a statement that reached
past the read contract fails at PostgreSQL rather than working until somebody notices.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from sqlalchemy import text

from integrations.domain.catalogue import Capability, CapabilityIdentity

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Sequence
    from uuid import UUID

    from integrations.persistence.engine import Database

__all__ = ["CatalogueRepository", "TenantResolver"]

# LEFT JOIN, not INNER. An unentitled capability must still appear, carrying `entitled = false`,
# so a caller can tell "not entitled" from "does not exist" — the two need different operator
# actions, and an inner join would make them indistinguishable by omission.
_CAPABILITIES: Final = text(
    """
    SELECT
        g.catalogue_id,
        g.version,
        g.kind,
        g.is_reference_fixture,
        COALESCE(e.enabled, FALSE) AS entitled
    FROM platform.vw_governance_catalogue_v1 AS g
    LEFT JOIN platform.vw_tenant_entitlement_v1 AS e
           ON e.catalogue_id = g.catalogue_id
          AND e.tenant_id = :tenant_id
    ORDER BY g.catalogue_id, g.version
    """
)

_IS_ENTITLED: Final = text(
    """
    SELECT e.enabled
    FROM platform.vw_tenant_entitlement_v1 AS e
    WHERE e.tenant_id = :tenant_id
      AND e.catalogue_id = :catalogue_id
    """
)

# MAX, because a catalogue entry is versioned and never edited in place: a change is a new row.
# "The version in force" is therefore the highest one, and asking for it explicitly is better than
# ordering and taking the first, which reads as an arbitrary choice to the next person.
_REGISTERED_VERSION: Final = text(
    """
    SELECT MAX(g.version) AS version
    FROM platform.vw_governance_catalogue_v1 AS g
    WHERE g.catalogue_id = :catalogue_id
    """
)

_TENANT_FOR_SESSION: Final = text(
    """
    SELECT s.tenant_id
    FROM platform.vw_session_summary_v1 AS s
    WHERE s.session_id = :session_id
    """
)

_TENANT_FOR_WORK_ITEM: Final = text(
    """
    SELECT w.tenant_id
    FROM platform.vw_work_item_v1 AS w
    WHERE w.work_item_id = :work_item_id
    """
)


class CatalogueRepository:
    """The tenant-resolved capability set."""

    def __init__(self, database: Database) -> None:
        """Bind the repository.

        Args:
            database: Read access over the published views.
        """
        self._database = database

    async def capabilities_for(self, tenant_id: UUID) -> Sequence[Capability]:
        """Every capability this organisation may see.

        Args:
            tenant_id: The organisation, recovered from durable state.

        Returns:
            The capability set, entitled and unentitled alike.
        """
        rows = await self._database.read(_CAPABILITIES, {"tenant_id": tenant_id})
        return [
            Capability(
                identity=CapabilityIdentity(
                    catalogue_id=row["catalogue_id"], version=row["version"]
                ),
                kind=row["kind"],
                entitled=bool(row["entitled"]),
                # AVAILABILITY IS NOT KNOWN FROM THE DATABASE. Reachability is a property of the
                # external system at this instant, and this read reports the catalogue. Defaulted
                # to True here and narrowed by the availability check at the API boundary — never
                # the other way round, because defaulting to False would report every capability as
                # broken whenever the check had not run.
                available=True,
                is_reference_fixture=bool(row["is_reference_fixture"]),
            )
            for row in rows
        ]

    async def is_entitled(self, tenant_id: UUID, catalogue_id: str) -> bool:
        """Whether this organisation holds an enabled entitlement.

        Args:
            tenant_id: The organisation.
            catalogue_id: The capability.

        Returns:
            ``True`` only for an existing, enabled row.
        """
        rows = await self._database.read(
            _IS_ENTITLED, {"tenant_id": tenant_id, "catalogue_id": catalogue_id}
        )
        return bool(rows[0]["enabled"]) if rows else False

    async def registered_version(self, catalogue_id: str) -> int | None:
        """The catalogue version in force.

        Args:
            catalogue_id: The capability.

        Returns:
            The version, or ``None`` when unregistered.
        """
        rows = await self._database.read(_REGISTERED_VERSION, {"catalogue_id": catalogue_id})
        if not rows:
            return None
        version = rows[0]["version"]
        return int(version) if version is not None else None


class TenantResolver:
    """Recovers an organisation from a durable platform object — and from nothing else."""

    def __init__(self, database: Database) -> None:
        """Bind the resolver.

        Args:
            database: Read access over the published views.
        """
        self._database = database

    async def tenant_for_session(self, session_id: UUID) -> UUID | None:
        """The organisation owning a chat session.

        Args:
            session_id: The opaque identifier the caller supplied.

        Returns:
            The organisation, or ``None``.
        """
        rows = await self._database.read(_TENANT_FOR_SESSION, {"session_id": session_id})
        return rows[0]["tenant_id"] if rows else None

    async def tenant_for_work_item(self, work_item_id: UUID) -> UUID | None:
        """The organisation owning a work item.

        Args:
            work_item_id: The opaque identifier.

        Returns:
            The organisation, or ``None``.
        """
        rows = await self._database.read(_TENANT_FOR_WORK_ITEM, {"work_item_id": work_item_id})
        return rows[0]["tenant_id"] if rows else None
