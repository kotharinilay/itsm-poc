"""Azure AI Search. **Tenant-filtered by construction, derived by design, data by rule.**

Three properties, each enforced structurally rather than remembered.

**1. The tenant filter is not optional and no unfiltered path exists** (constitution Principle IV,
spec FR-IDENT-008, FR-IDENT-009). :meth:`AzureAiSearchRetrieval.search` takes a
:class:`~ragcore.domain.tenancy.TenantContext` as a required, non-defaulted parameter, and the
filter expression is built by :func:`tenant_filter` from that context alone — it is not a parameter,
not a setting and not composable with a caller-supplied filter. There is no method here that accepts
an OData filter string, and that absence is the control: the moment one exists, a caller can pass
one that omits the organisation, and the isolation test is reduced to checking that nobody did.
A caller-supplied ``$filter`` would also be the obvious injection target, reachable from retrieved
content or chat text.

**2. The index is derived.** It holds a projection of ingested knowledge and is authoritative for
nothing. A lost index is rebuilt by re-running ingestion from its watermark, never restored from a
backup — restoring it would reintroduce documents that erasure had removed from the authoritative
store, which is how a derived copy becomes a data-protection incident.

**3. Retrieved content is data, never instruction, and never confers authority** (spec FR-EXT-017,
FR-EXT-018). Every chunk leaves this module through
:func:`~ragcore.egress.validation.as_data`. The defence is structural, not a filter: content
cannot reach a treatment, a role or an outbound destination, so a successful injection produces at
most a bad proposal that governance still refuses.

**Managed identity, no key.** The service is reached with an Entra token for
``https://search.azure.com/.default``. ``build/policy/azure-identity.json`` names
``AzureKeyCredential``, ``admin key``, ``query key`` and ``api-key`` as forbidden configuration for
this resource; the granted role is ``Search Index Data Reader``, so this path can read the index and
cannot author it. Index authoring belongs to ingestion.

The REST API is called through the shared HTTP layer rather than through ``azure-search-documents``,
for the same reason :mod:`ragcore.notifications.signalr` calls the SignalR data plane directly: the
resilience policy, the connection pool and the mandatory timeout are platform rules, and an SDK
client brings its own version of all three.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from ragcore.egress.http import IntegrationError, OutboundRequest, ResilientHttpCaller
from ragcore.egress.validation import (
    BoundaryValidationError,
    as_data,
    optional_text,
    require_object,
    require_text,
)
from ragcore.infrastructure.azure_credentials import azure_credential

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import RetrievalSettings
    from ragcore.domain.tenancy import TenantContext

SYSTEM: Final = "ai-search"
SEARCH_SCOPE: Final = "https://search.azure.com/.default"
"""The data-plane scope. A token for this and nothing broader."""

API_VERSION: Final = "2024-07-01"

TENANT_FIELD: Final = "tenant_id"
"""The index field every document carries and every query filters on.

Named here once. An index without this field cannot be queried by this module at all, because the
filter it builds would match nothing — which is the correct failure: an index that cannot be
tenant-filtered must return nothing rather than everything.
"""

MAX_RESULTS: Final = 50
"""The ceiling on one query, whatever the caller asks for.

Bounded because an unbounded retrieval is an unbounded prompt, and because a large result set is
how an isolation defect stops being theoretical.
"""


def tenant_filter(tenant: TenantContext) -> str:
    """Build the organisation filter for one query.

    **The only filter this module ever sends.** It takes a trusted context and returns an OData
    expression over :data:`TENANT_FIELD`; there is no parameter for additional criteria and no
    caller-supplied fragment is concatenated to it, so there is no expression a caller can craft
    that widens the scope.

    Args:
        tenant: The organisation, resolved from validated identity or from the work item. Never
            from a client request and never from retrieved content.

    Returns:
        The filter expression.
    """
    # The identifier is a UUID by type, so it cannot carry a quote or an OData operator. The
    # formatting is still explicit rather than an f-string over a `str`, because the day this
    # becomes a `str` is the day the escaping question becomes real.
    return f"{TENANT_FIELD} eq '{tenant.tenant_id.value!s}'"


@dataclass(frozen=True, slots=True)
class SearchChunk:
    """One piece of grounding evidence.

    Satisfies :class:`~ragcore.application.ports.RetrievedChunk`. Frozen, so a node cannot edit a
    citation's source after the fact.

    Attributes:
        content: The chunk text. **Data, never instruction.**
        score: The relevance score as the index reported it. **A raw similarity score is not a
            probability**, and nothing downstream treats it as one.
        source_reference: Where it came from, for citation.
    """

    content: str
    score: float
    source_reference: str


class RetrievalNotConfiguredError(IntegrationError):
    """No index is configured.

    Raised rather than returning an empty result, because the two are different facts: "the
    organisation has no matching knowledge" and "this process cannot retrieve at all" lead to
    different operator actions, and an empty list would present the second as the first.
    """

    def __init__(self) -> None:
        super().__init__(SYSTEM, "no AI Search endpoint is configured")


class AzureAiSearchRetrieval:
    """Grounding evidence from the derived index, within one organisation and only within it.

    Satisfies :class:`~ragcore.application.ports.RetrievalPort`.
    """

    def __init__(
        self,
        settings: RetrievalSettings,
        caller: ResilientHttpCaller,
        credential: Any | None = None,  # noqa: ANN401 — the concrete type needs the SDK imported
    ) -> None:
        """Bind retrieval to an index.

        Args:
            settings: The retrieval settings. There is no key field to pass.
            caller: The shared resilient HTTP caller, which supplies the pool, the retry policy and
                the mandatory timeout.
            credential: The Azure credential. The shared process credential when omitted.
        """
        self._settings = settings
        self._caller = caller
        self._credential = credential

    async def search(self, tenant: TenantContext, query: str, limit: int) -> Sequence[SearchChunk]:
        """Retrieve within the organisation.

        Args:
            tenant: The organisation. **Required and non-defaulted**: a code path able to issue an
                unfiltered query MUST NOT exist, and a parameter with a default would be one.
            query: The search text.
            limit: How many chunks to return, bounded above by :data:`MAX_RESULTS`.

        Returns:
            The chunks, each marked as data. Empty when the organisation has no matching knowledge —
            which is an answer, not a failure.

        Raises:
            RetrievalNotConfiguredError: When no index is configured.
            TransientIntegrationError: When the index is unreachable. Reported by the caller as
                *temporarily unavailable*, distinctly from *not entitled*, and never as a failure of
                the user's request (spec FR-EXT-022).
            BoundaryValidationError: When a document does not match the index contract.
        """
        if not self._settings.is_configured:
            raise RetrievalNotConfiguredError

        endpoint = self._settings.endpoint.rstrip("/")
        url = (
            f"{endpoint}/indexes/{self._settings.index_name}/docs/search?api-version={API_VERSION}"
        )

        response = await self._caller.send(
            SYSTEM,
            OutboundRequest(
                method="POST",
                url=url,
                timeout_seconds=self._settings.request_timeout_seconds,
                headers=await self._headers(),
                json_body={
                    "search": query,
                    "top": max(1, min(limit, MAX_RESULTS)),
                    # Built from the trusted context and nowhere else. There is no parameter on
                    # this method that contributes to it.
                    "filter": tenant_filter(tenant),
                },
            ),
        )

        return self._read(tenant, response.json())

    async def _headers(self) -> dict[str, str]:
        """The data-plane headers. A bearer token, and no ``api-key``."""
        credential = self._credential if self._credential is not None else azure_credential()
        token = await credential.get_token(SEARCH_SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

    def _read(self, tenant: TenantContext, payload: object) -> list[SearchChunk]:
        """Validate the response and read the chunks.

        Every document is checked against the index contract before it becomes evidence, because
        malformed provider output MUST be rejected at the boundary rather than reaching the agent
        loop (spec FR-EXT-021).

        **Each document's own tenant field is re-checked here**, and that is not redundancy. The
        filter is what the query asked for; this is what came back. They differ if the index is
        misconfigured, if a document was written without the field, or if the filter silently failed
        to apply — and the platform's promise is that content belonging to another organisation is
        never returned **under any circumstances** (spec FR-IDENT-009), which is a promise about the
        result rather than about the request.
        """
        body = require_object(SYSTEM, payload)
        documents = body.get("value")

        if not isinstance(documents, list):
            raise BoundaryValidationError(SYSTEM, "the response carries no document list")

        expected = str(tenant.tenant_id.value)
        chunks: list[SearchChunk] = []

        for document in documents:
            fields = require_object(SYSTEM, document)

            if fields.get(TENANT_FIELD) != expected:
                raise BoundaryValidationError(
                    SYSTEM,
                    "a returned document does not belong to the organisation that was queried. "
                    "The result is discarded in full rather than filtered, because a filter that "
                    "did not apply cannot be trusted to have applied partially.",
                )

            score = fields.get("@search.score")

            chunks.append(
                SearchChunk(
                    content=as_data(require_text(SYSTEM, fields, "content")),
                    score=float(score) if isinstance(score, int | float) else 0.0,
                    source_reference=optional_text(SYSTEM, fields, "source_reference") or "",
                )
            )

        return chunks
