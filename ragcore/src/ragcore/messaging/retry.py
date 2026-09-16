"""Bounded retry with jitter — **before the claim only**.

Two rules, and the second is the one that matters:

1. **Pre-claim transient failure** — the database is unreachable, the message will not deserialize —
   retries with exponential backoff and jitter, inside the remaining window. Exhausted attempts
   dead-letter.
2. **Post-claim execution failure — no retry, ever.** The outcome is recorded, the work escalates,
   and the item is left non-executable until a human authorizes it again.

Rule 2 is a governance decision, not a resilience trade-off (ADR-0002, answering OQ-07). Re-firing
a failed consequential operation without a human seeing the failure is the wrong default: the first
attempt may have half-succeeded in a system this platform cannot see inside, and "it failed, so do
it again" is exactly how one refused action becomes two performed ones.

**Jitter is not decoration.** Every consumer of a queue that goes down retries on the same
schedule, so a fixed backoff reconverges the whole fleet onto the same instant and the recovering
dependency is hit by a thundering herd at each step. The jitter is full-range for that reason — a
narrow band spreads the herd without breaking it up.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

DEFAULT_CEILING: Final = 10
"""Attempts before a row or message is given up on (``contracts/triggers.md``).

Ten, and bounded rather than indefinite, because the execution window is fifteen minutes: a trigger
that cannot be delivered inside it can no longer lead to a valid execution, so retrying past that
point manufactures the appearance of pending work that can never complete.
"""

DEFAULT_BASE_DELAY: Final = timedelta(seconds=1)
DEFAULT_MAX_DELAY: Final = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """Exponential backoff with full jitter, bounded by a ceiling.

    Frozen: a policy that could be mutated mid-run is one where two messages in the same batch can
    be retried on different rules for reasons nobody can reconstruct afterwards.
    """

    ceiling: int = DEFAULT_CEILING
    base_delay: timedelta = DEFAULT_BASE_DELAY
    max_delay: timedelta = DEFAULT_MAX_DELAY

    def exhausted(self, attempts: int) -> bool:
        """Whether this many attempts has reached the ceiling.

        Args:
            attempts: Attempts already made.

        Returns:
            ``True`` when no further attempt may be made.
        """
        return attempts >= self.ceiling

    def delay_for(self, attempts: int, *, rng: random.Random | None = None) -> timedelta:
        """The delay before the next attempt.

        Full jitter: the delay is drawn uniformly from ``[0, exponential]`` rather than being the
        exponential itself. The expected wait is halved and — the point — two consumers that failed
        together do not retry together.

        Args:
            attempts: Attempts already made. ``0`` yields the first delay.
            rng: Injectable randomness, so a test can assert the bound rather than the draw.

        Returns:
            How long to wait. Never longer than :attr:`max_delay`.
        """
        source = rng if rng is not None else random
        exponential = self.base_delay.total_seconds() * (2 ** max(attempts, 0))
        bounded = min(exponential, self.max_delay.total_seconds())
        return timedelta(seconds=source.uniform(0.0, bounded))


class PostClaimRetryError(RuntimeError):
    """Raised if anything attempts to retry after the claim has been taken.

    **A guard rail with a blast radius, not a style rule.** The claim is the moment the platform
    commits to executing once; retrying past it risks a second external effect for an action a human
    authorized once. This exists so that a future caller reaching for a retry decorator on the
    post-claim path fails loudly instead of quietly becoming correct-looking code.
    """


def refuse_post_claim_retry(operation: str) -> None:
    """Refuse a retry on the post-claim path.

    Args:
        operation: What was about to be retried, for the message.

    Raises:
        PostClaimRetryError: Always. That is the function's purpose.
    """
    raise PostClaimRetryError(
        f"{operation} failed after the work item was claimed, and post-claim work is never "
        "retried (ADR-0002). Record the outcome, escalate, and leave the work non-executable — a "
        "failed authorized action requires fresh human authorization, not a second attempt."
    )
