"""Ingestion run state — the twelfth bounded context's only durable vocabulary.

Acquisition, chunking and embedding are **not** here and are not implemented in the scaffold
(research R-021, tasks T100). What is here is the state a run is in, because the run row is
platform state and platform state is PostgreSQL's.

Like everything under ``domain/``, this module imports nothing outside the standard library.
"""

from __future__ import annotations

from enum import Enum


class IngestionRunState(Enum):
    """The lifecycle of one incremental acquisition pass.

    There is no ``partial``. A run either advanced its watermark and completed, or it did not and
    failed — and because runs are idempotent, a failed run is re-run from the last watermark
    rather than resumed from the middle of one. A ``partial`` state would describe a position
    nothing can restart from.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Whether the run has finished, either way. Terminal runs never advance again."""
        return self in {IngestionRunState.COMPLETED, IngestionRunState.FAILED}
