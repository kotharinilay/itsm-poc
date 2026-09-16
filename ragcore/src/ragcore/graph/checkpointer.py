"""The durable checkpoint boundary: PostgreSQL, one store, and nowhere else.

**No second durable checkpoint store may exist** (constitution Principle IV, §LangGraph). This
module is the entire surface through which a production graph acquires a checkpointer, so that
rule has one place to be true and one place to be tested
(``tests/checkpoint/test_durable_checkpointer.py``).

**Schema ownership.** The checkpoint tables live in their own ``langgraph`` schema, created and
versioned by ``langgraph-checkpoint-postgres``'s own ``setup()``. Alembic owns ``platform`` and
excludes ``langgraph`` from autogenerate (research R-004) — without the exclusion, autogenerate
would propose dropping tables it did not create. The schema is selected by a ``search_path`` on
the connection rather than by a parameter, because the saver has no schema argument: see
:func:`checkpointer_dsn`.

**``setup()`` runs from the migration job, never at application startup.** Migrations run as a
gated job before revision activation (plan §Stage 7). A process that ran DDL on boot would need
DDL rights at runtime, which is exactly what the separated database principals exist to prevent:
the migration job holds DDL, the RagCore runtime holds DML and SELECT.

**No foreign key crosses the boundary.** The work item is the authority record and the checkpoint
is working state (data-model.md §Graph checkpoint); they are joined by identifier in application
code. That separation is the structural reason a misbehaving agent cannot retarget approved work —
it can write its own working state all it likes and still cannot reach the row that authorizes.

The import of the PostgreSQL saver is **deliberately local** to :func:`durable_checkpointer`.
Importing it at module scope pulls in ``psycopg`` and its libpq binding, which would make
importing this module — for a type, a constant, or a test that asserts the rules — fail on any
machine without PostgreSQL client libraries.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from ragcore.graph.context import RunContext
    from ragcore.graph.dependencies import GraphDependencies
    from ragcore.graph.state import AgentState

CHECKPOINT_SCHEMA: Final = "langgraph"
"""The schema the checkpointer owns outright. Excluded from Alembic autogenerate."""

PLATFORM_SCHEMA: Final = "platform"
"""The schema Alembic owns. Named here only to state that the two are disjoint."""


def checkpointer_dsn(base_dsn: str) -> str:
    """Return ``base_dsn`` with the connection pinned to the checkpoint schema.

    ``AsyncPostgresSaver`` takes no schema argument — it issues unqualified DDL and DML, and the
    schema is whatever ``search_path`` resolves to. Setting it on the connection is therefore the
    mechanism, not a shortcut, and doing it in one function means no call site can forget and
    quietly create checkpoint tables in ``public``.

    Args:
        base_dsn: A PostgreSQL connection string.

    Returns:
        The same DSN carrying ``options=-c search_path=langgraph``.

    Raises:
        ValueError: When the DSN already sets ``options``. Rather than merge two option strings
            and hope, this refuses: a caller that needs both should build the DSN itself, and
            silently dropping somebody's existing options is how the schema ends up wrong.
    """
    if "options=" in base_dsn:
        raise ValueError(
            "the connection string already sets `options`; refusing to overwrite it. The "
            f"checkpointer requires `search_path={CHECKPOINT_SCHEMA}` on its connection."
        )
    separator = "&" if "?" in base_dsn else "?"
    return f"{base_dsn}{separator}options=-c%20search_path%3D{CHECKPOINT_SCHEMA}"


@asynccontextmanager
async def durable_checkpointer(dsn: str) -> AsyncIterator[BaseCheckpointSaver[str]]:
    """Open the one durable checkpointer, for the lifetime of the context.

    An async context manager rather than a factory, because the saver owns a connection pool and
    a pool that is never closed is a file-descriptor leak that only shows up under load. Binding
    it to the application lifespan makes the close as certain as the open.

    **Cancellation-safe.** ``from_conn_string`` is itself an async context manager, so a
    cancellation delivered while the graph is mid-run unwinds through ``__aexit__`` and closes the
    pool on the way out. Nothing here catches :class:`asyncio.CancelledError`, and nothing shields
    the body — a shield would mean a cancelled request holding a connection until its work
    finished anyway.

    This function does **not** call ``setup()``. See the module docstring: DDL belongs to the
    migration job.

    Args:
        dsn: The base connection string. Pinned to the checkpoint schema by
            :func:`checkpointer_dsn`, so callers pass the ordinary platform DSN.

    Yields:
        The saver, ready to be passed to ``StateGraph.compile(checkpointer=...)``.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(checkpointer_dsn(dsn)) as saver:
        yield saver


async def provision_checkpoint_schema(dsn: str) -> None:
    """Create or upgrade the checkpoint tables. **Called from the migration job only.**

    The checkpointer versions its own tables, so this is the ``langgraph`` schema's equivalent of
    ``alembic upgrade head`` — run in the same gated job, under the same principal that holds DDL,
    before the new revision is activated.

    ``setup()`` is declared on the concrete PostgreSQL saver rather than on
    :class:`BaseCheckpointSaver`, so this opens the saver itself rather than going through
    :func:`durable_checkpointer`. That is the honest shape: only one checkpointer has DDL to run,
    and only one job may run it.

    Args:
        dsn: The base connection string, as a migration job holds it.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(checkpointer_dsn(dsn)) as saver:
        await saver.setup()


@asynccontextmanager
async def durable_graph(
    dsn: str, deps: GraphDependencies
) -> AsyncIterator[CompiledStateGraph[AgentState, RunContext, AgentState, AgentState]]:
    """Compile the graph against the one durable checkpointer, for the lifetime of the context.

    **This is the only place a production graph is compiled**, and the reason it lives here rather
    than in :mod:`ragcore.graph.builder` is that the builder must stay ignorant of savers: a test
    compiles the same shape against an in-memory saver, and ``builder.py`` naming one would put an
    in-memory saver on the import path of every production module that builds a graph.

    Compiling with a checkpointer is what makes a suspension survive a restart. The three interrupts
    persist indefinitely (spec FR-INTR-001, FR-SESS-016), and "indefinitely" across a deployment is
    a property of the store rather than of the graph — an in-memory saver would lose every awaiting
    conversation on the next scale-to-zero, silently and without an error anywhere.

    Args:
        dsn: The base platform connection string. Pinned to the checkpoint schema by
            :func:`checkpointer_dsn`.
        deps: The collaborators every node is bound to.

    Yields:
        The compiled graph, backed by PostgreSQL.
    """
    from ragcore.graph.builder import build_graph

    async with durable_checkpointer(dsn) as saver:
        yield build_graph(deps).compile(checkpointer=saver)
