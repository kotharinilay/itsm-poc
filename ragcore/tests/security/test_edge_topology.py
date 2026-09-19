"""The edge topology, asserted as configuration rather than as a diagram.

    client → Front Door + WAF → APIM → Container Apps (internal ingress) → RagCore / .NET

``test_edge_trust_policy.py`` asserts the **controls** on that chain — the closed
identity contract, no token parsing, no direct service-to-service route. This file asserts the
**shape**: that every hop is configured to exist, that traffic can only enter at the front, and that
what APIM routes where is a reviewable fact rather than a sentence in a document.

**Why routing deserves its own tests.** A misrouted path does not fail loudly. ``/views/...``
delivered to RagCore instead of the monolith reaches a service that serves the audience but not the
route, and returns a 404 indistinguishable from a client calling something that does not exist. The
same is true of an OpenAPI document imported from a hand-written copy: it works, right up until it
describes a route the service does not have.

**Nothing here needs Azure.** These read committed configuration, so the boundary is checked on
every pull request rather than only after a deployment — which matters because a deployed
environment is the scaffold's longest-lead dependency, and a control that can only be checked there
is one that goes unchecked until then.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

pytestmark = pytest.mark.security

ROOT: Final = Path(__file__).resolve().parents[3]
APIS_PATH: Final = ROOT / "build" / "infra" / "apim" / "apis.json"
EDGE_TRUST_PATH: Final = ROOT / "build" / "policy" / "edge-trust.json"
FRONT_DOOR_PATH: Final = ROOT / "build" / "infra" / "frontdoor" / "front-door.json"
GLOBAL_POLICY: Final = ROOT / "build" / "infra" / "apim" / "global.inbound.xml"

AUDIENCES: Final = ("customer", "staff", "workload")


def _load(path: Path) -> dict[str, Any]:
    assert path.is_file(), f"missing committed configuration: {path}"
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(scope="module")
def apis() -> dict[str, Any]:
    """The APIM API and backend definitions."""
    return _load(APIS_PATH)


@pytest.fixture(scope="module")
def edge_trust() -> dict[str, Any]:
    """The shared edge trust registry both stacks read."""
    return _load(EDGE_TRUST_PATH)


@pytest.fixture(scope="module")
def front_door() -> dict[str, Any]:
    """The public edge definition."""
    return _load(FRONT_DOOR_PATH)


class TestThePublicEdgeIsFrontDoorAndOnlyFrontDoor:
    """Requirement 1 and 4: one way in, and the applications are not it."""

    def test_the_chain_runs_client_to_front_door_to_apim_to_backend(
        self, edge_trust: dict[str, Any]
    ) -> None:
        """Three hops, in order. A missing middle hop is a topology where something is reachable
        that should not be."""
        assert [hop["id"] for hop in edge_trust["chain"]["hops"]] == [
            "client-to-frontdoor",
            "frontdoor-to-apim",
            "apim-to-backend",
        ]

    def test_every_edge_route_targets_a_declared_origin_group(
        self, front_door: dict[str, Any]
    ) -> None:
        """Which origin groups may exist is asserted in ``test_edge_trust_policy.py``. This is the
        other half, and the one a new route would break: a route pointing at something undeclared
        is a public path with no reviewed target, and in a portal it looks like an ordinary
        routing entry.
        """
        groups = {group["name"] for group in front_door["originGroups"]}

        for route in front_door["routes"]:
            assert route["originGroup"] in groups, (
                f"edge route {route['name']!r} targets {route['originGroup']!r}, "
                "which is not a declared origin group"
            )

    def test_each_route_sits_on_its_own_endpoint(self, front_door: dict[str, Any]) -> None:
        """The API and the two portals are separate host names, and each serves one thing.

        The isolation ADR-0009 buys is the browser's: separate origins mean separate storage,
        cookies and script context for the customer and staff surfaces. A route attaching a portal
        group to the API endpoint — or the gateway to a portal endpoint — would collapse that while
        every other assertion here still passed.
        """
        endpoints = {endpoint["name"] for endpoint in front_door["endpoints"]}
        assert endpoints == {"synthia-api", "synthia-customer-portal", "synthia-staff-portal"}

        expected = {
            "synthia-api": "apim",
            "synthia-customer-portal": "customer-portal",
            "synthia-staff-portal": "staff-portal",
        }
        for route in front_door["routes"]:
            assert expected[route["endpoint"]] == route["originGroup"], (
                f"route {route['name']!r} attaches {route['originGroup']!r} to "
                f"{route['endpoint']!r}, which serves a different surface"
            )

    def test_one_waf_policy_covers_every_endpoint(self, front_door: dict[str, Any]) -> None:
        """A public host with no WAF in front of it is the one an attacker picks.

        One policy rather than one per endpoint: two policies drift, and the portal hosts would be
        the pair nobody upgraded.
        """
        policies = front_door["securityPolicies"]
        assert len(policies) == 1

        covered = set(policies[0]["endpoints"])
        declared = {endpoint["name"] for endpoint in front_door["endpoints"]}
        assert covered == declared, f"endpoints with no WAF: {sorted(declared - covered)}"

    def test_the_edge_publishes_the_audience_prefixes_and_no_wildcard(
        self, front_door: dict[str, Any]
    ) -> None:
        """A ``/*`` pattern **on the gateway endpoint** would publish whatever APIM happens to
        expose today and whatever it is given tomorrow — including an API somebody added for an
        internal purpose.

        The portal endpoints do carry ``/*``, and that is not the same claim: behind them is a
        directory of static files, and a single-page application must answer every deep link with
        its index document. What they must never carry is an ``/api`` path, asserted in
        ``test_edge_trust_policy.py`` and by ``check-edge-path.sh``.
        """
        gateway_patterns = [
            pattern
            for route in front_door["routes"]
            if route["originGroup"] == "apim"
            for pattern in route["patternsToMatch"]
        ]
        patterns = gateway_patterns

        assert patterns, "the edge publishes no gateway route at all"
        assert "/*" not in gateway_patterns
        for audience in AUDIENCES:
            assert any(
                f"/api/{audience}".startswith(pattern.rstrip("*")) for pattern in patterns
            ), f"no edge route matches the {audience!r} audience prefix"

    def test_every_edge_route_is_https_only(self, front_door: dict[str, Any]) -> None:
        """The identity contract and the correlation identifier both travel over this hop."""
        for route in front_door["routes"]:
            assert route["supportedProtocols"] == ["Https"]
            assert route["forwardingProtocol"] == "HttpsOnly"

    def test_no_container_app_is_publicly_reachable(self) -> None:
        """The network half of "public application APIs are not directly exposed". External ingress
        on either application would make the gateway advisory."""
        manifests = sorted((ROOT / "build" / "docker" / "containerapps").glob("*.yaml"))

        assert manifests, "no container app manifests found"
        for manifest in manifests:
            text = manifest.read_text(encoding="utf-8")
            assert "external: false" in text, f"{manifest.name} does not declare internal ingress"
            assert "external: true" not in text, f"{manifest.name} declares external ingress"


class TestTheWafProtectsThePublicEdge:
    """Requirement 2. A WAF in detection mode is a dashboard, not a control.

    Read from the fields rather than by searching the document, because every one of these words
    also appears in the prose explaining why it was chosen — and a check that a word appears
    somewhere would pass against a document that had been switched to Detection with the
    explanation left in place.
    """

    def test_the_waf_is_enabled_and_in_prevention_mode(self, front_door: dict[str, Any]) -> None:
        settings = front_door["wafPolicy"]["policySettings"]

        assert settings["enabledState"] == "Enabled"
        assert settings["mode"] == "Prevention", (
            "the WAF is in Detection mode, which writes reports about the attacks it allowed"
        )

    def test_a_managed_rule_set_is_named_with_a_version_and_blocks(
        self, front_door: dict[str, Any]
    ) -> None:
        """Named and versioned, so a rule-set upgrade is a decision rather than a surprise; and the
        default set blocks, because a rule set that does not act is one more report nobody reads."""
        rule_sets = front_door["wafPolicy"]["managedRuleSets"]

        assert rule_sets, "the WAF applies no managed rule set"
        for rule_set in rule_sets:
            assert rule_set["ruleSetType"]
            assert rule_set["ruleSetVersion"]

        default = next(
            rule_set
            for rule_set in rule_sets
            if rule_set["ruleSetType"] == "Microsoft_DefaultRuleSet"
        )
        assert default["ruleSetAction"] == "Block"

    def test_the_edge_makes_a_forged_identity_attempt_visible(
        self, front_door: dict[str, Any], edge_trust: dict[str, Any]
    ) -> None:
        """Defence in depth for requirement 7, and **deliberately not the control**.

        APIM deletes every inbound copy of the contract unconditionally. The backend-side half —
        refusing a request that could not prove gateway provenance — is deferred (ADR 0008) and was
        not replaced, so this rule now sits behind one control rather than two. What it adds is
        that an attempt is *visible* at the outermost layer, in the WAF log, before it has consumed
        anything further in.

        **It matches one header rather than all five, by design.** A caller forging identity sends
        the tenant, and matching the whole set here would put a second copy of the contract in a
        file nobody reviews beside the policy — with edge-trust.json as the single authoritative
        one. What is asserted instead is below: that the header it names is a real member of that
        contract.
        """
        rules = front_door["wafPolicy"]["customRules"]
        forging = [
            rule
            for rule in rules
            if rule["action"] == "Block"
            and any(
                condition.get("matchVariable") == "RequestHeader"
                and str(condition.get("selector", "")).startswith("X-Idp-")
                for condition in rule.get("matchConditions", [])
            )
        ]

        assert forging, "no edge rule blocks a self-asserted identity header"

    def test_the_header_the_edge_rule_names_is_part_of_the_contract(
        self, front_door: dict[str, Any], edge_trust: dict[str, Any]
    ) -> None:
        """**The failure this catches is a typo, and a typo here is silent.**

        A selector naming ``X-Idp-TenantId`` matches nothing. The rule deploys, the portal shows it
        enabled, the WAF log stays empty — and empty is indistinguishable from "nobody is trying".
        The contract is versioned in one place, so a renamed header must reach this rule too.
        """
        contract = set(edge_trust["identityContract"]["headers"])
        selectors = {
            condition["selector"]
            for rule in front_door["wafPolicy"]["customRules"]
            for condition in rule.get("matchConditions", [])
            if condition.get("matchVariable") == "RequestHeader" and "selector" in condition
        }

        assert selectors, "no edge rule inspects a request header"
        assert selectors <= contract, (
            f"an edge rule matches {sorted(selectors - contract)}, which is not part of the "
            f"identity contract {sorted(contract)}. A selector naming no real header matches "
            "nothing and fails silently."
        )

    def test_the_edge_rate_limits_before_a_request_costs_gateway_capacity(
        self, front_door: dict[str, Any]
    ) -> None:
        """A ceiling on an anonymous flood, and not the authorization control. APIM limits again per
        organisation, and neither is a substitute for the other."""
        limits = [
            rule
            for rule in front_door["wafPolicy"]["customRules"]
            if rule["ruleType"] == "RateLimitRule"
        ]

        assert limits, "the public edge applies no rate limit"
        for limit in limits:
            assert limit["action"] == "Block"
            assert limit["rateLimitThreshold"] > 0


class TestApimIsTheOnlyPathToABackend:
    """Requirements 3 and 4, from the configuration rather than the prose."""

    def test_every_backend_is_a_container_app_with_internal_ingress(
        self, apis: dict[str, Any]
    ) -> None:
        """Each backend names the manifest it routes to, so the claim is checkable rather than
        asserted."""
        for backend in apis["backends"]:
            manifest = ROOT / backend["containerApp"]
            assert manifest.is_file(), f"{backend['id']} names a manifest that does not exist"
            assert "external: false" in manifest.read_text(encoding="utf-8")

    def test_every_api_routes_to_a_declared_backend(self, apis: dict[str, Any]) -> None:
        declared = {backend["id"] for backend in apis["backends"]}

        for api in apis["apis"]:
            assert api["backend"] in declared, f"{api['id']} routes to an undeclared backend"


class TestRoutingCoversEveryAudienceAndNothingElse:
    """Requirement 10, and the rule that is invisible when it is wrong."""

    def test_every_audience_in_the_registry_has_at_least_one_api(
        self, apis: dict[str, Any], edge_trust: dict[str, Any]
    ) -> None:
        """The registry and the routing table must name the same audiences. An audience with a
        policy and no route is a policy that never runs."""
        routed = {api["audience"] for api in apis["apis"]}
        registered = {audience["id"] for audience in edge_trust["audiences"]}

        assert routed == registered == set(AUDIENCES)

    def test_every_api_path_matches_its_audience_prefix(
        self, apis: dict[str, Any], edge_trust: dict[str, Any]
    ) -> None:
        """The path prefix decides the authorization model (spec FR-SURF-005), so an API whose path
        disagrees with its audience would derive the wrong identity for every request it served."""
        prefixes = {
            audience["id"]: audience["pathPrefix"].lstrip("/")
            for audience in edge_trust["audiences"]
        }

        for api in apis["apis"]:
            expected = prefixes[api["audience"]]
            assert api["path"].startswith(expected), (
                f"{api['id']} is on path {api['path']!r} but claims the {api['audience']!r} "
                f"audience, whose prefix is {expected!r}"
            )

    def test_the_read_views_route_to_the_read_only_deployable(self, apis: dict[str, Any]) -> None:
        """``/views/`` is the monolith's half of an audience (ADR-0001, contracts README). Routing a
        view to RagCore returns a 404 that looks exactly like a client error."""
        for api in apis["apis"]:
            if api["path"].endswith("/views"):
                assert api["backend"] == "monolith", (
                    f"{api['id']} serves read views from {api['backend']!r}; "
                    "the monolith owns reads"
                )

    def test_no_view_route_exists_on_a_deployable_that_writes(self, apis: dict[str, Any]) -> None:
        """The converse: RagCore serves no ``/views`` prefix."""
        for api in apis["apis"]:
            if api["backend"] == "ragcore":
                assert not api["path"].endswith("/views")

    def test_each_audience_uses_one_policy_for_every_backend_serving_it(
        self, apis: dict[str, Any]
    ) -> None:
        """Identity is derived per AUDIENCE, not per deployable. Two policies for one audience would
        be two places for the derivation to drift, and the drift appears as one backend seeing a
        role the other did not."""
        by_audience: dict[str, set[str]] = {}
        for api in apis["apis"]:
            by_audience.setdefault(api["audience"], set()).add(api["policy"])

        for audience, policies in by_audience.items():
            assert len(policies) == 1, f"{audience} derives identity in {len(policies)} places"

    def test_every_named_policy_file_exists_and_derives_identity(
        self, apis: dict[str, Any]
    ) -> None:
        for api in apis["apis"]:
            policy = ROOT / api["policy"]
            assert policy.is_file(), f"{api['id']} names a policy that does not exist"
            assert "X-Idp-Tenant-Id" in policy.read_text(encoding="utf-8")


class TestEveryDocumentIsGeneratedAndNotHandWritten:
    """Requirement 12 (spec FR-DEMO-013, contracts README rule 5)."""

    def test_every_api_imports_a_document_that_exists(self, apis: dict[str, Any]) -> None:
        """An API pointing at a missing document imports nothing and publishes an empty surface."""
        for api in apis["apis"]:
            document = ROOT / api["openApi"]["source"]
            assert document.is_file(), (
                f"{api['id']} imports {api['openApi']['source']}, which is not present. "
                "Documents are emitted from the running services by the contract workflow."
            )

    def test_no_api_declares_a_hand_written_document(self, apis: dict[str, Any]) -> None:
        for api in apis["apis"]:
            assert api["openApi"]["handWritten"] is False
            assert api["openApi"]["generatedBy"], f"{api['id']} does not say what generated it"

    def test_every_imported_document_is_valid_openapi_for_its_audience(
        self, apis: dict[str, Any]
    ) -> None:
        """Parsed rather than merely present. A truncated or empty document is worse than a missing
        one: it imports cleanly and publishes a surface nobody meant to publish."""
        for api in apis["apis"]:
            document = json.loads((ROOT / api["openApi"]["source"]).read_text(encoding="utf-8"))

            assert document.get("openapi", "").startswith("3."), f"{api['id']}: not OpenAPI 3"
            assert document.get("paths"), f"{api['id']}: the document declares no paths"

    def test_no_document_merges_two_audiences(self, apis: dict[str, Any]) -> None:
        """A merged document would let a customer-facing client discover the staff and workload
        surfaces. Asserted against the paths the document actually declares."""
        for api in apis["apis"]:
            document = json.loads((ROOT / api["openApi"]["source"]).read_text(encoding="utf-8"))
            foreign = {other for other in AUDIENCES if other != api["audience"]}

            for path in document["paths"]:
                for other in foreign:
                    assert f"/api/{other}/" not in path, (
                        f"{api['id']} publishes {path!r}, which belongs to the {other!r} audience"
                    )

    def test_every_emitted_document_is_imported_by_some_api(self, apis: dict[str, Any]) -> None:
        """The converse, and the one that catches a surface published by accident: a document the
        contract workflow emits and no API imports is a route nobody routed — or a route somebody
        expected to be reachable and is not."""
        emitted = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in (ROOT / "build" / "contracts").rglob("*.openapi.json")
        }
        imported = {api["openApi"]["source"] for api in apis["apis"]}

        assert emitted == imported, (
            f"emitted but not routed: {sorted(emitted - imported)}; "
            f"routed but not emitted: {sorted(imported - emitted)}"
        )


class TestTheRateAndBudgetBoundaryIsPerOrganisation:
    """Requirement 11 (spec FR-OPS-005)."""

    def test_a_global_rate_limit_bounds_an_anonymous_flood(self) -> None:
        """Before any token is validated, which is when it is needed and why it cannot be
        per-organisation — there is no organisation yet."""
        assert "rate-limit-by-key" in GLOBAL_POLICY.read_text(encoding="utf-8")

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_each_audience_limits_and_budgets_per_organisation(self, audience: str) -> None:
        """Counting by IP cannot do this: one organisation behind one NAT is one IP, and fifty
        users of another are fifty."""
        policy = (ROOT / "build" / "infra" / "apim" / f"{audience}.v1.xml").read_text(
            encoding="utf-8"
        )

        assert "rate-limit-by-key" in policy, f"{audience} applies no per-organisation rate limit"
        assert "quota-by-key" in policy, f"{audience} applies no per-organisation quota"

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_counter_key_is_the_derived_identity(self, audience: str) -> None:
        """**The control, not a detail.** A budget keyed on anything a caller supplies is a budget
        a caller escapes by changing it. ``X-Idp-Tenant-Id`` is derived by this very policy, after
        the global one deleted every inbound copy."""
        policy = (ROOT / "build" / "infra" / "apim" / f"{audience}.v1.xml").read_text(
            encoding="utf-8"
        )

        for limit in ("rate-limit-by-key", "quota-by-key"):
            start = policy.index(f"<{limit}")
            block = policy[start : policy.index("/>", start)]
            assert "X-Idp-Tenant-Id" in block, (
                f"{audience}: {limit} does not count against the derived organisation"
            )

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_limit_is_applied_after_identity_is_derived(self, audience: str) -> None:
        """Ordering is what makes the counter key trustworthy. Applied earlier, the header would be
        either absent or whatever the caller sent."""
        policy = (ROOT / "build" / "infra" / "apim" / f"{audience}.v1.xml").read_text(
            encoding="utf-8"
        )

        assert policy.index('set-header name="X-Idp-Tenant-Id"') < policy.index(
            "<rate-limit-by-key"
        )

    def test_the_registry_records_both_levels(self, apis: dict[str, Any]) -> None:
        boundary = apis["rateBoundary"]

        assert boundary["global"]["counterKey"] == "client IP"
        assert {entry["audience"] for entry in boundary["perOrganisation"]} == set(AUDIENCES)
        for entry in boundary["perOrganisation"]:
            assert entry["counterKey"] == "X-Idp-Tenant-Id"

    def test_the_token_budget_is_separate_and_elsewhere(self, apis: dict[str, Any]) -> None:
        """Request volume and model spend fail for different reasons and at different rates, so they
        are metered at different boundaries."""
        token_budget = apis["rateBoundary"]["tokenBudget"]

        assert (ROOT / token_budget["definedIn"]).is_file()
        assert token_budget["policy"] == "llm-token-limit"


class TestNoBackendSharedSecretExists:
    """The managed-identity requirement, and the one named exemption."""

    def test_no_backend_authenticates_with_a_shared_secret(self, apis: dict[str, Any]) -> None:
        """A credential the application holds is one that can be exfiltrated and replayed."""
        forbidden = {
            "key",
            "apiKey",
            "api_key",
            "sharedSecret",
            "clientSecret",
            "password",
            "sasToken",
            "authorizationHeader",
        }

        for backend in apis["backends"]:
            credentials = backend.get("credentials") or {}
            assert not forbidden & set(credentials), (
                f"{backend['id']} holds a shared secret: {sorted(forbidden & set(credentials))}"
            )

    def test_no_backend_holds_a_credential_at_all(self, apis: dict[str, Any]) -> None:
        """APIM presents nothing on the backend connection, and that is the *deferred* state.

        The client certificate this test used to pin is deferred in full (ADR 0008) and nothing
        replaced it. This asserts the absence rather than leaving it unstated, because the failure
        mode of a deferral is somebody quietly filling the gap with the first thing to hand — a
        shared secret, an API key, a bearer header — and calling it equivalent.
        """
        for backend in apis["backends"]:
            assert "credentials" not in backend, (
                f"{backend['id']} declares a backend credential. Gateway-to-backend provenance is "
                "deferred (docs/adr/0008-defer-certificate-based-gateway-to-backend-provenance.md) "
                "and re-introducing one requires that decision to be revisited first."
            )

    def test_no_azure_resource_exemption_remains_for_the_backend_hop(self) -> None:
        """The exemption existed only because the hop used a client certificate.

        With the certificate deferred, the platform is back to managed identity everywhere it is
        supported and there is nothing left to exempt. A new entry here means somebody introduced
        a standing credential; it needs the same review the old one had.
        """
        policy = _load(ROOT / "build" / "policy" / "azure-identity.json")
        exemptions = [entry for entry in policy["exemptions"] if "resource" in entry]

        assert exemptions == [], (
            "an Azure identity exemption has appeared. Each one is a credential with a lifecycle "
            f"living outside managed identity: {[e['resource'] for e in exemptions]}"
        )

    def test_no_api_requires_a_subscription_key(self, apis: dict[str, Any]) -> None:
        """A subscription key is a shared secret distributed to clients. It grants nothing this
        platform needs — callers are authenticated by an Entra token — and it is the credential that
        ends up in a front-end bundle."""
        for api in apis["apis"]:
            assert api["subscriptionRequired"] is False

    def test_no_named_value_is_a_credential(self, apis: dict[str, Any]) -> None:
        """Each is an address, an entity id or a number. The security suite scans this file for
        credential shapes; this asserts the intent alongside it."""
        for name, entry in apis["namedValues"].items():
            if name.startswith("$"):
                continue
            assert entry["source"] == "deployment"
            assert entry["why"], f"{name} does not say what it is for"


class TestCorrelationOriginatesAtTheEdge:
    """Requirement 9 (spec FR-OPS-001)."""

    def test_the_gateway_establishes_a_correlation_identifier(self) -> None:
        """Accepted from the caller when present so a client-initiated journey stays one journey;
        minted otherwise, so a refusal is still correlatable."""
        policy = GLOBAL_POLICY.read_text(encoding="utf-8")

        assert "X-Correlation-Id" in policy
        assert "context.RequestId" in policy

    def test_correlation_is_established_before_anything_can_refuse_the_request(self) -> None:
        """A refusal a user can quote is one somebody can find. Established after the refusal paths
        would leave the most interesting requests uncorrelated.

        Anchored on the rate limiter, which is the last inbound element that can refuse a request.
        It previously anchored on the client certificate APIM attached; that element is gone with
        the deferred mechanism (ADR 0008), and an assertion whose anchor has vanished would pass
        vacuously rather than fail.
        """
        policy = GLOBAL_POLICY.read_text(encoding="utf-8")
        inbound = policy[policy.index("<inbound>") : policy.index("</inbound>")]

        assert inbound.index("X-Correlation-Id") < inbound.index("<rate-limit-by-key")

    def test_the_identifier_is_echoed_on_the_response(self) -> None:
        policy = GLOBAL_POLICY.read_text(encoding="utf-8")
        outbound = policy[policy.index("<outbound>") :]

        assert "X-Correlation-Id" in outbound
