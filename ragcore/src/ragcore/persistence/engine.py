"""The async engine and the unit of work.

**Read Committed everywhere. No Serializable transaction exists in this platform**
(``data-model.md`` §Conventions). Every invariant is held by a constraint or by an atomic
conditional update rather than by isolation level: the work-item claim is a conditional update on
``claimed_at IS NULL``; first-valid-verdict-wins rests on the unique ``work_item_id`` on
``approval``; duplicate external effects are prevented by the ``idempotency_key`` primary key;
feedback revision rests on the unique ``(message_id, given_by_oid)``. An unnamed Serializable
transaction is indistinguishable from a copy-paste, so if a future invariant genuinely needs one it
is named in ``data-model.md`` first.

**Every statement carries a timeout.** ``statement_timeout`` is set on the connection rather than
per query, because an unbounded query against a shared database is a shared outage — and because
one slow call can hold work past its fifteen-minute expiry, turning a slow dependency into an
expired approval.

**The unit of work exists for the outbox.** An outbox row must become durable in the *same*
transaction as the state change it describes; two writes, however close together, are the bug the
pattern prevents. That is the whole reason there is a transactional boundary here rather than
autocommit at each repository call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from types import TracebackType
from typing import Final, Self

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ragcore.config.settings import DatabaseSettings

ASYNC_DRIVER: Final = "postgresql+asyncpg"
"""The one driver the runtime uses. Named here so a DSN from Key Vault does not have to know."""


def _async_dsn(dsn: str) -> str:
    """Normalise a connection string onto the async driver.

    Args:
        dsn: The DSN as configuration holds it.

    Returns:
        The same DSN with the async driver named.
    """
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", f"{ASYNC_DRIVER}://", 1)
    return dsn


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Build the application's one engine.

    **No DDL rights are implied and none are used.** The runtime principal holds DML and ``SELECT``;
    migrations run as a gated job under a separate principal, before revision activation. A process
    that ran DDL on boot would need rights the separation exists to withhold — and, on a platform
    that scales to zero and runs several replicas, would run it concurrently and repeatedly.

    Args:
        settings: Validated database configuration.

    Returns:
        The engine. Disposed by the caller that owns the application lifespan.
    """
    return create_async_engine(
        _async_dsn(str(settings.dsn)),
        pool_size=settings.pool_max_size,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                # Milliseconds, as PostgreSQL wants them. Rounded rather than truncated so a
                # sub-millisecond setting cannot become `0`, which means *no timeout at all* —
                # the exact opposite of what configuring one is for.
                "statement_timeout": str(max(1, round(settings.statement_timeout_seconds * 1000))),
                "application_name": "ragcore",
            },
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the session factory every repository resolves its session from.

    ``expire_on_commit=False``: a committed entity that expires re-loads on the next attribute
    access, which inside an async handler is a query issued from what looks like an attribute read.
    """
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


_CURRENT_SESSION: ContextVar[AsyncSession | None] = ContextVar(
    "ragcore_current_session", default=None
)
"""The session the innermost open :class:`UnitOfWork` is running in.

**A ``ContextVar``, not a module global.** Several requests are in flight in one process at once,
and a global would hand one request another's transaction — which, in a repository whose whole job
is applying a tenant filter, is the worst possible thing to share.

It exists because the ports declare no session and must not: ``application/ports.py`` is stated in
domain terms only, and an ``AsyncSession`` parameter would put SQLAlchemy in the application layer
(``tests/architecture/test_layering.py`` fails on exactly that). The unit of work is a port; the
session it holds is not, so repositories resolve it from the open boundary rather than receiving it.
"""


def current_session() -> AsyncSession:
    """The session of the innermost open unit of work.

    Raises:
        RuntimeError: When no unit of work is open. **A write outside a transaction is refused
            rather than autocommitted**: the transactional outbox depends on an outbox row landing
            in the same transaction as the state change it describes, and a repository that quietly
            opened its own would break that without failing.
    """
    session = _CURRENT_SESSION.get()
    if session is None:
        raise RuntimeError(
            "no unit of work is open. Every write goes through `async with UnitOfWork(...)`, "
            "because an outbox row must commit in the same transaction as the change it describes."
        )
    return session


class UnitOfWork:
    """One transaction. Satisfies :class:`~ragcore.application.ports.UnitOfWorkPort`.

    Commits on a clean exit and rolls back on any exception, including
    :class:`asyncio.CancelledError` — which matters here more than usual, because a cancelled
    request that left a transaction open would hold its rows until the connection was reclaimed.

    **Nothing here catches the exception it rolls back for.** The caller sees the failure; this
    only guarantees the transaction does not survive it.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._token: Token[AsyncSession | None] | None = None

    @property
    def session(self) -> AsyncSession:
        """The open session.

        Raises:
            RuntimeError: When read outside the context manager. A repository that reached for a
                session without a transaction would be writing outside the boundary the outbox
                depends on.
        """
        if self._session is None:
            raise RuntimeError("the unit of work is not open; use it as an async context manager")
        return self._session

    async def __aenter__(self) -> Self:
        """Begin."""
        self._session = self._session_factory()
        await self._session.begin()
        self._token = _CURRENT_SESSION.set(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Commit on success, roll back on failure, and close either way."""
        session = self._session
        if session is None:  # pragma: no cover — unreachable via the context manager protocol
            return
        try:
            if exc_type is None:
                await session.commit()
            else:
                await session.rollback()
        finally:
            await session.close()
            if self._token is not None:
                # Reset rather than set-to-None, so a nested unit of work restores the outer one
                # instead of leaving every repository in the enclosing scope without a session.
                _CURRENT_SESSION.reset(self._token)
                self._token = None
            self._session = None


@asynccontextmanager
async def read_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Open a session for reads only.

    Separate from :class:`UnitOfWork` because a read path that opened a write transaction would
    hold a snapshot for the length of a listing, and because a caller holding this has no commit to
    call. Repositories issue their reads through it with ``execution_options(stream_results=False)``
    defaults and no identity-map tracking — the Python equivalent of the monolith's
    ``AsNoTracking``: a read model that is never written back does not need change tracking, and
    tracking it invites a mutation nobody meant to persist.
    """
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
