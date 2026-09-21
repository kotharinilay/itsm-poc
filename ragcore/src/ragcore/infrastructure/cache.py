"""Redis. **Transient only — never an authority, never a durable record** (A2 §8.1).

PostgreSQL is the single authority for platform durable state. Redis holds copies of things that are
cheap to recompute and worthless to keep: it is never a source of truth, no sample flow reads it,
and losing the entire cache costs latency and nothing else. That is the test of whether a store is
genuinely transient, and this one is built to pass it.

**The type is the control, not the convention.** A cache with a general ``set(key, value)`` is a
durable store that everyone has agreed to use politely, and the agreement lasts until the first
person who needs somewhere to put a decision. So:

* **Every entry carries a TTL, and there is no way to write one without.** ``ttl`` is a required,
  non-defaulted parameter of :meth:`TransientCache.put`. There is no ``persist``, no ``ttl=None``
  and no ``EXPIRE``-clearing method anywhere in this module.
* **The TTL is bounded above** by :data:`MAX_TTL_SECONDS`. An entry that outlives the execution
  window it relates to is a stale answer to a question somebody is asking *now*.
* **Values are text.** There is no object serialisation, so a work item, an approval or a
  :class:`~ragcore.domain.decisions.StaffVerdict` cannot be round-tripped through here. Putting one
  in is a deliberate act of serialising it first, which is a code review rather than an import.
* **A read may always return** ``None``. Callers are written for a miss because a miss is the normal
  case after any eviction, restart or failover — which means no code path can come to depend on a
  value being there.

**Managed identity where the configuration supports it.** ``build/policy/azure-identity.json`` lists
Redis as ``managedIdentity: conditional`` — Azure Cache for Redis and Azure Managed Redis support
Entra authentication on the tiers this platform selects, and it is *required* wherever the selected
configuration supports it. Conditional records a genuine provider limitation, not a preference: a
password is not an acceptable default, and a configuration without Entra support is an exemption
that belongs in the registry with a named owner. Authorization is a Redis **access policy** assigned
to the identity's object id, not an RBAC role assignment — writing it as a role produces a
deployment that succeeds and an application that cannot connect.

**A cache failure is never a request failure.** Every method swallows transport errors and reports a
miss, because the fallback for a cache miss is to do the work, and the fallback for a cache outage
must be the same thing. A cache that could fail a request would be durable state wearing a cache's
name.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import CacheSettings
    from ragcore.domain.tenancy import TenantContext

_log: Final = logging.getLogger(__name__)

REDIS_SCOPE: Final = "https://redis.azure.com/.default"
"""The Entra scope for Azure Managed Redis data-plane access.

A scope, not a credential. The token is minted on demand by the shared managed identity, and what it
actually permits is decided by the access policy assigned to that identity on the cache.
"""

MAX_TTL_SECONDS: Final = 900
"""Fifteen minutes — the execution window, and the longest anything here may live.

Bounded above by the same number deliberately. Nothing cached can usefully outlive the window of the
work it relates to: past that point the decision it was helping with has expired, and a surviving
entry is a stale answer to a question being asked now.
"""

MAX_VALUE_BYTES: Final = 65_536
"""The ceiling on one entry. A cache holding large objects is a store, whatever it is called."""


@runtime_checkable
class TransientCachePort(Protocol):
    """A cache. **Deliberately the smallest interface that is still useful.**

    Three methods and no others. There is no ``keys``, no ``scan`` and no ``flush``: an enumerable
    cache is one something can iterate to rebuild state from, which is the first step towards
    treating it as a record.
    """

    async def get(self, tenant: TenantContext, key: str) -> str | None:
        """Read within the organisation.

        Returns:
            The value, or ``None``. **A miss is normal**, and every caller is written for it.
        """
        ...

    async def put(self, tenant: TenantContext, key: str, value: str, *, ttl_seconds: int) -> None:
        """Write within the organisation, with an expiry.

        ``ttl_seconds`` is required and keyword-only — required so that an entry without one cannot
        be written, keyword-only so that it cannot be supplied by accident in a positional slot and
        must be named at every call site.
        """
        ...

    async def invalidate(self, tenant: TenantContext, key: str) -> None:
        """Drop an entry early. Always safe: the fallback is to do the work."""
        ...


def cache_key(tenant: TenantContext, key: str) -> str:
    """Namespace a key to one organisation.

    **Every key is prefixed, with no way to write an unprefixed one**, for the same reason retrieval
    has no unfiltered query path: a shared key space is a cross-organisation read, and here it would
    be one that no database-level isolation could catch — the platform would be serving one
    organisation an answer computed for another, with the tenant filter applied correctly at every
    layer below.

    Args:
        tenant: The organisation, from trusted context.
        key: The caller's key.

    Returns:
        The namespaced key.

    Raises:
        ValueError: When the key is blank. An empty key collides with every other empty key across
            the whole platform.
    """
    if not key.strip():
        raise ValueError("a cache key is required; an empty one collides with every other")

    return f"synthia:{tenant.tenant_id.value}:{key.strip()}"


class NullCache:
    """A cache that stores nothing and always misses.

    Satisfies :class:`TransientCachePort`. What a process gets when no cache is configured, which is
    the developer-machine case and a legitimate deployed one.

    **Honest rather than convenient** (constitution Principle IX): it does not pretend to cache, and
    every caller takes the path it would take after an eviction. If anything ever stops working with
    this bound, that is the discovery that something had come to depend on the cache — which is the
    exact defect the transient-only rule exists to prevent, surfaced at development time.
    """

    async def get(self, tenant: TenantContext, key: str) -> str | None:
        """Always a miss."""
        del tenant, key
        return None

    async def put(self, tenant: TenantContext, key: str, value: str, *, ttl_seconds: int) -> None:
        """Discard. Validated first, so a call site that would be rejected by the real cache is
        rejected here too — otherwise a bad TTL ships because it was only ever exercised locally."""
        _validate(key, value, ttl_seconds)
        del tenant

    async def invalidate(self, tenant: TenantContext, key: str) -> None:
        """Nothing to drop."""
        del tenant, key


class RedisTransientCache:
    """Azure Managed Redis, reached by managed identity, holding nothing that matters.

    Satisfies :class:`TransientCachePort`.
    """

    def __init__(
        self,
        settings: CacheSettings,
        client: Any | None = None,  # The concrete type needs the SDK imported
        credential: Any | None = None,  # Likewise
    ) -> None:
        """Bind the cache to an endpoint.

        Args:
            settings: The cache settings. **There is no password field and there will not be one**
                — ``build/policy/azure-identity.json`` names ``password`` and ``access key`` as
                forbidden configuration for this resource.
            client: A Redis client. Constructed on first use when omitted; supplied by a test so the
                key namespacing and TTL rules are exercised without a server.
            credential: The Azure credential. The shared process credential when omitted.
        """
        self._settings = settings
        self._client = client
        self._credential = credential

    async def get(self, tenant: TenantContext, key: str) -> str | None:
        """Read within the organisation.

        Returns:
            The value, or ``None`` on a miss **or on any failure**. A cache outage is reported as a
            miss because the caller's response to both is identical: do the work.
        """
        client = await self._connect()
        if client is None:
            return None

        try:
            value = await client.get(cache_key(tenant, key))
        except Exception:  # A cache failure must never fail a request
            _log.warning("The transient cache could not be read; treating it as a miss.")
            return None

        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def put(self, tenant: TenantContext, key: str, value: str, *, ttl_seconds: int) -> None:
        """Write within the organisation, with a bounded expiry.

        Raises:
            ValueError: When the TTL is outside ``(0, MAX_TTL_SECONDS]`` or the value is oversized.
                **Raised rather than clamped**: a caller asking for a day-long TTL has misunderstood
                what this store is, and silently giving them fifteen minutes would leave the
                misunderstanding in place until it mattered.
        """
        _validate(key, value, ttl_seconds)

        client = await self._connect()
        if client is None:
            return

        try:
            # SET with an expiry in one command, never SET followed by EXPIRE. Two commands leave a
            # window in which a crash produces an entry with no expiry at all — one immortal row in
            # a store whose whole guarantee is that nothing in it is.
            await client.set(cache_key(tenant, key), value, ex=ttl_seconds)
        except Exception:  # A cache failure must never fail a request
            _log.warning("The transient cache could not be written; the entry is simply absent.")

    async def invalidate(self, tenant: TenantContext, key: str) -> None:
        """Drop an entry early."""
        client = await self._connect()
        if client is None:
            return

        try:
            await client.delete(cache_key(tenant, key))
        except Exception:  # A cache failure must never fail a request
            _log.warning("The transient cache could not be invalidated; the entry expires anyway.")

    async def _connect(self) -> Any | None:  # The concrete type needs the SDK
        """The Redis client, built on first use with an Entra token as the password.

        Entra authentication to Redis presents the access token in the password position, exactly as
        it does for PostgreSQL. That is why this module can hold no password field and still
        authenticate: the value in that position is minted per connection by the managed identity
        and is never configuration.

        Returns:
            The client, or ``None`` when no cache is configured or the connection cannot be made.
        """
        if self._client is not None:
            return self._client

        if not self._settings.is_configured:
            return None

        try:
            import redis.asyncio as redis

            credential = self._credential
            if credential is None:
                from ragcore.infrastructure.azure_credentials import azure_credential

                credential = azure_credential()

            token = await credential.get_token(REDIS_SCOPE)
            self._client = redis.Redis(
                host=self._settings.host,
                port=self._settings.port,
                ssl=True,
                username=self._settings.identity_object_id,
                password=token.token,
                socket_timeout=self._settings.request_timeout_seconds,
                socket_connect_timeout=self._settings.request_timeout_seconds,
            )
        except Exception:  # An unreachable cache is a miss, not an outage
            _log.warning("The transient cache is unreachable; every lookup will report a miss.")
            return None

        return self._client


def _validate(key: str, value: str, ttl_seconds: int) -> None:
    """Enforce the three rules that make this store transient.

    Raises:
        ValueError: When the key is blank, the TTL is absent, non-positive or above
            :data:`MAX_TTL_SECONDS`, or the value exceeds :data:`MAX_VALUE_BYTES`.
    """
    if not key.strip():
        raise ValueError("a cache key is required; an empty one collides with every other")

    if not 0 < ttl_seconds <= MAX_TTL_SECONDS:
        raise ValueError(
            f"a cache entry needs a TTL in (0, {MAX_TTL_SECONDS}] seconds, got {ttl_seconds}. "
            "Redis is transient only: nothing here may outlive the execution window of the work it "
            "relates to, and nothing here is a durable record."
        )

    if len(value.encode("utf-8")) > MAX_VALUE_BYTES:
        raise ValueError(
            f"a cache entry may not exceed {MAX_VALUE_BYTES} bytes. A cache holding large objects "
            "is a store, whatever it is called."
        )
