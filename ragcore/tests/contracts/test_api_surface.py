"""The API surface, checked against the generated contracts under ``build/contracts/``.

Three audiences, the SSE envelope, and the conventions that outrank any individual endpoint.

**The route table is asserted exactly, not as a subset.** A missing route is a gap; an *extra*
route is a surface nobody reviewed, and on this platform an unreviewed state-changing route is the
more dangerous of the two. So the set is compared with ``==``.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn, TypeAdapter

from ragcore.api.app import create_app
from ragcore.api.customer import streaming
from ragcore.api.middleware.problems import PROBLEM_MEDIA_TYPE
from ragcore.config.composition import Container, build_container
from ragcore.config.settings import DatabaseSettings, Settings
from ragcore.domain.identifiers import EntraTenantId, PrincipalId
from ragcore.domain.principal import (
    Audience,
    AuthenticatedPrincipal,
    CredentialClass,
    HumanIdentity,
)
from ragcore.domain.roles import RoleSet
from ragcore.domain.tenancy import TenantContext, TenantStatus
from ragcore.infrastructure.clock import SystemClock
from tests.support.fakes import admitted_tenant

CUSTOMER_ROUTES = {
    ("POST", "/api/customer/v1/sessions"),
    ("POST", "/api/customer/v1/sessions/{sessionId}/messages"),
    ("POST", "/api/customer/v1/sessions/{sessionId}/answers"),
    ("POST", "/api/customer/v1/work/{workItemId}/consent"),
    ("GET", "/api/customer/v1/work/{workItemId}/instruction"),
    ("POST", "/api/customer/v1/work/{workItemId}/result"),
    ("PUT", "/api/customer/v1/messages/{messageId}/feedback"),
    ("DELETE", "/api/customer/v1/messages/{messageId}/feedback"),
    ("POST", "/api/customer/v1/realtime/negotiate"),
    # The inert sample flow (Stage 8). Platform plumbing, never a product capability: it opens a
    # durable record and its outbox row in one transaction, reads the outcome back — which is the
    # recovery path that keeps the realtime notification a leaf — and demonstrates the
    # Customer-to-Workload hop through the gateway.
    ("POST", "/api/customer/v1/sample-flows/round-trip"),
    ("GET", "/api/customer/v1/sample-flows/round-trip/{workItemId}"),
    ("POST", "/api/customer/v1/sample-flows/service-hop"),
}
"""contracts/customer-api.md, RagCore section. Every row, and only those rows."""

STAFF_ROUTES = {
    ("POST", "/api/staff/v1/approvals/{approvalId}/verdict"),
    ("POST", "/api/staff/v1/sessions/{sessionId}/takeover"),
    ("POST", "/api/staff/v1/sessions/{sessionId}/messages"),
    ("POST", "/api/staff/v1/work/{workItemId}/cancel"),
}
"""contracts/staff-api.md, RagCore section."""

WORKLOAD_ROUTES = {
    ("POST", "/api/workload/v1/work/{workItemId}/claim"),
    ("POST", "/api/workload/v1/work/{workItemId}/outcome"),
}
"""contracts/workload-api.md."""

FORBIDDEN_PARAMETERS = {
    "tenantid",
    "tenant",
    "roles",
    "role",
    "audience",
    "actas",
    "onbehalfof",
    "principalid",
    "oid",
    "treatment",
    "approved",
    "authorized",
}
"""Authority a request may never assert. Rule 1 of contracts/README.md."""

TENANT_HEADER = "X-Idp-Tenant-Id"
PRINCIPAL_HEADER = "X-Idp-Principal-Id"


@pytest.fixture(name="app")
def app_fixture() -> Any:
    """An application with a container holding the clock and an admitting tenant registry.

    The registry is bound because the conversation surface needs one: a turn is retrieved,
    grounded and gated within an organisation, so ``POST .../messages`` depends on
    :func:`~ragcore.api.deps.get_tenant` and an unbound registry correctly fails closed with a 503.
    Binding one here keeps these tests about the surface — casing, correlation, the streaming
    envelope — rather than about admission, which
    :class:`TestTenantAdmissionFailsClosed` asserts directly.
    """
    # A syntactically valid DSN pointing nowhere. Nothing in the scaffold opens a connection:
    # the container binds no repository, so a reachable database would prove nothing.
    dsn = TypeAdapter(PostgresDsn).validate_python("postgresql://user:pw@localhost/synthia")
    settings = Settings(database=DatabaseSettings(dsn=dsn))
    return create_app(
        container=Container(
            settings=settings,
            clock=SystemClock(),
            tenant_registry=_registry(admitted_tenant()),
        )
    )


@pytest.fixture(name="client")
def client_fixture(app: Any) -> Any:
    """A test client arriving the way every real request does.

    It carries no gateway-provenance marker, because the application no longer looks for one: that
    mechanism is deferred (ADR 0008) and was not replaced. A request reaching this process is
    admitted on its ``X-Idp-*`` contract alone.
    """
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _identity() -> dict[str, str]:
    """A well-formed Gateway-derived identity contract, as APIM would set it."""
    return {TENANT_HEADER: str(uuid4()), PRINCIPAL_HEADER: str(uuid4())}


def _routes(app: Any) -> set[tuple[str, str]]:
    spec = app.openapi()
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
    }


class TestTheThreeAudiences:
    """The route table, compared exactly."""

    def test_the_customer_surface_matches_the_contract(self, app: Any) -> None:
        actual = {route for route in _routes(app) if "/api/customer/" in route[1]}
        assert actual == CUSTOMER_ROUTES

    def test_the_staff_surface_matches_the_contract(self, app: Any) -> None:
        actual = {route for route in _routes(app) if "/api/staff/" in route[1]}
        assert actual == STAFF_ROUTES

    def test_the_workload_surface_matches_the_contract(self, app: Any) -> None:
        actual = {route for route in _routes(app) if "/api/workload/" in route[1]}
        assert actual == WORKLOAD_ROUTES

    def test_there_is_no_fourth_audience(self, app: Any) -> None:
        """Every route belongs to a declared audience with a declared authorization model."""
        assert _routes(app) == CUSTOMER_ROUTES | STAFF_ROUTES | WORKLOAD_ROUTES

    def test_no_route_serves_a_read_view(self, app: Any) -> None:
        """``views`` routes are the monolith's, and it is read-only (ADR-0001).

        Neither deployable calls the other; they meet at PostgreSQL. A ``views`` route here would
        be RagCore duplicating a read model the schema contract already publishes.
        """
        assert not [path for _, path in _routes(app) if "/views/" in path]

    def test_every_path_is_versioned(self, app: Any) -> None:
        """A breaking change adds ``/v2/``; it never mutates ``/v1/``."""
        assert all("/v1/" in path or path.endswith("/v1") for _, path in _routes(app))


class TestNoEndpointAcceptsAuthority:
    """Rule 1: no endpoint accepts a tenant, role or audience parameter and trusts it."""

    def test_no_declared_parameter_names_authority(self, app: Any) -> None:
        """Checked against the OpenAPI document, so a parameter cannot hide behind a default."""
        spec = app.openapi()
        offenders: list[str] = []
        for path, operations in spec["paths"].items():
            for method, operation in operations.items():
                for parameter in operation.get("parameters", []):
                    folded = parameter["name"].lower().replace("-", "").replace("_", "")
                    if folded in FORBIDDEN_PARAMETERS:
                        offenders.append(f"{method.upper()} {path}: {parameter['name']}")
        assert not offenders, "\n  ".join(offenders)

    def test_no_request_schema_declares_authority(self, app: Any) -> None:
        """The same rule for bodies. A model that declared one would advertise it in OpenAPI."""
        spec = app.openapi()
        offenders: list[str] = []
        for name, schema in spec.get("components", {}).get("schemas", {}).items():
            for field in schema.get("properties", {}):
                folded = field.lower().replace("-", "").replace("_", "")
                if folded in FORBIDDEN_PARAMETERS:
                    offenders.append(f"{name}.{field}")
        assert not offenders, "\n  ".join(offenders)

    @pytest.mark.parametrize(
        "query",
        ["tenantId=other", "roles=administrator", "actAs=someone", "audience=staff"],
    )
    def test_a_self_asserted_query_parameter_is_rejected(self, client: Any, query: str) -> None:
        """**Rejected, not ignored.** A caller must be told the claim did not work."""
        response = client.post(f"/api/customer/v1/sessions?{query}", headers=_identity())
        assert response.status_code == 400
        assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)

    @pytest.mark.parametrize("header", ["X-Tenant-Id", "X-Roles", "X-Act-As", "On-Behalf-Of"])
    def test_a_self_asserted_header_is_rejected(self, client: Any, header: str) -> None:
        response = client.post(
            "/api/customer/v1/sessions", headers={**_identity(), header: "anything"}
        )
        assert response.status_code == 400

    def test_the_gateway_derived_headers_are_not_rejected(self, client: Any) -> None:
        """The closed contract is what the platform consumes; only *client* claims are refused."""
        response = client.post("/api/customer/v1/sessions", headers=_identity())
        assert response.status_code == 201


class TestIdentityIsDerivedNeverParsed:
    """No token is validated at this tier; the Gateway-derived contract is consumed."""

    def test_a_request_without_the_identity_contract_is_unauthenticated(self, client: Any) -> None:
        """401, and no guessed default. An incomplete contract means the Gateway was bypassed."""
        assert client.post("/api/customer/v1/sessions").status_code == 401

    def test_a_malformed_identity_contract_is_unauthenticated(self, client: Any) -> None:
        response = client.post(
            "/api/customer/v1/sessions",
            headers={TENANT_HEADER: "not-a-uuid", PRINCIPAL_HEADER: str(uuid4())},
        )
        assert response.status_code == 401

    def test_no_bearer_token_is_required_or_parsed(self, client: Any) -> None:
        """A request with only the derived headers succeeds; no ``Authorization`` is consulted."""
        assert client.post("/api/customer/v1/sessions", headers=_identity()).status_code == 201

    def test_the_health_check_needs_no_identity(self, client: Any) -> None:
        """A health check that needed identity could not run before identity worked.

        It sits at ``/health/*`` rather than under an audience because of where the caller is: the
        probe comes from the Container Apps infrastructure on the internal network and does not
        traverse APIM, so it carries no identity.
        """
        assert client.get("/health/live").status_code == 200

        # Readiness is REACHED rather than refused, which is what this test is about. Its answer is
        # 503 here because the probe genuinely checks the platform database and this client has
        # none — a served verdict, not a rejection. Asserting 200 would have quietly turned this
        # into a test that readiness performs no dependency check.
        assert client.get("/health/ready").status_code not in (401, 403)


class TestProblemDetails:
    """RFC 9457, in the shape the .NET side emits."""

    def test_an_error_carries_the_full_problem_shape(self, client: Any) -> None:
        response = client.post("/api/customer/v1/sessions")
        body = response.json()
        for field in ("type", "title", "status", "detail", "instance", "correlationId"):
            assert field in body, f"{field} missing from the problem document"

    def test_the_media_type_is_problem_json(self, client: Any) -> None:
        response = client.post("/api/customer/v1/sessions")
        assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)

    def test_a_problem_document_leaks_no_internals(self, client: Any) -> None:
        """No stack trace, no SQL, no provider string, no tenant or principal identifier."""
        body = json.dumps(client.post("/api/customer/v1/sessions").json()).lower()
        for leak in ("traceback", "select ", "psycopg", "sqlalchemy", 'file "'):
            assert leak not in body

    def test_an_unknown_body_field_is_a_400_not_a_silent_drop(self, client: Any) -> None:
        """``extra="forbid"``. A client sending ``treatment`` must be told it is not a field."""
        response = client.post(
            f"/api/customer/v1/work/{uuid4()}/consent",
            headers=_identity(),
            json={"verdict": "granted", "treatment": "AUTO"},
        )
        assert response.status_code == 422


class TestCorrelation:
    """One identifier, accepted at the edge, echoed on every response."""

    def test_a_correlation_identifier_is_echoed(self, client: Any) -> None:
        response = client.post("/api/customer/v1/sessions", headers=_identity())
        assert response.headers["X-Correlation-Id"]

    def test_a_client_supplied_identifier_is_used(self, client: Any) -> None:
        supplied = "journey-42"
        response = client.post(
            "/api/customer/v1/sessions", headers={**_identity(), "X-Correlation-Id": supplied}
        )
        assert response.headers["X-Correlation-Id"] == supplied

    def test_an_oversized_identifier_is_replaced_rather_than_rejected(self, client: Any) -> None:
        """A bad correlation identifier is not worth failing a user's request over."""
        response = client.post(
            "/api/customer/v1/sessions", headers={**_identity(), "X-Correlation-Id": "x" * 500}
        )
        assert response.status_code == 201
        assert response.headers["X-Correlation-Id"] != "x" * 500

    def test_a_refused_request_is_still_correlated(self, client: Any) -> None:
        """Correlation wraps identity, so even a rejection can be traced."""
        response = client.post("/api/customer/v1/sessions?tenantId=other", headers=_identity())
        assert response.status_code == 400
        assert response.headers["X-Correlation-Id"]


class TestTheStreamingEnvelope:
    """Five event kinds, and a stream that carries no authority."""

    def test_the_kinds_are_exactly_the_five_in_the_contract(self) -> None:
        assert {kind.value for kind in streaming.StreamEventKind} == {
            "token",
            "step",
            "interrupt",
            "done",
            "error",
        }

    def test_a_frame_is_well_formed_sse(self) -> None:
        frame = streaming.token("hello")
        assert frame.startswith("event: token\ndata: ")
        assert frame.endswith("\n\n")
        assert json.loads(frame.split("data: ", 1)[1].strip()) == {"text": "hello"}

    def test_an_interrupt_frame_carries_kind_and_identifiers_only(self) -> None:
        """No approval state, no target, no command content, no treatment."""
        frame = streaming.interrupt("approval", "s1", "w1", "c1")
        payload = json.loads(frame.split("data: ", 1)[1].strip())
        assert set(payload) == {"kind", "sessionId", "workItemId", "correlationId"}

    def test_an_error_frame_carries_no_detail_beyond_a_correlation_identifier(self) -> None:
        payload = json.loads(streaming.error("c1").split("data: ", 1)[1].strip())
        assert set(payload) == {"correlationId", "detail"}
        assert "c1" in payload["correlationId"]

    def test_the_message_route_streams(self, client: Any) -> None:
        response = client.post(
            f"/api/customer/v1/sessions/{uuid4()}/messages",
            headers=_identity(),
            json={"content": "my printer is broken"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(streaming.SSE_MEDIA_TYPE)

    def test_the_stream_ends_with_done_rather_than_silence(self, client: Any) -> None:
        """A client must be able to tell 'the turn finished' from 'the connection dropped'."""
        response = client.post(
            f"/api/customer/v1/sessions/{uuid4()}/messages",
            headers=_identity(),
            json={"content": "hello"},
        )
        assert "event: done" in response.text

    def test_buffering_is_disabled(self, client: Any) -> None:
        """A buffering proxy turns a progressive response into a slow one."""
        response = client.post(
            f"/api/customer/v1/sessions/{uuid4()}/messages",
            headers=_identity(),
            json={"content": "hello"},
        )
        assert response.headers["X-Accel-Buffering"] == "no"


class TestTheScaffoldPerformsNothing:
    """Constitution Principle IX: scaffold honestly; do not invent product."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("POST", "/api/customer/v1/work/{id}/consent", {"verdict": "granted"}),
            ("POST", "/api/staff/v1/approvals/{id}/verdict", {"verdict": "approved"}),
            ("POST", "/api/workload/v1/work/{id}/claim", None),
            ("POST", "/api/staff/v1/work/{id}/cancel", None),
        ],
    )
    def test_a_consequential_route_reports_not_implemented(
        self, client: Any, method: str, path: str, body: dict[str, str] | None
    ) -> None:
        """501, not a plausible success.

        A scaffold that appeared to record a consent or a verdict would be worse than one that
        says it cannot: somebody would build against the appearance.
        """
        response = client.request(
            method, path.replace("{id}", str(uuid4())), headers=_identity(), json=body
        )
        assert response.status_code == 501

    def test_the_instruction_route_returns_no_script(self, client: Any) -> None:
        """The catalogue holds only inert reference fixtures; no real script is ever returned."""
        response = client.get(f"/api/customer/v1/work/{uuid4()}/instruction", headers=_identity())
        assert response.status_code == 501
        assert "script" not in response.text.lower()


class TestTenantAdmission:
    """Trusted identity **plus** registry state. Neither alone is admission.

    Exercised directly rather than through a route: no endpoint depends on
    :func:`~ragcore.api.deps.get_tenant` yet, because the container binds no registry until
    Stage 7. Testing it now means the boundary is working code when the adapter arrives, rather
    than code nobody has run.
    """

    async def test_an_unbound_registry_fails_closed(self, app: Any) -> None:
        """No registry, no admission. Never a default of admitted."""
        from fastapi import HTTPException

        from ragcore.api.deps import get_tenant

        # Unbound explicitly, rather than relying on the container's default. Stage 7 binds a real
        # registry, so a test that assumed `None` would silently stop testing the fail-closed path
        # and start testing a database connection instead.
        container = replace(build_container(_settings_for_test()), tenant_registry=None)
        with pytest.raises(HTTPException) as caught:
            await get_tenant(container, _principal())
        assert caught.value.status_code == 503

    async def test_an_unknown_organisation_is_not_admitted(self) -> None:
        """Fails closed: an organisation the registry does not know does not get in."""
        from fastapi import HTTPException

        from ragcore.api.deps import get_tenant

        container = replace(build_container(_settings_for_test()), tenant_registry=_registry(None))
        with pytest.raises(HTTPException) as caught:
            await get_tenant(container, _principal())
        assert caught.value.status_code == 403

    async def test_a_suspended_organisation_is_not_admitted(self) -> None:
        """Registry state is the second half, and it can say no (spec FR-EXEC-003)."""
        from fastapi import HTTPException

        from ragcore.api.deps import get_tenant

        suspended = admitted_tenant(TenantStatus.SUSPENDED)
        container = replace(
            build_container(_settings_for_test()), tenant_registry=_registry(suspended)
        )
        with pytest.raises(HTTPException) as caught:
            await get_tenant(container, _principal())
        assert caught.value.status_code == 403

    async def test_an_active_organisation_is_admitted_with_its_provenance_recorded(self) -> None:
        """The context names where it came from: the end user's own validated identity."""
        from ragcore.api.deps import get_tenant
        from ragcore.domain.tenancy import TenantSource

        expected = admitted_tenant()
        container = replace(
            build_container(_settings_for_test()), tenant_registry=_registry(expected)
        )

        resolved = await get_tenant(container, _principal())

        assert resolved == expected
        assert resolved.source is TenantSource.END_USER_IDENTITY


def _settings_for_test() -> Settings:
    dsn = TypeAdapter(PostgresDsn).validate_python("postgresql://user:pw@localhost/synthia")
    return Settings(database=DatabaseSettings(dsn=dsn))


def _principal() -> AuthenticatedPrincipal:
    """A customer-audience principal, as the Gateway-derived contract would produce."""
    return AuthenticatedPrincipal(
        identity=HumanIdentity(EntraTenantId(uuid4()), PrincipalId(uuid4())),
        roles=RoleSet.of(),
        credential_class=CredentialClass.DELEGATED,
        audience=Audience.CUSTOMER,
        client_surface="web",
    )


def _registry(result: TenantContext | None) -> Any:
    """A tenant registry returning one answer. Satisfies ``TenantRegistryPort``."""

    class _Registry:
        async def admit_end_user(self, entra_tenant_id: object) -> TenantContext | None:
            del entra_tenant_id
            return result

        async def status_for(self, tenant_id: object) -> TenantContext | None:
            del tenant_id
            return result

    return _Registry()
