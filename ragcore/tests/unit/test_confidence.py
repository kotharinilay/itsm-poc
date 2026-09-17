"""Confidence and margin, **including the exact boundary, asserted in both directions**.

The plan singles this out (§Stage 12): "Both comparisons are ``>=``: a value exactly equal to its
threshold passes. The threshold is the lowest acceptable value, not the first unacceptable one.
This is stated because the choice is invisible in review — two implementers will split on it, both
will believe they chose the obvious reading, and the resulting behaviour differs only on the exact
boundary, which is precisely where a confidence gate is most often wrong."

So the boundary is asserted **directly rather than inferred**: a score exactly equal to the
absolute threshold passes, one epsilon below it fails, and the same pair for the margin.

The second thing asserted here is the property the margin exists for: a near-tie and a confident
singleton **at the same top score** route differently. A test that only exercised the absolute
threshold would pass against an implementation with no margin at all.
"""

from __future__ import annotations

import math

import pytest

from ragcore.governance.conditions import ConditionOutcome, KnowledgeCondition
from ragcore.retrieval.confidence import (
    MINIMUM_MARGIN,
    MINIMUM_TOP_SCORE,
    assess,
    assess_scores,
    clears_thresholds,
)

EPSILON = 1e-9
"""A step below a threshold, small enough that passing can only mean ``>`` rather than ``>=``."""


class _Chunk:
    """Anything with a score satisfies the protocol; this is the smallest such thing."""

    def __init__(self, score: float) -> None:
        self.score = score


class TestTheComparisonItself:
    """The boundary, asserted where equality is actually reachable.

    **A margin exactly equal to the threshold cannot be produced from two scores.** The difference
    of two doubles near 0.85 is a multiple of that binade's ulp — about 1.1e-16 — and the stored
    value of 0.08 is not such a multiple, so no pair of realistic scores subtracts to exactly
    ``MINIMUM_MARGIN``. A test that fed in scores and hoped for equality would be asserting ``>``
    or ``<`` depending on the values somebody happened to choose, which is the accident the plan
    singles this case out to prevent.

    :func:`~ragcore.retrieval.confidence.clears_thresholds` takes the two figures directly, so the
    thresholds themselves can be passed in and the answer is unambiguous.
    """

    def test_both_figures_exactly_equal_to_their_thresholds_pass(self) -> None:
        """`>=`, both of them. The threshold is the lowest acceptable value."""
        assert clears_thresholds(MINIMUM_TOP_SCORE, MINIMUM_MARGIN)

    def test_a_top_score_one_step_below_its_threshold_fails(self) -> None:
        assert not clears_thresholds(math.nextafter(MINIMUM_TOP_SCORE, 0.0), MINIMUM_MARGIN)

    def test_a_margin_one_step_below_its_threshold_fails(self) -> None:
        assert not clears_thresholds(MINIMUM_TOP_SCORE, math.nextafter(MINIMUM_MARGIN, 0.0))

    def test_neither_threshold_can_compensate_for_the_other(self) -> None:
        """A very high top score does not buy a thin margin, and the reverse."""
        assert not clears_thresholds(0.99, math.nextafter(MINIMUM_MARGIN, 0.0))
        assert not clears_thresholds(math.nextafter(MINIMUM_TOP_SCORE, 0.0), 0.99)


class TestTheAbsoluteThreshold:
    """``top_score >= MINIMUM_TOP_SCORE``, end to end from a field of scores."""

    def test_a_score_exactly_equal_to_the_threshold_passes(self) -> None:
        """The threshold is the lowest **acceptable** value.

        Asserted with a margin comfortably clear of its own threshold, so that a failure here can
        only be about the absolute comparison.
        """
        confidence = assess_scores([MINIMUM_TOP_SCORE, MINIMUM_TOP_SCORE - 0.3])

        assert confidence.top_score == MINIMUM_TOP_SCORE
        assert confidence.is_confident

    def test_a_score_one_step_below_the_threshold_fails(self) -> None:
        """The other direction. Without this, ``> 0`` would also pass the test above."""
        confidence = assess_scores([MINIMUM_TOP_SCORE - EPSILON, 0.0])

        assert not confidence.is_confident


class TestTheMarginThreshold:
    """``margin >= MINIMUM_MARGIN``, end to end from a field of scores.

    The exact boundary lives in :class:`TestTheComparisonItself`, for the floating-point reason
    given there. What these assert is that :func:`~ragcore.retrieval.confidence.assess_scores`
    routes a just-clearing field and a just-failing field to different answers.
    """

    def test_a_margin_just_clear_of_the_threshold_passes(self) -> None:
        top = MINIMUM_TOP_SCORE + 0.4
        confidence = assess_scores([top, top - MINIMUM_MARGIN - 0.001])

        assert confidence.margin > MINIMUM_MARGIN
        assert confidence.is_confident

    def test_a_margin_just_inside_the_threshold_fails(self) -> None:
        top = MINIMUM_TOP_SCORE + 0.4
        confidence = assess_scores([top, top - MINIMUM_MARGIN + 0.001])

        assert confidence.margin < MINIMUM_MARGIN
        assert not confidence.is_confident


class TestANearTieAndAConfidentSingletonRouteDifferently:
    """The whole reason the margin exists (plan §Stage 12 validation gates).

    Two candidates at the same top score: one with a runner-up almost level with it, one alone.
    A threshold on the absolute score cannot tell them apart, and the first is a coin toss the
    score does not disclose.
    """

    def test_a_near_tie_is_not_confident(self) -> None:
        confidence = assess_scores([0.71, 0.70])

        assert confidence.top_score == pytest.approx(0.71)
        assert not confidence.is_confident

    def test_a_confident_singleton_at_the_same_top_score_is_confident(self) -> None:
        confidence = assess_scores([0.71, 0.31])

        assert confidence.top_score == pytest.approx(0.71)
        assert confidence.is_confident

    def test_a_lone_candidate_uses_its_own_score_as_its_margin(self) -> None:
        """One match, nothing else close. The absolute test and the margin test then agree."""
        confidence = assess_scores([0.71])

        assert confidence.margin == pytest.approx(0.71)
        assert confidence.is_confident


class TestOrderingIsNotTrusted:
    """Scores arrive in whatever order a provider returned them."""

    def test_an_unsorted_field_produces_the_same_answer_as_a_sorted_one(self) -> None:
        """A provider that changed its ordering must not change the margin.

        Without the sort, the margin becomes the gap between two arbitrary candidates — which reads
        as a tuning problem rather than as the defect it is.
        """
        assert assess_scores([0.31, 0.71, 0.10]) == assess_scores([0.71, 0.31, 0.10])


class TestEmptyEvidence:
    """An absence of evidence is not a weak positive."""

    def test_no_candidates_is_not_confident(self) -> None:
        confidence = assess_scores([])

        assert confidence.top_score == 0.0
        assert confidence.margin == 0.0
        assert not confidence.is_confident

    def test_the_knowledge_condition_agrees(self) -> None:
        """Empty evidence withholds at the gate, not merely in the retrieval report."""
        condition = KnowledgeCondition.assess([])

        assert condition.outcome is ConditionOutcome.NOT_MET
        assert condition.withholds


class TestTheThresholdsLiveInExactlyOneModule:
    """Plan §Stage 12: the constants and their comparison direction live in one module."""

    def test_the_governance_condition_reads_the_retrieval_constants(self) -> None:
        """Identity, not equality of value.

        Two modules holding ``0.45`` would satisfy an equality assertion and would still be two
        places to change. ``is`` against the same object is what says one of them imported the
        other.
        """
        from ragcore.governance import conditions

        assert conditions.MINIMUM_TOP_SCORE is MINIMUM_TOP_SCORE
        assert conditions.MINIMUM_MARGIN is MINIMUM_MARGIN

    def test_no_other_module_defines_a_threshold_of_its_own(self) -> None:
        """A grep, deliberately: the rule is about where a literal may appear."""
        import ast
        from pathlib import Path

        src = Path(__file__).resolve().parents[2] / "src" / "ragcore"
        definers = {
            str(path.relative_to(src)).replace("\\", "/")
            for path in sorted(src.rglob("*.py"))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.AnnAssign | ast.Assign)
            for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
            if isinstance(target, ast.Name) and target.id in {"MINIMUM_TOP_SCORE", "MINIMUM_MARGIN"}
        }

        assert definers == {"retrieval/confidence.py"}, (
            "a confidence threshold is defined outside retrieval/confidence.py. Two thresholds "
            f"agree until somebody tunes one: {sorted(definers)}"
        )


class TestTheConditionProjectsTheSameAnswer:
    """``KnowledgeCondition`` adds meaning, not arithmetic."""

    def test_a_confident_field_is_met_and_withholds_nothing(self) -> None:
        condition = KnowledgeCondition.assess([_Chunk(0.71), _Chunk(0.31)])

        assert condition.outcome is ConditionOutcome.MET
        assert not condition.withholds
        assert condition.top_score == pytest.approx(assess([_Chunk(0.71), _Chunk(0.31)]).top_score)

    def test_an_unconfident_field_withholds(self) -> None:
        condition = KnowledgeCondition.assess([_Chunk(0.71), _Chunk(0.70)])

        assert condition.outcome is ConditionOutcome.NOT_MET
        assert condition.withholds

    def test_knowledge_has_no_way_to_authorize(self) -> None:
        """`FR-AGENT-005`: the knowledge condition may withhold but MUST NEVER authorize."""
        condition = KnowledgeCondition.assess([_Chunk(0.99)])

        assert not hasattr(condition, "authorizes")
        assert not hasattr(condition, "permits")
