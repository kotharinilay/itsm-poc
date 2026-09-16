"""The migration chain itself: one head, applies, matches the models, and reverses.

**pytest-alembic's four built-in tests, imported rather than reimplemented** (ADR-0003). Each
answers a question that only a real run can answer:

``test_single_head_revision``
    Two heads mean two people edited the chain and neither noticed. The deploy that follows applies
    one of them, and which one depends on ordering nobody controls.
``test_upgrade``
    Every revision applies, in order, against an empty database — which is what a fresh environment
    does and what a rehearsal never quite exercises otherwise.
``test_model_definitions_match_ddl``
    The models and the migrations describe the same schema. This is the test that catches the
    change made in one and forgotten in the other, and it is the reason the table revisions carry
    DDL compiled from the models rather than transcribed by hand.
``test_up_down_consistency``
    **Every downgrade succeeds.** A revision that cannot be undone is a revision that cannot be
    rolled back at three in the morning, and the enum types dropped in ``0001`` are exactly the kind
    of leftover that makes the *next* upgrade fail with ``type already exists``.

These need a real PostgreSQL — native enums, partial indexes, a plpgsql trigger and ``LATERAL``
views are not portable — so they are marked ``integration`` and skip where Docker is unavailable.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_alembic.tests import (
    test_model_definitions_match_ddl,
    test_single_head_revision,
    test_up_down_consistency,
    test_upgrade,
)

pytestmark = pytest.mark.integration

__all__ = [
    "test_model_definitions_match_ddl",
    "test_single_head_revision",
    "test_up_down_consistency",
    "test_upgrade",
]


@pytest.fixture
def alembic_config(database_url: str) -> Any:
    """Point pytest-alembic at the throwaway container.

    Args:
        database_url: The container's DSN. **Not** the ``migrated`` fixture: these tests upgrade and
            downgrade the chain themselves, and running them against an already-migrated database
            would test the second application rather than the first.
    """
    from alembic.config import Config

    from ragcore.persistence.base import PLATFORM_SCHEMA

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    config.set_main_option("version_table_schema", PLATFORM_SCHEMA)
    return config


@pytest.fixture
def alembic_engine(database_url: str) -> Any:
    """The engine pytest-alembic drives the chain with.

    Synchronous, because pytest-alembic's own tests are synchronous. ``env.py`` handles both: it
    honours a connection handed to it through ``config.attributes`` and only builds an async engine
    when it has to open one itself.
    """
    from sqlalchemy import create_engine

    return create_engine(database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://"))
