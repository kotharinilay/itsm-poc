"""What Alembic autogenerate may look at. **The ``langgraph`` exclusion lives here.**

Two filters, and both are needed (research R-004):

* :func:`include_name` stops a schema being *reflected at all*. Without it, autogenerate reads the
  checkpoint tables, finds no model for them, and proposes dropping them — turning a routine
  revision into a silent loss of every suspended conversation.
* :func:`include_object` filters what has been reflected. It catches the objects that carry no
  schema of their own — a column, an index, a constraint — by judging them on the table they hang
  off.

They live in this module rather than in ``migrations/env.py`` so they can be tested without
executing an Alembic environment. ``env.py`` decides at import time whether it is running offline,
against a supplied connection, or online, and a test that imported it to reach these two functions
would be starting a migration to ask a question about a filter.
"""

from __future__ import annotations

from typing import Any

from ragcore.graph.checkpointer import CHECKPOINT_SCHEMA
from ragcore.persistence.base import PLATFORM_SCHEMA


def include_object(
    obj: Any,  # Alembic passes SchemaItem subclasses of several kinds
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """Decide whether autogenerate may consider a schema object.

    Alembic owns ``platform``; the checkpointer owns ``langgraph``. An object in any other schema is
    somebody else's and is not compared, so a revision generated here can neither create nor drop
    one.

    Args:
        obj: The reflected or modelled object.
        name: Its name.
        type_: ``"table"``, ``"column"``, ``"index"`` and so on.
        reflected: Whether it came from the database rather than from the metadata.
        compare_to: The counterpart being diffed against, if any.

    Returns:
        ``True`` when the object belongs to the platform schema and Alembic may act on it.
    """
    del name, reflected, compare_to  # Part of Alembic's signature; the decision uses neither.

    schema = getattr(obj, "schema", None)
    if type_ == "table":
        return bool(schema == PLATFORM_SCHEMA)

    # A column, index or constraint is judged by the table it hangs off, which is how an index
    # inside `langgraph` is excluded even though it carries no schema of its own.
    parent_schema = getattr(getattr(obj, "table", None), "schema", None)
    return bool((schema or parent_schema or PLATFORM_SCHEMA) == PLATFORM_SCHEMA)


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """Decide whether autogenerate may *reflect* a name at all.

    The stronger of the two filters: it stops ``langgraph`` being read in the first place, which is
    what prevents autogenerate from proposing to drop a schema it can see but does not own.

    Args:
        name: The schema or table name under consideration.
        type_: ``"schema"``, ``"table"`` or similar.
        parent_names: The enclosing names Alembic has resolved so far.

    Returns:
        ``True`` when the name is inside the platform schema.
    """
    del parent_names

    if type_ == "schema":
        # `None` is the default schema. Excluding it keeps `public` out of comparison entirely —
        # and no principal in this platform holds rights there anyway.
        if name is None or name == CHECKPOINT_SCHEMA:
            return False
        return name == PLATFORM_SCHEMA
    return True
