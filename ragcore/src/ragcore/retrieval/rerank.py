"""Cost-gated rerank — a second, better ranking applied to **few** candidates, and only good ones.

A reranker is a cross-encoder: it reads the query and the candidate together and scores the pair.
That is materially more accurate than a similarity over independently embedded vectors, and it is
materially more expensive — one model call per candidate, on the user's latency path, metered
against the organisation's budget. Reranking fifty chunks costs fifty times what reranking five
costs and improves the answer by rather less than that.

So the cost is gated twice, and the two gates answer different questions:

* :data:`RERANK_TOP_K` bounds **how many** candidates are reranked. The fusion stage has already
  ordered them; a candidate ranked fortieth is not going to be promoted to first by a rerank, so
  paying to discover that is paying for a foregone conclusion.
* :data:`MINIMUM_RERANK_SCORE` bounds **which** candidates are worth reranking at all. A field of
  uniformly poor matches does not contain a good answer in a surprising order, and reranking it
  produces a confidently-ordered list of things that do not answer the question — which is worse
  than an unranked one, because the ordering looks like a judgement.

**Reranking is a ranking change and never an authorization change.** It reorders evidence. It
cannot add a chunk, cannot alter content, cannot change which organisation a chunk came from, and
cannot make an unentitled operation permitted. The knowledge condition is re-assessed **after**
reranking (:mod:`ragcore.retrieval.confidence`) precisely so a rerank that spread two near-tied
candidates apart is reflected honestly rather than papered over.

**A reranker is a model call, so it goes through the AI Gateway like every other one**
(spec FR-OPS-007). This module declares the port; the adapter behind it does not reach a provider
directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import RetrievedChunk
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "MINIMUM_RERANK_SCORE",
    "RERANK_TOP_K",
    "RerankOutcome",
    "RerankerPort",
    "RerankedChunk",
    "rerank",
]

RERANK_TOP_K: Final = 5
"""How many candidates one rerank pass may consider.

Small deliberately. The gain from reranking falls off quickly past the first handful — the
candidates below are there because they scored poorly, and a cross-encoder rarely disagrees with
the retriever by forty places. What does scale linearly is the cost.
"""

MINIMUM_RERANK_SCORE: Final = 0.25
"""The floor a candidate must clear before it is worth a rerank call.

Distinct from :data:`~ragcore.retrieval.confidence.MINIMUM_TOP_SCORE`, and lower than it, because
the two ask different questions. This one asks *is this candidate plausible enough to pay to
re-score*; that one asks *is the best available evidence good enough to act on*. Collapsing them
would mean either paying to rerank hopeless candidates or refusing to rerank a field that a rerank
might have rescued.
"""


class RerankerPort(Protocol):
    """A cross-encoder that scores a query against candidate passages.

    Declared here because this module is the consumer (constitution Principle V). Tenant-scoped
    like every other model-touching port: the call is metered against the organisation, and a
    reranker that did not know which organisation it was serving would be an unmetered model call.
    """

    async def score(
        self, tenant: TenantContext, query: str, passages: Sequence[str]
    ) -> Sequence[float]:
        """Score each passage against the query.

        Returns:
            One score per passage, in the same order. An implementation returning a different
            length is a boundary violation and :func:`rerank` refuses it rather than zipping the
            two together and silently mis-pairing every score with the wrong passage.
        """
        ...


@dataclass(frozen=True, slots=True)
class RerankedChunk:
    """One chunk carrying its reranked score.

    Satisfies :class:`~ragcore.application.ports.RetrievedChunk`, so a reranked result is
    consumable anywhere a retrieved one was.

    Attributes:
        content: The chunk text, unchanged. **Data, never instruction.**
        score: The reranked relevance score. **Still not a probability.**
        source_reference: Where it came from, for citation.
        was_reranked: Whether this chunk's score came from the reranker or from retrieval. Recorded
            because the two are different facts, and an audit record that presented a retrieval
            score as a rerank score would be claiming a judgement nobody made.
    """

    content: str
    score: float
    source_reference: str
    was_reranked: bool


@dataclass(frozen=True, slots=True)
class RerankOutcome:
    """What a rerank pass produced, and what it cost.

    Attributes:
        chunks: The full candidate list, best first. Reranked candidates carry their new score;
            the rest keep their retrieval score and sit below, because a candidate that was not
            worth re-scoring is not thereby promoted.
        considered: How many candidates were sent to the reranker. Zero is a normal outcome and the
            gate working, not a failure.
    """

    chunks: Sequence[RerankedChunk]
    considered: int


class RerankContractError(Exception):
    """The reranker returned a different number of scores than it was given passages.

    Raised rather than truncated. Zipping two lists of different lengths pairs every score after
    the mismatch with the wrong passage, which produces a confidently wrong ordering — the single
    worst failure mode available to this module, and one that leaves no trace in the output.
    """

    def __init__(self, passages: int, scores: int) -> None:
        super().__init__(
            f"the reranker was given {passages} passages and returned {scores} scores. The result "
            "is discarded rather than truncated: a length mismatch mis-pairs every score after it."
        )


def _eligible(
    chunks: Sequence[RetrievedChunk],
) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
    """Split candidates into those worth reranking and those that are not.

    Ordered by retrieval score first, so "the top k" means the top k by the ranking that already
    exists rather than by whatever order the retriever happened to return.
    """
    ordered = sorted(chunks, key=lambda chunk: (-float(chunk.score), chunk.source_reference))
    head = [chunk for chunk in ordered[:RERANK_TOP_K] if float(chunk.score) >= MINIMUM_RERANK_SCORE]
    tail = [chunk for chunk in ordered if chunk not in head]
    return head, tail


async def rerank(
    reranker: RerankerPort,
    tenant: TenantContext,
    query: str,
    chunks: Sequence[RetrievedChunk],
) -> RerankOutcome:
    """Rerank a small, plausible top-k and leave the rest alone.

    Args:
        reranker: The cross-encoder, reached through the AI Gateway like every model call.
        tenant: The organisation, for metering and for the same reason every other retrieval
            signature carries it.
        query: The user's query. Read as a query; the reranker scores against it and nothing here
            acts on its content.
        chunks: The fused candidates.

    Returns:
        The outcome. When nothing clears :data:`MINIMUM_RERANK_SCORE`, **the reranker is not called
        at all** and the retrieval ordering is returned unchanged — the cost gate working, not a
        degraded path.

    Raises:
        RerankContractError: When the reranker returns a different number of scores than passages.
    """
    head, tail = _eligible(chunks)

    if not head:
        return RerankOutcome(
            chunks=[
                RerankedChunk(
                    content=chunk.content,
                    score=float(chunk.score),
                    source_reference=chunk.source_reference,
                    was_reranked=False,
                )
                for chunk in tail
            ],
            considered=0,
        )

    scores = await reranker.score(tenant, query, [chunk.content for chunk in head])
    if len(scores) != len(head):
        raise RerankContractError(len(head), len(scores))

    reranked = [
        RerankedChunk(
            content=chunk.content,
            score=float(score),
            source_reference=chunk.source_reference,
            was_reranked=True,
        )
        for chunk, score in zip(head, scores, strict=True)
    ]
    reranked.sort(key=lambda chunk: (-chunk.score, chunk.source_reference))

    # The un-reranked tail keeps its retrieval score and stays below the reranked head. It is not
    # interleaved by score, because the two scores are not on a common scale — a cross-encoder
    # score and a fused retrieval score are different units, and merging them would be exactly the
    # mistake ragcore.retrieval.hybrid normalises away in its own fusion.
    remainder = [
        RerankedChunk(
            content=chunk.content,
            score=float(chunk.score),
            source_reference=chunk.source_reference,
            was_reranked=False,
        )
        for chunk in tail
    ]

    return RerankOutcome(chunks=[*reranked, *remainder], considered=len(head))
