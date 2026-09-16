"""The declarative base, the schema, and the column conventions every table obeys.

**PostgreSQL is the single authoritative durable store** (constitution Principle IV). Everything
mapped from this module lives in the ``platform`` schema, which Alembic owns outright. The
``langgraph`` schema belongs to the checkpointer's own ``setup()`` and no class here reaches into
it — see :mod:`ragcore.graph.checkpointer` for why that separation is structural rather than
stylistic.

**The conventions, stated once so no table restates them.**

*Audit columns.* Every table carries ``created_at`` and ``updated_at``. Tables whose rows have a
meaningful acting principal also carry ``created_by`` and ``updated_by``, as free text rather than
a foreign key: the principal may be an Entra ``oid``, a workload principal name, or the migration
job, and none of those is a row in this database.

*Optimistic concurrency.* Every mutable table carries ``version``. **There is no pessimistic lock
and no distributed lock anywhere in this platform** (``data-model.md`` §Conventions). A writer that
loses a race re-reads; it never blocks, and it never waits on a lease it might outlive.

*Soft delete.* **No table in the scaffold declares ``deleted_at``**, and none is intended to. The
convention — a nullable ``deleted_at`` excluded by a global query filter and by every published
view — exists, and :class:`SoftDeletable` below is where the first table that genuinely needs
recoverable deletion will find it. Erasure (spec FR-AUDIT-006) is a hard delete, because a
soft-deleted row is still the organisation's data and a flag would defeat the requirement.
Retention (spec FR-SESS-007) is likewise a removal, not a flag.

**Immutable columns are not enforced here.** The work item's authority fields are protected by a
database trigger, at the permission boundary, because an application convention is exactly the kind
of protection a future code path forgets (constitution Principle III, spec FR-EXEC-008).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Identity, Integer, MetaData, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PLATFORM_SCHEMA: Final = "platform"
"""The schema Alembic owns. Every table below lives here; ``langgraph`` is somebody else's."""

NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}
"""Deterministic constraint names.

Without this, PostgreSQL names constraints and Alembic autogenerate cannot tell an existing
constraint from a new one — which turns ``test_model_definitions_match_ddl`` into a test that
reports a diff on every run and is therefore switched off. Named here so a downgrade can drop by
name and a reviewer can read a migration without opening the database.
"""

metadata: Final = MetaData(schema=PLATFORM_SCHEMA, naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """The declarative base for every platform table."""

    metadata = metadata

    type_annotation_map: Final[dict[Any, Any]] = {  # noqa: RUF012
        # `timestamptz`, never a naive timestamp. A naive value compared against a
        # fifteen-minute authorization window compares wrongly and fails silently.
        datetime: DateTime(timezone=True),
        UUID: PG_UUID(as_uuid=True),
        int: Integer(),
        str: String(),
    }


class TenantScoped:
    """The explicit tenant column every tenant-owned table carries.

    **Denormalised deliberately.** ``message`` could reach its tenant through ``chat_session`` and
    ``approval`` through ``work_item``; both carry ``tenant_id`` anyway. A filter that depends on a
    join is a filter a future query can drop by changing the join, and the rule this platform
    enforces is that **no code path able to issue an unfiltered query may exist** (constitution
    Principle IV). A column on the row makes the filter local to the table.

    The column is **not** nullable and has no default. A missing tenant is a failed insert, not a
    row that quietly belongs to nobody.
    """

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class Audited:
    """``created_at`` and ``updated_at``, on every table without exception.

    Server-side defaults rather than Python ones: the database is the single authority for durable
    state, and two application replicas with drifting clocks would otherwise write timestamps that
    disagree about the order of events they both observed.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Attributed:
    """``created_by`` and ``updated_by``, for tables where a principal is meaningful.

    Applied where a row has an actor — a session has a requester, a work item has one and an
    approver — and omitted where it does not: nothing meaningful writes ``created_by`` on an outbox
    row, and a column populated with ``"system"`` on every row answers no question.

    Text rather than a foreign key or a ``uuid``. The value may be an Entra ``oid``, a workload
    principal name, or the migration job, and none of those is a row in this database.
    """

    created_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(256), nullable=True)


class Versioned:
    """The optimistic-concurrency column.

    Every mutable table carries it. The one exemption is ``idempotency_record``, which is named in
    ``data-model.md`` §Conventions and asserted by ``tests/concurrency/test_optimistic.py`` — and
    which is exempt because its primary key already serialises every concurrent writer.

    Append-only tables (``message``, ``consent``, ``audit_event``) carry the column too, and its
    value stays ``1`` for the life of the row. That is not waste: the runtime principal holds no
    ``UPDATE`` grant on ``audit_event``, so the constancy is enforced by the database rather than
    asserted here, and keeping the convention exceptionless means a reader never has to work out
    whether a missing column is a decision or an oversight.

    **Incremented by the writer, in the same statement as the change**, through
    :func:`ragcore.persistence.concurrency.guarded_update`. It is not driven by SQLAlchemy's
    ``version_id_col``: repositories issue conditional Core updates so that a lost race is a
    ``False`` return the caller handles rather than an exception raised at an unrelated flush.
    """

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class SoftDeletable:
    """The soft-delete convention. **Unused in the scaffold, and deliberately so.**

    No scaffold entity mixes this in. It is declared to fix the shape of the convention — a
    nullable ``deleted_at``, excluded by every repository read and by every published view — so the
    first table that genuinely needs recoverable deletion adopts an existing convention rather than
    inventing a second one.

    A table that mixes this in **must** state in ``data-model.md`` why recoverable deletion is right
    for it, because the two removals the platform already performs are both hard deletes: erasure
    must leave nothing behind, and retention must actually free the data.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class Sequenced:
    """A monotonic ordering column, for the one table read in insertion order.

    The outbox dispatcher publishes in the order rows were written. ``occurred_at`` cannot carry
    that: two rows committed in the same transaction share a ``now()``, and ordering by a value with
    ties makes the dispatcher's cursor non-deterministic.
    """

    sequence: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), nullable=False, unique=True
    )
    """``GENERATED ALWAYS``, so no writer can supply one.

    A caller that could choose its own sequence could publish out of order, and the dispatcher's
    ordering guarantee would become a convention each writer had to keep.
    """
