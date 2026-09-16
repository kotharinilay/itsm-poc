"""Per-organisation, per-system credentials. **A reference in PostgreSQL; the value in Key Vault.**

Credentials for a third-party system are held per organisation and per system, resolved from the
single secret source, and MUST NEVER appear in conversation, the step trail, telemetry or audit
records (spec FR-EXT-016). This module is the only path from an entitlement row to a usable
credential, and it is short on purpose — a second path would be a second place to review.

**Two stores, and only one of them ever holds a value.** ``tenant_entitlement.credential_reference``
holds a Key Vault secret *name* (``data-model.md``); the value is fetched at the point of use
through managed identity and returned as
:class:`~ragcore.config.secrets.SecretValue`, which redacts itself in every rendering path. A
resolved value is never written back to PostgreSQL, never logged and never attached to a span.

**The port is declared here rather than in ``application/``, and that is the rule rather than an
exception.** Ports belong to the consuming module (constitution Principle V). The consumer of a
per-organisation credential is an *adapter* — nothing in the application layer or the agent loop
has any business holding one, and declaring the port there would invite exactly that.

**A missing reference is a refusal.** :class:`TenantCredentialResolver` raises rather than
returning ``None``, because a caller handed ``None`` has to decide what it means, and the tempting
decision — carry on unauthenticated, or fall back to a platform-wide credential — is precisely the
cross-organisation credential leak this arrangement exists to prevent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ragcore.config.secrets import SecretRef
from ragcore.domain.errors import DomainError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.secrets import SecretResolverPort, SecretValue
    from ragcore.domain.tenancy import TenantContext


class CredentialNotEntitledError(DomainError):
    """This organisation holds no credential for this system.

    Distinct from "the system is unreachable" (:mod:`ragcore.execution.availability`) and from
    "the secret would not resolve" (:class:`~ragcore.config.secrets.SecretResolutionError`). Three
    different operator actions — entitle the organisation, fix the system, fix the vault — so three
    different failures.

    **Names the organisation by its platform identifier and names the system. Never the reference,
    and never a value.**
    """

    def __init__(self, tenant_id: str, system: str) -> None:
        super().__init__(
            f"organisation {tenant_id} holds no credential for {system}. Capabilities resolve per "
            "organisation on a least-privilege basis; there is no global credential to fall back "
            "to and none is used."
        )
        self.system = system


@runtime_checkable
class CredentialReferenceStorePort(Protocol):
    """Where a credential **reference** is read from.

    Returns a name, never a value — which is why this port can be satisfied by a repository over
    PostgreSQL without PostgreSQL ever holding secret material.
    """

    async def credential_reference(
        self, tenant: TenantContext, catalogue_prefix: str
    ) -> str | None:
        """The Key Vault secret name this organisation uses for one system's capabilities.

        Args:
            tenant: The organisation, from trusted context.
            catalogue_prefix: The catalogue-identifier prefix the system owns, formed by
                :func:`catalogue_prefix_for`. The store receives it already formed so that no
                implementation has to build a string inside a query.

        Returns:
            The reference, or ``None`` when the organisation has no entitlement row for the system
            or the row names no credential.
        """
        ...


def catalogue_prefix_for(system: str) -> str:
    """The catalogue-identifier prefix one system owns, for example ``onelogin.``.

    One function rather than a convention each caller repeats. Every integration module declares the
    same value as its own ``CATALOGUE_PREFIX`` — the name is the credential key, the endpoint key
    and the catalogue prefix at once, and three separately assembled spellings would be three places
    for a mismatch to hide. A mismatch here presents as "entitled, but nothing works".

    Args:
        system: The system's platform name.

    Returns:
        The prefix.

    Raises:
        ValueError: When the name is blank. An empty prefix would match every capability in the
            catalogue, and the credential it resolved would be whichever row happened to be first.
    """
    if not system.strip():
        raise ValueError("a system name is required; an empty prefix would match every capability")

    return f"{system.strip()}."


class TenantCredentialResolver:
    """Resolves one organisation's credential for one system, at the point of use.

    **Nothing is cached here.** :class:`~ragcore.config.secrets.KeyVaultSecretResolver` caches by
    secret name for the process lifetime, which is the correct place for it: a cache keyed by
    organisation in this class would be a second cache with its own eviction rules, and an
    entitlement that was revoked would keep working for however long that cache decided.
    """

    def __init__(self, store: CredentialReferenceStorePort, secrets: SecretResolverPort) -> None:
        """Bind the resolver to its two halves.

        Args:
            store: Where the reference is read. The platform database.
            secrets: Where the value is resolved. Key Vault, through managed identity.
        """
        self._store = store
        self._secrets = secrets

    async def resolve(self, tenant: TenantContext, system: str) -> SecretValue:
        """Resolve this organisation's credential for this system.

        Args:
            tenant: The organisation, from trusted context. Never supplied by a client.
            system: The system's platform name — ``servicenow``, ``onelogin``, ``duo``.

        Returns:
            The value, wrapped so that logging, tracing or serialising it yields ``<redacted>``.
            Call :meth:`~ragcore.config.secrets.SecretValue.reveal` as late as possible — ideally
            while handing it to the client that needs it.

        Raises:
            CredentialNotEntitledError: When the organisation holds no reference for this system.
            SecretResolutionError: When the reference exists but the value will not resolve.
        """
        reference = await self._store.credential_reference(tenant, catalogue_prefix_for(system))

        if not reference:
            raise CredentialNotEntitledError(str(tenant.tenant_id.value), system)

        return await self._secrets.resolve(SecretRef(reference))
