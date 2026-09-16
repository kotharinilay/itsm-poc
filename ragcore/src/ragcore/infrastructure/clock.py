"""The system clock — the only adapter the scaffold has.

Present rather than deferred because it needs nothing to construct, and because without it the
rule it exists to enforce has no alternative: **nothing outside an adapter calls
``datetime.now``**. With it, that rule is checkable — there is exactly one caller, and everything
else takes a :class:`~ragcore.application.ports.ClockPort`.

Timezone-aware UTC, always. A naive datetime compared against an ``expires_at`` read from
``timestamptz`` raises at best and compares wrongly at worst, and the value being compared is a
fifteen-minute authorization window.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """The real clock. Satisfies :class:`~ragcore.application.ports.ClockPort`."""

    def now(self) -> datetime:
        """Return the current instant, timezone-aware and in UTC."""
        return datetime.now(UTC)
