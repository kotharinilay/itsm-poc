"""The message envelope contract. **Three fields, and nothing authority-bearing.**

Specification §27.2. These are the tests that would fail if the payload rule were relaxed, which is
the bar the constitution sets for a protection named as a hard failure.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from integrations.execution.idempotency import derive_key
from integrations.messaging.envelope import EnvelopeError, MessageEnvelope, MessageKind

pytestmark = pytest.mark.security

_JOB = UUID("66666666-6666-6666-6666-666666666666")
_CORRELATION = "0123abcd-4567-89ef-0123-456789abcdef"


def _body(**overrides: object) -> str:
    payload: dict[str, object] = {
        "jobId": str(_JOB),
        "correlationId": _CORRELATION,
        "kind": "integration.execute",
    }
    payload.update(overrides)
    return json.dumps(payload)


# --------------------------------------------------------------------------- positive


def test_a_conforming_command_parses() -> None:
    """**Positive.** Three fields, correct shapes."""
    envelope = MessageEnvelope.from_json(_body())

    assert envelope.job_id == _JOB
    assert envelope.correlation_id == _CORRELATION
    assert envelope.kind is MessageKind.EXECUTE


def test_the_wire_form_carries_exactly_three_fields() -> None:
    """The serialised envelope is the contract, and it is closed.

    Asserted on the emitted JSON rather than the object, because what travels is what matters — an
    object could grow a field that the serialiser happened not to emit, and the next person would
    emit it.
    """
    emitted = json.loads(MessageEnvelope(_JOB, _CORRELATION, MessageKind.COMPLETED).to_json())

    assert set(emitted) == {"jobId", "correlationId", "kind"}


def test_serialisation_is_deterministic() -> None:
    """Two publications of the same envelope are byte-identical.

    Keys are sorted, so a queue inspection can be diffed rather than eyeballed.
    """
    envelope = MessageEnvelope(_JOB, _CORRELATION, MessageKind.EXECUTE)

    assert envelope.to_json() == envelope.to_json()
    assert MessageEnvelope.from_json(envelope.to_json()) == envelope


# --------------------------------------------------------------------------- negative


@pytest.mark.parametrize(
    "forbidden",
    [
        "tenantId",
        "tenant_id",
        "roles",
        "parameters",
        "treatment",
        "approvalState",
        "catalogueId",
        "credential",
        "target",
    ],
)
def test_an_authority_bearing_field_is_refused(forbidden: str) -> None:
    """**The test this whole contract exists for.**

    Each of these is something the specification explicitly forbids a trigger from carrying. The
    message is **refused**, not sanitised: stripping the field would return success to whoever sent
    it and leave the attempt indistinguishable from an ordinary message — so the one event worth
    alerting on would become invisible.
    """
    with pytest.raises(EnvelopeError):
        MessageEnvelope.from_json(_body(**{forbidden: "anything"}))


def test_an_unknown_kind_is_refused_rather_than_ignored() -> None:
    """An unhandled kind is **never** treated as authorization to proceed.

    It dead-letters, which is the correct behaviour under the trigger contract rather than a gap in
    it.
    """
    with pytest.raises(EnvelopeError, match="closed set"):
        MessageEnvelope.from_json(_body(kind="integration.do_whatever"))


def test_a_malformed_correlation_identifier_is_refused() -> None:
    """A correlation identifier is an index into telemetry.

    One a publisher can shape freely is an injection point into every log line that carries it, so
    the queue applies the same acceptance rule as the HTTP boundary.
    """
    with pytest.raises(EnvelopeError, match="correlation"):
        MessageEnvelope.from_json(_body(correlationId="not a correlation id\nINJECTED"))


def test_a_missing_field_is_refused() -> None:
    """An incomplete envelope is refused rather than defaulted.

    A defaulted correlation identifier would silently start a second journey.
    """
    incomplete = json.dumps({"jobId": str(_JOB), "kind": "integration.execute"})

    with pytest.raises(EnvelopeError, match="omits"):
        MessageEnvelope.from_json(incomplete)


def test_a_non_object_body_is_refused() -> None:
    """A JSON array or scalar is not an envelope."""
    with pytest.raises(EnvelopeError):
        MessageEnvelope.from_json("[]")


def test_the_error_discloses_no_message_content() -> None:
    """The exception names the class of problem, never the offending value.

    This exception is the thing most likely to be logged, and a forged field is exactly the content
    not to copy into a log line — it could carry an organisation identifier or a log-format token.
    """
    # Not a credential — a distinctive marker whose presence in the message proves the exception
    # did not copy the offending value out.
    marker = "distinctive-organisation-marker-abc123"

    with pytest.raises(EnvelopeError) as raised:
        MessageEnvelope.from_json(_body(tenantId=marker))

    assert marker not in str(raised.value)


# --------------------------------------------------------------------------- derived key


def test_the_derived_key_is_deterministic() -> None:
    """Idempotency boundary 2 rests on this, and on nothing else.

    A random key makes every attempt look like a new logical action, so a redelivered command
    produces a second external effect and the boundary protects nothing.
    """
    tenant, work, operation = uuid4(), uuid4(), uuid4()

    assert derive_key(tenant, work, operation) == derive_key(tenant, work, operation)


def test_two_organisations_never_share_a_key() -> None:
    """The organisation is in the material, so identifiers reused across tenants cannot collide."""
    work, operation = uuid4(), uuid4()

    assert derive_key(uuid4(), work, operation) != derive_key(uuid4(), work, operation)


def test_two_operations_on_one_work_item_never_share_a_key() -> None:
    """A work item may carry more than one operation.

    A key without the operation would make two different actions look like retries of each other —
    and the unique constraint would then silently suppress the second, which is the worst possible
    outcome: a real action dropped and reported as a duplicate.
    """
    tenant, work = uuid4(), uuid4()

    assert derive_key(tenant, work, uuid4()) != derive_key(tenant, work, uuid4())


def test_the_key_discloses_no_organisation() -> None:
    """Hashed in, not emitted.

    The key travels to third-party systems whose logs are outside the platform's control.
    """
    tenant = uuid4()

    assert str(tenant) not in derive_key(tenant, uuid4(), uuid4())
