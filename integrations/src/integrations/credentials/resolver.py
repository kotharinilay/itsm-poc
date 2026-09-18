"""Per-organisation connector credentials. **A reference in PostgreSQL; the value in Key Vault.**

Spec `FR-EXT-016`, `FR-INTEG-017`. Credentials are held per organisation and per system, resolved
from the single secret source through managed identity, and MUST NEVER appear in conversation, the
step trail, telemetry or an audit record.

**This module is the only path from an entitlement row to a usable credential**, and it is short on
purpose — a second path would be a second place to review.

**The port is declared here rather than in `application/`, and that is the rule rather than an
exception** (constitution Principle V). Ports belong to the consuming module, and the consumer of a
per-organisation credential is an *adapter*. Nothing in the application layer or the API has any
business holding one, and declaring the port there would invite exactly that.

**A missing reference is a refusal.** :class:`TenantCredentialResolver` raises rather than returning
``None``, because a caller handed ``None`` has to decide what it means — and the tempting decisions,
carry on unauthenticated or fall back to a platform-wide credential, are precisely the
cross-organisation leak this arrangement exists to prevent.

**This service is the only holder of the vault role for connector secrets.** RagCore's identity does
not hold it; the role was withdrawn rather than duplicated, which is what makes `SC-DEMO-020`
provable by attempting the resolution from RagCore and observing Key Vault refuse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from sqlalchemy import text

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from uuid import UUID

    from integrations.persistence.engine import Database

__all__ = [
    "CredentialNotEntitledError",
    "SecretResolverPort",
    "SecretValue",
    "TenantCredentialResolver",
]

_CREDENTIAL_REFERENCE: Final = text(
    """
    SELECT c.credential_reference
    FROM platform.vw_connector_credential_ref_v1 AS c
    WHERE c.tenant_id = :tenant_id
      AND c.catalogue_id = :catalogue_id
    """
)


class SecretValue:
    """A resolved secret that **redacts itself in every rendering path**.

    The class exists because the guarantee cannot rest on discipline. A bare `str` passed to a
    logger, an f-string, a span attribute or an exception message is disclosed; this type renders as
    ``<redacted>`` in all four, and the value is reachable only through
    :meth:`reveal`, which is greppable.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        """Wrap a resolved value.

        Args:
            value: The secret. Held privately and never exposed by any dunder.
        """
        self._value = value

    def reveal(self) -> str:
        """The value itself.

        Call as late as possible — ideally while handing it to the client that needs it. A revealed
        value assigned to a local is a value that ends up in a traceback.

        Returns:
            The secret.
        """
        return self._value

    def __repr__(self) -> str:
        """``<redacted>``, so an f-string or a traceback discloses nothing."""
        return "<redacted>"

    __str__ = __repr__


@runtime_checkable
class SecretResolverPort(Protocol):
    """Where a secret **value** is resolved from. Key Vault, through managed identity."""

    async def resolve(self, secret_name: str) -> SecretValue:
        """Resolve one secret by name.

        Args:
            secret_name: The Key Vault secret name. A **name**, never a value.

        Returns:
            The wrapped value.
        """
        ...


class CredentialNotEntitledError(Exception):
    """This organisation holds no credential for this capability.

    Distinct from "the system is unreachable" and from "the secret would not resolve". Three
    different operator actions — entitle the organisation, fix the system, fix the vault — so three
    different failures.

    **Names the organisation and the capability. Never the reference, and never a value.**
    """

    def __init__(self, tenant_id: UUID, catalogue_id: str) -> None:
        """Describe the refusal without disclosing anything.

        Args:
            tenant_id: The organisation, by platform identifier.
            catalogue_id: The capability.
        """
        super().__init__(
            f"organisation {tenant_id} holds no credential for {catalogue_id}. Capabilities "
            "resolve per organisation on a least-privilege basis; there is no global credential to "
            "fall back to and none is used."
        )
        self.catalogue_id = catalogue_id


class TenantCredentialResolver:
    """Resolves one organisation's credential for one capability, at the point of use.

    **Nothing is cached here.** A cache keyed by organisation would be a second cache with its own
    eviction rules, and an entitlement revoked in the database would keep working for however long
    that cache decided. Caching belongs in the secret resolver, keyed by secret name, where its
    lifetime is a property of the vault rather than of an authorization decision.
    """

    def __init__(self, database: Database, secrets: SecretResolverPort) -> None:
        """Bind the resolver to its two halves.

        Args:
            database: Where the reference is read — the platform database, through the one view
                granted to this principal and to no other.
            secrets: Where the value is resolved — Key Vault, through managed identity.
        """
        self._database = database
        self._secrets = secrets

    async def resolve(self, tenant_id: UUID, catalogue_id: str) -> SecretValue:
        """Resolve this organisation's credential for this capability.

        Args:
            tenant_id: The organisation, from durable state. **Never supplied by a caller.**
            catalogue_id: The capability.

        Returns:
            The value, wrapped so logging, tracing or serialising it yields ``<redacted>``.

        Raises:
            CredentialNotEntitledError: When no enabled entitlement names a reference. Note the view
                itself filters on `enabled` — a disabled entitlement's credential has no legitimate
                reader, so it is not merely refused here, it is not visible to be refused.
        """
        rows = await self._database.read(
            _CREDENTIAL_REFERENCE, {"tenant_id": tenant_id, "catalogue_id": catalogue_id}
        )
        if not rows:
            raise CredentialNotEntitledError(tenant_id, catalogue_id)

        reference = rows[0]["credential_reference"]
        if not reference:
            raise CredentialNotEntitledError(tenant_id, catalogue_id)

        return await self._secrets.resolve(str(reference))
