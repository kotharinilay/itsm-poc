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

import pytest

from ragcore.config.settings import ModelGatewaySettings, RetrievalSettings
from ragcore.domain.identifiers import CorrelationId
from ragcore.egress.http import (
    HttpClientFactory,
    OutboundRequest,
    PermanentIntegrationError,
    ResilientHttpCaller,
    RetryPolicy,
    TransientIntegrationError,
)
from ragcore.egress.validation import BoundaryValidationError
from ragcore.execution.availability import CapabilityAvailability, availability_of
from ragcore.integrations.model.adapter import GatewayModelAdapter
from ragcore.integrations.model.egress import (
    ModelBudgetExceededError,
    ModelEgressError,
    ModelPurpose,
    ModelRequest,
)
from ragcore.integrations.model.gateway import AiGatewayEgress, GatewayNotConfiguredError
from ragcore.integrations.model.local import SERVED_BY, LocalDevelopmentEgress
from ragcore.retrieval.search import AzureAiSearchRetrieval, RetrievalNotConfiguredError
from tests.support.fakes import admitted_tenant
from tests.support.integrations import (
    FakeCredential,
    FakeModelEgress,
    json_response,
    transport_returning,
)

GATEWAY = ModelGatewaySettings(
    base_url="https://gateway.example", entra_scope="api://gateway/.default"
)
SEARCH = RetrievalSettings(endpoint="https://search.example", index_name="knowledge")


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
# The Graph and MCP sections stood here and are gone (T289, T292, T296)
# ---------------------------------------------------------------------------
#
# `TestTheDirectoryBoundary` and `TestDiscoveryConfersNothing` tested adapters this deployable no
# longer contains. They were not deleted: the facts they pinned — that Graph's vocabulary stops at
# the boundary, that a directory profile carries no roles, that discovery confers no entitlement and
# that there is no overload taking an advertised tool — moved with the code they were about, to
# `integrations/tests/unit/test_connectors.py` and the MCP tests beside it.
#
# **What replaces them in THIS tree is an absence proof, not a behaviour test**, because the claim
# here is different. There is nothing left to exercise; the claim is that nothing can be added back.
# `tests/architecture/test_no_connector_in_ragcore.py` makes it, and `check-boundaries.sh` makes it
# again at build time.


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
