"""Structured logging. **Nothing sensitive reaches a sink, and the guard is not the author.**

Logs and telemetry leak no secret, token, authorization header, sensitive payload or cross-tenant
value (plan §Stage 10 security, spec FR-OPS-002). Every mechanism here exists because the obvious
alternative — *authors remember not to log secrets* — fails in exactly the places nobody reviews:
the error paths, the debug line added at 2am, the ``%r`` on a settings object.

**Four layers, each closing a different escape route.**

1. :class:`SecretValue` already redacts in ``str``, ``repr`` and ``format``
   (:mod:`ragcore.config.secrets`). That covers a value someone deliberately holds.
2. :class:`RedactingFilter` below screens **every record's message and arguments** against the
   shapes a credential actually takes — a bearer token, an ``Authorization`` header, a connection
   string, a key-looking query parameter. That covers a value someone did not know they held.
3. :class:`JsonFormatter` emits a **fixed field set**. A record attribute nobody allow-listed is not
   serialised, so attaching an object with an interesting ``__dict__`` to a log record does not
   quietly publish it.
4. The message template is constant and the variable parts are fields. That is what makes a log
   searchable, and it also means the sensitive thing is a *value* in a named field rather than
   spliced into free text where no filter can find it reliably.

**Redaction is a backstop, not the design.** A filter that pattern-matches secrets is a guess; the
real controls are that secrets are :class:`SecretValue`, that payloads are not logged, and that the
formatter publishes only what it was told to. Layer 2 exists for the case where all three were
forgotten, and it is deliberately loud — a redacted log line says ``<redacted>`` where the value
was, so a reviewer sees that something was caught rather than seeing nothing at all.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Final

from ragcore.api.middleware.correlation import correlation_id_var
from ragcore.config.secrets import REDACTED
from ragcore.observability.context import current_tenant_id

SENSITIVE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # A bearer token in any rendering of an Authorization header. The token, not the word, is
    # replaced — a line reading `Authorization: <redacted>` is more useful than one with the header
    # removed, because it shows the call was authenticated.
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    # A JWT, wherever it appears and whatever field it was put in.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),
    # Credential-bearing connection-string tokens, matching the vocabulary of
    # build/policy/azure-identity.json so the two agree on what a credential looks like.
    re.compile(r"(?i)\b(SharedAccessKey|SharedAccessSignature|AccountKey|AccessKey)=[^\s;\"']+"),
    # A key-looking query parameter or assignment. `sig=` is how a SAS token is spelled.
    re.compile(r"(?i)\b(api[-_]?key|client[-_]?secret|password|sig)=[^\s&;\"']+"),
    # A PostgreSQL DSN carrying an embedded password. Entra authentication puts a token in the
    # password position, so this matches the correct usage too — which is the intended outcome.
    re.compile(r"(?i)\bpostgres(?:ql)?(?:\+\w+)?://[^\s:/@\"']+:[^\s@\"']+@"),
)
"""The shapes a credential actually takes in a log line.

Each entry is a shape rather than a word, because a filter keyed on words catches
``password=hunter2`` and misses the same value in a connection string. The list is deliberately
short: a long one is slow on every record and lulls the reader into thinking it is exhaustive.
"""

LOGGED_FIELDS: Final = (
    "timestamp",
    "level",
    "logger",
    "message",
    "correlation_id",
    "tenant_id",
    "trace_id",
    "span_id",
    "exception",
)
"""Every field a log record may carry into a sink. **An allow-list, not a denial list.**

A record attribute that is not named here is not serialised. That is what stops an object attached
with ``extra={...}`` — a settings instance, a request, a provider response — from being published
because somebody wanted one of its fields.
"""


def redact(text: str) -> str:
    """Replace anything matching a credential shape.

    Args:
        text: The rendered text.

    Returns:
        The text with each match replaced by ``<redacted>``. The surrounding words survive, so the
        line still says what happened.
    """
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(
            lambda match: (
                f"{match.group(1)}={REDACTED}"
                if "=" in match.group(0)
                else f"{match.group(1)} {REDACTED}"
                if match.lastindex
                else REDACTED
            ),
            text,
        )
    return text


class RedactingFilter(logging.Filter):
    """Screen every record's message and arguments before anything formats them.

    A filter rather than a formatter concern, because a filter runs once per record on every
    handler path — including handlers a future change adds, and including the ones a library
    installed. A formatter that redacted would protect only the sink it was attached to.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact in place. **Never filters a record out.**

        Dropping a record would lose the event along with the secret, and an operator investigating
        an incident would find a gap where the interesting line should be. Redacting keeps the
        event and removes the value.
        """
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: _redact_value(value) for key, value in record.args.items()}
            else:
                record.args = tuple(_redact_value(value) for value in record.args)

        return True


def _redact_value(value: object) -> object:
    """Redact one interpolation argument, leaving non-text values alone.

    Numbers and identifiers pass through untouched: rendering every argument through a regular
    expression would be slow on the hot path and would corrupt values that merely resemble one.
    """
    return redact(value) if isinstance(value, str) else value


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with a fixed field set.

    JSON rather than a rendered string because the destination is Application Insights, which
    indexes fields and cannot search inside a sentence. The constant-template rule follows from the
    same place: ``"Claimed work item %s"`` with the identifier as a field groups every claim
    together, while an f-string produces a million distinct messages and no aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render one record as a JSON object carrying only :data:`LOGGED_FIELDS`."""
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }

        tenant_id = current_tenant_id()
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id

        trace_id, span_id = _active_span_ids()
        if trace_id:
            payload["trace_id"] = trace_id
            payload["span_id"] = span_id

        if record.exc_info:
            # The traceback is formatted and then redacted like everything else: a stack frame can
            # carry a local variable's repr, and a provider client's exception can carry a URL with
            # a token in it.
            payload["exception"] = redact(self.formatException(record.exc_info))

        return json.dumps({key: payload[key] for key in LOGGED_FIELDS if key in payload})


def _active_span_ids() -> tuple[str, str]:
    """The current span's identifiers, for joining a log line to a trace.

    Returns:
        ``(trace_id, span_id)`` as hex, or ``("", "")`` when OpenTelemetry is absent or no span is
        recording. Absence is normal on a developer machine and is never an error: correlation by
        ``correlation_id`` still works, and that is the identifier a human quotes.
    """
    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover — optional on a developer machine
        return ("", "")

    context = trace.get_current_span().get_span_context()

    if not context.is_valid:
        return ("", "")

    return (f"{context.trace_id:032x}", f"{context.span_id:016x}")


def configure_logging(*, level: int = logging.INFO) -> None:
    """Install the structured handler on the root logger.

    Called once, from the application lifespan and from each worker's entry point. Replaces any
    existing handlers rather than adding to them: a second handler is a second copy of every line,
    and the copy is usually the unfiltered one a library installed.

    Args:
        level: The root level.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    # Both filters on the handler, and the order is not arbitrary: correlation attaches the
    # identifier, redaction removes what must not travel. Neither ever drops a record.
    from ragcore.api.middleware.correlation import CorrelationIdFilter

    handler.addFilter(CorrelationIdFilter())
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
