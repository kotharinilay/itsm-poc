"""Traces, metrics, structured logs and correlation. **Never a substitute for audit.**

Telemetry MUST NOT be used to answer a question that audit is responsible for (spec FR-OPS-004), and
the separation is structural rather than a matter of discipline:

* **Different stores.** Audit is a PostgreSQL table, written through its own port and its own
  repository in ``persistence/``. Telemetry goes to Application Insights. **No audit adapter lives
  in this package**, and ``tests/architecture/test_boundaries.py`` asserts it by reading this file —
  which is why the class is described here rather than named.
* **Different retention.** Telemetry keeps 30 days, audit keeps seven years (spec FR-OPS-011). After
  a month, a question only audit can answer *demonstrably* cannot be answered from here — which is
  what makes the rule true in practice rather than only in policy.
* **Different failure modes, deliberately.** An audit write that fails stops the work. Every
  function in this package tolerates its exporter being absent and carries on, because telemetry
  that could fail the work it observes would be observability outranking the thing observed.

The modules, and the one thing each is for:

| Module | Responsibility |
|---|---|
| :mod:`~ragcore.observability.telemetry` | Configure everything, once, at startup |
| :mod:`~ragcore.observability.logging` | Structured JSON logs, redacted, fixed field set |
| :mod:`~ragcore.observability.propagation` | W3C Trace Context; no custom header replaces it |
| :mod:`~ragcore.observability.sampling` | One decision per journey; head sampling prohibited |
| :mod:`~ragcore.observability.agent_metrics` | The five agent signals FR-OPS-003 names |
| :mod:`~ragcore.observability.context` | The organisation tag, from trusted context only |
"""

from __future__ import annotations

from ragcore.observability.agent_metrics import AgentMetrics, GuardrailAction
from ragcore.observability.context import bind_tenant, current_tenant_id
from ragcore.observability.logging import configure_logging, redact
from ragcore.observability.propagation import (
    configure_propagation,
    context_from,
    current_traceparent,
    outbound_headers,
)
from ragcore.observability.sampling import journey_is_sampled
from ragcore.observability.telemetry import configure_telemetry

__all__ = [
    "AgentMetrics",
    "GuardrailAction",
    "bind_tenant",
    "configure_logging",
    "configure_propagation",
    "configure_telemetry",
    "context_from",
    "current_tenant_id",
    "current_traceparent",
    "journey_is_sampled",
    "outbound_headers",
    "redact",
]
