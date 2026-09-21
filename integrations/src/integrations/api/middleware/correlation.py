"""Correlation. **One identifier, the whole journey, across three deployables.**

A correlation identifier originates at the public edge and propagates through every tier,
appearing on every log record, trace, message, execution record and audit record
(A2 P10).
For this service the journey is longer than a request: it spans the APIM hop, the command queue, the
external call, the result queue and back into RagCore. `FR-DEMO-027` makes recovering it end to end
an acceptance criterion.

**W3C Trace Context, and a custom propagation header MUST NOT replace it.** The reason is concrete
rather than stylistic: a bespoke header would work perfectly between our own services and be
invisible to APIM, to the Azure SDKs and to every managed hop in between — so the trace would break
exactly where the platform stops being ours.

**An inbound value is accepted only when well formed.** A malformed one is replaced rather than
propagated: a correlation identifier is an index into telemetry, and one that a caller can shape
freely is an injection point into every log line that carries it.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["CORRELATION_HEADER", "CorrelationMiddleware", "current_correlation_id"]

CORRELATION_HEADER: Final = "X-Correlation-Id"

# THE ONE RULE, on all three deployables: ASCII letters, digits, '.', '_' and '-', 1-128 characters
# (build/policy/correlation-id.json, asserted by each stack's suite). Wide enough for a UUID or a
# W3C trace id, tight enough that nothing a caller sends can carry a newline, a control character
# or a log-format token into a structured log record.
#
# It used to be hex only, while .NET accepted letters and '_' and RagCore accepted anything
# printable — so one journey's identifier was kept on one hop and replaced on the next. Matched with
# `fullmatch`: `^...$` with `match` also accepts a trailing newline.
_WELL_FORMED: Final = re.compile(r"[A-Za-z0-9._-]{1,128}")

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def current_correlation_id() -> str:
    """The correlation identifier bound to the current context.

    Returns:
        The identifier, or an empty string outside a request or consumer scope. Callers that log
        outside a scope get an empty field rather than a fabricated identifier — an invented one
        would correlate two unrelated journeys, which is worse than a missing value.
    """
    return _correlation_id.get()


def bind_correlation_id(value: str) -> None:
    """Bind an identifier to the current context.

    Used by the message consumers, which have a correlation identifier from the envelope but no
    HTTP request for the middleware to act on.

    Args:
        value: The identifier recovered from the message envelope.
    """
    _correlation_id.set(value)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Establishes the correlation identifier **before** request logging.

    Ordering is load-bearing (constitution §Middleware order): correlation and trace context are
    established before request logging, so the first log line of a request already carries the
    identifier. A middleware that logged first would produce exactly one uncorrelated record per
    request — the record describing the request nobody can then find.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Accept a well-formed inbound identifier, generate one otherwise, and echo it.

        Args:
            request: The inbound request.
            call_next: The rest of the pipeline.

        Returns:
            The response, carrying the identifier the request was handled under.
        """
        inbound = request.headers.get(CORRELATION_HEADER, "")
        correlation_id = inbound if _WELL_FORMED.fullmatch(inbound) else str(uuid.uuid4())

        token = _correlation_id.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)

        response.headers[CORRELATION_HEADER] = correlation_id
        return response
