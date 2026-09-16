"""Cancellation-safety helpers.

**``asyncio.CancelledError`` MUST NOT be swallowed** (constitution §Python). It is not an error
condition; it is the runtime telling a coroutine that its result is no longer wanted. A
coroutine that catches it and carries on has turned a cancelled HTTP request into work the
platform keeps doing, holding a database connection, a Service Bus lease or an outbound call
inside a fifteen-minute execution window nobody is waiting on any more.

Two mistakes this module exists to prevent, both of which pass code review easily:

* ``except Exception`` around an ``await``. On Python 3.8+ ``CancelledError`` inherits from
  ``BaseException``, so this one is *usually* safe — but ``except BaseException``, a bare
  ``except:``, and ``contextlib.suppress(BaseException)`` are not, and they look almost identical
  in a diff. ``tests/unit/test_cancellation.py`` reads the source for all three.
* Cleanup that itself awaits. A cancelled task that runs ``await conn.rollback()`` in a
  ``finally`` gets cancelled *again* at that await, and the rollback never happens.
  :func:`shielded_cleanup` is the answer to that, and the only legitimate use of
  :func:`asyncio.shield` in this codebase.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

_log = logging.getLogger(__name__)

CLEANUP_GRACE_SECONDS = 5.0
"""How long shielded cleanup may run before it is abandoned.

Bounded rather than unlimited: a shield with no timeout turns one hung cleanup into a task that
never finishes, which is a worse failure than the one it was protecting against.
"""


@asynccontextmanager
async def shielded_cleanup(
    cleanup: Callable[[], Awaitable[None]],
    *,
    grace_seconds: float = CLEANUP_GRACE_SECONDS,
) -> AsyncIterator[None]:
    """Run ``cleanup`` even when the body is cancelled, then **re-raise the cancellation**.

    The body is *not* shielded — a cancelled request should stop doing work immediately, and
    shielding it would defeat the point. Only the cleanup is, and only for a bounded grace
    period.

    The cancellation always propagates. This helper makes cleanup reliable; it never makes a
    cancelled operation look like it completed.

    Args:
        cleanup: What must run regardless. Called exactly once.
        grace_seconds: Upper bound on the shielded cleanup.

    Yields:
        Nothing. Use as ``async with shielded_cleanup(conn.rollback): ...``.

    Raises:
        asyncio.CancelledError: Always re-raised after cleanup, never converted or absorbed.
    """
    try:
        yield
    except asyncio.CancelledError:
        await _run_cleanup(cleanup, grace_seconds)
        raise
    else:
        await cleanup()


async def _run_cleanup(cleanup: Callable[[], Awaitable[None]], grace_seconds: float) -> None:
    """Run cleanup under a shield and a timeout, reporting rather than raising on failure.

    A cleanup failure is logged and dropped **on purpose**, and this is the one place that is the
    right call: the caller is already unwinding a cancellation, and raising here would replace
    the cancellation with a secondary error — losing the fact that the operation was cancelled,
    which is the fact everything upstream needs.
    """
    try:
        await asyncio.wait_for(asyncio.shield(cleanup()), timeout=grace_seconds)
    except TimeoutError:
        _log.warning("cleanup exceeded its %ss grace period and was abandoned", grace_seconds)
    except Exception:
        # Not `BaseException`: a CancelledError delivered *during* cleanup must still propagate.
        _log.exception("cleanup failed while unwinding a cancellation")
