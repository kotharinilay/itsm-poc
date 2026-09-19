"""Structured logging. **Constant templates, and no secret ever reaches a record.**

Constitution Principle VIII: logs and telemetry MUST NOT leak secrets, access tokens, authorization
headers, sensitive customer payloads, or any cross-tenant information. This service is the one that
holds connector credentials, so the rule binds hardest here.

**Templates are constant and values are parameters.** A message built by interpolation produces a
new template per value, which defeats grouping and — more importantly — makes it impossible to
review what a log line can contain by reading the call site.

**The redaction filter is a backstop, not the control.** The control is that secret material is
wrapped in a type that renders as `<redacted>` wherever it is formatted. A filter that scanned for
secrets would have to know every shape one takes; this one catches the small set of header and field
names that are known to carry credentials, and its job is to fail loudly in review rather than to be
relied upon at runtime.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from integrations.api.middleware.correlation import current_correlation_id

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.config.settings import ObservabilitySettings

__all__ = ["CorrelationFilter", "configure_logging"]

# Field and header names that carry credential material. Matched case-insensitively against
# `extra` keys. Deliberately short: a long list reads as a sanitiser people then rely on, and
# relying on it is the failure mode this is a backstop for.
_REDACT_KEYS: Final = frozenset(
    {
        "authorization",
        # Retained deliberately after ADR 0008 deferred gateway-to-backend certificate provenance.
        # Nothing sets or reads this header any more, so the entry is inert — but a redaction list
        # is a backstop, and narrowing one costs nothing to keep and something to get wrong.
        "x-client-certificate-sha256",
        "credential",
        "credential_reference",
        "secret",
        "secret_value",
        "password",
        "token",
        "access_token",
        "connection_string",
        "api_key",
    }
)

_REDACTED: Final = "<redacted>"


class CorrelationFilter(logging.Filter):
    """Attaches the correlation identifier to every record and redacts known credential fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Enrich and scrub the record.

        Args:
            record: The record being emitted.

        Returns:
            Always ``True`` — this filter enriches rather than excludes. A logging filter that
            dropped records would hide the very events an operator needs, so scrubbing is the
            correct response to a suspicious field rather than suppression.
        """
        if not hasattr(record, "correlationId"):
            record.correlationId = current_correlation_id()

        for key in list(vars(record)):
            if key.lower() in _REDACT_KEYS:
                setattr(record, key, _REDACTED)

        return True


def configure_logging(observability: ObservabilitySettings) -> None:
    """Install structured logging for the process.

    Args:
        observability: Telemetry settings, including the service name this process reports under.
    """
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
                '"service":"' + observability.service_name + '",'
                '"correlationId":"%(correlationId)s","message":"%(message)s"}'
            )
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_context(**fields: Any) -> dict[str, Any]:  # noqa: ANN401 — structured log fields are heterogeneous by nature
    """Build an `extra` mapping with the correlation identifier already present.

    Args:
        **fields: Structured fields. **Never a credential** — the filter redacts known names, but
            the obligation is at the call site.

    Returns:
        The mapping, for `logger.info(..., extra=log_context(...))`.
    """
    return {"correlationId": current_correlation_id(), **fields}
