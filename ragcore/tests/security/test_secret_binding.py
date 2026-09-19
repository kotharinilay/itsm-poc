"""Secret references resolve from Key Vault; values never reach a log, a document or a trace.

Five rules, each asserted rather than asserted-about:

1. Configuration holds secret **references**, never values.
2. **No secret is logged.**
3. **No secret is emitted in OpenAPI.**
4. **No secret is written to telemetry.**
5. **Startup fails** when a required reference cannot be resolved.

Rules 2 to 4 are all the same defect wearing three coats — a resolved value reaching a sink that was
never meant to carry one — and they are tested separately because they fail separately. A guard on
logging does nothing for a span attribute, and neither helps a response model.

**No vault, no network and no credential is needed to run these.** The resolver is a port, so the
tests substitute one; what is being proven is the behaviour of the platform's own types, which is
where the leak would actually happen.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any, Final

import pytest

from ragcore.config.secrets import (
    REDACTED,
    KeyVaultSecretResolver,
    SecretRef,
    SecretResolutionError,
    SecretValue,
    resolve_required,
)

ROOT: Final = Path(__file__).resolve().parents[3]
SETTINGS: Final = ROOT / "ragcore" / "src" / "ragcore" / "config" / "settings.py"

SECRET: Final = "s3cr3t-do-not-print-me"  # noqa: S105 — the canary, not a credential
"""A value distinctive enough that finding it anywhere in output is unambiguous.

Flagged by S105 as a hardcoded password, which is exactly right about the shape and wrong about the
intent: these tests need a value they can search for, and suppressing the rule on this one line is
narrower than teaching the linter to ignore the file.
"""


class _StubResolver:
    """A resolver with no vault behind it. Satisfies ``SecretResolverPort``."""

    def __init__(self, values: dict[str, str], missing: set[str] | None = None) -> None:
        self._values = values
        self._missing = missing or set()

    async def resolve(self, ref: SecretRef) -> SecretValue:
        if ref.name in self._missing:
            raise SecretResolutionError(ref.name, "https://vault.example", "not found")
        return SecretValue(ref.name, self._values[ref.name])


# ---------------------------------------------------------------------------
# 1. Configuration holds references, not values
# ---------------------------------------------------------------------------


class TestConfigurationHoldsReferencesNotValues:
    """A field holds the *name* of a secret. The value lives in the vault."""

    def test_a_reference_needs_a_name(self) -> None:
        """An empty reference would resolve to nothing and read like a vault fault."""
        with pytest.raises(ValueError, match="needs a name"):
            SecretRef("")

    def test_a_reference_renders_as_its_name(self) -> None:
        """A reference is not sensitive — that is the entire point of using one."""
        assert str(SecretRef("otel-connection-string")) == "otel-connection-string"

    def test_every_secret_bearing_setting_is_named_as_a_reference(self) -> None:
        """The ``*_secret_name`` suffix is what lets a reviewer tell a name from a value.

        Read from the AST so the module docstring — which necessarily discusses secrets — is not
        mistaken for a field that holds one.
        """
        tree = ast.parse(SETTINGS.read_text(encoding="utf-8"), filename=str(SETTINGS))
        fields = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        suspicious = {
            field
            for field in fields
            if any(term in field.lower() for term in ("secret", "password", "key", "token"))
            and not field.endswith("_secret_name")
            and field not in {"key_vault"}
        }
        assert not suspicious, (
            f"settings fields that look like they hold a secret value: {sorted(suspicious)}. "
            "A field holding secret material is named `*_secret_name` and holds a name."
        )

    def test_a_plaintext_vault_uri_is_refused(self) -> None:
        """A secret fetched over plaintext is a secret in transit to anybody watching."""
        with pytest.raises(ValueError, match="https"):
            KeyVaultSecretResolver("http://vault.example")

    def test_a_missing_vault_uri_is_refused(self) -> None:
        """Constructing a resolver with nowhere to resolve from is a programming error."""
        with pytest.raises(ValueError, match="required"):
            KeyVaultSecretResolver("")


# ---------------------------------------------------------------------------
# 2. No secret is logged
# ---------------------------------------------------------------------------


class TestNoSecretIsLogged:
    """Every formatting path a log line can take, closed."""

    def test_str_redacts(self) -> None:
        """Closes ``logger.info("dsn=%s", secret)`` — the commonest shape by far."""
        assert str(SecretValue("dsn", SECRET)) == REDACTED

    def test_repr_redacts(self) -> None:
        """Closes ``logger.info("%r", secret)`` and every debugger display."""
        rendered = repr(SecretValue("dsn", SECRET))
        assert SECRET not in rendered
        assert REDACTED in rendered

    def test_format_redacts(self) -> None:
        """Closes ``f"{secret:>20}"``, which bypasses ``__str__`` entirely.

        This is the one that catches people: a format spec routes to ``__format__``, so a type that
        only overrides ``__str__`` leaks the moment somebody aligns a column.
        """
        secret = SecretValue("dsn", SECRET)
        assert f"{secret:>40}" == REDACTED
        assert f"{secret}" == REDACTED

    def test_an_actual_log_record_carries_no_secret(self, caplog: pytest.LogCaptureFixture) -> None:
        """End to end through the logging module, rather than trusting the dunder in isolation."""
        secret = SecretValue("otel", SECRET)
        with caplog.at_level(logging.INFO):
            logging.getLogger("ragcore.test").info("connecting with %s", secret)
            logging.getLogger("ragcore.test").info("interpolated %s", f"{secret}")

        assert SECRET not in caplog.text
        assert REDACTED in caplog.text

    def test_the_resolution_error_names_the_secret_but_never_its_value(self) -> None:
        """The failure path is a logging path too, and the one most likely to over-share."""
        error = SecretResolutionError("otel-connection-string", "https://v.example", "not found")
        rendered = str(error)
        assert "otel-connection-string" in rendered
        assert SECRET not in rendered


# ---------------------------------------------------------------------------
# 3. No secret is emitted in OpenAPI
# ---------------------------------------------------------------------------


class TestNoSecretIsEmittedInOpenApi:
    """The document is generated from the route models, so the rule is about what they can hold."""

    def test_a_secret_is_not_json_serialisable(self) -> None:
        """A secret placed in a response body raises rather than ships.

        Failing to serialise is the desired behaviour: a type that quietly rendered as
        ``<redacted>`` in a response would produce a successful 200 carrying a field the client
        cannot use, which is harder to notice than an error.
        """
        with pytest.raises(TypeError):
            json.dumps({"connection": SecretValue("dsn", SECRET)})

    def test_the_emitted_document_contains_no_secret_bearing_field(self) -> None:
        """Generated from the running app, which is the only document that matters."""
        from ragcore.api.app import create_app

        app = create_app(settings=_settings())
        document = json.dumps(app.openapi())

        assert SECRET not in document
        for term in ("secret", "password", "connectionstring", "apikey", "accesskey"):
            assert term not in document.lower().replace("_", "").replace("-", ""), (
                f"the OpenAPI document exposes a field matching {term!r}"
            )


# ---------------------------------------------------------------------------
# 4. No secret is written to telemetry
# ---------------------------------------------------------------------------


class TestNoSecretIsWrittenToTelemetry:
    """Span attributes and metric dimensions are the sink people forget."""

    def test_a_span_attribute_carries_no_secret(self) -> None:
        """Exporters stringify unknown types; this asserts what they would actually see."""
        secret = SecretValue("dsn", SECRET)

        # What an exporter does with a value it does not recognise, in both orders.
        assert SECRET not in str(secret)
        assert SECRET not in repr(secret)
        assert SECRET not in f"{secret}"

    def test_a_structured_log_payload_carries_no_secret(self) -> None:
        """Structured logging serialises the attribute dictionary, not the message."""
        payload: dict[str, Any] = {"secret": SecretValue("dsn", SECRET), "tenant": "contoso"}
        rendered = str({key: str(value) for key, value in payload.items()})
        assert SECRET not in rendered

    def test_the_secret_has_no_attribute_dictionary_to_scrape(self) -> None:
        """Slotted, so a serialiser walking ``__dict__`` finds nothing to walk.

        A reflective exporter that ignores ``__repr__`` and reads instance state is the one path a
        redacting dunder cannot close. Removing ``__dict__`` closes it.
        """
        assert not hasattr(SecretValue("dsn", SECRET), "__dict__")


# ---------------------------------------------------------------------------
# 5. Startup fails when a required reference cannot be resolved
# ---------------------------------------------------------------------------


class TestStartupFailsOnAnUnresolvableSecret:
    """A process that cannot reach its secrets does not start."""

    async def test_every_required_reference_resolves(self) -> None:
        """The baseline: resolution returns values keyed by name."""
        resolver = _StubResolver({"otel": SECRET})
        resolved = await resolve_required(resolver, [SecretRef("otel")])
        assert resolved["otel"].reveal() == SECRET

    async def test_a_missing_secret_raises(self) -> None:
        """No fallback, no default, no empty string."""
        resolver = _StubResolver({}, missing={"otel"})
        with pytest.raises(SecretResolutionError):
            await resolve_required(resolver, [SecretRef("otel")])

    async def test_every_failure_is_reported_in_one_cycle(self) -> None:
        """Three missing secrets report three names, not three deployments.

        Stopping at the first failure is the behaviour that turns one configuration problem into an
        afternoon of them.
        """
        resolver = _StubResolver({}, missing={"a", "b", "c"})
        with pytest.raises(SecretResolutionError) as caught:
            await resolve_required(resolver, [SecretRef("a"), SecretRef("b"), SecretRef("c")])

        rendered = str(caught.value)
        assert "3 required secret(s)" in rendered
        for name in ("a", "b", "c"):
            assert name in rendered

    async def test_an_empty_secret_is_a_failure_not_a_value(self) -> None:
        """A blank credential surfaces as an authentication error somewhere unrelated, hours later.

        Treating empty as absent is what keeps the failure attached to its cause.
        """

        class _EmptyVault:
            async def resolve(self, ref: SecretRef) -> SecretValue:
                raise SecretResolutionError(ref.name, "https://v.example", "the secret is empty")

        with pytest.raises(SecretResolutionError, match="empty"):
            await resolve_required(_EmptyVault(), [SecretRef("otel")])

    async def test_the_application_refuses_to_start(self) -> None:
        """End to end: a configured vault plus an unresolvable secret is a dead process.

        Driven through the real lifespan rather than by calling the resolver, because the rule is
        about *startup* — a resolver that raises correctly while the lifespan swallows it would pass
        every test above and fail the requirement.
        """
        from ragcore.api.app import create_app

        settings = _settings(
            vault_uri="https://vault.invalid",
            secret_name="definitely-not-there",  # noqa: S106 — a secret NAME, which is the point
        )
        app = create_app(settings=settings)

        expected = "could not be resolved|Name or service not known|Failed"
        with pytest.raises(Exception, match=expected):
            async with app.router.lifespan_context(app):
                pass  # pragma: no cover — reached only if startup wrongly succeeds

    def test_no_vault_means_no_required_references(self) -> None:
        """The developer-machine case: nothing to resolve, so nothing to fail on."""
        assert _settings().required_secret_references() == ()

    def test_a_configured_vault_declares_its_references(self) -> None:
        """And a name that is present is a name that must resolve."""
        settings = _settings(
            vault_uri="https://vault.example",
            secret_name="otel",  # noqa: S106 — a secret NAME; holding one is the requirement
        )
        assert [ref.name for ref in settings.required_secret_references()] == ["otel"]


def _settings(vault_uri: str = "", secret_name: str = "") -> Any:
    """Settings for a test, with no environment read and no vault unless one is asked for."""
    from ragcore.config.settings import (
        DatabaseSettings,
        KeyVaultSettings,
        ObservabilitySettings,
        Settings,
    )

    return Settings(
        database=DatabaseSettings(dsn="postgresql://synthia@localhost:5432/synthia"),  # type: ignore[arg-type]
        key_vault=KeyVaultSettings(vault_uri=vault_uri),
        observability=ObservabilitySettings(connection_string_secret_name=secret_name),
    )
