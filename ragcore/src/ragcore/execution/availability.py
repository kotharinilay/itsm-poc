"""Entitled-but-unreachable is its own outcome. **It is not a refusal and not a failure.**

A capability that is entitled but whose system is unreachable MUST be reported as temporarily
unavailable, distinctly from one that is not entitled — and **neither** MUST be presented to the
user as a failure of their request (spec FR-EXT-022).

Three distinctions, and each one is a different conversation:

* *Not entitled* — the organisation may not use this capability. Nothing is wrong; the answer is no,
  and it will still be no in ten minutes. The operator action is an entitlement decision.
* *Entitled but unreachable* — the organisation may use it and the platform could not reach it. The
  answer is "not now". The operator action is to look at the third party.
* *Available* — it may be used and the system answered.

Collapsing the first two into one "unavailable" is the mistake this module exists to prevent, and it
is an easy one because both end with the user not getting the thing. They are opposite failures: one
is a policy position that is working correctly, the other is an outage. A support queue that cannot
tell them apart triages every entitlement decision as an incident.

**Nothing here is a failure of the user's request**, which is why :class:`CapabilityAvailability`
has no ``FAILED`` member. The platform continues in reduced mode when an external system is
unavailable and does not take an ungrounded action in its absence (spec FR-EXT-020) — the request is
still being handled, with less.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from ragcore.integrations.http import TransientIntegrationError

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from collections.abc import Awaitable, Callable


class CapabilityAvailability(Enum):
    """Whether a capability can be used right now, and why not when it cannot.

    Three members, no ``UNKNOWN`` and no ``FAILED``. ``UNKNOWN`` would be a state nothing could act
    on; ``FAILED`` would be the presentation FR-EXT-022 prohibits, available as an enum member for
    any caller who reached for it.
    """

    AVAILABLE = "available"
    """Entitled, and the system answered."""

    NOT_ENTITLED = "not_entitled"
    """The organisation may not use this capability.

    **A settled answer, not a temporary one.** There is no global toolset and capabilities resolve
    per organisation on a least-privilege basis (spec FR-EXT-015); the absence of an entitlement
    denies. Retrying changes nothing, and presenting it as a retryable problem invites a user to
    wait for something that is not coming.
    """

    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    """Entitled, and the system could not be reached.

    Temporary by claim as well as by name: the entitlement stands, and the capability returns when
    the third party does. This MUST NOT be reported as a refusal — a user told "you are not allowed
    to do that" during an outage receives a false statement about their own permissions.
    """


async def availability_of(
    *, entitled: bool, probe: Callable[[], Awaitable[object]] | None = None
) -> CapabilityAvailability:
    """Classify one capability's current availability.

    **Entitlement is checked first, and the system is not probed when it fails.** Not an
    optimisation: probing a system the organisation may not use would send that organisation's
    credential to a third party over a capability it has no right to, and the answer would change
    nothing.

    Args:
        entitled: Whether the organisation is entitled, from the governance catalogue. Never
            inferred from whether a system advertised the capability — discovery is not entitlement
            (spec FR-EXT-014).
        probe: A callable that reaches the system, or ``None`` to report on entitlement alone.
            **A callable rather than an awaitable**, so that a capability the organisation is not
            entitled to is genuinely never called — an awaitable parameter would already have been
            constructed by the caller, and "it was not probed" would be a claim about what was
            awaited rather than about what was done.

    Returns:
        The availability.
    """
    if not entitled:
        return CapabilityAvailability.NOT_ENTITLED

    if probe is None:
        return CapabilityAvailability.AVAILABLE

    try:
        await probe()
    except TransientIntegrationError:
        # Transient only. A permanent failure is a defect in the platform's own request — a bad
        # contract, a rejected payload — and reporting that as "the third party is down" would send
        # an operator to look at somebody else's system.
        return CapabilityAvailability.TEMPORARILY_UNAVAILABLE

    return CapabilityAvailability.AVAILABLE
