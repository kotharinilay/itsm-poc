"""One durable checkpoint store, in PostgreSQL, and no second one anywhere.

**No second durable checkpoint store may exist** (constitution Principle IV, §LangGraph). That is
a rule about the shape of the codebase, so these are structural tests: they read the source
rather than open a connection, and they run in CI without a database.

The in-memory saver is legitimate — in tests. The distinction this file enforces is *where*, and
it is enforced by an allowlist rather than by a prohibition, so a new production module that
reaches for ``InMemorySaver`` fails here rather than passing every functional test it has while
losing every suspension on restart.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ragcore.graph import checkpointer

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
WORKERS = ROOT / "workers"

DURABLE_SAVERS = frozenset(
    {"AsyncPostgresSaver", "PostgresSaver", "AsyncShallowPostgresSaver", "ShallowPostgresSaver"}
)
"""PostgreSQL savers. The only durable checkpointers this platform may construct."""

FOREIGN_DURABLE_SAVERS = frozenset(
    {
        "SqliteSaver",
        "AsyncSqliteSaver",
        "MongoDBSaver",
        "AsyncMongoDBSaver",
        "RedisSaver",
        "AsyncRedisSaver",
        "DynamoDBSaver",
    }
)
"""Every other durable saver LangGraph ships. Each would be a second source of truth."""

IN_MEMORY_SAVERS = frozenset({"InMemorySaver", "MemorySaver"})
"""Legitimate in tests, nowhere else: a suspension it holds does not survive a restart."""


def _modules(*roots: Path) -> list[Path]:
    return sorted(path for root in roots for path in root.rglob("*.py"))


def _referenced_names(path: Path) -> set[str]:
    """Every bare name and attribute name a module mentions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return names


class TestExactlyOneDurableStore:
    """PostgreSQL, and nothing alongside it."""

    def test_no_foreign_durable_saver_appears_in_production_code(self) -> None:
        """SQLite, Mongo, Redis and DynamoDB savers are each a second source of truth."""
        offenders = [
            f"{path.relative_to(ROOT)}: {sorted(found)}"
            for path in _modules(SRC, WORKERS)
            if (found := _referenced_names(path) & FOREIGN_DURABLE_SAVERS)
        ]
        assert not offenders, "a second durable checkpoint store was introduced:\n  " + "\n  ".join(
            offenders
        )

    def test_the_postgres_saver_is_constructed_in_exactly_one_module(self) -> None:
        """One module, so the schema, the pool lifetime and the DDL rule have one home."""
        users = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in _modules(SRC, WORKERS)
            if _referenced_names(path) & DURABLE_SAVERS
        }
        assert users == {"src/ragcore/graph/checkpointer.py"}

    def test_no_in_memory_saver_reaches_a_non_test_path(self) -> None:
        """An in-memory saver in production loses every suspension on restart.

        The three ``awaiting_*`` states persist indefinitely (spec FR-SESS-016), which is a
        promise the checkpointer keeps — or does not.
        """
        offenders = [
            f"{path.relative_to(ROOT)}: {sorted(found)}"
            for path in _modules(SRC, WORKERS)
            if (found := _referenced_names(path) & IN_MEMORY_SAVERS)
        ]
        assert not offenders, "in-memory saver on a production path:\n  " + "\n  ".join(offenders)


class TestTheBuilderDoesNotChooseTheCheckpointer:
    """Building the graph and choosing where it persists are separate decisions."""

    def test_build_graph_returns_an_uncompiled_graph(self) -> None:
        """A builder that compiled with a checkpointer would be a builder tests must bypass.

        Bypassing it is how an in-memory saver ends up on a path nobody checks. Returning the
        uncompiled graph means tests and production compile the *same* shape, differing only in
        the one argument that is actually different.
        """
        from langgraph.graph import StateGraph

        from ragcore.graph.builder import build_graph
        from tests.support.fakes import build_harness

        graph = build_graph(build_harness().deps)
        assert isinstance(graph, StateGraph)

    def test_the_builder_module_names_no_saver(self) -> None:
        source = (SRC / "ragcore" / "graph" / "builder.py").read_text(encoding="utf-8")
        for saver in DURABLE_SAVERS | IN_MEMORY_SAVERS:
            assert saver not in source


class TestTheCheckpointSchemaIsPinned:
    """The saver has no schema argument, so the connection carries it."""

    def test_the_dsn_pins_the_search_path(self) -> None:
        pinned = checkpointer.checkpointer_dsn("postgresql://host/db")
        assert "search_path" in pinned
        assert checkpointer.CHECKPOINT_SCHEMA in pinned

    def test_an_existing_query_string_is_preserved(self) -> None:
        pinned = checkpointer.checkpointer_dsn("postgresql://host/db?sslmode=require")
        assert "sslmode=require" in pinned
        assert pinned.count("?") == 1

    def test_a_dsn_that_already_sets_options_is_refused(self) -> None:
        """Merging two option strings and hoping is how the schema ends up wrong."""
        with pytest.raises(ValueError, match="already sets"):
            checkpointer.checkpointer_dsn(
                "postgresql://host/db?options=-c%20statement_timeout%3D5s"
            )

    def test_the_two_schemas_are_disjoint(self) -> None:
        """Alembic owns one, the checkpointer owns the other, and neither proposes the other's.

        Two migration systems in one database are safe only while their schemas stay disjoint
        (research R-004). Compared as strings because both constants are ``Final`` literals, and
        an ``is not`` between two literal types is a comparison the type checker resolves
        statically — which would make the assertion vacuous rather than checked.
        """
        assert str(checkpointer.CHECKPOINT_SCHEMA) != str(checkpointer.PLATFORM_SCHEMA)


class TestDdlBelongsToTheMigrationJob:
    """``setup()`` runs from the gated migration job, never at application startup."""

    def test_the_provisioning_entry_point_is_separate_from_the_runtime_one(self) -> None:
        """Two functions, so the runtime one has no ``setup()`` to call by accident."""
        assert hasattr(checkpointer, "provision_checkpoint_schema")
        assert hasattr(checkpointer, "durable_checkpointer")

    def test_the_runtime_checkpointer_never_calls_setup(self) -> None:
        """A process that ran DDL on boot would need DDL rights at runtime.

        That is exactly what the separated database principals exist to prevent: the migration
        job holds DDL, the RagCore runtime holds DML and SELECT (ADR-0003).
        """
        tree = ast.parse(
            (SRC / "ragcore" / "graph" / "checkpointer.py").read_text(encoding="utf-8")
        )
        setup_callers = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and any(
                isinstance(inner, ast.Attribute) and inner.attr == "setup"
                for inner in ast.walk(node)
            )
        ]
        assert setup_callers == ["provision_checkpoint_schema"]

    def test_no_application_module_provisions_the_schema(self) -> None:
        """Only a migration job may call it, and no application module does."""
        callers = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in _modules(SRC)
            if "provision_checkpoint_schema" in _referenced_names(path)
        }
        assert callers <= {"src/ragcore/graph/checkpointer.py"}


class TestNoForeignKeyCrossesTheBoundary:
    """The checkpoint is working state; the work item is the authority record."""

    def test_the_state_carries_the_work_item_only_as_an_identifier(self) -> None:
        """Joined by identifier in application code, never by a foreign key.

        This is the structural reason a misbehaving agent cannot retarget approved work: it can
        write its own working state freely and still cannot reach the row that authorizes.
        """
        from typing import get_type_hints

        from ragcore.graph.state import AgentState

        hints = get_type_hints(AgentState)
        assert hints["work_item_id"] == (str | None)
