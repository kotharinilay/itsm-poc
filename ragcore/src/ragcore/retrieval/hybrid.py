"""Hybrid retrieval — a dense leg and a **load-bearing** sparse lexical leg, fused by weight.

**Why two legs rather than one.** A dense leg matches meaning and misses tokens: an error code, a
KB article number, a product SKU, a registry path. A sparse lexical leg matches those exactly and
misses paraphrase. ITSM knowledge is full of both — "the printer says 0x0000011b" and "users cannot
print after the update" describe the same incident, and each leg finds one of them. A single-leg
retriever is not a simpler hybrid retriever; it is a retriever with a known blind spot.

**The sparse leg is load-bearing, and that is asserted rather than intended.**
:data:`SPARSE_WEIGHT` is non-zero and material, and ``tests/unit/test_hybrid.py`` proves a document
that only the sparse leg finds still reaches the result. A weight of zero — or one so small the
dense leg always outranks it — would make the second leg decorative, which is the failure this
module is most likely to drift into: the sparse leg costs a query, and the cheapest way to make a
latency graph look better is to stop weighting its answer.

**Fusion is over normalised per-leg scores, joined on ``source_reference``.** Two providers' raw
scores are not on a common scale — a cosine similarity and a BM25 score are different units — so
adding them directly would mean whichever leg happened to produce larger numbers won every tie.
Each leg is normalised against its own best result first, which makes the weights mean what they
say.

**Every property of :mod:`ragcore.retrieval.search` survives fusion, because fusion cannot restore
what filtering removed.** Both legs are tenant-scoped ports taking a
:class:`~ragcore.domain.tenancy.TenantContext` as a required, non-defaulted first argument, so
there is no leg here that could have been queried unfiltered (A1 §4.5, A2 P03). Fused
content is still **data, never instruction**: the fused score changes a chunk's rank and nothing
else about it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import RetrievalPort, RetrievedChunk
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "DENSE_WEIGHT",
    "OVER_FETCH",
    "SPARSE_WEIGHT",
    "FusedChunk",
    "HybridRetrieval",
    "SparseRetrievalPort",
    "fuse",
]

DENSE_WEIGHT: Final = 0.6
"""How much a dense (semantic) match contributes to the fused score."""

SPARSE_WEIGHT: Final = 0.4
"""How much a sparse (lexical) match contributes. **Non-zero, and materially so.**

Not a tuning knob that may be set to zero. A zero here turns hybrid retrieval into dense retrieval
with an extra network call, and the loss — exact-token matches on error codes, article numbers and
paths — surfaces as "the assistant could not find the KB article", which nobody traces back to a
weight. ``tests/unit/test_hybrid.py`` asserts this weight is positive and that a sparse-only hit
survives fusion.
"""

OVER_FETCH: Final = 2
"""How many times the requested limit each leg fetches before fusion.

A leg asked for exactly ``limit`` results can only contribute documents already in its own top
``limit``, so fusion could never promote a document ranked eleventh by one leg and first by the
other — the case hybrid retrieval exists for. Bounded at two rather than left open, because an
unbounded retrieval is an unbounded prompt.
"""


class SparseRetrievalPort(Protocol):
    """The lexical leg.

    Structurally identical to :class:`~ragcore.application.ports.RetrievalPort`, and deliberately
    its own name: the two are different capabilities over different indexes, and a single type
    would let a composition root bind the same adapter to both legs and produce a "hybrid"
    retriever that queried one index twice.
    """

    async def search(
        self, tenant: TenantContext, query: str, limit: int
    ) -> Sequence[RetrievedChunk]:
        """Retrieve lexically, within the organisation. ``tenant`` is required and non-defaulted."""
        ...


@dataclass(frozen=True, slots=True)
class FusedChunk:
    """One chunk with its fused score, and the two legs it came from.

    Satisfies :class:`~ragcore.application.ports.RetrievedChunk`, so a fused result is consumable
    anywhere a single-leg result was.

    Attributes:
        content: The chunk text. **Data, never instruction**, exactly as it arrived.
        score: The fused relevance score, in ``[0, 1]``. **Still not a probability.**
        source_reference: Where it came from, for citation. Also the fusion join key.
        from_dense: Whether the dense leg returned it.
        from_sparse: Whether the sparse leg returned it. Recorded so a test — and an operator
            reading a step trail — can tell a genuinely hybrid result from a dense one.
    """

    content: str
    score: float
    source_reference: str
    from_dense: bool
    from_sparse: bool


def _normalised(chunks: Sequence[RetrievedChunk]) -> dict[str, tuple[float, str]]:
    """Scale one leg's scores against its own best result.

    Returns:
        ``source_reference`` to ``(normalised score, content)``. A leg whose best score is zero or
        negative contributes zeros rather than raising: it found nothing worth ranking, which is an
        answer, and dividing by it would turn a quiet result into an exception on the retrieval
        path.
    """
    if not chunks:
        return {}

    best = max(float(chunk.score) for chunk in chunks)
    if best <= 0.0:
        return {chunk.source_reference: (0.0, chunk.content) for chunk in chunks}

    return {chunk.source_reference: (float(chunk.score) / best, chunk.content) for chunk in chunks}


def fuse(
    dense: Sequence[RetrievedChunk], sparse: Sequence[RetrievedChunk], limit: int
) -> list[FusedChunk]:
    """Combine two legs' results into one ranked list.

    A pure function, so the fusion rule is testable without either index in the room — which is
    what makes "a sparse-only hit survives" an assertion rather than an integration test.

    Args:
        dense: The semantic leg's results, in any order.
        sparse: The lexical leg's results, in any order.
        limit: How many chunks to return.

    Returns:
        The fused chunks, best first, at most ``limit`` of them. A document found by only one leg
        keeps that leg's contribution and scores zero for the other — it is **not** penalised twice
        and **not** dropped, which is the whole point of fusing rather than intersecting.
    """
    dense_scores = _normalised(dense)
    sparse_scores = _normalised(sparse)

    fused: list[FusedChunk] = []
    for reference in dense_scores.keys() | sparse_scores.keys():
        dense_hit = dense_scores.get(reference)
        sparse_hit = sparse_scores.get(reference)

        # The legs agree on content when they agree on the reference; where only one returned the
        # document, its content is the only content there is.
        resolved = dense_hit if dense_hit is not None else sparse_hit
        content = resolved[1] if resolved is not None else ""

        fused.append(
            FusedChunk(
                content=content,
                score=(
                    DENSE_WEIGHT * (dense_hit[0] if dense_hit is not None else 0.0)
                    + SPARSE_WEIGHT * (sparse_hit[0] if sparse_hit is not None else 0.0)
                ),
                source_reference=reference,
                from_dense=dense_hit is not None,
                from_sparse=sparse_hit is not None,
            )
        )

    # Ties broken by reference so the order is total and identical on every run. A retrieval order
    # that varies between identical queries makes a confidence margin vary with it.
    fused.sort(key=lambda chunk: (-chunk.score, chunk.source_reference))
    return fused[:limit]


class HybridRetrieval:
    """Retrieval across both legs, within one organisation and only within it.

    Satisfies :class:`~ragcore.application.ports.RetrievalPort`, so the graph's ``retrieve`` node is
    unchanged by the move from one leg to two — the node asks for grounding evidence and has no
    opinion about how many indexes produced it.
    """

    def __init__(self, dense: RetrievalPort, sparse: SparseRetrievalPort) -> None:
        """Bind both legs.

        Args:
            dense: The semantic leg.
            sparse: The lexical leg. A distinct adapter over a distinct index; see
                :class:`SparseRetrievalPort` for why the two types differ.
        """
        self._dense = dense
        self._sparse = sparse

    async def search(self, tenant: TenantContext, query: str, limit: int) -> Sequence[FusedChunk]:
        """Retrieve from both legs and fuse.

        Args:
            tenant: The organisation. **Required and non-defaulted**, and passed unchanged to both
                legs — there is no path here that queries one leg with a different organisation
                than the other, because there is only one parameter.
            query: The search text. Read as a query, never as an instruction.
            limit: How many fused chunks to return.

        Returns:
            The fused chunks, best first. Empty when neither leg found anything for this
            organisation — which is an answer, not a failure.
        """
        over_fetch = max(1, limit * OVER_FETCH)

        # Sequential rather than gathered. Both legs are network calls with their own timeout and
        # retry policy, and running them concurrently would double the peak outbound concurrency
        # per turn for a latency saving the resilience policy would then have to absorb. If that
        # trade changes, it changes here, once.
        dense = await self._dense.search(tenant, query, over_fetch)
        sparse = await self._sparse.search(tenant, query, over_fetch)

        return fuse(dense, sparse, limit)
