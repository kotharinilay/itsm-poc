"""Shared fixtures — chiefly the throwaway PostgreSQL every integration test runs against.

**A real PostgreSQL, never a substitute.** The properties these tests exist to hold are properties
of *this* database: a partial index, a ``CHECK`` constraint, an ``ON DELETE CASCADE``, a plpgsql
trigger, a native enum, ``GENERATED ALWAYS AS IDENTITY``, a ``LATERAL`` join. SQLite has none of
them, so a suite that ran against SQLite would pass while proving nothing about what ships.

**The schema comes from the migrations**, not from ``metadata.create_all``. Creating tables from the
models would test the models against themselves and leave the migrations — the thing that actually
runs in production — unexercised. Running ``alembic upgrade head`` here means every integration test
is also a test that the migration chain applies.

**Every test gets a clean database and the container is shared.** Starting PostgreSQL once and
truncating between tests is roughly two orders of magnitude faster than a container per test, and
truncation with ``RESTART IDENTITY CASCADE`` leaves the schema exactly as the migration left it.

Tests requiring the container are marked ``integration`` and **skip** where Docker is unavailable.
Skipping is the honest outcome for a developer without Docker; CI has it, and the workflow runs the
marked tests there, so the coverage is not optional where it counts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

DOCKER_UNAVAILABLE = "Docker is not available; integration tests need a real PostgreSQL"


def _postgres_container() -> Any:
    """Start a throwaway PostgreSQL, or return ``None`` when Docker is unreachable.

    The import is local so that a machine without ``testcontainers`` installed can still collect
    and run the rest of the suite — the unit, architecture and structural tests need no database
    and should not be blocked by one.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover — testcontainers is a dev dependency
        return None

    try:
        container = PostgresContainer("postgres:17-alpine")
        container.start()
    except Exception:  # Any startup failure means the same thing: no Docker here
        return None
    return container


SUPPLIED_DSN = "SYNTHIA_TEST_DB_DSN"
"""An existing throwaway database to use instead of starting a container.

CI already runs a PostgreSQL service alongside the job (``.github/workflows/migrations.yml``), and
starting a second one inside it would be a container per run for no benefit. Locally the variable
is unset and Testcontainers takes over, so a developer needs no setup.

**It must point at a database the suite may destroy**: every test truncates every table.
"""


@pytest.fixture(scope="session")
def postgres() -> Iterator[Any]:
    """The shared container, started once for the whole session.

    Skipped entirely when a DSN was supplied — there is nothing to start.
    """
    import os

    if os.environ.get(SUPPLIED_DSN):
        yield None
        return

    container = _postgres_container()
    if container is None:
        pytest.skip(DOCKER_UNAVAILABLE)
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def database_url(postgres: Any) -> str:
    """The DSN under test, normalised onto the async driver."""
    import os

    url: str = os.environ.get(SUPPLIED_DSN) or postgres.get_connection_url()
    # testcontainers hands back a psycopg2 URL; everything here speaks asyncpg.
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
def migrated(database_url: str) -> str:
    """Apply every migration once, and hand back the DSN.

    ``alembic upgrade head`` rather than ``metadata.create_all``: see the module docstring. This is
    also where a broken migration chain surfaces — before any test that assumed a table exists.
    """
    from alembic import command
    from alembic.config import Config

    from ragcore.persistence.base import PLATFORM_SCHEMA

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("version_table_schema", PLATFORM_SCHEMA)
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
async def engine(migrated: str) -> AsyncIterator[AsyncEngine]:
    """An engine against the migrated database, disposed after each test."""
    from sqlalchemy.ext.asyncio import create_async_engine

    created = create_async_engine(migrated, pool_pre_ping=True)
    try:
        yield created
    finally:
        await created.dispose()


@pytest.fixture
async def sessions(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory, with the database truncated before the test and after it.

    Truncated on both sides rather than only one: before, so a test never inherits a predecessor's
    rows; after, so a failing test leaves nothing behind for the next one to trip over while
    somebody is reading the failure.
    """
    from ragcore.persistence.engine import create_session_factory

    await _truncate(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await _truncate(engine)


async def _truncate(engine: AsyncEngine) -> None:
    """Empty every platform table, leaving the schema as the migrations left it.

    ``RESTART IDENTITY`` resets ``outbox_message.sequence``, so a test asserting publication order
    sees the sequence it expects rather than one carrying a previous test's offset.
    """
    from sqlalchemy import text

    from ragcore.persistence.base import PLATFORM_SCHEMA
    from ragcore.persistence.models import TABLES_BY_NAME

    names = ", ".join(f"{PLATFORM_SCHEMA}.{name}" for name in sorted(TABLES_BY_NAME))
    async with engine.begin() as connection:
        # Table names come from the mapped metadata, not from any input; there is no parameterised
        # form of TRUNCATE for identifiers.
        await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))  # noqa: S608
