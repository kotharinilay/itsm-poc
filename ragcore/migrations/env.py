"""Alembic's runtime environment.

**Async, because the application is** (ADR-0003). ``async_engine_from_config`` with
``connection.run_sync`` is the supported way to drive Alembic's synchronous migration context from
an async driver, and running the schema through the same driver the runtime uses means a type or a
default that asyncpg renders differently is found here rather than in production.

**``NullPool``, deliberately.** A migration job is a short-lived process that opens one connection,
runs DDL, and exits. A pool would hold connections open past the work and, worse, would let two
pooled connections interleave DDL against a database where one advisory-free migration at a time is
the whole discipline.

**The ``langgraph`` schema is excluded from autogenerate** (research R-004). Those tables are
created and versioned by ``langgraph-checkpoint-postgres``'s own ``setup()``. Without the exclusion
below, autogenerate would see tables it has no model for and propose dropping them — turning a
routine revision into a silent loss of every suspended conversation.

**No DSN is committed.** ``SYNTHIA_DB_DSN`` is resolved from Key Vault by the job that runs this,
and this module reads it through the same validated settings the application uses, so a malformed
value fails here in the same way it would fail there.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from alembic_utils.pg_view import PGView
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import Connection, Engine, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from ragcore.persistence.autogenerate import include_name, include_object
from ragcore.persistence.base import PLATFORM_SCHEMA, metadata
from ragcore.persistence.views import ALL_VIEWS

# Importing the models is what populates the metadata. Without it autogenerate compares the live
# database against an empty MetaData and proposes dropping every table in it.
from ragcore.persistence import models as _models  # noqa: F401  isort:skip

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata

# alembic_utils manages the published views as first-class entities, so `--autogenerate` proposes
# a `create_or_replace` when a definition changes rather than leaving the view to drift silently
# away from the file that is supposed to define it.
#
# `entity_types` is restricted to views deliberately. alembic_utils reflects every entity type it
# understands — views, functions, triggers, grants, policies — and proposes dropping any it finds
# that were not registered. The `0017` immutability trigger and the `0019` grants are exactly that:
# hand-written, deliberate, and not modelled here. Without this restriction autogenerate proposes
# dropping the immutability guard and every grant, which is a revision that would quietly undo the
# two structural controls in the schema.
register_entities(list(ALL_VIEWS), schemas=[PLATFORM_SCHEMA], entity_types=[PGView])

DSN_ENV_VAR = "SYNTHIA_DB_DSN"
"""The one place a connection string enters this process. Resolved from Key Vault by the job."""


def _database_url() -> str:
    """Resolve the connection string for the migration job.

    Prefers an explicit ``sqlalchemy.url`` when one was set programmatically — which is how
    pytest-alembic points this environment at a throwaway container — and falls back to the
    environment variable the deployed job sets.

    Returns:
        The DSN, with the async driver named explicitly.

    Raises:
        RuntimeError: When neither source supplies one. A migration job with no database is a
            failure, not a no-op that reports success.
    """
    configured = config.get_main_option("sqlalchemy.url", None)
    if configured:
        return configured

    dsn = os.environ.get(DSN_ENV_VAR)
    if not dsn:
        raise RuntimeError(
            f"no database URL: set `{DSN_ENV_VAR}` or configure `sqlalchemy.url`. "
            "Refusing to run migrations against an unspecified target."
        )
    # `postgresql://` is what Key Vault holds and what every other tool accepts. Alembic needs the
    # driver named, and normalising here means the stored secret does not have to know which
    # driver this process happens to use.
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return dsn


CREATE_SCHEMA = f"CREATE SCHEMA IF NOT EXISTS {PLATFORM_SCHEMA}"
"""**Emitted before anything else, including Alembic's own version table.**

``alembic_version`` lives in the ``platform`` schema (``alembic.ini``), and Alembic creates it on
the first run — before the first revision executes. On an empty database that is a ``CREATE TABLE``
into a schema that revision ``0001`` has not created yet. This statement is what makes the very
first migration of a fresh database work, and it is ``IF NOT EXISTS`` because every subsequent run
finds the schema already there.
"""


def _configure(connection: Connection | None = None, url: str | None = None) -> None:
    """Apply the one configuration both the online and offline paths share.

    Kept in one function because a difference between the two is a difference between the SQL a
    reviewer reads in a dry run and the SQL the job actually executes.

    The two filters come from :mod:`ragcore.persistence.autogenerate`, where they can be tested
    without starting a migration to ask a question about a filter.
    """
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
        include_name=include_name,
        version_table=config.get_main_option("version_table", "alembic_version"),
        version_table_schema=PLATFORM_SCHEMA,
        # Without this a `server_default` change is invisible to autogenerate, and a default that
        # exists in the model but not in the database is exactly the drift these tests exist for.
        compare_server_default=True,
        compare_type=True,
        # Every migration runs in one transaction, so a failure part-way leaves no half-applied
        # revision for the next run to trip over.
        transaction_per_migration=False,
        literal_binds=url is not None,
        dialect_opts={"paramstyle": "named"} if url is not None else {},
    )


def run_migrations_offline() -> None:
    """Emit SQL without connecting — the reviewable dry run.

    ``alembic upgrade head --sql`` produces the exact statements the gated job will run, which is
    how a schema change is reviewed before anything touches a database.
    """
    _configure(url=_database_url())

    with context.begin_transaction():
        context.execute(CREATE_SCHEMA)
        context.run_migrations()


def _run(connection: Connection) -> None:
    """Run migrations against an already-open synchronous connection.

    **The schema is created in its own committed transaction, and the commit is load-bearing.**
    Executing any statement on a fresh connection opens an implicit transaction; if that
    transaction were still open when ``context.begin_transaction()`` ran, alembic's would no longer
    be the outermost one and it would never issue the final ``COMMIT``. The upgrade would then
    report success, log every revision, and roll the whole thing back when the connection closed —
    a failure that ``alembic upgrade head --sql`` cannot reveal, because the offline renderer never
    opens a transaction at all. Only an integration test against a real database catches it, which
    is why ``tests/migrations/test_migrations.py`` is not optional.
    """
    connection.exec_driver_sql(CREATE_SCHEMA)
    connection.commit()

    _configure(connection=connection)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Open one connection and run every pending revision through it."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_run)
    finally:
        # The job exits after this, but disposing explicitly means a failure during DDL closes its
        # connection rather than leaving it to the interpreter's shutdown order.
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif (_supplied := config.attributes.get("connection")) is not None:
    # pytest-alembic and any other in-process driver hand Alembic a live database handle rather
    # than a URL. Honouring it is what lets the migration tests drive the chain directly.
    #
    # It may be either an `Engine` or a `Connection` — pytest-alembic passes the engine — so it is
    # normalised here, as the stock Alembic template does. Assuming one and getting the other is
    # an `AttributeError` raised from inside a migration, where it reads as a broken revision
    # rather than as a caller passing something else.
    if isinstance(_supplied, Engine):
        with _supplied.connect() as _connection:
            _run(_connection)
    else:
        _run(_supplied)
else:
    asyncio.run(run_migrations_online())
