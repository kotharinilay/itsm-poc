"""The correlation identifier: accepted at the edge, bound to the log context, echoed back.

**A correlation identifier MUST originate at the public edge and be propagated through every
tier** (spec FR-OPS-001). It appears on every log record, trace, notification, trigger and audit
record, which is what makes one user request followable across a flow that suspends for a day and
resumes in a different process.

**A client-supplied identifier is accepted, and it is still untrusted.** It correlates; it
authorizes nothing, and nothing reads it to make a decision. What it can do is get long, or carry
control characters into a log file, so it is bounded and screened before anything writes it.
"""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragcore.domain.identifiers import CORRELATION_ID_MAX_LENGTH

CORRELATION_HEADER = "X-Correlation-Id"

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
"""The identifier for the current task.

A :class:`~contextvars.ContextVar` rather than a module global: context variables are per-task
and are copied into tasks a request spawns, so concurrent requests cannot read each other's
value. A module global here would be exactly the "no global mutable state"
.claude/rules/10-principles.md P-28 prohibits, and would mis-attribute log lines under load.
"""


class CorrelationIdFilter(logging.Filter):
    """Attach the current correlation identifier to every log record.

    A filter rather than a call site obligation. ``logger.info(..., extra={...})`` at each call
    site is one omission away from a log line nobody can correlate, and the omissions are always
    in the error paths.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Set ``record.correlation_id``. Never filters anything out."""
        if not hasattr(record, "correlation_id"):
            record.correlation_id = correlation_id_var.get()
        return True


WELL_FORMED: Final = re.compile(rf"[A-Za-z0-9._-]{{1,{CORRELATION_ID_MAX_LENGTH}}}")
"""The one rule for a well-formed correlation identifier, on all three deployables.

Recorded in ``build/policy/correlation-id.json``, which the .NET and Integrations suites read as
well. It used to be "any printable string" here — so ``<script>`` was echoed in a header and a
problem body — while the Integrations Service accepted hex only, and would dead-letter a command
whose identifier this service had accepted and carried. One journey, one identifier, one rule.
Matched with ``fullmatch``: a pattern anchored with ``$`` also accepts a trailing newline.
"""


def _accepted(raw: str) -> str | None:
    """Screen a client-supplied identifier.

    Returns:
        The identifier when it is well formed, or ``None`` when a fresh one should be minted.
        Rejecting is silent and non-fatal: a bad correlation identifier is not worth failing a
        user's request over, and a minted one still correlates everything downstream of here.
    """
    return raw if WELL_FORMED.fullmatch(raw) else None


class CorrelationIdMiddleware:
    """Bind a correlation identifier for the duration of one request.

    Pure ASGI, for the same reason as the identity middleware: ``BaseHTTPMiddleware`` changes how
    cancellation propagates on client disconnect.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Resolve the identifier, bind it, echo it on the response."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _resolve(scope)
        scope.setdefault("state", {})
        state = scope["state"]
        if isinstance(state, dict):
            state["correlation_id"] = correlation_id
        token = correlation_id_var.set(correlation_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                # This middleware OWNS the header. An inner layer that also set it — a problem
                # response, the SSE stream — is replaced rather than joined, so a response carries
                # exactly one identifier. It used to carry two.
                name = CORRELATION_HEADER.lower().encode()
                headers = [
                    (key, value) for key, value in message.get("headers", []) if key.lower() != name
                ]
                headers.append((name, correlation_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            # Reset in `finally` so a cancelled request does not leak its identifier into
            # whatever the event loop runs next. The cancellation itself is untouched: there is
            # no `except` here, so `CancelledError` passes straight through.
            correlation_id_var.reset(token)


def _resolve(scope: Scope) -> str:
    """Take the client's identifier when it is acceptable; mint one otherwise."""
    wanted = CORRELATION_HEADER.lower().encode()
    for name, value in scope.get("headers", []):
        if name.lower() == wanted:
            accepted = _accepted(value.decode("latin-1", errors="replace"))
            if accepted is not None:
                return accepted
            break
    return str(uuid.uuid4())
