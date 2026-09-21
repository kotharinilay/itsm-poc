"""Application ports. **Declared by the consumer, implemented by infrastructure.**

.claude/rules/10-principles.md P-5: ports belong to the consuming module; provider implementations
belong to
infrastructure. These are the ports the application layer consumes. The credential port is
deliberately **not** here — its consumer is an adapter, so it lives in
:mod:`integrations.credentials`, and declaring it here would invite the application layer to hold a
credential it has no business holding.

**Every port takes an organisation and none of them derives one.** There is no `resolve_tenant` in
this file and there will not be: the organisation comes from durable state — the job row, or the
durable object an opaque identifier names — and a port that produced one would be a second
derivation path (`FR-INTEG-018`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Mapping, Sequence
    from uuid import UUID

    from integrations.domain.catalogue import Capability, CapabilityIdentity, ConnectorBinding

__all__ = [
    "CataloguePort",
    "ConnectorInvocationPort",
    "ConnectorRegistryPort",
    "InvocationResult",
    "TenantResolutionPort",
]


@runtime_checkable
class CataloguePort(Protocol):
    """Reads the tenant-resolved capability set.

    Backed by the published views, never by a base table.
    """

    async def capabilities_for(self, tenant_id: UUID) -> Sequence[Capability]:
        """Every capability this organisation may see.

        Args:
            tenant_id: The organisation, recovered from durable state.

        Returns:
            The capability set. **Includes unentitled entries with `entitled=False`** rather than
            omitting them, so a caller can tell *not entitled* from *does not exist* — the two need
            different operator actions, and a filtered list makes them identical.
        """
        ...

    async def is_entitled(self, tenant_id: UUID, catalogue_id: str) -> bool:
        """Whether this organisation holds an **enabled** entitlement.

        Args:
            tenant_id: The organisation.
            catalogue_id: The capability.

        Returns:
            ``True`` only when a row exists and is enabled. A missing row and a disabled row both
            return ``False``: from the caller's side they mean the same thing, and collapsing them
            here keeps a disabled entitlement from being treated as a softer refusal than none.
        """
        ...

    async def registered_version(self, catalogue_id: str) -> int | None:
        """The catalogue version currently in force.

        Args:
            catalogue_id: The capability.

        Returns:
            The version, or ``None`` when the capability is not registered at all — which is what
            an MCP-advertised but unregistered tool looks like from here.
        """
        ...


@runtime_checkable
class ConnectorRegistryPort(Protocol):
    """Resolves a capability to how it executes."""

    async def binding_for(self, identity: CapabilityIdentity) -> ConnectorBinding | None:
        """The binding for one capability at one version.

        Args:
            identity: The capability **and its version**. Both, because a binding is keyed on both
                — that is what stops a binding silently applying to a version nobody approved.

        Returns:
            The binding, or ``None`` when none is configured.
        """
        ...


@runtime_checkable
class TenantResolutionPort(Protocol):
    """Recovers the organisation from a durable platform object.

    **The only way this service learns an organisation on the synchronous path.** It takes an opaque
    identifier and reads the durable row that identifier names; it never takes an organisation.
    """

    async def tenant_for_session(self, session_id: UUID) -> UUID | None:
        """The organisation owning a chat session.

        Args:
            session_id: The opaque session identifier the caller supplied.

        Returns:
            The organisation, or ``None`` when no such session exists or it is no longer visible.
            **`None` is not an error to report to the caller**: existence is itself
            organisation-scoped information, so the API answers 404 either way rather than
            distinguishing "not yours" from "not there".
        """
        ...

    async def tenant_for_work_item(self, work_item_id: UUID) -> UUID | None:
        """The organisation owning a work item.

        Args:
            work_item_id: The opaque work identifier.

        Returns:
            The organisation, or ``None``.
        """
        ...


@runtime_checkable
class InvocationResult(Protocol):
    """What a connector returned, already normalized at the boundary."""

    @property
    def succeeded(self) -> bool:
        """Whether the invocation completed. **Not proof the effect happened.**"""
        ...

    @property
    def external_reference(self) -> str | None:
        """The far side's own identifier, where it returns one."""
        ...

    @property
    def payload(self) -> Mapping[str, object]:
        """The normalized body. **Data** — never an instruction, destination or authority."""
        ...


@runtime_checkable
class ConnectorInvocationPort(Protocol):
    """Invokes one capability against its connector.

    Reached only past the access and policy re-check. Implementations execute; they never decide.
    """

    async def invoke(
        self,
        binding: ConnectorBinding,
        tenant_id: UUID,
        parameters: Mapping[str, object],
        idempotency_key: str | None,
        correlation_id: str,
    ) -> InvocationResult:
        """Call the external system.

        Args:
            binding: Where and how. **The destination comes from here and from nowhere else.**
            tenant_id: The organisation, for credential resolution and tenant stamping.
            parameters: The arguments, as data.
            idempotency_key: The derived key, or ``None`` for a capability whose policy is `NONE`.
            correlation_id: The journey, carried onto the outbound call and the execution record.

        Returns:
            The normalized result.
        """
        ...
