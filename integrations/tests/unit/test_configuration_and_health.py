"""Configuration validation and health semantics.

.claude/rules/40-testing.md §40.8: *Configuration validation — options bind, validate and fail
fast at start.* These cover the two rules that are easy to state and easy to lose.
"""

from __future__ import annotations

import pytest

from integrations.api.health import ReadinessRegistry
from integrations.config.settings import PersistenceSettings
from integrations.persistence.engine import build_engine

# No module-level asyncio mark: `asyncio_mode = "auto"` already collects the coroutine tests, and a
# blanket mark would also attach to the synchronous ones below — which pytest warns about rather
# than failing, so it is the kind of noise that becomes permanent if left.


class _Probe:
    """A probe with a fixed answer, for the registry's own behaviour."""

    def __init__(self, name: str, ready: bool, *, raises: bool = False) -> None:
        self._name = name
        self._ready = ready
        self._raises = raises

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> bool:
        if self._raises:
            raise RuntimeError("dependency unreachable")
        return self._ready


async def test_empty_registry_is_ready() -> None:
    """No registered probe means nothing to wait for — not "checks disabled".

    A process that has bound no platform dependency genuinely has nothing to block on. The honest
    answer is ready; the moment a dependency exists, its owning subsystem registers a probe.
    """
    assert await ReadinessRegistry().all_ready() is True


async def test_one_failing_probe_makes_the_process_not_ready() -> None:
    """Readiness is an AND across platform dependencies."""
    registry = ReadinessRegistry([_Probe("store", True), _Probe("bus", False)])
    assert await registry.all_ready() is False


async def test_a_raising_probe_is_not_ready_rather_than_an_error() -> None:
    """Unreachable and refused have the same consequence.

    Both mean this replica should not take traffic, so a raising probe is not-ready rather than a
    500 out of the health endpoint — which would be an unhealthy signal of a different kind and
    would restart a process that is merely waiting.
    """
    registry = ReadinessRegistry([_Probe("vault", True, raises=True)])
    assert await registry.all_ready() is False


def test_dsn_with_an_embedded_password_is_rejected() -> None:
    """A credential-bearing connection string is the shape the secret rule usually breaks in.

    PostgreSQL is reached by managed identity. A DSN carrying a password defeats every secret rule
    at once while looking like ordinary configuration, which is exactly why it is caught by type
    rather than by review.
    """
    with pytest.raises(ValueError, match="MUST NOT embed a password"):
        PersistenceSettings(dsn="postgresql://user:password=hunter2@host/db")


def test_dsn_without_a_credential_is_accepted() -> None:
    """The check rejects credentials, not connection strings."""
    assert PersistenceSettings(dsn="postgresql://host/db").dsn == "postgresql://host/db"


def test_a_missing_dsn_stops_the_process_and_names_the_setting() -> None:
    """The process must not start without its database — and must say which setting is missing.

    It already failed to start, but on SQLAlchemy's "Could not parse SQLAlchemy URL", which names
    neither the setting nor the variable an operator has to set.
    """
    with pytest.raises(ValueError, match="SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN"):
        build_engine(PersistenceSettings())
