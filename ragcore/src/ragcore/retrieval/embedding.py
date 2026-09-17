"""The embedding path — **the symptom or description field, and nothing else**.

Plan Stage 9 settles what gets embedded, and the answer is narrow on purpose: one field, the one
that describes the problem in the words somebody used. Not the whole record.

**Why one field.** An ITSM record is mostly metadata — assignment group, category, CI, priority,
state, timestamps, the requester's name, the technician's name, a resolution code. Concatenating
all of it and embedding the result produces a vector dominated by the fields that recur across
every record, so the nearest neighbours of "printer offline in Bristol" become other tickets from
the same assignment group at the same priority, which is a plausible-looking result set that
answers a different question. The symptom field is the part that varies with the problem, and the
problem is what retrieval is for.

**Why this also matters for data protection.** The derived index is a copy, and every field copied
into it is a field that has to be erased from it when erasure runs and rebuilt when the index is
lost. Embedding the description alone keeps requester names, technician names and free-text
comments out of the vector store entirely — not redacted from it, absent from it. A field that was
never copied cannot leak from the copy.

**The source text is data, never instruction.** A ticket description is written by a person and
sometimes by an attacker; it reaches a model here as text to be embedded and never as a prompt to
be followed. It also cannot reach an outbound destination: nothing in this module takes a
destination, and the embedding it returns is a list of floats.

**Every embedding call goes through the AI Gateway** (spec FR-OPS-007). This module calls
:class:`~ragcore.application.ports.ModelPort`, whose only implementation routes through the
gateway — an embedding computed by a directly-reached provider would be an unmetered model call,
and a single egress some calls skip is not a single egress.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.application.ports import ModelPort
    from ragcore.domain.tenancy import TenantContext

__all__ = [
    "EMBEDDED_FIELDS",
    "MAX_EMBEDDED_CHARACTERS",
    "EmbeddingPath",
    "NoEmbeddableFieldError",
    "embeddable_text",
]

EMBEDDED_FIELDS: Final[tuple[str, ...]] = ("symptom", "description")
"""The only fields that are ever embedded, in the order they are preferred.

A closed tuple rather than a configuration value. A list an operator can extend is a list that
grows a requester name into the vector store one incident at a time, and the growth is invisible
until somebody asks what the index contains.

``symptom`` first because a record that has both has usually put the caller's own words in
``symptom`` and a summarised restatement in ``description``.
"""

MAX_EMBEDDED_CHARACTERS: Final = 8_000
"""The ceiling on one embedded field.

Bounded because an unbounded embedding is an unbounded model call, metered against the
organisation, on a field a user controls the length of. Truncation is honest here in a way it would
not be for a prompt: a vector built from the first eight thousand characters of a description is a
slightly worse vector, not a differently-behaved one.
"""


class NoEmbeddableFieldError(ValueError):
    """The record carries neither a symptom nor a description.

    Raised rather than embedding something else. The fallback a caller would reach for — embed the
    title, embed the whole record, embed the category — is precisely the widening this module
    exists to prevent, and a record with nothing to describe it is a record with nothing to
    retrieve on.
    """

    def __init__(self, available: Sequence[str]) -> None:
        super().__init__(
            "the record carries no symptom or description field, so there is nothing to embed. "
            f"Fields present: {sorted(available)}. No other field is substituted: embedding the "
            "rest of the record produces a vector dominated by metadata that recurs across every "
            "record."
        )


def embeddable_text(record: Mapping[str, object]) -> str:
    """Extract the one field that may be embedded.

    Args:
        record: The source record, as the ingestion boundary validated it.

    Returns:
        The symptom text, or the description where no symptom is present, stripped and truncated to
        :data:`MAX_EMBEDDED_CHARACTERS`.

    Raises:
        NoEmbeddableFieldError: When neither field is present or both are blank.
    """
    for field in EMBEDDED_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_EMBEDDED_CHARACTERS]

    raise NoEmbeddableFieldError(list(record.keys()))


@dataclass(frozen=True, slots=True)
class EmbeddingPath:
    """Turns a record into a vector, through the gateway, within one organisation.

    Frozen and slotted: the model port this holds is chosen in the composition root, and an
    embedding path whose port could be swapped mid-run is one whose vectors could come from two
    different models in the same index.

    Attributes:
        model: Model access, routed exclusively through the AI Gateway.
    """

    model: ModelPort

    async def embed_record(
        self, tenant: TenantContext, record: Mapping[str, object]
    ) -> Sequence[float]:
        """Embed one record's symptom or description.

        Args:
            tenant: The organisation. Required and non-defaulted — it is what the model call is
                metered against, and what the resulting vector is filtered by once indexed.
            record: The source record.

        Returns:
            The vector.

        Raises:
            NoEmbeddableFieldError: When the record has no symptom and no description.
        """
        return await self.model.embed(tenant, embeddable_text(record))

    async def embed_query(self, tenant: TenantContext, query: str) -> Sequence[float]:
        """Embed a user's query for the dense retrieval leg.

        The same truncation as a record, and for the same reason. The query is **read as a query**:
        this method returns a vector and there is nothing here that could act on its content.

        Args:
            tenant: The organisation, for metering.
            query: The search text.

        Returns:
            The vector.
        """
        return await self.model.embed(tenant, query.strip()[:MAX_EMBEDDED_CHARACTERS])
