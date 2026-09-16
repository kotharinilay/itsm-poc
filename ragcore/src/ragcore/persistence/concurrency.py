"""Optimistic concurrency. **The only concurrency control this platform has.**

Three positions, all stated in ``data-model.md`` §Conventions and all enforced here:

1. **No distributed lock, anywhere.** A lease is a promise about a process that may already be
   dead, and every lock that has to be released is a lock that eventually is not. A writer that
   loses a race here re-reads and retries; it never blocks and never waits on a lease it might
   outlive.
2. **No Serializable transaction, anywhere.** Read Committed everywhere, with each invariant held
   by a constraint or by an atomic conditional update. Raising the isolation level would make the
   guarantee depend on something a reader of the repository cannot see.
3. **No ``deleted_at`` on any scaffold entity.** Removal is removal — see
   :class:`ragcore.persistence.base.SoftDeletable` for the convention and why nothing uses it.

**The mechanism is one conditional ``UPDATE``.** The version the caller read goes into the
``WHERE`` clause; the statement increments it. A row count of one means this writer won, and zero
means somebody else committed first. There is no read-then-write window for a competitor to slip
into, because the check and the write are the same statement.

**``idempotency_record`` is the one exemption** and it is named, here and in ``data-model.md``.
Its primary key already serialises every concurrent writer, so a version column would be a second
concurrency mechanism on a row that structurally cannot have two live writers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, cast

from sqlalchemy import ColumnElement, Result, Table, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ragcore.domain.errors import DomainError

EXEMPT_FROM_VERSIONING: Final = frozenset({"idempotency_record"})
"""The single named exemption. **Adding a second one requires naming it in ``data-model.md``**,
and ``tests/concurrency/test_optimistic.py`` fails until it is."""


class ConcurrencyConflictError(DomainError):
    """Raised when a caller demanded a write that a concurrent writer had already invalidated.

    Raised only by :func:`require_guarded_update`. The plain :func:`guarded_update` returns
    ``False`` instead, because at most call sites a lost race is an ordinary outcome that the
    caller handles by re-reading — and an exception for an expected outcome is how retries end up
    wrapped in a ``try`` that also swallows real failures.
    """

    def __init__(self, table: str, expected_version: int) -> None:
        super().__init__(
            f"{table} was modified concurrently: version {expected_version} is no longer current. "
            "Re-read the row and retry; there is no lock to wait on."
        )
        self.table = table
        self.expected_version = expected_version


@dataclass(frozen=True, slots=True)
class VersionedRow:
    """What a caller needs to attempt a guarded write: the row's identity and the version it read.

    A pair rather than two loose arguments, because ``(id, version)`` travelling separately is how
    a retry ends up passing the *new* identity with the *old* version.
    """

    identity: ColumnElement[bool]
    """The predicate selecting exactly one row — including its ``tenant_id``, always."""

    expected_version: int
    """The version the caller read. The write applies only if it is still current."""


async def guarded_update(
    session: AsyncSession,
    table: Table,
    row: VersionedRow,
    **changes: Any,  # noqa: ANN401 — column values are as varied as the columns
) -> bool:
    """Apply ``changes`` if and only if the row is still at the version the caller read.

    The statement increments ``version`` and refreshes ``updated_at`` itself, so no caller has to
    remember either. Values are bound as parameters by SQLAlchemy — **nothing here interpolates a
    value into SQL**, and the predicate is built from column objects rather than from text.

    Args:
        session: The open session. The write joins whatever transaction the caller already has,
            which is what lets an outbox row commit alongside the state change it describes.
        table: The table to update.
        row: The row's identity predicate and the version the caller read.
        **changes: Column values to set. ``version`` and ``updated_at`` are managed here and
            passing either is refused rather than silently overridden.

    Returns:
        ``True`` when this writer won, ``False`` when another committed first.

    Raises:
        ValueError: When ``changes`` contains ``version`` or ``updated_at``, or when the table has
            no ``version`` column to guard on.
    """
    _reject_managed_columns(changes)

    version_column = table.c.get("version")
    if version_column is None:
        raise ValueError(
            f"{table.name} has no `version` column, so it cannot be updated under optimistic "
            "concurrency. If that is deliberate, it must be named in data-model.md §Conventions."
        )

    statement = (
        update(table)
        .where(row.identity, version_column == row.expected_version)
        .values(**changes, version=version_column + 1, updated_at=_now())
    )
    result = await session.execute(statement)
    return rows_affected(result) == 1


async def require_guarded_update(
    session: AsyncSession,
    table: Table,
    row: VersionedRow,
    **changes: Any,  # noqa: ANN401
) -> None:
    """Apply ``changes`` or raise.

    For the call sites where losing the race is genuinely exceptional — a caller that has already
    established it holds the only claim, for instance — and where returning ``False`` would put the
    burden of noticing on code that has nothing useful to do about it.

    Raises:
        ConcurrencyConflictError: When another writer committed first.
    """
    if not await guarded_update(session, table, row, **changes):
        raise ConcurrencyConflictError(table.name, row.expected_version)


async def claim_once(
    session: AsyncSession,
    table: Table,
    identity: ColumnElement[bool],
    **changes: Any,  # noqa: ANN401
) -> bool:
    """Take an unclaimed row, atomically. **Idempotency boundary 1.**

    Distinct from :func:`guarded_update` on purpose. A claim is not a version check: the caller has
    not read a version and does not care what it is — the question is only *has anybody taken this
    yet*, and the predicate the caller supplies answers it (``claimed_at IS NULL``). Folding the two
    together would mean a duplicate trigger could lose the claim to a version bump that had nothing
    to do with claiming.

    At-least-once delivery makes a duplicate trigger routine rather than exceptional, and this is
    what absorbs it: the second caller gets ``False`` and does nothing, which is the correct
    outcome and not an error.

    Returns:
        ``True`` when this caller won the claim, ``False`` when another already holds it.
    """
    _reject_managed_columns(changes)

    version_column = table.c.get("version")
    managed: dict[str, Any] = {"updated_at": _now()}
    if version_column is not None:
        managed["version"] = version_column + 1

    result = await session.execute(update(table).where(identity).values(**changes, **managed))
    return rows_affected(result) == 1


def _reject_managed_columns(changes: dict[str, Any]) -> None:
    """Refuse an attempt to set a column this module owns.

    Raises:
        ValueError: When ``version`` or ``updated_at`` appears in the caller's changes. Silently
            overriding either would mean a caller could pin a version and defeat the guard, or
            backdate a row and defeat the audit trail.
    """
    managed = {"version", "updated_at"} & changes.keys()
    if managed:
        raise ValueError(
            f"{sorted(managed)} are managed by the concurrency helper and must not be passed. "
            "The version is incremented and `updated_at` refreshed as part of the guarded write."
        )


def _now() -> ColumnElement[Any]:
    """The database's clock, as a SQL expression.

    ``now()`` rather than a Python timestamp, and this is the one place in the codebase where that
    is right: ``updated_at`` orders writes against each other, and two replicas with drifting
    clocks would write timestamps that disagree about an ordering the database already knows. Every
    *business* instant still comes from :class:`~ragcore.application.ports.ClockPort`.
    """
    from sqlalchemy import func

    return func.now()


def rows_affected(result: Result[Any]) -> int:
    """The number of rows a DML statement actually changed.

    ``AsyncSession.execute`` is declared to return :class:`~sqlalchemy.engine.Result`, which is
    accurate for a ``SELECT`` and understated for an ``UPDATE`` — only the cursor result carries
    ``rowcount``. The narrowing happens here, once, so every conditional write in the persistence
    layer reads the count the same way and no call site invents its own cast.

    **This count is the outcome of an optimistic write**, not a diagnostic: ``1`` means this writer
    won, ``0`` means another committed first.
    """
    return cast("CursorResult[Any]", result).rowcount
