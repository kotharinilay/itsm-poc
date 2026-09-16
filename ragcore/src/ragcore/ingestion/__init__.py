"""Ingestion — the twelfth bounded context.

Acquisition, normalisation, chunking, embedding, indexing.

**The index it builds is derived, never authoritative** (constitution Principle IV). Azure AI
Search holds a representation of knowledge that exists elsewhere; a lost index is rebuilt by
re-running ingestion rather than restored from backup, and nothing reads business truth from it.

**Runs are idempotent.** Re-running from a watermark MUST NOT duplicate documents (research
R-021), which is what makes "rebuild by re-running" a safe recovery rather than a hopeful one.

**Nothing produced here can grant authority.** What ingestion puts in the index is what retrieval
later returns as grounding evidence, and retrieved content is data, never instruction
(spec FR-IDENT-004). A poisoned document can at most produce a bad proposal, which meets the same
deterministic gate as every other proposal.

**No behaviour exists at this stage** (T077). The five stages below are declared as a pipeline
shape and a port; nothing acquires, normalises, chunks, embeds or indexes. The worker entry point
in ``workers/ingestion_run.py`` opens a run row and records its terminal state, and does no work
in between.
"""

from __future__ import annotations

from enum import Enum


class IngestionStage(Enum):
    """The five stages of a run, in order.

    Named as a closed enumeration rather than left implicit in a function's control flow, so a
    run row can record which stage it reached — and so a partial run reports *where* it stopped
    rather than only that it failed.
    """

    ACQUISITION = "acquisition"
    """Fetch from the source. The only stage that reaches outside the platform."""

    NORMALISATION = "normalisation"
    """Reduce heterogeneous source formats to one internal representation."""

    CHUNKING = "chunking"
    """Split into retrievable units. A tuning concern, never a security boundary."""

    EMBEDDING = "embedding"
    """Vectorise. Routed through the AI Gateway like every other model call."""

    INDEXING = "indexing"
    """Write to the derived index, tenant-stamped. Cross-tenant corpora do not exist."""


class IngestionRunState(Enum):
    """Where one run finished. Mirrors ``ingestion_run.state`` in data-model.md."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
