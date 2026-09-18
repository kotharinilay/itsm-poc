"""The connector registry. **The only place a destination comes from.**

Implements :class:`~integrations.application.ports.ConnectorRegistryPort` over the `integration`
schema this service owns.

**Spec `FR-EXT-018`: the destination of an outbound call MUST NEVER be derived from retrieved
content, model output or chat text.** This module is where that rule is kept, and the way it is kept
is that there is no function here taking a URL, a host, a path override or a base address. A
capability resolves to a binding; the binding carries an endpoint that came from a row. A helper
accepting an override is how that hole opens, so none exists.

**Keyed on `(catalogue_id, catalogue_version)`.** Both halves, always. A binding found by identifier
alone would apply to whatever version happened to be current, which is exactly how an approval
granted against one version comes to execute another.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from sqlalchemy import text

from integrations.domain.catalogue import ConnectorBinding, IdempotencyPolicy

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.domain.catalogue import CapabilityIdentity
    from integrations.persistence.engine import Database

__all__ = ["ConnectorRegistry"]

_BINDING: Final = text(
    """
    SELECT
        b.catalogue_id,
        b.catalogue_version,
        b.connector_id,
        b.operation_path,
        b.signing_profile,
        b.idempotency_policy,
        c.base_endpoint,
        c.is_reference_fixture
    FROM integration.connector_binding AS b
    JOIN integration.connector AS c ON c.connector_id = b.connector_id
    WHERE b.catalogue_id = :catalogue_id
      AND b.catalogue_version = :catalogue_version
    """
)


class ConnectorRegistry:
    """Resolves a capability at a version to the connector that runs it."""

    def __init__(self, database: Database) -> None:
        """Bind the registry.

        Args:
            database: The `integration` schema.
        """
        self._database = database

    async def binding_for(self, identity: CapabilityIdentity) -> ConnectorBinding | None:
        """The binding for one capability at one version.

        Args:
            identity: The capability and its version.

        Returns:
            The binding, or ``None`` when none is configured. ``None`` is a **configuration gap**,
            not a denial — the caller maps it to `NO_BINDING` so an operator is told to configure a
            binding rather than to entitle an organisation that is already entitled.
        """
        rows = await self._database.read(
            _BINDING,
            {"catalogue_id": identity.catalogue_id, "catalogue_version": identity.version},
        )
        if not rows:
            return None

        row = rows[0]
        return ConnectorBinding(
            identity=identity,
            connector_id=row["connector_id"],
            base_endpoint=row["base_endpoint"],
            operation_path=row["operation_path"],
            signing_profile=row["signing_profile"],
            idempotency_policy=IdempotencyPolicy(row["idempotency_policy"]),
            is_reference_fixture=bool(row["is_reference_fixture"]),
        )
