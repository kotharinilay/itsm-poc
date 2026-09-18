"""The result leg: RagCore consumes an outcome, concludes from durable state, and never re-fires.

**Nothing in RagCore referenced `integration.completed` before this.** The result queue had no
consumer at all, so a dispatched job stayed apparently in flight for ever — indistinguishable from a
slow external system.

The load-bearing assertions:

* the conclusion is read from the **row**, never from the message kind;
* a failure concludes and **cannot re-dispatch** — there is no verb to call;
* `may_report_resolution` is the single gate on telling a user something is resolved;
* an out-of-contract field is **refused**, not ignored.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from workers.integration_result_worker import (
    Conclusion,
    UndeserializableResultError,
    concluded_from,
    main,
    parse_result_message,
)

from ragcore.domain.envelopes import IntegrationMessageKind
from ragcore.persistence.integration_jobs import IntegrationResult

_CORRELATION = "0f9a5f4c-1111-4000-8000-000000000002"


def _result(
    *,
    executed: bool,
    verification: str | None,
    recorded: bool = True,
) -> IntegrationResult:
    """Build a real :class:`IntegrationResult`, not a stand-in.

    **The production dataclass rather than a local fake.** `IntegrationResult` is a concrete type,
    not a Protocol, so a look-alike would not satisfy `concluded_from` under `mypy --strict` — and
    the version that did satisfy it would be one whose fields had been guessed. Constructing the
    real thing makes drift impossible: a field added to it fails here.

    Args:
        executed: Whether the operation ran.
        verification: What the far side observed.
        recorded: Whether a result has landed at all. ``False`` gives the pending row.

    Returns:
        The result as RagCore reads it from its own four columns.
    """
    return IntegrationResult(
        executed=executed,
        verification=verification,
        execution_id=uuid4() if recorded else None,
        recorded_at=datetime.now(UTC) if recorded else None,
    )


def _body(**overrides: Any) -> str:
    payload = {
        "jobId": str(uuid4()),
        "correlationId": _CORRELATION,
        "kind": "integration.completed",
    }
    payload.update(overrides)
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Parsing — strict, and closed on the field set
# ---------------------------------------------------------------------------


def test_a_well_formed_result_parses_with_its_trace_context() -> None:
    """**Positive.** Three fields in the body; trace context in the application properties."""
    parsed = parse_result_message(
        _body(), {"traceparent": "00-abc-def-01", "tracestate": "vendor=1"}
    )

    assert parsed.kind is IntegrationMessageKind.COMPLETED
    assert str(parsed.correlation_id) == _CORRELATION
    assert parsed.trace.traceparent == "00-abc-def-01"
    assert parsed.trace.tracestate == "vendor=1"


def test_an_out_of_contract_field_is_refused_rather_than_ignored() -> None:
    """Ignoring it would let a publisher believe the field had been honoured.

    It would also leave a forged `tenantId` sitting in the queue looking accepted — and the one
    event worth alerting on would become indistinguishable from an ordinary message.
    """
    with pytest.raises(UndeserializableResultError):
        parse_result_message(_body(tenantId=str(uuid4())), None)


def test_the_refusal_does_not_echo_the_offending_field_name() -> None:
    """The count, never the names.

    A forged field could carry an organisation identifier or a log-format token, and this exception
    is the thing most likely to be logged.
    """
    with pytest.raises(UndeserializableResultError) as raised:
        parse_result_message(_body(tenantId="acme-corporation"), None)

    assert "acme-corporation" not in str(raised.value)
    assert "tenantId" not in str(raised.value)


def test_a_command_kind_is_not_accepted_on_the_results_queue() -> None:
    """**`EXECUTE` travels in the other direction.**

    A consumer that accepted it here would be RagCore consuming its own dispatch — and, worse,
    would do so with none of the Integrations Service's re-verification.
    """
    with pytest.raises(UndeserializableResultError):
        parse_result_message(_body(kind="integration.execute"), None)


@pytest.mark.parametrize("body", ["not json", "[]", '{"jobId": "not-a-uuid"}'])
def test_a_malformed_body_raises_rather_than_being_defaulted(body: str) -> None:
    """A body that will not parse is one whose job identifier cannot be trusted."""
    with pytest.raises(UndeserializableResultError):
        parse_result_message(body, None)


# ---------------------------------------------------------------------------
# Concluding — from the row, never from the message
# ---------------------------------------------------------------------------


def test_a_server_confirmed_outcome_is_the_only_one_reportable_as_resolved() -> None:
    """ADR-0004. `client_attested` means nobody checked, and MUST NOT read as confirmation."""
    confirmed = _result(executed=True, verification="server_confirmed")
    attested = _result(executed=True, verification="client_attested")

    assert concluded_from(confirmed) is Conclusion.RESOLVED
    assert concluded_from(attested) is Conclusion.ACTED_UNVERIFIED


def test_a_contradicted_outcome_is_not_resolved() -> None:
    """A claim the platform has actively disproved is worse than one it never checked."""
    assert (
        concluded_from(_result(executed=True, verification="contradicted"))
        is Conclusion.ACTED_UNVERIFIED
    )


def test_an_unexecuted_outcome_is_a_failure() -> None:
    """It escalates. It does not retry."""
    assert concluded_from(_result(executed=False, verification=None)) is Conclusion.FAILED


@pytest.mark.parametrize(
    "result",
    [None, _result(executed=True, verification="server_confirmed", recorded=False)],
    ids=["no such job", "no result recorded yet"],
)
def test_no_recorded_result_concludes_pending_not_success(
    result: IntegrationResult | None,
) -> None:
    """**The forged-message case.**

    A `integration.completed` naming a job whose row says nothing happened concludes `PENDING`. The
    worst a forged result achieves is a read that finds nothing — which is exactly why the outcome
    is read from the row and not from the kind.
    """
    assert concluded_from(result) is Conclusion.PENDING


def test_the_conclusion_cannot_be_derived_from_the_message_kind() -> None:
    """`concluded_from` takes no kind argument, and that omission is the control.

    Asserted on the signature rather than on behaviour: a future edit that added a `kind` parameter
    would let a caller conclude success from a message, and this fails the moment it does.
    """
    import inspect

    assert list(inspect.signature(concluded_from).parameters) == ["result"]


def test_there_is_no_redispatch_outcome() -> None:
    """`FR-EXEC-006`. A failed authorized action requires **fresh human authorization**.

    The prohibition is enforced by there being nothing to call: no `Conclusion` member means
    "retry", and the module exports no publisher. A re-dispatch here would spend one authority
    record twice, in a loop that looks like resilience.
    """
    assert {member.name for member in Conclusion} == {
        "RESOLVED",
        "ACTED_UNVERIFIED",
        "FAILED",
        "PENDING",
    }

    import workers.integration_result_worker as module

    assert not [name for name in dir(module) if "publish" in name.lower()]
    assert not [name for name in dir(module) if "dispatch" in name.lower()]


def test_the_worker_refuses_to_start_rather_than_consuming_nothing() -> None:
    """Deliberately loud, matching `resume_worker` and the other five workers.

    A worker that started, logged "listening" and consumed no message would leave every dispatched
    job apparently in flight for ever. Process wiring lands with the other workers; the behaviour
    above is what ships now, and it is tested.
    """
    with pytest.raises(NotImplementedError, match="process wiring"):
        main()
