"""Hybrid retrieval: **the sparse leg is load-bearing**, and fusion cannot widen the tenant scope.

The property worth testing here is not "two legs are queried" — that is visible in the source. It
is that the second leg's answer **changes the result**. A weight of zero, or one so small the dense
leg always outranks it, would make the sparse leg decorative while every structural test still
passed: both legs would be called, both would return, and the fused list would be the dense one.

So the tests below plant a document only the sparse leg can find and assert it survives.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ragcore.domain.tenancy import TenantContext
from ragcore.retrieval.hybrid import (
    DENSE_WEIGHT,
    OVER_FETCH,
    SPARSE_WEIGHT,
    HybridRetrieval,
    fuse,
)
from ragcore.retrieval.search import SearchChunk
from tests.support.fakes import admitted_tenant


class _Leg:
    """One retrieval leg that returns what it was seeded with, per organisation."""

    def __init__(self, *chunks: SearchChunk) -> None:
        self._chunks = list(chunks)
        self.calls: list[tuple[TenantContext, str, int]] = []

    async def search(self, tenant: TenantContext, query: str, limit: int) -> Sequence[SearchChunk]:
        self.calls.append((tenant, query, limit))
        return self._chunks[:limit]


def chunk(reference: str, score: float) -> SearchChunk:
    return SearchChunk(content=f"body of {reference}", score=score, source_reference=reference)


class TestTheSparseLegIsLoadBearing:
    """The failure this module is most likely to drift into, asserted directly."""

    def test_the_sparse_weight_is_positive(self) -> None:
        """A zero here turns hybrid retrieval into dense retrieval with an extra network call."""
        assert SPARSE_WEIGHT > 0.0

    def test_the_weights_cover_the_whole_score(self) -> None:
        """Together they normalise to one, so a fused score stays comparable across queries."""
        assert pytest.approx(1.0) == DENSE_WEIGHT + SPARSE_WEIGHT

    def test_a_document_only_the_sparse_leg_found_survives_fusion(self) -> None:
        """The exact-token case: an error code, a KB number, a registry path.

        The dense leg misses it entirely. If the sparse contribution did not count, it would not
        appear in the result at all.
        """
        fused = fuse([chunk("dense-hit", 0.9)], [chunk("kb-0x0000011b", 0.9)], limit=5)

        references = [item.source_reference for item in fused]
        assert "kb-0x0000011b" in references

    def test_a_sparse_only_document_can_outrank_a_weak_dense_one(self) -> None:
        """Load-bearing means it can change the ordering, not merely appear in the tail.

        Both legs are normalised against their own best result, so a leg's top hit scores 1.0
        within that leg. The sparse-only document therefore contributes ``SPARSE_WEIGHT`` and the
        weak dense one contributes ``DENSE_WEIGHT`` times its normalised score.
        """
        fused = fuse(
            [chunk("strong-dense", 1.0), chunk("weak-dense", 0.2)],
            [chunk("sparse-only", 1.0)],
            limit=5,
        )

        order = [item.source_reference for item in fused]
        assert order.index("sparse-only") < order.index("weak-dense")

    def test_a_document_both_legs_found_outranks_either_alone(self) -> None:
        """Agreement is the signal hybrid retrieval exists to reward."""
        fused = fuse(
            [chunk("agreed", 1.0), chunk("dense-only", 1.0)],
            [chunk("agreed", 1.0), chunk("sparse-only", 1.0)],
            limit=5,
        )

        assert fused[0].source_reference == "agreed"
        assert fused[0].from_dense
        assert fused[0].from_sparse


class TestFusion:
    """Properties of the pure function, provable without either index in the room."""

    def test_a_one_legged_document_is_not_penalised_twice(self) -> None:
        """Scored zero for the leg that missed it, and **not dropped**.

        Fusing rather than intersecting is the whole design: an intersection would return only
        what both legs agreed on, which is the smallest and least useful answer available.
        """
        fused = fuse([chunk("only-dense", 1.0)], [], limit=5)

        assert len(fused) == 1
        assert fused[0].from_dense
        assert not fused[0].from_sparse
        assert fused[0].score == pytest.approx(DENSE_WEIGHT)

    def test_raw_scores_on_different_scales_do_not_let_one_leg_win_everything(self) -> None:
        """A cosine similarity and a BM25 score are different units.

        The sparse leg here reports numbers two orders of magnitude larger. Without per-leg
        normalisation it would outrank the dense leg on every document, and the weights would mean
        nothing.
        """
        fused = fuse([chunk("dense-best", 0.9)], [chunk("sparse-best", 87.0)], limit=5)

        assert fused[0].source_reference == "dense-best"

    def test_the_order_is_total_and_stable(self) -> None:
        """Ties break on the reference, so identical queries produce identical orders.

        A retrieval order that varied between identical queries would make the confidence margin
        vary with it — and the margin is what decides whether the platform acts.
        """
        first = fuse([chunk("b", 1.0), chunk("a", 1.0)], [], limit=5)
        second = fuse([chunk("a", 1.0), chunk("b", 1.0)], [], limit=5)

        assert [item.source_reference for item in first] == ["a", "b"]
        assert first == second

    def test_the_limit_is_honoured(self) -> None:
        fused = fuse([chunk(f"d{i}", 1.0 - i / 10) for i in range(10)], [], limit=3)

        assert len(fused) == 3

    def test_a_leg_that_scored_everything_zero_contributes_nothing_and_does_not_raise(self) -> None:
        """Dividing by a zero best would turn a quiet result into an exception on the hot path."""
        fused = fuse([chunk("zeroed", 0.0)], [chunk("real", 1.0)], limit=5)

        assert fused[0].source_reference == "real"


class TestTheTenantScopeSurvives:
    """Fusion cannot restore what filtering removed — and must not widen it either."""

    async def test_both_legs_are_queried_with_the_same_organisation(self) -> None:
        """One parameter, passed to both. There is no path here that queries them differently."""
        tenant = admitted_tenant()
        dense, sparse = _Leg(chunk("d", 1.0)), _Leg(chunk("s", 1.0))

        await HybridRetrieval(dense, sparse).search(tenant, "printer offline", 4)

        assert [call[0] for call in dense.calls] == [tenant]
        assert [call[0] for call in sparse.calls] == [tenant]

    async def test_each_leg_over_fetches_so_fusion_can_promote(self) -> None:
        """A leg asked for exactly ``limit`` can only contribute what it already ranked top."""
        tenant = admitted_tenant()
        dense, sparse = _Leg(), _Leg()

        await HybridRetrieval(dense, sparse).search(tenant, "vpn", 4)

        assert dense.calls[0][2] == 4 * OVER_FETCH
        assert sparse.calls[0][2] == 4 * OVER_FETCH

    async def test_no_search_signature_omits_the_organisation(self) -> None:
        """Required and non-defaulted, on the fused port as on each leg.

        A code path able to issue an unfiltered query MUST NOT exist (A1 §4.5, A2 P03),
        and a parameter with a default would be one.
        """
        import inspect

        signature = inspect.signature(HybridRetrieval.search)
        assert signature.parameters["tenant"].default is inspect.Parameter.empty
