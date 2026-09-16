"""The organisation telemetry is tagged with — **from trusted context, and from nowhere else**.

Traces, metrics and structured logs are each tagged with the owning organisation from trusted
context, **never from a supplied header or from message content** (spec FR-OPS-002). That rule needs
a single place where the value can be written, or it becomes a rule every call site is trusted to
have honoured.

This module is that place. :func:`bind_tenant` accepts a
:class:`~ragcore.domain.tenancy.TenantContext`, which can only be constructed through a ``from_*``
classmethod naming its provenance — so the type system has already done the hard half: there is no
way to reach this function holding an organisation identifier that came from a client.

**It is deliberately not a setter taking a string.** ``bind_tenant_id("...")`` would accept a header
value, a message field or a model's output with equal enthusiasm, and the one call site that did
that would be indistinguishable from the twenty that did not.

**Reading is best-effort and never fails.** :func:`current_tenant_id` returns ``None`` outside a
request — a worker at startup, a migration, a test — because telemetry must never be the reason a
piece of work does not run. An untagged span is a small loss; an exception raised from the logging
path is an outage.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.domain.tenancy import TenantContext

_tenant_id_var: ContextVar[str] = ContextVar("telemetry_tenant_id", default="")
"""The current organisation's platform identifier, as a string, for telemetry attributes.

A :class:`~contextvars.ContextVar` rather than a module global: context variables are per-task and
are copied into tasks a request spawns, so two concurrent requests cannot read each other's value.
A module global here would mis-attribute telemetry under load — and mis-attributed telemetry is
worse than none, because it is believed.

**The platform ``tenant_id``, never the Entra ``tid``.** The platform identifier is this system's
own key for an organisation; the directory identifier belongs to the identity provider and is one
join away from naming a real company in a dashboard nobody treats as sensitive.
"""


def bind_tenant(tenant: TenantContext) -> None:
    """Tag everything this task emits with the organisation it is being done for.

    Called once per request, from :mod:`ragcore.api.deps` at the point admission succeeds, and once
    per message from the consumer after it resolves the organisation from the durable row. Both are
    trusted derivations; there is no third caller and no overload taking a string.

    Args:
        tenant: The admitted organisation. Its provenance is recorded on the context itself.
    """
    _tenant_id_var.set(str(tenant.tenant_id.value))


def current_tenant_id() -> str | None:
    """The organisation this task is working for, or ``None`` when there is not one.

    Returns:
        The platform identifier as a string, or ``None`` outside a request or message — a worker
        at startup, a migration, a test. ``None`` is correct rather than a gap to be filled: work
        that belongs to no organisation must not be attributed to one.
    """
    return _tenant_id_var.get() or None
