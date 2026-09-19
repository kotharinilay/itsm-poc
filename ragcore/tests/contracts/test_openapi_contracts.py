"""The published contracts: emitted per audience, disclosing nothing, and guarded against breakage.

Three concerns, and they fail for different reasons so they are tested separately:

* **Emission** — each audience document is generated from the running app and carries only that
  audience's paths and only the schemas those paths reach.
* **Disclosure** — no secret, no credential, no internal-only detail reaches a published document.
* **Authority** — no document offers a client a way to assert tenant, role or audience. Separate
  from disclosure because it is a rule about a *position* rather than a name: the same word is a
  defect in a request and correct in a response.
* **Breakage** — the comparator in ``build/scripts/openapi_diff.py`` must actually detect a breaking
  change. A diff tool that never fails is worse than no diff tool, because it is believed.

The comparator is tested here rather than in a shell script because it is the thing CI trusts. It
runs over **both** stacks' documents, so a defect in it would weaken the rule everywhere at once.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Final

import pytest

from ragcore.api.openapi import (
    AUDIENCES,
    CONTRACT_VERSION,
    audience_document,
    audience_prefix,
    authority_findings,
    disclosure_findings,
)

ROOT: Final = Path(__file__).resolve().parents[3]
CONTRACTS: Final = ROOT / "build" / "contracts"


def _comparator() -> Any:  # noqa: ANN401 — a module object
    """Load the shared comparator by path.

    It lives under ``build/scripts/`` because CI runs it over both stacks' output, and it is not a
    RagCore package. Loading it by path keeps that placement honest rather than moving a shared
    tool into one deployable so a test can import it conveniently.
    """
    path = ROOT / "build" / "scripts" / "openapi_diff.py"
    spec = importlib.util.spec_from_file_location("openapi_diff", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app() -> Any:  # noqa: ANN401 — FastAPI, imported lazily
    """The application, built with settings that need no environment and no vault."""
    from ragcore.api.app import create_app
    from ragcore.config.settings import DatabaseSettings, Settings

    return create_app(
        settings=Settings(
            database=DatabaseSettings(dsn="postgresql://synthia@localhost:5432/synthia"),  # type: ignore[arg-type]
        )
    )


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


class TestEachAudienceEmitsItsOwnDocument:
    """One document per audience. A merged document is prohibited."""

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_document_carries_only_its_own_paths(self, app: Any, audience: str) -> None:
        """The rule the split exists for.

        A merged document would let a customer-facing client enumerate the staff and workload
        surfaces — reconnaissance handed over for free.
        """
        document = audience_document(app, audience)
        prefix = audience_prefix(audience)

        assert document["paths"], f"the {audience} document has no paths"
        for path in document["paths"]:
            assert path.startswith(prefix), f"{path} is not part of the {audience} audience"

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_document_carries_only_reachable_schemas(self, app: Any, audience: str) -> None:
        """Carrying the whole component section would leak the other audiences' models.

        That is the same disclosure the path split prevents, reintroduced one level down where
        nobody looks.
        """
        document = audience_document(app, audience)
        rendered = json.dumps(document)
        declared = set(document.get("components", {}).get("schemas", {}))

        referenced = {part.split('"')[0] for part in rendered.split("#/components/schemas/")[1:]}
        assert referenced <= declared, (
            f"the {audience} document references schemas it does not declare: "
            f"{sorted(referenced - declared)}"
        )

    def test_an_unknown_audience_is_refused(self, app: Any) -> None:
        """A typo would otherwise emit an empty document, reading as a service with no routes."""
        with pytest.raises(ValueError, match="unknown audience"):
            audience_document(app, "admin")

    def test_the_audiences_are_exactly_three(self) -> None:
        """There is no fourth surface, and no combined one."""
        assert AUDIENCES == ("customer", "staff", "workload")

    def test_emission_is_deterministic(self, app: Any) -> None:
        """A document that has not changed produces a byte-identical file.

        Without this the comparator's signal drowns in noise nobody reads, and a real breaking
        change arrives in a diff everyone has learned to skim.
        """
        first = json.dumps(audience_document(app, "customer"), indent=2, sort_keys=True)
        second = json.dumps(audience_document(app, "customer"), indent=2, sort_keys=True)
        assert first == second


# ---------------------------------------------------------------------------
# Disclosure
# ---------------------------------------------------------------------------


class TestAPublishedDocumentDisclosesNothingItMustNot:
    """Secrets, credentials and internal-only detail, each caught by name."""

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_generated_document_is_clean(self, app: Any, audience: str) -> None:
        """The real document, not a constructed one."""
        assert disclosure_findings(audience_document(app, audience)) == []

    @pytest.mark.parametrize(
        "name",
        ["apiKey", "clientSecret", "password", "connectionString", "sharedAccessKey"],
    )
    def test_a_secret_bearing_field_is_caught(self, name: str) -> None:
        """Matched on the name, whatever the field happens to hold today."""
        thing = {"properties": {name: {"type": "string"}}}
        document = {"components": {"schemas": {"Thing": thing}}}
        findings = disclosure_findings(document)
        assert findings, f"{name} was not caught"
        assert "secret-bearing" in findings[0]

    @pytest.mark.parametrize("name", ["outbox", "checkpoint", "langgraph", "stacktrace"])
    def test_internal_implementation_detail_is_caught(self, name: str) -> None:
        """A client that can see these starts depending on them."""
        thing: dict[str, Any] = {"properties": {name: {}}}
        document = {"components": {"schemas": {"Thing": thing}}}
        assert disclosure_findings(document), f"{name} was not caught"

    def test_a_description_mentioning_a_secret_is_not_a_finding(self) -> None:
        """Names are scanned, not prose.

        A document explaining that an operation carries no credential is correct documentation, and
        a scanner that flagged it would get the documentation deleted — which is how the next
        reader loses the explanation of why the rule exists.
        """
        document = {
            "paths": {
                "/api/customer/v1/x": {
                    "get": {"description": "Carries no password, secret or credential."}
                }
            }
        }
        assert disclosure_findings(document) == []


class TestNoDocumentOffersAClientAWayToAssertAuthority:
    """Tenant, roles and audience are derived and never accepted (constitution P-I).

    **This is a position rule, not a name rule**, and the distinction is the whole point. What must
    not exist is a *channel* — somewhere a client can put a value the platform would read. A rule
    that forbade the name everywhere would be satisfied by renaming the field rather than by
    removing the channel, and would meanwhile forbid an audit read model from reporting which
    organisation a record concerns, which is the field a staff reviewer opens it for.
    """

    @pytest.mark.parametrize("name", ["tenantId", "roles", "audience", "actAs"])
    def test_a_parameter_a_client_could_supply_is_caught(self, name: str) -> None:
        """Publishing one advertises exactly what the platform refuses."""
        document = {
            "paths": {
                "/api/customer/v1/x": {"get": {"parameters": [{"name": name, "in": "query"}]}}
            }
        }
        findings = authority_findings(document, "customer")
        assert findings, f"{name} was not caught"
        assert "client-suppliable authority" in findings[0]

    @pytest.mark.parametrize("where", ["query", "header", "path"])
    def test_it_is_caught_wherever_the_parameter_sits(self, where: str) -> None:
        """A header is as much a channel as a query string, and easier to forget."""
        document = {
            "paths": {
                "/api/customer/v1/x": {"get": {"parameters": [{"name": "tenantId", "in": where}]}}
            }
        }
        assert authority_findings(document, "customer"), f"{where} was not caught"

    def test_a_request_body_field_is_caught(self) -> None:
        """A body is the channel a parameter check on its own would miss."""
        document = {
            "paths": {
                "/api/customer/v1/x": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Body"}
                                }
                            }
                        }
                    }
                }
            },
            "components": {"schemas": {"Body": {"properties": {"tenantId": {"type": "string"}}}}},
        }
        assert authority_findings(document, "customer")

    def test_it_is_caught_through_a_nested_reference(self) -> None:
        """The same channel one level down — exactly where a shallow check stops looking."""
        document = {
            "paths": {
                "/api/customer/v1/x": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Outer"}
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "Outer": {"properties": {"inner": {"$ref": "#/components/schemas/Inner"}}},
                    "Inner": {"properties": {"roles": {"type": "array"}}},
                }
            },
        }
        assert authority_findings(document, "customer")

    def test_a_response_field_is_not_a_finding(self) -> None:
        """The organisation a row belongs to, reported to a caller already entitled to the row.

        Forbidding this would force a read model to hide the fact a staff reviewer is reading it
        for, and would be satisfied by renaming the field rather than by closing a channel.
        """
        document = {
            "paths": {
                "/api/staff/v1/x": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Row"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {"schemas": {"Row": {"properties": {"tenantId": {"type": "string"}}}}},
        }
        assert authority_findings(document, "staff") == []

    def test_the_staff_narrowing_is_permitted(self) -> None:
        """``tenantId`` as a staff query filter selects *within* the caller's existing scope.

        It reaches the query as one more ``WHERE`` clause underneath the global scope filter, so a
        caller naming an organisation outside their scope receives no rows rather than that
        organisation's rows (contracts §README).
        """
        document = {
            "paths": {
                "/api/staff/v1/views/audit": {
                    "get": {"parameters": [{"name": "tenantId", "in": "query"}]}
                }
            }
        }
        assert authority_findings(document, "staff") == []

    @pytest.mark.parametrize("audience", ["customer", "workload"])
    def test_the_narrowing_is_permitted_on_staff_and_nowhere_else(self, audience: str) -> None:
        """The exception is scoped, or it is not an exception."""
        document = {
            "paths": {
                f"/api/{audience}/v1/x": {
                    "get": {"parameters": [{"name": "tenantId", "in": "query"}]}
                }
            }
        }
        assert authority_findings(document, audience), f"{audience} was not caught"

    def test_the_narrowing_is_permitted_only_as_a_query_parameter(self) -> None:
        """Even on staff. A header or a body is a different channel with a familiar name."""
        document = {
            "paths": {
                "/api/staff/v1/x": {"get": {"parameters": [{"name": "tenantId", "in": "header"}]}}
            }
        }
        assert authority_findings(document, "staff")

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_generated_document_offers_no_such_channel(self, app: Any, audience: str) -> None:
        """The real document, not a constructed one."""
        assert authority_findings(audience_document(app, audience), audience) == []


# ---------------------------------------------------------------------------
# Breakage
# ---------------------------------------------------------------------------


def _document(**paths: Any) -> dict[str, Any]:  # noqa: ANN401
    return {"openapi": "3.1.0", "info": {"title": "t", "version": "v1"}, "paths": paths}


_SIMPLE: Final[dict[str, Any]] = _document(
    **{
        "/api/customer/v1/things": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "required": ["id"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "note": {"type": "string"},
                                    "kind": {"type": "string", "enum": ["a", "b"]},
                                },
                            }
                        }
                    }
                },
                "responses": {"201": {}},
            },
        }
    }
)


class TestTheComparatorDetectsBreakingChanges:
    """A diff tool that never fails is worse than none, because it is believed."""

    def test_an_identical_document_is_clean(self) -> None:
        breaking, additive = _comparator().compare(_SIMPLE, json.loads(json.dumps(_SIMPLE)))
        assert breaking == []
        assert additive == []

    def test_removing_an_operation_is_breaking(self) -> None:
        """Every client of it stops working."""
        current = json.loads(json.dumps(_SIMPLE))
        del current["paths"]["/api/customer/v1/things"]["post"]
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("operation removed" in finding for finding in breaking)

    def test_removing_a_response_field_is_breaking(self) -> None:
        """A client reading it gets nothing, silently."""
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        del schema["properties"]["name"]
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("response field removed" in finding for finding in breaking)

    def test_making_an_optional_request_field_required_is_breaking(self) -> None:
        """Requests that used to succeed start failing."""
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        schema["required"].append("note")
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("now required" in finding for finding in breaking)

    def test_removing_a_request_enum_value_is_breaking(self) -> None:
        """A value the client may already be sending stops being accepted."""
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        schema["properties"]["kind"]["enum"] = ["a"]
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("enum value removed" in finding for finding in breaking)

    def test_changing_a_field_type_is_breaking(self) -> None:
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        schema["properties"]["id"]["type"] = "integer"
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("type changed" in finding for finding in breaking)

    def test_removing_a_response_code_is_breaking(self) -> None:
        current = json.loads(json.dumps(_SIMPLE))
        del current["paths"]["/api/customer/v1/things"]["post"]["responses"]["201"]
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("response" in finding and "removed" in finding for finding in breaking)

    def test_adding_a_required_parameter_is_breaking(self) -> None:
        current = json.loads(json.dumps(_SIMPLE))
        current["paths"]["/api/customer/v1/things"]["get"]["parameters"] = [
            {"in": "query", "name": "since", "required": True}
        ]
        breaking, _ = _comparator().compare(_SIMPLE, current)
        assert any("required parameter added" in finding for finding in breaking)

    def test_adding_an_operation_is_additive(self) -> None:
        """A client that does not call it is unaffected."""
        current = json.loads(json.dumps(_SIMPLE))
        current["paths"]["/api/customer/v1/things"]["delete"] = {"responses": {"204": {}}}
        breaking, additive = _comparator().compare(_SIMPLE, current)
        assert breaking == []
        assert any("operation added" in finding for finding in additive)

    def test_adding_an_optional_request_field_is_additive(self) -> None:
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["post"]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        schema["properties"]["extra"] = {"type": "string"}
        breaking, additive = _comparator().compare(_SIMPLE, current)
        assert breaking == []
        assert any("optional request field added" in finding for finding in additive)

    def test_adding_a_response_field_is_additive(self) -> None:
        """A client ignoring what it does not recognise keeps working."""
        current = json.loads(json.dumps(_SIMPLE))
        schema = current["paths"]["/api/customer/v1/things"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        schema["properties"]["added"] = {"type": "string"}
        breaking, additive = _comparator().compare(_SIMPLE, current)
        assert breaking == []
        assert any("response field added" in finding for finding in additive)


# ---------------------------------------------------------------------------
# The committed baselines
# ---------------------------------------------------------------------------


class TestTheCommittedContractsAreCurrent:
    """The artifacts in the repository describe the service as it is now."""

    @pytest.mark.parametrize("audience", AUDIENCES)
    def test_the_committed_document_matches_the_generated_one(
        self, app: Any, audience: str
    ) -> None:
        """Regenerate with ``scripts/emit_contracts.py --out ../build/contracts/ragcore``.

        A stale baseline is worse than none: the comparator would pass a breaking change because the
        thing it compares against already contains it.
        """
        committed = CONTRACTS / "ragcore" / f"{audience}.{CONTRACT_VERSION}.openapi.json"
        assert committed.is_file(), f"no committed contract for {audience}; emit and commit it"

        expected = json.dumps(
            audience_document(app, audience), indent=2, sort_keys=True, ensure_ascii=False
        )
        assert committed.read_text(encoding="utf-8").rstrip("\n") == expected, (
            f"the committed {audience} contract is stale. Re-emit it and commit the result."
        )

    def test_every_audience_has_a_committed_contract(self) -> None:
        """A missing artifact means an unpublished API, which is a decision, not an oversight."""
        for audience in AUDIENCES:
            assert (CONTRACTS / "ragcore" / f"{audience}.{CONTRACT_VERSION}.openapi.json").is_file()
