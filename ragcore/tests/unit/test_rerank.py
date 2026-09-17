"""Cost-gated rerank: **the gate is what is tested**, not the reranking.

A reranker that reordered candidates correctly and ran on every one of them would pass a test that
only checked the ordering. What matters here is that it runs on **few** candidates and only on
**plausible** ones — and that when nothing is plausible it is not called at all, because the cost is
a model call per candidate on the user's latency path, metered against the organisation.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ragcore.domain.tenancy import TenantContext
from ragcore.retrieval.rerank import (
    MINIMUM_RERANK_SCORE,
    RERANK_TOP_K,
    RerankContractError,
    rerank,
)
from ragcore.retrieval.search import SearchChunk
from tests.support.fakes import admitted_tenant


class _Reranker:
    """A cross-encoder that reverses the retrieval ordering, and records what it was given."""

    def __init__(self, *, scores: Sequence[float] | None = None) -> None:
        self.calls: list[tuple[TenantContext, str, Sequence[str]]] = []
        self._scores = scores

    async def score(
        self, tenant: TenantContext, query: str, passages: Sequence[str]
    ) -> Sequence[float]:
        self.calls.append((tenant, query, list(passages)))
        if self._scores is not None:
            return self._scores
        # Reversed, so a rerank that ran is visible in the output ordering rather than inferred
        # from a call count.
        return [float(index) for index in range(len(passages))]


def chunk(reference: str, score: float) -> SearchChunk:
    return SearchChunk(content=f"body of {reference}", score=score, source_reference=reference)


class TestTheCostGate:
    """Two gates, answering two different questions."""

    async def test_nothing_plausible_means_the_reranker_is_never_called(self) -> None:
        """The gate working, not a degraded path.

        Reranking a field of uniformly poor matches produces a confidently-ordered list of things
        that do not answer the question — worse than an unordered one, because the ordering looks
        like a judgement.
        """
        reranker = _Reranker()
        candidates = [chunk("a", MINIMUM_RERANK_SCORE - 0.01), chunk("b", 0.01)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert reranker.calls == []
        assert outcome.considered == 0
        assert [item.source_reference for item in outcome.chunks] == ["a", "b"]
        assert not any(item.was_reranked for item in outcome.chunks)

    async def test_at_most_the_top_k_are_reranked(self) -> None:
        """Cost scales linearly with the number of candidates; accuracy does not."""
        reranker = _Reranker()
        candidates = [chunk(f"c{index}", 0.9 - index / 100) for index in range(20)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert outcome.considered == RERANK_TOP_K
        assert len(reranker.calls[0][2]) == RERANK_TOP_K

    async def test_the_top_k_is_taken_by_retrieval_score_not_by_arrival_order(self) -> None:
        """ "The top k" means the top k of the ranking that already exists."""
        reranker = _Reranker()
        candidates = [chunk("weak", 0.30), chunk("strong", 0.95)]

        await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert reranker.calls[0][2][0] == "body of strong"

    async def test_a_candidate_below_the_floor_is_excluded_even_inside_the_top_k(self) -> None:
        """The two gates are independent: being in the top five is not being worth the call."""
        reranker = _Reranker()
        candidates = [chunk("good", 0.9), chunk("hopeless", 0.01)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert outcome.considered == 1
        assert reranker.calls[0][2] == ["body of good"]


class TestWhatRerankingChanges:
    """It changes rank. It changes nothing else."""

    async def test_reranked_candidates_carry_their_new_score_and_say_so(self) -> None:
        """A retrieval score presented as a rerank score would claim a judgement nobody made."""
        reranker = _Reranker(scores=[0.1, 0.9])
        candidates = [chunk("first", 0.9), chunk("second", 0.8)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert [item.source_reference for item in outcome.chunks] == ["second", "first"]
        assert all(item.was_reranked for item in outcome.chunks)
        assert outcome.chunks[0].score == pytest.approx(0.9)

    async def test_the_un_reranked_tail_keeps_its_own_score_and_stays_below(self) -> None:
        """Two scales are not merged.

        A cross-encoder score and a fused retrieval score are different units; interleaving them by
        value is the mistake hybrid fusion normalises away in its own leg combination.
        """
        reranker = _Reranker(scores=[0.01] * RERANK_TOP_K)
        candidates = [chunk(f"c{index}", 0.9 - index / 100) for index in range(RERANK_TOP_K + 2)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        reranked = [item for item in outcome.chunks if item.was_reranked]
        tail = [item for item in outcome.chunks if not item.was_reranked]
        assert len(reranked) == RERANK_TOP_K
        assert outcome.chunks[: len(reranked)] == reranked
        assert tail and all(item.score > outcome.chunks[0].score for item in tail)

    async def test_no_content_is_altered(self) -> None:
        """Reranking reorders evidence. It cannot edit it."""
        reranker = _Reranker()
        candidates = [chunk("a", 0.9), chunk("b", 0.8)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert {item.content for item in outcome.chunks} == {"body of a", "body of b"}

    async def test_no_candidate_is_added(self) -> None:
        reranker = _Reranker()
        candidates = [chunk("a", 0.9), chunk("b", 0.8)]

        outcome = await rerank(reranker, admitted_tenant(), "vpn", candidates)

        assert len(outcome.chunks) == len(candidates)


class TestTheBoundaryContract:
    """A length mismatch is the worst failure available to this module."""

    async def test_a_short_score_list_is_refused_rather_than_zipped(self) -> None:
        """Truncating mis-pairs every score after the mismatch, and leaves no trace in the output.

        The result is a confidently wrong ordering, which is why this raises rather than trimming.
        """
        reranker = _Reranker(scores=[0.5])
        candidates = [chunk("a", 0.9), chunk("b", 0.8)]

        with pytest.raises(RerankContractError):
            await rerank(reranker, admitted_tenant(), "vpn", candidates)


class TestTenantScope:
    """Every model-touching call names the organisation it is metered against."""

    async def test_the_reranker_is_called_with_the_organisation(self) -> None:
        tenant = admitted_tenant()
        reranker = _Reranker()

        await rerank(reranker, tenant, "vpn", [chunk("a", 0.9)])

        assert reranker.calls[0][0] == tenant
