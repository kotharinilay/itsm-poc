"""Alembic owns ``platform``. The checkpointer owns ``langgraph``. Neither reaches into the other.

**Autogenerate must never propose a change inside ``langgraph``** (research R-004). Those tables are
created and versioned by ``langgraph-checkpoint-postgres``'s own ``setup()``; Alembic has no model
for them, so without the exclusion it would see tables it did not create and propose dropping them —
turning a routine revision into a silent loss of every suspended conversation.

These are structural tests. They exercise the two filters directly rather than diffing against a
live database, so the rule holds in CI without a container and a failure names the filter that
broke rather than producing a diff nobody can read.
"""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, Table

from ragcore.graph.checkpointer import CHECKPOINT_SCHEMA, PLATFORM_SCHEMA
from ragcore.persistence.autogenerate import include_name, include_object
from ragcore.persistence.base import metadata
from ragcore.persistence.views import ALL_VIEWS

# Importing the models is what populates the metadata — the same reason `env.py` imports them.
from ragcore.persistence import models as _models  # noqa: F401  isort:skip

ENV = Path(__file__).resolve().parents[2] / "migrations" / "env.py"


class TestTheCheckpointSchemaIsExcluded:
    """The ``langgraph`` schema is not Alembic's to compare, create or drop."""

    def test_the_two_schemas_are_disjoint(self) -> None:
        """Stated here as well as in the checkpointer, because both sides have to agree."""
        assert len({str(PLATFORM_SCHEMA), str(CHECKPOINT_SCHEMA)}) == 2

    def test_a_checkpoint_table_is_never_included(self) -> None:
        """A reflected ``langgraph`` table is filtered out before autogenerate can act on it."""
        foreign = Table("checkpoints", MetaData(), Column("id", Integer), schema=CHECKPOINT_SCHEMA)
        assert not include_object(foreign, "checkpoints", "table", True, None)

    def test_a_checkpoint_index_is_never_included(self) -> None:
        """An index carries no schema of its own, so it is judged by the table it hangs off."""
        foreign = Table("checkpoints", MetaData(), Column("id", Integer), schema=CHECKPOINT_SCHEMA)
        assert not include_object(foreign.c.id, "id", "column", True, None)

    def test_a_platform_table_is_included(self) -> None:
        """The filter excludes one schema; it does not exclude everything."""
        own = metadata.tables[f"{PLATFORM_SCHEMA}.work_item"]
        assert include_object(own, "work_item", "table", True, None)

    def test_a_platform_column_is_included(self) -> None:
        """Including tables and excluding their columns would produce an unusable revision."""
        own = metadata.tables[f"{PLATFORM_SCHEMA}.work_item"]
        assert include_object(own.c.tenant_id, "tenant_id", "column", True, None)

    def test_the_checkpoint_schema_is_never_reflected(self) -> None:
        """``include_name`` stops it being read at all, which is the stronger of the two filters."""
        assert not include_name(CHECKPOINT_SCHEMA, "schema", {})

    def test_the_default_schema_is_never_reflected(self) -> None:
        """``public`` is nobody's here, and no principal in this platform has rights over it."""
        assert not include_name(None, "schema", {})

    def test_only_the_platform_schema_is_reflected(self) -> None:
        """An unrelated schema in the same database is not this migration's business either."""
        assert include_name(PLATFORM_SCHEMA, "schema", {})
        assert not include_name("someone_elses", "schema", {})


class TestTheMigrationEnvironmentInstallsBothFilters:
    """A filter nothing passes to Alembic is a filter that protects nothing."""

    def test_env_configures_include_object_and_include_name(self) -> None:
        """Both are wired into ``context.configure``, read from the source rather than executed.

        Importing ``env.py`` runs a migration — it decides at import time whether it is offline,
        connection-driven or online — so this reads the call it makes instead.
        """
        tree = ast.parse(ENV.read_text(encoding="utf-8"), filename=str(ENV))
        configured = {
            keyword.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "configure"
            for keyword in node.keywords
        }
        assert {"include_object", "include_name", "include_schemas"} <= configured

    def test_env_defines_neither_filter_itself(self) -> None:
        """The exclusion belongs to one module, so there is one place for it to be wrong.

        A second copy in ``env.py`` would be the one that actually ran, and the tested one would
        pass forever while protecting nothing.
        """
        tree = ast.parse(ENV.read_text(encoding="utf-8"), filename=str(ENV))
        defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert not defined & {"include_object", "include_name"}


class TestEveryModelledObjectLivesInThePlatformSchema:
    """The exclusion works only because nothing of ours is outside the schema it protects."""

    def test_no_table_escapes_the_platform_schema(self) -> None:
        """A table mapped into another schema would be invisible to the migration job."""
        strays = [
            table.fullname for table in metadata.sorted_tables if table.schema != PLATFORM_SCHEMA
        ]
        assert not strays, f"tables outside the platform schema: {strays}"

    def test_no_published_view_escapes_the_platform_schema(self) -> None:
        """The monolith is granted ``SELECT`` per qualified name; a stray view is ungrantable."""
        strays = [view.signature for view in ALL_VIEWS if view.schema != PLATFORM_SCHEMA]
        assert not strays, f"views outside the platform schema: {strays}"

    def test_no_model_references_the_checkpoint_schema(self) -> None:
        """**No foreign key crosses into ``langgraph``**, in either direction.

        The work item is the authority record and the checkpoint is working state. That separation
        is the structural reason a misbehaving agent cannot retarget approved work — it can write
        its own working state all it likes and still cannot reach the row that authorizes.
        """
        crossings = [
            f"{table.name}.{key.parent.name} -> {key.target_fullname}"
            for table in metadata.sorted_tables
            for key in table.foreign_keys
            if CHECKPOINT_SCHEMA in key.target_fullname
        ]
        assert not crossings, f"a foreign key crosses the checkpoint boundary: {crossings}"
