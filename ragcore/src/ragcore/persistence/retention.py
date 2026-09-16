"""Retention windows, and when the clock starts.

**The clock starts at the terminal state, not at creation** (spec FR-SESS-020). A conversation that
stayed open for six months and resolved yesterday has ninety days left, not none. That is the whole
reason ``chat_session.content_expires_at`` is nullable: null means *not yet eligible to expire*, and
a stamp written at creation would have deleted live conversations.

**A missing override never means unbounded retention.** Where an organisation configures nothing,
the platform default applies (spec FR-SESS-008). :func:`window_for` resolves that, and it resolves
*to a default* rather than to ``None`` — a function that could return "no window" is a function
that could silently disable retention for whoever forgot to configure it.

**The classes are independent.** Expiring chat content does not touch audit; expiring audit is a
separate, privileged job the runtime cannot perform at all, because it holds no ``DELETE`` on
``audit_event``. ``tests/retention/test_retention_classes.py`` asserts both directions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Final

from ragcore.domain.work import SessionState


class RetentionClass(Enum):
    """The four classes in ``data-model.md`` §Retention summary.

    Named as an enum rather than passed as strings so a typo in an override key is a lookup that
    fails rather than a class that silently keeps its default forever.
    """

    CHAT_CONTENT = "chat_content"
    """Sessions, messages, steps and feedback. Ninety days **from terminal state**."""

    AUDIT = "audit"
    """Audit events. Seven years, and independent of everything above."""

    GRAPH_CHECKPOINT = "graph_checkpoint"
    """Working state. Thirty days after the owning work completes (ADR-0003)."""

    WORK = "work"
    """Work items, operations, approvals and consent. **Follows audit**, not chat."""


PLATFORM_DEFAULTS: Final[dict[RetentionClass, timedelta]] = {
    RetentionClass.CHAT_CONTENT: timedelta(days=90),
    RetentionClass.AUDIT: timedelta(days=365 * 7),
    RetentionClass.GRAPH_CHECKPOINT: timedelta(days=30),
    RetentionClass.WORK: timedelta(days=365 * 7),
}
"""The platform defaults, applied wherever an organisation configures nothing.

``WORK`` deliberately equals ``AUDIT``. Work items, operations, approvals and consent are the record
of what was authorized, and keeping them for ninety days alongside the conversation would mean an
audit event pointing at a work item that no longer exists.
"""


@dataclass(frozen=True, slots=True)
class RetentionWindow:
    """One resolved window, and where the value came from.

    ``is_override`` is carried rather than inferred so an operator reading a sweep log can tell a
    configured ninety days from a defaulted one — which is the difference between a deliberate
    policy and a missing configuration that happens to look right.
    """

    retention_class: RetentionClass
    duration: timedelta
    is_override: bool


def window_for(
    retention_class: RetentionClass, overrides: dict[str, Any] | None
) -> RetentionWindow:
    """Resolve the window for one class, for one organisation.

    Args:
        retention_class: The class being resolved.
        overrides: ``tenant_mapping.retention_overrides``, or ``None`` when none are configured.
            A malformed or negative value is ignored in favour of the default: retention that
            stopped working because somebody typed ``-1`` would be indistinguishable from
            retention that was never configured, and the safe reading of an unusable value is that
            the platform default applies.

    Returns:
        The window. **Never ``None``** — every class always has one.
    """
    default = PLATFORM_DEFAULTS[retention_class]
    if not overrides:
        return RetentionWindow(retention_class, default, is_override=False)

    raw = overrides.get(retention_class.value)
    if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
        # `bool` is excluded explicitly: `True` is an `int` in Python, and `{"audit": true}` in a
        # JSON override would otherwise resolve to a one-day audit retention.
        return RetentionWindow(retention_class, default, is_override=False)

    return RetentionWindow(retention_class, timedelta(days=raw), is_override=True)


def content_expiry_for(
    state: SessionState, terminal_at: datetime, overrides: dict[str, Any] | None
) -> datetime | None:
    """The value to write into ``chat_session.content_expires_at`` on a transition.

    **Returns ``None`` for every non-terminal state**, and that is the control: a caller that
    applied this on every transition still only ever stamps a session that has actually finished.
    The alternative — the caller deciding when to call — is the version where one path forgets and
    a resolved conversation never expires.

    Args:
        state: The state being transitioned *to*.
        terminal_at: The instant of the transition, from
            :class:`~ragcore.application.ports.ClockPort`. Not ``datetime.now``: nothing outside an
            adapter calls that.
        overrides: The organisation's retention overrides, or ``None``.

    Returns:
        The expiry instant, or ``None`` when the session is not yet eligible to expire.
    """
    if not state.is_terminal:
        return None
    return terminal_at + window_for(RetentionClass.CHAT_CONTENT, overrides).duration


def audit_retain_until(occurred_at: datetime, overrides: dict[str, Any] | None) -> datetime:
    """The value to write into ``audit_event.retain_until``.

    Stamped on the row at write time rather than computed at read time, because audit retention must
    not change retroactively: shortening an organisation's window should govern what is written from
    then on, not delete what is already recorded.
    """
    return occurred_at + window_for(RetentionClass.AUDIT, overrides).duration


def checkpoint_prune_after(completed_at: datetime, overrides: dict[str, Any] | None) -> datetime:
    """When a completed run's checkpoints become prunable.

    **Pruned by a job we own** (ADR-0003). The checkpointer versions its own tables and does not
    expire them, so nothing removes this data unless the platform does — which is why a retention
    class exists for a schema Alembic does not manage.
    """
    return completed_at + window_for(RetentionClass.GRAPH_CHECKPOINT, overrides).duration
