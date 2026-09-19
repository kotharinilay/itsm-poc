"""Provision the LangGraph checkpointer's own tables. **Run by the migration job.**

Alembic owns the ``platform`` schema; ``langgraph-checkpoint-postgres`` owns the checkpoint schema
and versions it through its own ``setup()``. Two owners, one database, and a boundary neither may
cross (ADR-0003) — which leaves exactly one problem: ``setup()`` has to run *somewhere*, and every
convenient place is wrong.

* **At application startup** it would need DDL rights on every serving replica, permanently,
  which the separated database principals exist to prevent. It would also race: Container Apps
  starts replicas in parallel, and Alembic's version table is not a distributed lock.
* **On first use** it cannot run at all — the application principal has no CREATE, so the tables it
  is supposed to make on demand are tables it is not permitted to make.
* **By hand** it runs once, in one environment, and is forgotten in the next.

So it runs here, from ``build/docker/migrate.job.yaml``, as the migration principal, immediately
after ``alembic upgrade head`` — and after rather than before, because the checkpoint schema lives
inside a schema the Alembic revisions create.

Run from ``ragcore/``::

    uv run python scripts/provision_checkpoint_schema.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Final

from ragcore.config.settings import get_settings
from ragcore.graph.checkpointer import provision_checkpoint_schema
from ragcore.observability.logging import configure_logging

_log: Final = logging.getLogger("ragcore.provision")


async def main() -> int:
    """Provision the checkpoint schema.

    Returns:
        ``0`` on success, ``1`` on failure.

    Takes the DSN from validated settings rather than from an argument: the job already supplies
    the migration principal's connection string as ``SYNTHIA_DB_DSN``, and a second way to pass one
    would be a way to point this at the wrong database with no review.
    """
    configure_logging()
    settings = get_settings()

    try:
        await provision_checkpoint_schema(str(settings.database.dsn))
    except Exception:
        # Logged and returned as a non-zero exit, never swallowed. A migration job that reported
        # success without provisioning would let a revision activate against a database whose
        # checkpoint tables do not exist — and the failure would surface on the first suspended
        # run, which is hours later and looks nothing like a deployment problem.
        _log.exception("The checkpoint schema could not be provisioned; the deployment must stop.")
        return 1

    _log.info("The checkpoint schema is provisioned.")
    return 0


if __name__ == "__main__":
    # The migration job runs this on Linux, where the default loop is fine. On Windows the default
    # is the Proactor loop, and psycopg refuses to run async on it — so a developer following the
    # README got a stack trace from inside the driver rather than a provisioned schema. Set only on
    # Windows, and only here: the application chooses no loop policy, because a library that picked
    # one would be deciding for whatever host embeds it.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    sys.exit(asyncio.run(main()))
