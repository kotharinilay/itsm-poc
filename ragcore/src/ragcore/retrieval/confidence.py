"""Confidence and margin — **the two thresholds, and the only place either one is written down**.

`FR-AGENT-014` and `FR-AGENT-015` require the resolution loop to decide whether it knows enough to
act, from an absolute score **and** a margin. `FR-AGENT-007` makes both figures global platform
constants rather than settings. This module owns them, and the plan says so explicitly: "the
constants and their comparison direction live in one module (``retrieval/confidence.py``) and
nowhere else" (plan §Stage 12).

**Why one module rather than one per consumer.** Two thresholds duplicated across the retrieval
path and the governance path are two thresholds that agree until somebody tunes one of them, and
the resulting divergence is invisible: retrieval would consider evidence sufficient while the gate
withheld on it, or worse, the reverse. :mod:`ragcore.governance.conditions` therefore imports from
here rather than restating the figures — an import direction chosen deliberately, because the
alternative is a copy.

**Both comparisons are ``>=``: a value exactly equal to its threshold passes** (plan §Stage 12).
The threshold is the lowest acceptable value, not the first unacceptable one. This is stated
because the choice is invisible in review — two implementers will split on it, both believing they
chose the obvious reading, and the behaviour differs only on the exact boundary, which is precisely
where a confidence gate is most often wrong. ``tests/unit/test_confidence.py`` asserts the boundary
in both directions rather than inferring it.

**A score is not a probability.** Nothing here converts one into a percentage, and nothing may
present ``top_score`` to a user as a confidence figure. What this module produces is a boolean and
the two numbers that produced it, so an audit record can say *why* rather than *how sure*.

Nothing here performs I/O, reads a clock or calls a model.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

__all__ = [
    "MINIMUM_MARGIN",
    "MINIMUM_TOP_SCORE",
    "Confidence",
    "Scored",
    "assess",
    "assess_scores",
    "clears_thresholds",
]

MINIMUM_TOP_SCORE: Final = 0.45
"""The best candidate must clear this on its own.

A **platform constant**, not configuration (`FR-AGENT-007`): a threshold an operator can turn down
is a threshold that gets turned down on the afternoon the platform looks unhelpful, and the
resolution loop must behave identically for every organisation.

Below it the best available evidence is weak in absolute terms however it compares to the rest, and
a field of uniformly poor matches is not made good by one of them being least poor.
"""

MINIMUM_MARGIN: Final = 0.08
"""The gap between the best and the second-best candidate.

Also a platform constant. Without it a near-tie reads as confidence: two chunks at 0.70 and 0.69
are two plausible and possibly contradictory answers, and picking the first is a coin toss the
score does not disclose. A single candidate has no runner-up to tie with, so its margin is its own
score — the absolute test and the margin test then ask the same question, which is the honest
reading of "one match, nothing else close".
"""


def clears_thresholds(top_score: float, margin: float) -> bool:
    """Whether both figures clear their thresholds. **The comparison, and the only copy of it.**

    A named function rather than two inline comparisons, for a reason that is specific rather than
    stylistic. The plan requires the boundary to be asserted directly in both directions
    (§Stage 12), and at the magnitudes this operates on, *a margin exactly equal to the threshold
    is not representable*: the difference of two doubles near 0.85 is a multiple of that binade's
    ulp, roughly 1.1e-16, and 0.08's stored value is not such a multiple. A test that fed in scores
    and hoped for equality would therefore be asserting ``>`` or ``<`` at the mercy of whichever
    values somebody picked — the exact accident the plan calls out.

    Pulling the comparison out makes the boundary reachable: a test passes the thresholds
    themselves and gets a definite answer about ``>=`` versus ``>``.

    Args:
        top_score: The best candidate's absolute score.
        margin: The gap to the runner-up, or the top score itself when there is none.

    Returns:
        ``True`` when both clear. **Both comparisons are ``>=``**: the threshold is the lowest
        acceptable value, not the first unacceptable one.
    """
    return top_score >= MINIMUM_TOP_SCORE and margin >= MINIMUM_MARGIN


class Scored(Protocol):
    """Anything carrying a relevance score. Satisfied by every chunk type in this package."""

    @property
    def score(self) -> float:
        """Relevance. **Not a probability** (`FR-AGENT-006`)."""
        ...


@dataclass(frozen=True, slots=True)
class Confidence:
    """The two figures and the one boolean they produce.

    Frozen: a confidence recomputed after the fact is a confidence that can be recomputed to a
    different answer, and the whole value of assessing it once is that the gate and the audit
    record agree about what was assessed.

    Attributes:
        top_score: The best candidate's absolute score. Recorded for the audit trail and the step
            trail; **never rendered to a user as a percentage or a certainty**.
        margin: The gap to the runner-up, or the top score itself when there is no runner-up.
        is_confident: Whether both comparisons passed. The only question anything downstream asks.
    """

    top_score: float
    margin: float
    is_confident: bool


def assess_scores(scores: Iterable[float]) -> Confidence:
    """Assess confidence from raw scores.

    Args:
        scores: The candidate scores, **in any order**. Sorted here rather than trusted to arrive
            sorted: a provider that changed its ordering would otherwise silently turn the margin
            into the gap between two arbitrary candidates, and the resulting bug reads as a tuning
            problem rather than as a defect.

    Returns:
        The two figures and the verdict. Empty input is **not confident** — an absence of evidence
        is not a weak positive, and it is the case where a scored implementation is most likely to
        return something that clears a threshold by default.
    """
    ordered = sorted((float(score) for score in scores), reverse=True)
    if not ordered:
        return Confidence(top_score=0.0, margin=0.0, is_confident=False)

    top = ordered[0]
    margin = top - ordered[1] if len(ordered) > 1 else top

    return Confidence(top_score=top, margin=margin, is_confident=clears_thresholds(top, margin))


def assess(chunks: Sequence[Scored]) -> Confidence:
    """Assess confidence from retrieved chunks.

    A thin projection onto :func:`assess_scores`, kept separate so callers holding chunks do not
    have to build a score list — and so the sorting rule has exactly one implementation.

    Args:
        chunks: The retrieved evidence, in any order.

    Returns:
        The two figures and the verdict.
    """
    return assess_scores(chunk.score for chunk in chunks)
