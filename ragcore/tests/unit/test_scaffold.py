"""The package imports, the composition root constructs, and bad configuration fails the process.

Started life at Stage 1 as a placeholder proving CI actually collects and runs this package,
rather than silently discovering nothing and reporting success. That job still matters, and
Stage 6 gave it a second one: :func:`~ragcore.config.composition.build_container` now validates
configuration, so "the container constructs" is a real assertion rather than a smoke test.
"""

from __future__ import annotations

import pytest
from pydantic import PostgresDsn, TypeAdapter, ValidationError

import ragcore
from ragcore.config.composition import build_container
from ragcore.config.settings import DatabaseSettings, Settings


def _settings(**overrides: object) -> Settings:
    dsn = TypeAdapter(PostgresDsn).validate_python("postgresql://user:pw@localhost/synthia")
    return Settings(database=DatabaseSettings(dsn=dsn), **overrides)  # type: ignore[arg-type]


def test_package_imports() -> None:
    """The package imports and the composition root constructs."""
    assert ragcore.__doc__ is not None
    assert build_container(_settings()) is not None


class TestConfigurationFailsFast:
    """A malformed setting should stop a deployment, not surface hours later (research R-019)."""

    def test_missing_required_configuration_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No database DSN, no container.

        There is deliberately no fallback. A default DSN would produce a container that starts
        and then fails on whichever endpoint first touched the database — moving a configuration
        defect from deployment, where it is cheap, to production, where it is not.
        """
        monkeypatch.delenv("SYNTHIA_DB_DSN", raising=False)
        with pytest.raises(ValidationError):
            build_container()

    def test_an_unknown_setting_is_rejected(self) -> None:
        """``extra="forbid"``. A misspelled setting is a failure, never a silently ignored one."""
        with pytest.raises(ValidationError):
            _settings(unknown_setting="value")

    def test_the_execution_window_cannot_be_widened(self) -> None:
        """Fifteen minutes is a ceiling, not a default.

        Configurable so a deployment can be *stricter* and for no other reason. Raising it would
        weaken a control the specification fixes, so the type refuses.
        """
        with pytest.raises(ValidationError):
            _settings(execution_window_minutes=60)

        assert _settings(execution_window_minutes=5).execution_window_minutes == 5


class TestTheScaffoldBindsNoAdapter:
    """Constitution Principle IX: scaffold honestly; do not invent product."""

    def test_only_the_clock_is_bound(self) -> None:
        """Every other port is ``None`` until its stage.

        A convenient default — a retrieval port returning an empty list, a catalogue answering
        ``AUTO`` — would let the platform appear to work while no boundary was real.
        """
        container = build_container(_settings())

        assert container.clock is not None
        for unbound in (
            container.tenant_registry,
            container.work_items,
            container.approvals,
            container.consents,
            container.catalogue,
            container.retrieval,
            container.model,
            container.execution,
            container.outbox,
            container.notifications,
            container.audit,
        ):
            assert unbound is None

    def test_the_container_cannot_be_mutated_after_construction(self) -> None:
        """Frozen, so nothing swaps a binding at runtime."""
        container = build_container(_settings())
        with pytest.raises((AttributeError, TypeError)):
            container.catalogue = None  # type: ignore[misc]
