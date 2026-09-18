"""The execution-time access and policy re-check. **Prior retrieval is not standing permission.**

Spec `FR-INTEG-019`. Every fact below is re-verified **at the point of effect, against durable
state**, even when the caller already retrieved the catalogue and even when governance already gated
the operation.

**What this re-verifies — facts:**

* the organisation holds an enabled entitlement;
* the capability is registered at all;
* the registered version matches the one being invoked;
* a connector binding exists.

**What it deliberately does not re-derive — decisions** (`FR-INTEG-008`):

* **execution treatment** — `AUTO`, `END_USER_APPROVAL`, `STAFF_APPROVAL`, `NOT_ALLOWED`. That is
  deterministic governance's, in RagCore. Re-deriving it here would create a second policy authority
  that can disagree with the first, and two authorities that disagree is strictly worse than one
  that is occasionally wrong: nobody can say which answer is the platform's.
* **role-set intersection** — roles are a request-time, gateway-derived concept, and the approval
  record already binds the roles held at decision time.

The division is: **this service re-verifies every fact; governance and approval remain the sole
authority for every decision.**

**Why re-check at all, if RagCore already gated it.** Because the gate ran at proposal time against
state that can have changed, and because a service that trusted its caller's word would be
authorizing on an assertion. An entitlement revoked between proposal and execution, a catalogue
entry versioned forward, a binding removed — each is ordinary, and each would otherwise execute.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from integrations.domain.catalogue import AccessDecision, AccessRefusal

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

    from integrations.application.ports import CataloguePort, ConnectorRegistryPort
    from integrations.domain.catalogue import CapabilityIdentity

__all__ = ["AccessPolicy"]


class AccessPolicy:
    """Re-verifies access and binding facts immediately before an effect."""

    def __init__(self, catalogue: CataloguePort, registry: ConnectorRegistryPort) -> None:
        """Bind the policy to its sources.

        Args:
            catalogue: Entitlement and registration, over the published views.
            registry: The connector binding, over the owned schema.
        """
        self._catalogue = catalogue
        self._registry = registry

    async def evaluate(self, tenant_id: UUID, identity: CapabilityIdentity) -> AccessDecision:
        """Decide whether this organisation may invoke this capability at this version, now.

        The order is deliberate and is **cheapest-and-most-specific first**: entitlement, then
        registration, then version, then binding. Two reasons — an unentitled caller is refused
        without a second query, and the refusal a caller receives names the *first* thing wrong
        rather than the last, which is what makes it actionable.

        Args:
            tenant_id: The organisation, recovered from durable state. **Never from a request field,
                a message payload or a token.**
            identity: The capability and the version being invoked.

        Returns:
            A permit carrying the binding, or a refusal naming what an operator must fix.
        """
        if not await self._catalogue.is_entitled(tenant_id, identity.catalogue_id):
            # Covers both "no row" and "row disabled". From the caller's side they are the same
            # thing, and the operator action — entitle this organisation — is the same too.
            return AccessDecision.refuse(AccessRefusal.NOT_ENTITLED)

        registered = await self._catalogue.registered_version(identity.catalogue_id)
        if registered is None:
            # Discovery never confers entitlement (spec FR-EXT-014). A capability an MCP server
            # advertises but the catalogue does not hold lands exactly here, which is the point:
            # the gap between advertised and callable is this check.
            return AccessDecision.refuse(AccessRefusal.NOT_REGISTERED)

        if registered != identity.version:
            # THE APPROVAL BOUND A VERSION. Executing a different one executes behaviour nobody
            # authorized, even though the identifier matches — and the identifier matching is
            # precisely why this would otherwise pass unnoticed.
            return AccessDecision.refuse(AccessRefusal.VERSION_MISMATCH)

        binding = await self._registry.binding_for(identity)
        if binding is None:
            # A configuration gap rather than a denial: entitled, registered, current — but nothing
            # says how to run it. Distinct so the operator configures a binding instead of
            # re-entitling an organisation that is already entitled.
            return AccessDecision.refuse(AccessRefusal.NO_BINDING)

        return AccessDecision.allow(binding)
