"""Redis is **transient only**: never an authority, never a durable record (constitution P-IV).

The rule is enforced by the type rather than by the convention, and these assert the type. Each one
corresponds to a way a cache turns into a store when nobody is watching:

* an entry written without a TTL,
* an entry whose TTL outlives the work it relates to,
* a key that is not namespaced to an organisation,
* an interface rich enough to enumerate or rebuild state from,
* a cache failure that fails the request rather than becoming a miss.

The last one is the one that matters most in practice. A cache whose outage takes the platform down
is durable state wearing a cache's name, whatever the documentation says — so every method reports a
miss on failure, and the caller's response to a miss and to an outage is the same: do the work.
"""

from __future__ import annotations

from typing import Any

import pytest

from ragcore.config.settings import CacheSettings
from ragcore.infrastructure.cache import (
    MAX_TTL_SECONDS,
    MAX_VALUE_BYTES,
    NullCache,
    RedisTransientCache,
    TransientCachePort,
    cache_key,
)
from tests.support.fakes import admitted_tenant


class FakeRedis:
    """A Redis client that records what it was asked to do, and can be told to fail."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, Any, Any]] = []
        self.values: dict[str, str] = {}
        self._fail = fail

    async def get(self, key: str) -> str | None:
        if self._fail:
            raise ConnectionError("the cache is unreachable")
        self.calls.append(("get", key, None))
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self._fail:
            raise ConnectionError("the cache is unreachable")
        self.calls.append(("set", key, ex))
        self.values[key] = value

    async def delete(self, key: str) -> None:
        if self._fail:
            raise ConnectionError("the cache is unreachable")
        self.calls.append(("delete", key, None))
        self.values.pop(key, None)


CONFIGURED = CacheSettings(
    host="synthia.redis.example", identity_object_id="00000000-0000-0000-0000-000000000001"
)


class TestNothingCanBeWrittenWithoutAnExpiry:
    """The single most important property. An entry with no TTL is a durable record."""

    async def test_a_write_carries_the_ttl_it_was_given(self) -> None:
        client = FakeRedis()
        cache = RedisTransientCache(CONFIGURED, client)

        await cache.put(admitted_tenant(), "answer", "42", ttl_seconds=60)

        assert client.calls[0][0] == "set"
        assert client.calls[0][2] == 60

    async def test_the_expiry_is_set_in_the_same_command_as_the_value(self) -> None:
        """SET with an expiry, never SET followed by EXPIRE. Two commands leave a window in which a
        crash produces an entry with no expiry at all — one immortal row in a store whose whole
        guarantee is that nothing in it is."""
        client = FakeRedis()

        await RedisTransientCache(CONFIGURED, client).put(
            admitted_tenant(), "answer", "42", ttl_seconds=60
        )

        assert [call[0] for call in client.calls] == ["set"]

    @pytest.mark.parametrize("ttl", [0, -1, MAX_TTL_SECONDS + 1, 86_400])
    async def test_an_unbounded_or_absent_ttl_is_refused(self, ttl: int) -> None:
        """Raised rather than clamped: a caller asking for a day-long TTL has misunderstood what
        this store is, and silently giving them fifteen minutes leaves the misunderstanding in
        place until it matters."""
        with pytest.raises(ValueError, match="TTL"):
            await RedisTransientCache(CONFIGURED, FakeRedis()).put(
                admitted_tenant(), "answer", "42", ttl_seconds=ttl
            )

    def test_the_ttl_ceiling_is_the_execution_window(self) -> None:
        """Nothing cached can usefully outlive the window of the work it relates to."""
        assert MAX_TTL_SECONDS == 900

    def test_the_port_declares_the_ttl_as_required_and_keyword_only(self) -> None:
        """Required so an entry without one cannot be written; keyword-only so it cannot be
        supplied by accident in a positional slot and must be named at every call site."""
        import inspect

        parameter = inspect.signature(TransientCachePort.put).parameters["ttl_seconds"]

        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


class TestEveryKeyIsNamespacedToAnOrganisation:
    """A shared key space is a cross-organisation read that no database isolation would catch."""

    def test_two_organisations_never_share_a_key(self) -> None:
        first, second = admitted_tenant(), admitted_tenant()

        assert cache_key(first, "answer") != cache_key(second, "answer")

    def test_the_key_carries_the_organisation_identifier(self) -> None:
        tenant = admitted_tenant()

        assert str(tenant.tenant_id.value) in cache_key(tenant, "answer")

    def test_an_empty_key_is_refused(self) -> None:
        """An empty key collides with every other empty key across the whole platform."""
        with pytest.raises(ValueError, match="cache key"):
            cache_key(admitted_tenant(), "   ")

    async def test_a_read_is_scoped_to_the_organisation_that_asked(self) -> None:
        tenant, stranger = admitted_tenant(), admitted_tenant()
        client = FakeRedis()
        cache = RedisTransientCache(CONFIGURED, client)

        await cache.put(tenant, "answer", "ours", ttl_seconds=60)

        assert await cache.get(tenant, "answer") == "ours"
        assert await cache.get(stranger, "answer") is None


class TestTheInterfaceCannotBeUsedAsAStore:
    """What is absent is the control."""

    def test_the_port_exposes_exactly_three_methods(self) -> None:
        """No ``keys``, no ``scan``, no ``flush``. An enumerable cache is one something can iterate
        to rebuild state from, which is the first step towards treating it as a record."""
        methods = {
            name
            for name in dir(TransientCachePort)
            if not name.startswith("_") and callable(getattr(TransientCachePort, name, None))
        }

        assert methods == {"get", "put", "invalidate"}

    def test_there_is_no_way_to_clear_an_expiry(self) -> None:
        for forbidden in ("persist", "expire", "keys", "scan", "flushdb", "flushall"):
            assert not hasattr(RedisTransientCache, forbidden)

    async def test_an_oversized_value_is_refused(self) -> None:
        """A cache holding large objects is a store, whatever it is called."""
        with pytest.raises(ValueError, match="bytes"):
            await RedisTransientCache(CONFIGURED, FakeRedis()).put(
                admitted_tenant(), "answer", "x" * (MAX_VALUE_BYTES + 1), ttl_seconds=60
            )


class TestACacheFailureIsNeverARequestFailure:
    """The fallback for a miss and the fallback for an outage are the same: do the work."""

    async def test_an_unreachable_cache_reports_a_miss(self) -> None:
        cache = RedisTransientCache(CONFIGURED, FakeRedis(fail=True))

        assert await cache.get(admitted_tenant(), "answer") is None

    async def test_an_unreachable_cache_does_not_fail_a_write(self) -> None:
        cache = RedisTransientCache(CONFIGURED, FakeRedis(fail=True))

        await cache.put(admitted_tenant(), "answer", "42", ttl_seconds=60)

    async def test_an_unreachable_cache_does_not_fail_an_invalidation(self) -> None:
        cache = RedisTransientCache(CONFIGURED, FakeRedis(fail=True))

        await cache.invalidate(admitted_tenant(), "answer")

    async def test_an_unconfigured_cache_is_a_miss_rather_than_an_error(self) -> None:
        cache = RedisTransientCache(CacheSettings())

        assert await cache.get(admitted_tenant(), "answer") is None


class TestTheNullCacheIsHonest:
    """What a process gets with no cache configured, and why it is not a convenience."""

    async def test_it_always_misses(self) -> None:
        cache = NullCache()
        await cache.put(admitted_tenant(), "answer", "42", ttl_seconds=60)

        assert await cache.get(admitted_tenant(), "answer") is None

    async def test_it_still_validates_what_it_discards(self) -> None:
        """A call site the real cache would reject is rejected here too — otherwise a bad TTL ships
        because it was only ever exercised locally."""
        with pytest.raises(ValueError, match="TTL"):
            await NullCache().put(admitted_tenant(), "answer", "42", ttl_seconds=0)


class TestNoCredentialIsConfigurable:
    """Entra authentication puts a token in the password position, minted per connection."""

    def test_the_settings_hold_no_password_or_key(self) -> None:
        fields = set(CacheSettings.model_fields)

        assert not fields & {"password", "access_key", "primary_key", "connection_string"}

    def test_a_host_is_an_address_and_not_a_credential(self) -> None:
        """Knowing it permits nothing without a token."""
        assert CacheSettings(host="synthia.redis.example").is_configured is True
        assert CacheSettings().is_configured is False
