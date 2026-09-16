"""The edge trust boundary, asserted from the attacker's position (constitution Principle I).

Every test here arrives the way something inside the network arrives: addressing the container
directly, free to send any header it likes. That is the threat the whole arrangement exists to
answer, and it is the one a suite that only ever calls through a correctly configured client never
poses.

**These run against the real pipeline.** Nothing is stubbed and nothing is bypassed — a provenance
test against a rearranged pipeline proves nothing about provenance.

The structural half — that the policy file, the APIM policies, the ingress manifests and both
enforcers agree — lives in ``test_edge_trust_policy.py``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn, TypeAdapter

from ragcore.api.app import create_app
from ragcore.api.middleware.provenance import (
    GatewayProvenanceMiddleware,
    GatewayProvenanceUnconfiguredError,
    forwarded_certificate_hash,
    parse_thumbprints,
)
from ragcore.config.composition import Container
from ragcore.config.settings import DatabaseSettings, EdgeTrustSettings, Settings
from ragcore.infrastructure.clock import SystemClock
from tests.support.gateway import (
    CERTIFICATE_HASH,
    FORWARDED_CLIENT_CERT_HEADER,
    UNKNOWN_CERTIFICATE_HASH,
    forwarded_client_cert,
    gateway_headers,
)

CUSTOMER_PATH = "/api/customer/v1/sessions"
STAFF_PATH = "/api/staff/v1/approvals"
WORKLOAD_PATH = "/api/workload/v1/work/00000000-0000-0000-0000-000000000000/claim"

FORGED_IDENTITY = {
    "X-Idp-Tenant-Id": str(uuid4()),
    "X-Idp-Principal-Id": str(uuid4()),
    "X-Idp-Roles": "administrator",
    "X-Idp-Credential-Class": "delegated",
    "X-Idp-Client-Surface": "forged",
}
"""A complete, well-formed identity context — everything an attacker would send.

Deliberately *valid*. A forgery that failed on its own merits would let these tests pass for the
wrong reason; the point is that a perfect forgery is refused, because it is refused on provenance
and never examined at all.
"""


def _settings(thumbprints: str = CERTIFICATE_HASH) -> Settings:
    """Settings for a process with the given allow-list."""
    dsn = TypeAdapter(PostgresDsn).validate_python("postgresql://user:pw@localhost/synthia")
    return Settings(
        database=DatabaseSettings(dsn=dsn),
        edge_trust=EdgeTrustSettings(gateway_certificate_thumbprints=thumbprints),
    )


@pytest.fixture(name="direct")
def direct_fixture() -> Any:
    """A client reaching the application without traversing the gateway.

    This is the attacker's position, and the one the whole edge model exists to refuse: inside the
    network, addressing the container directly.
    """
    app = create_app(container=Container(settings=_settings(), clock=SystemClock()))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestARequestThatDidNotTraverseTheGatewayIsRefused:
    """The central assertion, on every audience."""

    @pytest.mark.parametrize("path", [CUSTOMER_PATH, STAFF_PATH, WORKLOAD_PATH])
    def test_no_forwarded_certificate_is_a_refusal(self, direct: Any, path: str) -> None:
        """No certificate means the request did not come through APIM."""
        assert direct.post(path).status_code == 403

    @pytest.mark.parametrize("path", [CUSTOMER_PATH, STAFF_PATH, WORKLOAD_PATH])
    def test_a_forged_identity_context_is_refused_on_provenance(
        self, direct: Any, path: str
    ) -> None:
        """A *complete and well-formed* forgery is refused before any of it is parsed.

        That ordering is the property that matters. A service rejecting this on some detail of the
        headers would still accept a better forgery.
        """
        assert direct.post(path, headers=FORGED_IDENTITY).status_code == 403

    def test_a_certificate_from_another_holder_is_refused(self, direct: Any) -> None:
        """The check is an allow-list, not a format check.

        A well-formed hash belonging to somebody else's certificate is exactly what a format check
        would wave through, and exactly what an attacker holding their own certificate presents.
        """
        response = direct.post(CUSTOMER_PATH, headers=gateway_headers(UNKNOWN_CERTIFICATE_HASH))
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "header_value",
        [
            "",
            'Subject="CN=synthia-gateway"',
            "Hash=",
            "Hash=deadbeef",
            'By=spiffe://cluster/gateway;Cert="-----BEGIN CERTIFICATE-----"',
        ],
    )
    def test_a_forwarded_certificate_without_a_usable_hash_is_refused(
        self, direct: Any, header_value: str
    ) -> None:
        """Every shape of "the header is present but says nothing".

        A truncated hash is included because it is what a hand-edited or half-copied value looks
        like, and because accepting a prefix match would turn a 64-character control into an
        8-character one.
        """
        response = direct.post(CUSTOMER_PATH, headers={FORWARDED_CLIENT_CERT_HEADER: header_value})
        assert response.status_code == 403

    def test_a_forwarded_chain_is_refused_even_when_it_contains_an_accepted_hash(
        self, direct: Any
    ) -> None:
        """Two elements mean something appended to the header between APIM and this process.

        There is no safe reading of that: taking the first trusts whatever was furthest away,
        taking the last trusts whatever was nearest. An attacker who can append gets to choose
        which rule is convenient, so the answer is to accept neither.
        """
        chain = (
            forwarded_client_cert(UNKNOWN_CERTIFICATE_HASH)
            + ","
            + forwarded_client_cert(CERTIFICATE_HASH)
        )
        response = direct.post(CUSTOMER_PATH, headers={FORWARDED_CLIENT_CERT_HEADER: chain})
        assert response.status_code == 403


class TestARefusalSaysEnoughAndNoMore:
    """A refusal must be traceable by an operator and opaque to whoever triggered it."""

    def test_the_refusal_discloses_nothing_about_the_control(self, direct: Any) -> None:
        """Naming the header or the allow-list describes the boundary to whoever is probing it.

        An attacker who learns *which* check failed learns how close they got.
        """
        body = direct.post(
            CUSTOMER_PATH, headers=gateway_headers(UNKNOWN_CERTIFICATE_HASH)
        ).text.lower()
        for disclosure in (
            "x-forwarded-client-cert",
            "thumbprint",
            "allow-list",
            "certificate",
            CERTIFICATE_HASH,
        ):
            assert disclosure.lower() not in body, f"the refusal discloses {disclosure!r}"

    def test_a_refusal_is_a_problem_document_carrying_a_correlation_id(self, direct: Any) -> None:
        """Refusing at the edge must not cost the operator the thread.

        Provenance runs *inside* correlation for exactly this reason: a refusal a user can quote is
        one somebody can find.
        """
        response = direct.post(CUSTOMER_PATH)
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["status"] == 403
        assert body["correlationId"]
        assert body["type"].endswith("gateway-provenance-required")


class TestTheExemptionIsExactlyAsWideAsItLooks:
    """The one place where "served without provenance" is the correct answer."""

    @pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
    def test_a_health_probe_is_served_without_provenance(self, direct: Any, path: str) -> None:
        """The probe comes from the infrastructure, not through APIM.

        Safe only because these paths expose no identity: a caller reaching one has gained nothing
        it could not have guessed.
        """
        assert direct.get(path).status_code == 200

    def test_a_path_merely_beginning_with_health_is_not_exempt(self, direct: Any) -> None:
        """The exemption is a *segment* prefix.

        ``/healthcheck-bypass`` must not inherit it — which is precisely the route somebody would
        add to get around this.
        """
        assert direct.get("/healthcheck-bypass").status_code == 403


class TestProvenanceLetsTheRealThingThrough:
    """A control that refused everything would pass every test above and serve nobody."""

    def test_a_gateway_routed_request_reaches_the_pipeline(self) -> None:
        """401, not 200, and not 403.

        Provenance was satisfied, so the request reached the identity layer, which refused it for
        carrying no identity context. That is the two layers doing their own jobs in the right
        order.
        """
        app = create_app(container=Container(settings=_settings(), clock=SystemClock()))
        with TestClient(app, raise_server_exceptions=False, headers=gateway_headers()) as client:
            assert client.post(CUSTOMER_PATH).status_code == 401

    def test_rotation_accepts_both_the_outgoing_and_incoming_certificate(self) -> None:
        """Rotation is an overlap, so there is no instant at which neither is accepted.

        A single-valued setting would make every rotation a synchronised swap with a window in
        which the platform is either down or, worse, briefly unguarded.
        """
        both = f"{CERTIFICATE_HASH},{UNKNOWN_CERTIFICATE_HASH}"
        app = create_app(container=Container(settings=_settings(both), clock=SystemClock()))
        with TestClient(app, raise_server_exceptions=False) as client:
            for accepted in (CERTIFICATE_HASH, UNKNOWN_CERTIFICATE_HASH):
                response = client.post(CUSTOMER_PATH, headers=gateway_headers(accepted))
                assert response.status_code == 401, f"{accepted} was refused during rotation"


class TestAnUnconfiguredProcessDoesNotStart:
    """Fail closed, at startup, with no environment branch."""

    def test_an_empty_allow_list_refuses_to_build_the_application(self) -> None:
        """The alternative is a process that starts happily and accepts forged identity.

        That defect produces no error, no failed probe and no unusual log line, and looks exactly
        like a service working correctly — which is why it is fatal rather than permissive.
        """
        with pytest.raises(GatewayProvenanceUnconfiguredError):
            create_app(container=Container(settings=_settings(""), clock=SystemClock()))

    def test_the_failure_names_the_setting_to_fix(self) -> None:
        """A fail-closed control that does not say what to configure gets worked around."""

        async def unreached_app(scope: Any, receive: Any, send: Any) -> None:
            """The application the middleware would wrap. It is never called.

            An ASGI application is awaitable, and the middleware's parameter is typed as one. A
            synchronous stub type-checks as `-> None` and would be a silent mismatch here, where
            the assertion is that construction raises before anything is wrapped at all.
            """
            raise AssertionError("construction must fail before the application is reached")

        with pytest.raises(GatewayProvenanceUnconfiguredError) as caught:
            GatewayProvenanceMiddleware(unreached_app, accepted_thumbprints=frozenset())
        assert "SYNTHIA_EDGE_GATEWAY_CERTIFICATE_THUMBPRINTS" in str(caught.value)

    @pytest.mark.parametrize("malformed", ["deadbeef", "x" * 64, CERTIFICATE_HASH[:-1]])
    def test_a_malformed_thumbprint_is_refused_at_settings_validation(self, malformed: str) -> None:
        """A truncated or mistyped thumbprint matches nothing, and a control that matches nothing
        refuses every request — an outage whose cause is a formatting difference nobody can see.
        """
        with pytest.raises(ValueError, match="64-character hex"):
            EdgeTrustSettings(gateway_certificate_thumbprints=malformed)


class TestTheParsersFoldWhatTheyShouldAndNothingElse:
    """Unit-level, because these two functions are where a quiet widening would hide."""

    def test_a_thumbprint_copied_from_a_certificate_viewer_is_accepted(self) -> None:
        """Colons, quotes, whitespace and upper case all fold to the same value.

        Not leniency for its own sake: a viewer renders a thumbprint colon-separated and upper
        case, so refusing that spelling means the operator pasting the correct certificate gets a
        service that refuses every request.
        """
        viewer_format = ":".join(
            CERTIFICATE_HASH[index : index + 2] for index in range(0, 64, 2)
        ).upper()
        assert parse_thumbprints(f'  "{viewer_format}"  ') == frozenset({CERTIFICATE_HASH})

    def test_an_empty_setting_parses_to_nothing_rather_than_to_a_wildcard(self) -> None:
        """The empty set denies everything. An empty *rule* that allowed everything is the classic
        fail-open, and it is one line away from here.
        """
        assert parse_thumbprints("") == frozenset()
        assert parse_thumbprints(" , , ") == frozenset()

    def test_the_hash_element_is_found_regardless_of_position_or_case(self) -> None:
        """XFCC element order is not guaranteed, and the key's case is not either."""
        assert (
            forwarded_certificate_hash(f'Subject="CN=x";HASH={CERTIFICATE_HASH};URI=')
            == CERTIFICATE_HASH
        )

    def test_a_certificate_element_is_never_mistaken_for_the_hash(self) -> None:
        """``Cert`` carries the whole PEM and ``Hash`` carries the digest.

        Matching on a prefix rather than the exact key would read the certificate as the hash, and
        the certificate is the part an attacker can supply in full.
        """
        assert forwarded_certificate_hash('Cert="-----BEGIN CERTIFICATE-----"') is None
