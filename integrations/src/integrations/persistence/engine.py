"""Persistence. **Writes its own schema; reads the platform's only through published views.**

Two grants, and the asymmetry is the control (ADR-0007, data-model §Schemas):

* **`integration`** — this service owns and writes it: the connector registry, connector bindings,
  execution records, its own outbox.
* **`platform`** — **read-only, and only through `vw_*_v1` views.** No write grant on any base
  table exists, and the one write this service will ever have there is column-scoped to the result
  fields of an integration job.

The refusal is enforced by PostgreSQL, not by this module. That matters: application code that
"knows" not to write is application code one refactor away from writing. What this module adds is
that there is no code path *shaped* like a platform write — the read accessors return rows and the
session used for them is opened read-only, so a stray `INSERT` fails at the driver before it reaches
a grant check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import AsyncIterator, Mapping, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from integrations.config.settings import PersistenceSettings

__all__ = ["Database", "ReadinessProbeAdapter", "build_engine"]


def build_engine(persistence: PersistenceSettings) -> AsyncEngine:
    """Create the async engine.

    `NullPool` because Container Apps scales replicas rather than connections, and a pool held
    across a scale-in is a pool of sockets to a database that has already forgotten them.

    Args:
        persistence: The DSN and owned schema. The DSN carries **no credential** — PostgreSQL is
            reached by managed identity, and :class:`PersistenceSettings` rejects an embedded
            password at startup.

    Returns:
        The engine.

    Raises:
        ValueError: When no DSN is configured. Named here, at startup, because the alternative was
            SQLAlchemy's "Could not parse SQLAlchemy URL from given URL string" — a failure that
            stops the process, as it should, while naming neither the setting nor its variable.
    """
    if not persistence.dsn.strip():
        raise ValueError(
            "SYNTHIA_INTEGRATIONS_PERSISTENCE__DSN is not set. The Integrations Service cannot "
            "start without its database: the job row is its only source of an instruction."
        )
    return create_async_engine(
        persistence.dsn,
        poolclass=NullPool,
        echo=False,
        # Never log parameters: a query against a tenant-scoped view carries an organisation
        # identifier, and telemetry MUST NOT carry cross-tenant information.
        hide_parameters=True,
    )


class Database:
    """Sessions over the two schemas, with the read/write split made explicit at the call site."""

    def __init__(self, engine: AsyncEngine, persistence: PersistenceSettings) -> None:
        """Bind to an engine.

        Args:
            engine: The async engine.
            persistence: The owned schema name.
        """
        self._engine = engine
        self._schema = persistence.schema_name
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @property
    def schema(self) -> str:
        """The schema this service owns and writes."""
        return self._schema

    async def read(
        self, statement: Any, parameters: Mapping[str, Any]
    ) -> Sequence[Any]:  # SQLAlchemy executables are not one type
        """Run a read against a published view.

        Args:
            statement: The select.
            parameters: Bound parameters. **Always parameterised** — a query assembled by string
                formatting is the injection path every tenant filter in this platform depends on
                not existing.

        Returns:
            The rows.
        """
        async with self._sessions() as session:
            result = await session.execute(statement, dict(parameters))
            return result.mappings().all()

    async def session(self) -> AsyncIterator[AsyncSession]:
        """A read-write session over the `integration` schema.

        Yields:
            The session. The caller commits; nothing here commits on its behalf, so a failure part
            way through a unit of work leaves nothing half-written.
        """
        async with self._sessions() as session:
            yield session


class ReadinessProbeAdapter:
    """The durable-store readiness probe.

    A **platform** dependency, so it belongs in readiness. Registered by the composition root.
    """

    def __init__(self, database: Database) -> None:
        """Bind the probe.

        Args:
            database: The database to check.
        """
        self._database = database

    @property
    def name(self) -> str:
        """For telemetry only — never a response body."""
        return "postgresql"

    async def check(self) -> bool:
        """Whether the durable store answers.

        Returns:
            ``True`` when a trivial round trip succeeds. Deliberately trivial: a readiness probe
            that ran a real query would report *the query's* health, and would fail the replica for
            a slow view rather than for an unreachable database.
        """
        from sqlalchemy import text

        await self._database.read(text("SELECT 1"), {})
        return True
