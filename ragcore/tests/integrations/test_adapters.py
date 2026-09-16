"""Every Stage 9 adapter, against a fake honouring its contract.

**The adapter under test is always the production one.** The substitution happens at the transport
(:func:`tests.support.integrations.transport_returning`), so the resilience policy, the timeout
rule, the token acquisition and the boundary validation are all the shipping code. Only the far side
is fake — which is the most that can be arranged in a build with no AI Gateway, no AI Search index
and no ServiceNow instance.

What these assert is mostly **what went on the wire**, because that is where this stage's rules
live: the tenant filter that was sent, the idempotency key that was carried, the organisation the
model call was metered against, and the ``api-key`` header that was not there.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from ragcore.config.settings import IntegrationSettings, ModelGatewaySettings, RetrievalSettings
from ragcore.domain.identifiers import CorrelationId, IdempotencyKey, OperationIdentity, PrincipalId
from ragcore.execution.availability import CapabilityAvailability, availability_of
from ragcore.integrations.credentials import (
    CredentialNotEntitledError,
    TenantCredentialResolver,
)
from ragcore.integrations.graph.adapter import GRAPH_SCOPE, MicrosoftGraphAdapter
from ragcore.integrations.http import (
    HttpClientFactory,
    OutboundRequest,
    PermanentIntegrationError,
    ResilientHttpCaller,
    RetryPolicy,
    TransientIntegrationError,
)
from ragcore.integrations.mcp.client import McpToolClient, parse_server_urls
from ragcore.integrations.model.adapter import GatewayModelAdapter
from ragcore.integrations.model.egress import (
    ModelBudgetExceededError,
    ModelEgressError,
    ModelPurpose,
    ModelRequest,
)
from ragcore.integrations.model.gateway import AiGatewayEgress, GatewayNotConfiguredError
from ragcore.integrations.model.local import SERVED_BY, LocalDevelopmentEgress
from ragcore.integrations.servicenow.adapter import IDEMPOTENCY_HEADER, ServiceNowAdapter
from ragcore.integrations.servicenow.queue import InMemoryCaseWriteQueue
from ragcore.integrations.validation import BoundaryValidationError
from ragcore.retrieval.search import AzureAiSearchRetrieval, RetrievalNotConfiguredError
from tests.support.fakes import FakeClock, admitted_tenant
from tests.support.integrations import (
    FakeCredential,
    FakeCredentialReferenceStore,
    FakeModelEgress,
    FakeSecretResolver,
    json_response,
    transport_returning,
)

GATEWAY = ModelGatewaySettings(
    base_url="https://gateway.example", entra_scope="api://gateway/.default"
)
SEARCH = RetrievalSettings(endpoint="https://search.example", index_name="knowledge")
INTEGRATIONS = IntegrationSettings(
    servicenow_instance_url="https://itsm.example",
    mcp_server_urls="onelogin=https://mcp.example/onelogin,duo=https://mcp.example/duo",
)


def _credentials() -> tuple[TenantCredentialResolver, FakeCredentialReferenceStore]:
    store = FakeCredentialReferenceStore()
    return TenantCredentialResolver(store, FakeSecretResolver()), store


# ---------------------------------------------------------------------------
# The shared HTTP layer — the rules every adapter below inherits
# ---------------------------------------------------------------------------


class TestEveryOutboundCallCarriesATimeout:
    """The rule is enforced by the type, so no adapter can forget it (research R-020)."""

    async def test_a_request_without_a_positive_timeout_is_refused(self) -> None:
        with pytest.raises(ValueError, match="explicit timeout"):
            OutboundRequest(method="GET", url="https://example.com", timeout_seconds=0)

    async def test_a_timeout_beyond_the_ceiling_is_refused(self) -> None:
        """One call must not be able to occupy a meaningful fraction of the execution window."""
        with pytest.raises(ValueError, match="explicit timeout"):
            OutboundRequest(method="GET", url="https://example.com", timeout_seconds=600)

    async def test_a_plaintext_destination_is_refused(self) -> None:
        with pytest.raises(ValueError, match="https-only"):
            OutboundRequest(method="GET", url="http://example.com", timeout_seconds=5)


class TestTransientAndPermanentFailureAreDifferent:
    """Retrying a permanent failure turns one clear error into a burst of identical ones."""

    async def test_a_server_error_is_retried_and_then_reported_as_transient(self) -> None:
        transport, recorder = transport_returning(lambda _: json_response({}, status=503))
        caller = ResilientHttpCaller(
            HttpClientFactory(transport=transport),
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
        )

        with pytest.raises(TransientIntegrationError):
            await caller.send("x", OutboundRequest("GET", "https://example.com", 5.0))

        assert len(recorder.requests) == 3

    async def test_a_client_error_is_not_retried(self) -> None:
        transport, recorder = transport_returning(lambda _: json_response({}, status=400))
        caller = ResilientHttpCaller(
            HttpClientFactory(transport=transport),
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
        )

        with pytest.raises(PermanentIntegrationError):
            await caller.send("x", OutboundRequest("GET", "https://example.com", 5.0))

        assert len(recorder.requests) == 1

    async def test_a_throttle_is_transient(self) -> None:
        """429 is the provider saying *come back*, not *no*. Treating it as permanent would surface
        a throttle to the user as a failure of their request (spec FR-OPS-006)."""
        transport, _ = transport_returning(lambda _: json_response({}, status=429))
        caller = ResilientHttpCaller(
            HttpClientFactory(transport=transport),
            retry=RetryPolicy(max_attempts=2, backoff_seconds=0.0),
        )

        with pytest.raises(TransientIntegrationError):
            await caller.send("x", OutboundRequest("GET", "https://example.com", 5.0))


# ---------------------------------------------------------------------------
# The AI Gateway — the single model egress
# ---------------------------------------------------------------------------


class TestTheModelAdapterGoesThroughTheGateway:
    """``RagCore → AI Gateway → model provider``, asserted at the adapter."""

    async def test_a_completion_is_metered_against_the_organisation(self) -> None:
        egress = FakeModelEgress(text="a proposal")
        tenant = admitted_tenant()
        correlation = CorrelationId(str(uuid4()))

        result = await GatewayModelAdapter(egress).complete(tenant, "why", correlation)

        assert result == "a proposal"
        assert egress.sent[0].tenant_id == str(tenant.tenant_id.value)
        assert egress.sent[0].correlation_id == str(correlation)
        assert egress.sent[0].purpose is ModelPurpose.COMPLETION

    async def test_an_embedding_goes_through_the_same_egress(self) -> None:
        """An embedding call made directly to a provider would be an unmetered model call, and a
        single egress that some calls skip is not a single egress."""
        egress = FakeModelEgress(embedding=(0.5, 0.25))

        vector = await GatewayModelAdapter(egress).embed(admitted_tenant(), "text")

        assert list(vector) == [0.5, 0.25]
        assert egress.sent[0].purpose is ModelPurpose.EMBEDDING

    async def test_a_request_without_an_organisation_cannot_be_constructed(self) -> None:
        """An unattributable model call is an unbudgeted one."""
        with pytest.raises(ValueError, match="organisation"):
            ModelRequest(
                tenant_id="  ", correlation_id="c", purpose=ModelPurpose.COMPLETION, input_text="x"
            )


class TestTheGatewayClient:
    """What the gateway client actually sends, and what it refuses to do."""

    async def test_it_sends_the_organisation_and_correlation_headers(self) -> None:
        """The two things the gateway's metering, budget and cache policies read."""
        transport, recorder = transport_returning(lambda _: json_response({"output": "hello"}))
        egress = AiGatewayEgress(
            GATEWAY, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        )

        await egress.send(
            ModelRequest(
                tenant_id="org-1",
                correlation_id="corr-1",
                purpose=ModelPurpose.COMPLETION,
                input_text="why",
            )
        )

        assert recorder.header("X-Synthia-Organisation") == "org-1"
        assert recorder.header("X-Correlation-Id") == "corr-1"

    async def test_it_authenticates_with_a_bearer_token_and_no_key(self) -> None:
        """Managed identity, and ``build/policy/azure-identity.json`` forbids the alternative."""
        transport, recorder = transport_returning(lambda _: json_response({"output": "hello"}))
        credential = FakeCredential()
        egress = AiGatewayEgress(
            GATEWAY, ResilientHttpCaller(HttpClientFactory(transport=transport)), credential
        )

        await egress.send(
            ModelRequest(
                tenant_id="org-1",
                correlation_id="c",
                purpose=ModelPurpose.COMPLETION,
                input_text="x",
            )
        )

        assert recorder.header(
            "Authorization",
        ).startswith("Bearer ")  # type: ignore[union-attr]
        assert recorder.header("api-key") is None
        assert credential.requested_scopes == ["api://gateway/.default"]

    async def test_it_sends_no_provider_or_model_name(self) -> None:
        """A caller that could name a provider would make changing one a change to every call site
        (spec FR-OPS-009)."""
        transport, recorder = transport_returning(lambda _: json_response({"output": "hello"}))
        egress = AiGatewayEgress(
            GATEWAY, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        )

        await egress.send(
            ModelRequest(
                tenant_id="org-1",
                correlation_id="c",
                purpose=ModelPurpose.COMPLETION,
                input_text="x",
            )
        )

        assert set(recorder.last.body) == {"input"}

    async def test_an_exhausted_budget_is_not_a_failure(self) -> None:
        """A throttle MUST NOT be presented as a failure of the user's request (spec FR-OPS-006),
        which is why it has its own type rather than a status code the caller inspects."""
        transport, _ = transport_returning(lambda _: json_response({}, status=403))
        egress = AiGatewayEgress(
            GATEWAY, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        )

        with pytest.raises(ModelBudgetExceededError):
            await egress.send(
                ModelRequest(
                    tenant_id="o",
                    correlation_id="c",
                    purpose=ModelPurpose.COMPLETION,
                    input_text="x",
                )
            )

    async def test_an_unconfigured_gateway_reaches_no_provider(self) -> None:
        """Fails closed. The tempting alternative — fall back to a provider — is the single-egress
        rule with an ``except`` clause."""
        egress = AiGatewayEgress(
            ModelGatewaySettings(), ResilientHttpCaller(HttpClientFactory()), FakeCredential()
        )

        with pytest.raises(GatewayNotConfiguredError):
            await egress.send(
                ModelRequest(
                    tenant_id="o",
                    correlation_id="c",
                    purpose=ModelPurpose.COMPLETION,
                    input_text="x",
                )
            )

    async def test_a_malformed_response_is_rejected_at_the_boundary(self) -> None:
        """Provider output that does not match its contract does not reach the agent loop
        (spec FR-EXT-021)."""
        transport, _ = transport_returning(lambda _: json_response({"unexpected": True}))
        egress = AiGatewayEgress(
            GATEWAY, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        )

        with pytest.raises(BoundaryValidationError):
            await egress.send(
                ModelRequest(
                    tenant_id="o",
                    correlation_id="c",
                    purpose=ModelPurpose.COMPLETION,
                    input_text="x",
                )
            )


class TestTheLocalDevelopmentSeam:
    """A gateway substitute, never a provider shortcut."""

    async def test_it_calls_no_model_and_says_so(self) -> None:
        response = await LocalDevelopmentEgress(environment="local").send(
            ModelRequest(
                tenant_id="o", correlation_id="c", purpose=ModelPurpose.COMPLETION, input_text="x"
            )
        )

        assert response.served_by == SERVED_BY
        assert "No model was called" in response.text

    async def test_its_embedding_is_deterministic(self) -> None:
        """Deterministic so a retrieval test repeats — and short enough that nobody mistakes it for
        a real embedding."""
        seam = LocalDevelopmentEgress(environment="local")
        request = ModelRequest(
            tenant_id="o", correlation_id="c", purpose=ModelPurpose.EMBEDDING, input_text="same"
        )

        first = await seam.send(request)
        second = await seam.send(request)

        assert list(first.embedding) == list(second.embedding)
        assert len(first.embedding) == 16

    @pytest.mark.parametrize("environment", ["development", "staging", "production"])
    async def test_it_refuses_every_deployed_environment(self, environment: str) -> None:
        """A deployed process that fell back to this would meter nothing and look entirely
        healthy."""
        with pytest.raises(ModelEgressError, match="cannot be used"):
            LocalDevelopmentEgress(environment=environment)


# ---------------------------------------------------------------------------
# Azure AI Search — the mandatory tenant filter
# ---------------------------------------------------------------------------


class TestRetrievalIsTenantFiltered:
    """The filter is built from trusted context and cannot be widened by a caller."""

    async def test_every_query_carries_the_organisation_filter(self) -> None:
        tenant = admitted_tenant()
        transport, recorder = transport_returning(lambda _: json_response({"value": []}))

        await AzureAiSearchRetrieval(
            SEARCH, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        ).search(tenant, "printer", 5)

        assert recorder.last.body["filter"] == f"tenant_id eq '{tenant.tenant_id.value}'"

    async def test_it_authenticates_with_a_token_and_never_an_api_key(self) -> None:
        """Both the admin and the query key are application-owned credentials and are forbidden."""
        transport, recorder = transport_returning(lambda _: json_response({"value": []}))
        credential = FakeCredential()

        await AzureAiSearchRetrieval(
            SEARCH, ResilientHttpCaller(HttpClientFactory(transport=transport)), credential
        ).search(admitted_tenant(), "printer", 5)

        assert credential.requested_scopes == ["https://search.azure.com/.default"]
        assert recorder.header("api-key") is None

    async def test_a_document_from_another_organisation_discards_the_whole_result(self) -> None:
        """The filter is what the query asked for; this is what came back. Knowledge retrieval MUST
        NOT return another organisation's content **under any circumstances**
        (spec FR-IDENT-009)."""
        tenant = admitted_tenant()
        intruder = str(uuid4())
        transport, _ = transport_returning(
            lambda _: json_response(
                {
                    "value": [
                        {"tenant_id": str(tenant.tenant_id.value), "content": "ours"},
                        {"tenant_id": intruder, "content": "theirs"},
                    ]
                }
            )
        )

        with pytest.raises(BoundaryValidationError, match="does not belong"):
            await AzureAiSearchRetrieval(
                SEARCH,
                ResilientHttpCaller(HttpClientFactory(transport=transport)),
                FakeCredential(),
            ).search(tenant, "printer", 5)

    async def test_the_result_count_is_bounded_whatever_the_caller_asks(self) -> None:
        """An unbounded retrieval is an unbounded prompt."""
        transport, recorder = transport_returning(lambda _: json_response({"value": []}))

        await AzureAiSearchRetrieval(
            SEARCH, ResilientHttpCaller(HttpClientFactory(transport=transport)), FakeCredential()
        ).search(admitted_tenant(), "printer", 10_000)

        assert recorder.last.body["top"] == 50

    async def test_an_unconfigured_index_raises_rather_than_returning_nothing(self) -> None:
        """ "This organisation has no matching knowledge" and "this process cannot retrieve" are
        different facts, and an empty list would report the second as the first."""
        with pytest.raises(RetrievalNotConfiguredError):
            await AzureAiSearchRetrieval(
                RetrievalSettings(), ResilientHttpCaller(HttpClientFactory()), FakeCredential()
            ).search(admitted_tenant(), "printer", 5)


# ---------------------------------------------------------------------------
# ServiceNow — idempotent write-back, queue and replay
# ---------------------------------------------------------------------------


def _servicenow(
    transport: httpx.AsyncBaseTransport, queue: InMemoryCaseWriteQueue
) -> tuple[ServiceNowAdapter, FakeCredentialReferenceStore]:
    resolver, store = _credentials()
    adapter = ServiceNowAdapter(
        INTEGRATIONS,
        ResilientHttpCaller(
            HttpClientFactory(transport=transport), retry=RetryPolicy(max_attempts=1)
        ),
        resolver,
        queue,
        FakeClock(),
    )
    return adapter, store


class TestTheSystemOfRecordBoundary:
    """One owning boundary, idempotent writes, and an outage that loses nothing."""

    async def test_a_write_carries_the_idempotency_key_it_was_given(self) -> None:
        """A retried write MUST NOT double-post (spec FR-EXT-004), and a key generated inside the
        adapter would be a new key on every attempt."""
        tenant = admitted_tenant()
        transport, recorder = transport_returning(lambda _: json_response({"result": "ok"}))
        adapter, store = _servicenow(transport, InMemoryCaseWriteQueue())
        store.bind(tenant, "servicenow", "itsm-credential-name")

        receipt = await adapter.record_progress(
            tenant,
            "CASE-1",
            {"state": "triaged"},
            IdempotencyKey("key-1"),
            CorrelationId("corr-1"),
        )

        assert receipt.committed and not receipt.queued
        assert recorder.header(IDEMPOTENCY_HEADER) == "key-1"

    async def test_an_outage_queues_the_write_and_does_not_report_success(self) -> None:
        """Three obligations at once: the loop continues, the write survives, and the session does
        not resolve (spec FR-EXT-007)."""
        tenant = admitted_tenant()
        transport, _ = transport_returning(lambda _: json_response({}, status=503))
        queue = InMemoryCaseWriteQueue()
        adapter, store = _servicenow(transport, queue)
        store.bind(tenant, "servicenow", "itsm-credential-name")

        receipt = await adapter.record_progress(
            tenant, "CASE-1", {"state": "triaged"}, IdempotencyKey("key-1"), CorrelationId("c")
        )

        assert receipt.queued and not receipt.committed
        assert await adapter.uncommitted_writes(tenant) == 1

    async def test_a_queued_write_keeps_its_original_idempotency_key(self) -> None:
        """A regenerated key would make the replay a second write."""
        tenant = admitted_tenant()
        transport, _ = transport_returning(lambda _: json_response({}, status=503))
        queue = InMemoryCaseWriteQueue()
        adapter, store = _servicenow(transport, queue)
        store.bind(tenant, "servicenow", "itsm-credential-name")

        await adapter.record_progress(
            tenant, "CASE-1", {"a": "b"}, IdempotencyKey("key-1"), CorrelationId("c")
        )

        assert [write.idempotency_key for write in await queue.drain()] == [IdempotencyKey("key-1")]

    async def test_an_organisation_without_a_credential_is_refused_not_queued(self) -> None:
        """A write that could never be authorized is not waiting on an outage, and queueing it would
        hide a configuration defect behind a retry that never succeeds."""
        transport, _ = transport_returning(lambda _: json_response({"result": "ok"}))
        adapter, _store = _servicenow(transport, InMemoryCaseWriteQueue())

        with pytest.raises(CredentialNotEntitledError):
            await adapter.record_progress(
                admitted_tenant(), "CASE-1", {}, IdempotencyKey("k"), CorrelationId("c")
            )

    async def test_one_organisations_credential_is_never_used_for_another(self) -> None:
        """Credentials are held per organisation and per system (spec FR-EXT-016)."""
        entitled = admitted_tenant()
        other = admitted_tenant()
        transport, _ = transport_returning(lambda _: json_response({"result": "ok"}))
        adapter, store = _servicenow(transport, InMemoryCaseWriteQueue())
        store.bind(entitled, "servicenow", "itsm-credential-name")

        with pytest.raises(CredentialNotEntitledError):
            await adapter.record_progress(
                other, "CASE-1", {}, IdempotencyKey("k"), CorrelationId("c")
            )


# ---------------------------------------------------------------------------
# Microsoft Graph
# ---------------------------------------------------------------------------


class TestTheDirectoryBoundary:
    """Read-only, managed identity, and Graph's vocabulary stops at the adapter."""

    async def test_it_returns_platform_terms_not_graph_terms(self) -> None:
        transport, _ = transport_returning(
            lambda _: json_response(
                {"@odata.context": "…", "displayName": "Ada", "mail": "ada@example.com"}
            )
        )

        profile = await MicrosoftGraphAdapter(
            INTEGRATIONS,
            ResilientHttpCaller(HttpClientFactory(transport=transport)),
            FakeCredential(),
        ).lookup_principal(admitted_tenant(), PrincipalId(uuid4()))

        assert profile is not None
        assert profile.display_name == "Ada"
        assert profile.mail == "ada@example.com"

    async def test_an_unknown_principal_is_an_absence_not_an_error(self) -> None:
        """``None`` is an absence of information and is never read as an authorization outcome."""
        transport, _ = transport_returning(lambda _: json_response({}, status=404))

        profile = await MicrosoftGraphAdapter(
            INTEGRATIONS,
            ResilientHttpCaller(
                HttpClientFactory(transport=transport), retry=RetryPolicy(max_attempts=1)
            ),
            FakeCredential(),
        ).lookup_principal(admitted_tenant(), PrincipalId(uuid4()))

        assert profile is None

    async def test_it_requests_the_graph_application_scope(self) -> None:
        transport, _ = transport_returning(lambda _: json_response({"displayName": "Ada"}))
        credential = FakeCredential()

        await MicrosoftGraphAdapter(
            INTEGRATIONS, ResilientHttpCaller(HttpClientFactory(transport=transport)), credential
        ).lookup_principal(admitted_tenant(), PrincipalId(uuid4()))

        assert credential.requested_scopes == [GRAPH_SCOPE]


# ---------------------------------------------------------------------------
# MCP — discovery is not entitlement
# ---------------------------------------------------------------------------


class TestDiscoveryConfersNothing:
    """The gap between what a server advertises and what an organisation may call."""

    async def test_an_advertised_tool_carries_no_treatment_or_entitlement(self) -> None:
        """There is no field here a caller could read to decide whether to proceed
        (spec FR-EXT-014)."""
        tenant = admitted_tenant()
        transport, _ = transport_returning(
            lambda _: json_response({"tools": [{"name": "user.disable", "description": "d"}]})
        )
        resolver, store = _credentials()
        store.bind(tenant, "onelogin", "onelogin-credential-name")

        tools = await McpToolClient(
            INTEGRATIONS, ResilientHttpCaller(HttpClientFactory(transport=transport)), resolver
        ).discover(tenant, "onelogin")

        from dataclasses import fields

        assert [tool.name for tool in tools] == ["user.disable"]
        assert {field.name for field in fields(tools[0])} == {"system", "name", "description"}

    async def test_invoke_takes_a_catalogue_identity_and_not_an_advertised_tool(self) -> None:
        """An advertised tool cannot be passed to the method that calls one. Going from one to the
        other means going through the catalogue."""
        from ragcore.integrations.mcp.client import AdvertisedTool

        parameters = McpToolClient.invoke.__annotations__
        assert parameters["identity"] == "OperationIdentity"
        assert AdvertisedTool.__name__ not in str(parameters)

    async def test_an_unreachable_server_raises_rather_than_advertising_nothing(self) -> None:
        """ "Advertises nothing" and "could not be asked" are different facts; collapsing them would
        report an outage as a shrunken toolset."""
        tenant = admitted_tenant()
        transport, _ = transport_returning(lambda _: json_response({}, status=503))
        resolver, store = _credentials()
        store.bind(tenant, "onelogin", "onelogin-credential-name")

        with pytest.raises(TransientIntegrationError):
            await McpToolClient(
                INTEGRATIONS,
                ResilientHttpCaller(
                    HttpClientFactory(transport=transport), retry=RetryPolicy(max_attempts=1)
                ),
                resolver,
            ).discover(tenant, "onelogin")

    async def test_an_unconfigured_system_has_no_shared_fallback(self) -> None:
        tenant = admitted_tenant()
        transport, _ = transport_returning(lambda _: json_response({"tools": []}))
        resolver, store = _credentials()
        store.bind(tenant, "unlisted", "some-credential-name")

        with pytest.raises(Exception, match="no MCP server endpoint"):
            await McpToolClient(
                INTEGRATIONS, ResilientHttpCaller(HttpClientFactory(transport=transport)), resolver
            ).discover(tenant, "unlisted")

    async def test_an_invocation_never_claims_more_than_the_platform_knows(self) -> None:
        """A success field in the response is the server's claim about its own work; a
        server-confirmed outcome requires the platform to read the effect back."""
        from ragcore.domain.governance import VerificationOutcome

        tenant = admitted_tenant()
        transport, recorder = transport_returning(
            lambda _: json_response({"isError": False, "summary": "done"})
        )
        resolver, store = _credentials()
        store.bind(tenant, "duo", "duo-credential-name")

        result = await McpToolClient(
            INTEGRATIONS, ResilientHttpCaller(HttpClientFactory(transport=transport)), resolver
        ).invoke(
            tenant,
            OperationIdentity("duo.device.read", 1),
            {"device": "x"},
            IdempotencyKey("k-1"),
            CorrelationId("c-1"),
        )

        assert result.succeeded
        assert result.verification is VerificationOutcome.CLIENT_ATTESTED
        assert recorder.header("X-Synthia-Idempotency-Key") == "k-1"

    def test_a_malformed_server_list_is_refused_at_startup(self) -> None:
        with pytest.raises(ValueError, match="system=url"):
            parse_server_urls("https://mcp.example/onelogin")

    def test_a_plaintext_server_is_refused(self) -> None:
        with pytest.raises(ValueError, match="https"):
            parse_server_urls("onelogin=http://mcp.example")


# ---------------------------------------------------------------------------
# Entitled-but-unreachable is its own outcome
# ---------------------------------------------------------------------------


class TestAvailabilityDistinguishesThreeThings:
    """Not entitled, temporarily unavailable, available — and none of them is a failure of the
    user's request (spec FR-EXT-022)."""

    async def test_not_entitled_is_reported_without_probing_the_system(self) -> None:
        """Probing a system the organisation may not use would send its credential to a third party
        over a capability it has no right to.

        The probe is a *callable* rather than an awaitable for exactly this reason: an awaitable
        would already have been constructed by the caller, so "it was not probed" could only ever
        be a claim about what was awaited, not about what was done.
        """
        probed = False

        async def probe() -> None:
            nonlocal probed
            probed = True

        result = await availability_of(entitled=False, probe=probe)

        assert result is CapabilityAvailability.NOT_ENTITLED
        assert not probed

    async def test_an_unreachable_system_is_temporary_not_a_refusal(self) -> None:
        async def failing() -> None:
            raise TransientIntegrationError("duo", "unreachable")

        assert (
            await availability_of(entitled=True, probe=failing)
            is CapabilityAvailability.TEMPORARILY_UNAVAILABLE
        )

    async def test_a_reachable_entitled_capability_is_available(self) -> None:
        async def reachable() -> None:
            return None

        assert (
            await availability_of(entitled=True, probe=reachable)
            is CapabilityAvailability.AVAILABLE
        )

    def test_there_is_no_failure_member(self) -> None:
        """``FAILED`` would be the presentation FR-EXT-022 prohibits, available as an enum member
        for any caller who reached for it."""
        assert {member.name for member in CapabilityAvailability} == {
            "AVAILABLE",
            "NOT_ENTITLED",
            "TEMPORARILY_UNAVAILABLE",
        }
