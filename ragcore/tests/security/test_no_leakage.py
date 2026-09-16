"""No secret, token, authorization header, payload or cross-tenant value reaches a log sink.

Plan §Stage 10 security, spec FR-OPS-002. Asserted two ways, because the two catch different
defects and each one alone would be reassuring rather than sufficient:

* **Behaviourally**, by logging the thing and reading what the handler actually emitted. That is
  what proves the redaction runs, that the formatter's allow-list holds, and that a
  :class:`~ragcore.config.secrets.SecretValue` really does render as ``<redacted>`` through every
  path a real caller would use.
* **Structurally**, by reading the source for the shapes that leak in the first place — an
  ``exc_info`` on a provider client, an ``extra`` carrying a request, a formatted header.

**The tests below log real-looking secrets on purpose.** They are fixed literals that authenticate
nothing, and they have to look convincing: a redaction test against ``"secret"`` proves only that
the word is caught. Each is marked where it appears.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any, Final

import pytest

from ragcore.api.middleware.correlation import correlation_id_var
from ragcore.config.secrets import REDACTED, SecretValue
from ragcore.observability.context import bind_tenant
from ragcore.observability.logging import (
    LOGGED_FIELDS,
    JsonFormatter,
    RedactingFilter,
    configure_logging,
    redact,
)
from tests.support.fakes import admitted_tenant

pytestmark = pytest.mark.security

SRC: Final = Path(__file__).resolve().parents[2] / "src" / "ragcore"

# Fixed literals that authenticate nothing. They look real because a redaction test against an
# obviously fake value proves nothing about a real one.
FAKE_JWT: Final = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r"  # noqa: S105
FAKE_BEARER: Final = f"Bearer {FAKE_JWT}"
FAKE_DSN: Final = "postgresql://synthia:hunter2@db.example:5432/synthia"
FAKE_SAS: Final = "Endpoint=sb://x.servicebus.windows.net/;SharedAccessKey=abc123def456ghi789"
FAKE_API_KEY: Final = "api_key=sk-abcdefghijklmnopqrstuvwxyz0123456789"  # noqa: S105


def _emit(record_factory: Any) -> str:
    """Run one record through the production handler and return what a sink would receive."""
    formatter = JsonFormatter()
    redacting = RedactingFilter()

    record = record_factory()
    redacting.filter(record)

    return formatter.format(record)


def _record(message: str, *args: object, **kwargs: Any) -> logging.LogRecord:
    """Build a log record the way ``logger.info(...)`` does."""
    return logging.LogRecord(
        name="ragcore.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=kwargs.get("exc_info"),
    )


class TestNothingSensitiveSurvivesTheHandler:
    """The behavioural half. Log it, then read what came out."""

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("a bearer token", FAKE_BEARER),
            ("a bare JWT", FAKE_JWT),
            ("a DSN with an embedded password", FAKE_DSN),
            ("a connection string with a shared access key", FAKE_SAS),
            ("an API key in a query parameter", FAKE_API_KEY),
        ],
    )
    def test_the_value_does_not_reach_the_sink(self, name: str, value: str) -> None:
        """Whether it is in the message or in an interpolation argument."""
        in_message = _emit(lambda: _record(f"call failed: {value}"))
        in_args = _emit(lambda: _record("call failed: %s", value))

        assert value not in in_message, f"{name} survived in the message"
        assert value not in in_args, f"{name} survived as an argument"
        assert REDACTED in in_message and REDACTED in in_args, (
            f"{name} was removed without a marker; a reviewer should see that something was caught"
        )

    def test_the_surrounding_line_survives_redaction(self) -> None:
        """Redacting, not dropping. An operator investigating an incident must still find the
        event — a gap where the interesting line should be is worse than a redacted line."""
        emitted = json.loads(_emit(lambda: _record("call failed: %s", FAKE_BEARER)))

        assert "call failed" in emitted["message"]
        assert emitted["level"] == "INFO"

    def test_a_secret_value_renders_as_redacted_through_every_path(self) -> None:
        """The first line of defence, independent of the filter: ``str``, ``repr`` and ``format``
        all redact, so a secret deliberately held never needs the filter to catch it."""
        secret = SecretValue("synthia-database-dsn", FAKE_DSN)

        for rendered in (str(secret), repr(secret), f"{secret}", f"{secret:>40}"):
            assert FAKE_DSN not in rendered
            assert REDACTED in rendered

    def test_a_traceback_is_redacted_too(self) -> None:
        """A stack frame carries local variables, and a provider client's exception can carry a URL
        with a token in it. The formatted traceback goes through the same redaction."""
        try:
            raise RuntimeError(f"upstream refused: {FAKE_BEARER}")
        except RuntimeError as error:
            # Bound outside the lambda: Python clears the `except` name when the block ends, so a
            # lambda closing over it would work here and fail the moment anything deferred it.
            failure = (type(error), error, error.__traceback__)

        emitted = _emit(lambda: _record("the call failed", exc_info=failure))

        assert FAKE_JWT not in emitted

    def test_an_unlisted_record_attribute_is_not_serialised(self) -> None:
        """The formatter publishes an **allow-list**. An object attached with ``extra={...}`` — a
        settings instance, a request, a provider response — is not published because somebody
        wanted one of its fields."""
        record = _record("processing")
        record.authorization = FAKE_BEARER
        record.payload = {"ssn": "000-00-0000"}

        emitted = json.loads(JsonFormatter().format(record))

        assert set(emitted) <= set(LOGGED_FIELDS)
        assert "authorization" not in emitted
        assert "payload" not in emitted

    def test_the_identity_contract_is_never_a_logged_field(self) -> None:
        """The ``X-Idp-*`` headers are authority. A log line carrying them would be a record of who
        someone claimed to be, in a store with far weaker access control than audit."""
        for field in LOGGED_FIELDS:
            assert not field.lower().startswith("x-idp")
            assert "authorization" not in field.lower()


class TestWhatIsDeliberatelyLogged:
    """The positive half: correlation and organisation, and nothing else identifying."""

    def test_the_correlation_identifier_is_present(self) -> None:
        """It is what a user quotes and what joins the halves of a suspended journey."""
        token = correlation_id_var.set("corr-123")
        try:
            emitted = json.loads(_emit(lambda: _record("working")))
        finally:
            correlation_id_var.reset(token)

        assert emitted["correlation_id"] == "corr-123"

    def test_the_organisation_comes_from_trusted_context(self) -> None:
        """Bound from an admitted :class:`TenantContext`, never from a header. There is no setter
        here taking a string, so a header value cannot reach this field."""
        tenant = admitted_tenant()
        bind_tenant(tenant)

        emitted = json.loads(_emit(lambda: _record("working")))

        assert emitted["tenant_id"] == str(tenant.tenant_id.value)

    def test_the_platform_identifier_is_logged_and_not_the_directory_one(self) -> None:
        """The Entra ``tid`` is one join away from naming a real company in a store nobody treats
        as sensitive."""
        tenant = admitted_tenant()
        bind_tenant(tenant)

        emitted = _emit(lambda: _record("working"))

        assert str(tenant.entra_tenant_id.value) not in emitted


class TestTheHandlerIsTheOnlyPath:
    """Structural: the guarantees above are worthless if a second, unfiltered handler exists."""

    def test_configure_logging_replaces_handlers_rather_than_adding(self) -> None:
        """A second handler is a second copy of every line, and the copy is the unfiltered one a
        library installed."""
        root = logging.getLogger()
        original = list(root.handlers)
        try:
            root.addHandler(logging.StreamHandler())
            configure_logging()

            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JsonFormatter)
        finally:
            root.handlers = original

    def test_both_filters_are_installed(self) -> None:
        root = logging.getLogger()
        original = list(root.handlers)
        try:
            configure_logging()
            installed = {type(f).__name__ for f in root.handlers[0].filters}

            assert {"CorrelationIdFilter", "RedactingFilter"} <= installed
        finally:
            root.handlers = original


class TestNoModuleLogsAPayloadOrAHeader:
    """Structural: the shapes that leak before any filter gets a chance.

    Read from the AST, so the prose in this file — which necessarily contains every banned shape —
    does not trip its own rule.
    """

    @staticmethod
    def _logging_calls(path: Path) -> list[ast.Call]:
        """Every ``_log.<level>(...)`` call in a module."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"debug", "info", "warning", "error", "critical", "exception"}
        ]

    def test_no_log_call_passes_a_request_response_or_payload(self) -> None:
        """Not the objects themselves, and not a field plucked out of one. A response body is the
        payload FR-OPS-002 excludes whether it is logged whole or one key at a time."""
        forbidden = {
            "headers",
            "payload",
            "body",
            "content",
            "parameters",
            "arguments",
            "request",
            "response",
        }
        offenders: list[str] = []

        for path in sorted(SRC.rglob("*.py")):
            for call in self._logging_calls(path):
                for argument in call.args[1:] + [
                    k.value for k in call.keywords if k.arg != "exc_info"
                ]:
                    name = (
                        argument.id
                        if isinstance(argument, ast.Name)
                        else argument.attr
                        if isinstance(argument, ast.Attribute)
                        else ""
                    )
                    if name.lower() in forbidden:
                        offenders.append(f"{path.relative_to(SRC)}: {name}")

        assert not offenders, (
            "a log call passes a payload, a header collection or a request/response object:\n  "
            + "\n  ".join(offenders)
        )

    def test_no_log_call_formats_its_message_with_an_f_string(self) -> None:
        """Two reasons, and the second is the one people forget. A constant template with fields is
        searchable and aggregatable — an f-string produces a million distinct messages and no
        grouping. It also splices the value into free text, where the redacting filter has to find
        it by shape rather than being handed it as an argument."""
        offenders: list[str] = []

        for path in sorted(SRC.rglob("*.py")):
            for call in self._logging_calls(path):
                if call.args and isinstance(call.args[0], ast.JoinedStr):
                    offenders.append(f"{path.relative_to(SRC)}: {ast.unparse(call.args[0])[:60]}")

        assert not offenders, (
            "a log message is built with an f-string. Use a constant template and pass the values "
            "as arguments:\n  " + "\n  ".join(offenders)
        )


class TestTheRedactorItself:
    """Unit-level, because this function is the backstop everything else leans on."""

    def test_it_leaves_ordinary_text_alone(self) -> None:
        """A redactor that mangles ordinary lines is one somebody switches off."""
        ordinary = "Claimed work item 6f1c under correlation corr-123 for organisation 9b2e."

        assert redact(ordinary) == ordinary

    def test_it_is_idempotent(self) -> None:
        """Redacting twice must not corrupt an already-redacted line — records pass through more
        than one handler in a process that adds one."""
        once = redact(f"failed: {FAKE_BEARER}")

        assert redact(once) == once
