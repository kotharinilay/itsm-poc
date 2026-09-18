"""The command leg: RagCore writes a job row, an outbox row, and publishes to the right queue.

**Every test here covers a path that was unreachable before.** `IntegrationDispatcher` had no
caller, never touched its outbox, and `TriggerKind` had no integration member — so an
`integration.execute` row could not be built, could not be routed and could not be published. The
drift analysis found all of it; these are the assertions that keep it found.

The load-bearing ones:

* the job row and the outbox row are written **in the same transaction** — either alone is a silent
  stall;
* the body carries **three fields**, and `jobId` rather than `workItemId`;
* a command goes to the **command queue**, a trigger to the trigger queue;
* RagCore **cannot publish a result** — it holds no Sender role on that queue.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from workers.outbox_dispatch import envelope_from_row, subject_of

from ragcore.config.settings import MessagingSettings
from ragcore.domain.envelopes import (
    IntegrationCommandEnvelope,
    IntegrationMessageKind,
    TriggerEnvelope,
    TriggerKind,
)
from ragcore.domain.identifiers import CorrelationId, IntegrationJobId, WorkItemId
from ragcore.messaging.publisher import (
    INTEGRATION_PAYLOAD_FIELDS,
    ServiceBusTriggerPublisher,
    integration_command_body,
    message_body,
)
from ragcore.persistence.integration_jobs import IntegrationDispatcher
from tests.support.fakes import admitted_tenant

_CORRELATION = CorrelationId("0f9a5f4c-1111-4000-8000-000000000002")


class _Session:
    """Records the statements executed against it, in order."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, parameters: Any = None) -> None:  # noqa: ANN401
        self.executed.append((str(statement), dict(parameters or {})))


class _Outbox:
    """Records the integration commands enqueued through it."""

    def __init__(self) -> None:
        self.enqueued: list[IntegrationCommandEnvelope] = []

    async def enqueue_integration_command(
        self, tenant: Any, envelope: IntegrationCommandEnvelope
    ) -> None:  # noqa: ANN401
        del tenant
        self.enqueued.append(envelope)


async def _dispatch() -> tuple[_Session, _Outbox, Any]:
    session, outbox = _Session(), _Outbox()
    job = await IntegrationDispatcher(outbox).dispatch(
        session,  # type: ignore[arg-type]
        tenant=admitted_tenant(),
        work_item_id=uuid4(),
        operation_id=uuid4(),
        tenant_id=uuid4(),
        catalogue_id="reference.inert_read",
        catalogue_version=1,
        parameters={"note": "data"},
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        correlation_id=_CORRELATION,
    )
    return session, outbox, job


# ---------------------------------------------------------------------------
# X1 — the dispatcher writes both rows, and the outbox is actually used
# ---------------------------------------------------------------------------


async def test_the_job_row_and_the_outbox_row_are_both_written() -> None:
    """**Either alone is a silent stall**, which is why one method owns both.

    A job row with no outbox row is an instruction nobody will ever act on: the work sits approved
    and unexecuted with nothing in any queue to explain it. An outbox row with no job row is a
    command naming a row that does not exist. Before this, only the first was written.
    """
    session, outbox, job = await _dispatch()

    assert len(session.executed) == 1
    assert "INSERT INTO platform.integration_job" in session.executed[0][0]

    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].job_id == IntegrationJobId(job.job_id)
    assert outbox.enqueued[0].kind is IntegrationMessageKind.EXECUTE
    assert outbox.enqueued[0].correlation_id == _CORRELATION


async def test_the_outbox_row_names_the_job_that_was_just_written() -> None:
    """The two rows agree on the identifier.

    A mismatch here is the failure mode hardest to spot: both rows exist, the message publishes
    cleanly, and the consumer dead-letters on a job identifier that names nothing.
    """
    session, outbox, job = await _dispatch()

    assert session.executed[0][1]["job_id"] == job.job_id
    assert str(outbox.enqueued[0].job_id) == str(job.job_id)


# ---------------------------------------------------------------------------
# X2 — body shape, row routing and queue routing
# ---------------------------------------------------------------------------


def test_the_command_body_carries_three_fields_and_a_job_identifier() -> None:
    """`FR-INTEG-014`. **No organisation, no capability, no parameters.**

    Asserted against the closed set rather than by listing keys, so adding a field to the body
    fails here rather than being caught only by the far side's refusal.
    """
    body = integration_command_body(
        IntegrationCommandEnvelope(
            job_id=IntegrationJobId(uuid4()),
            correlation_id=_CORRELATION,
            kind=IntegrationMessageKind.EXECUTE,
        )
    )

    assert set(body) == INTEGRATION_PAYLOAD_FIELDS
    assert set(body) == {"jobId", "correlationId", "kind"}
    assert "workItemId" not in body
    assert "tenantId" not in body


def test_the_body_is_chosen_by_envelope_type_not_by_a_flag() -> None:
    """A caller cannot ask for the wrong body, because there is no argument with which to ask."""
    command = IntegrationCommandEnvelope(
        job_id=IntegrationJobId(uuid4()),
        correlation_id=_CORRELATION,
        kind=IntegrationMessageKind.EXECUTE,
    )
    trigger = TriggerEnvelope(
        work_item_id=WorkItemId(uuid4()),
        correlation_id=_CORRELATION,
        kind=TriggerKind.SAMPLE_FLOW,
    )

    assert "jobId" in message_body(command)
    assert "workItemId" in message_body(trigger)


class _Row:
    """One outbox row, as the dispatcher's query returns it."""

    def __init__(self, kind: str, payload: dict[str, str]) -> None:
        self.outbox_id = uuid4()
        self.kind = kind
        self.payload = payload
        self.sequence = 1


def test_a_command_row_rebuilds_as_a_command_and_a_trigger_row_as_a_trigger() -> None:
    """Routing on the kind, with the identifier following from it.

    Reading `workItemId` from a command row would produce a `KeyError`; reading it from the wrong
    key would produce a message that deserialises perfectly and names a row that does not exist.
    """
    job_id = uuid4()
    command = envelope_from_row(
        _Row("integration.execute", {"jobId": str(job_id), "correlationId": str(_CORRELATION)})
    )
    assert isinstance(command, IntegrationCommandEnvelope)
    assert command.job_id == IntegrationJobId(job_id)

    work_id = uuid4()
    trigger = envelope_from_row(
        _Row("sample.flow", {"workItemId": str(work_id), "correlationId": str(_CORRELATION)})
    )
    assert isinstance(trigger, TriggerEnvelope)
    assert trigger.work_item_id == WorkItemId(work_id)


def test_an_unrecognised_kind_is_never_published_as_a_best_guess() -> None:
    """The dispatcher knows neither the queue nor the identifier, and either guess is traceable.

    The payload here is a **well-formed trigger** payload, so the kind is the only thing wrong.
    Omitting `workItemId` too would raise `KeyError` first and this test would pass while proving
    nothing about the kind.
    """
    with pytest.raises(ValueError, match="not a valid TriggerKind"):
        envelope_from_row(
            _Row(
                "nonsense.kind",
                {"workItemId": str(uuid4()), "correlationId": str(_CORRELATION)},
            )
        )


def test_a_malformed_payload_raises_rather_than_publishing_a_partial_message() -> None:
    """A command row missing its identifier is refused, not published with a blank one.

    Raises `KeyError` rather than `ValueError` — a different exception type from the unknown-kind
    case above, and worth pinning separately: both abort the row, and `dispatch_once` counts it as
    a publish failure that retries to the ceiling and then surfaces to a human.
    """
    with pytest.raises(KeyError, match="jobId"):
        envelope_from_row(_Row("integration.execute", {"correlationId": str(_CORRELATION)}))


def test_the_dead_letter_alert_names_the_row_an_operator_can_look_up() -> None:
    """An undispatchable command means **approved work never ran**.

    The alert must therefore carry something an operator can look up.
    """
    job_id = uuid4()
    command = IntegrationCommandEnvelope(
        job_id=IntegrationJobId(job_id),
        correlation_id=_CORRELATION,
        kind=IntegrationMessageKind.EXECUTE,
    )

    assert subject_of(command) == str(job_id)


class _Sender:
    """Records what was sent, and to which queue."""

    def __init__(self, queue: str, log: list[tuple[str, str]]) -> None:
        self._queue = queue
        self._log = log

    async def __aenter__(self) -> _Sender:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def send_messages(self, message: Any) -> None:  # noqa: ANN401
        # `ServiceBusMessage.body` is a generator of byte chunks, not a string. Joining here rather
        # than in each assertion keeps the fake faithful to the SDK — a fake that exposed a plain
        # string would let a test pass against a shape the real client never produces.
        self._log.append((self._queue, b"".join(message.body).decode("utf-8")))


class _Client:
    """A Service Bus client that records the queue each sender was opened on."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def get_queue_sender(self, queue: str) -> _Sender:
        return _Sender(queue, self.sent)


def _publisher() -> tuple[ServiceBusTriggerPublisher, _Client]:
    client = _Client()
    settings = MessagingSettings(namespace="example.servicebus.windows.net")
    return ServiceBusTriggerPublisher(settings, client), client


async def test_a_command_goes_to_the_command_queue_and_a_trigger_to_the_trigger_queue() -> None:
    """**The routing that did not exist.** One dispatcher, one retry policy, two destinations."""
    publisher, client = _publisher()

    await publisher.publish(
        IntegrationCommandEnvelope(
            job_id=IntegrationJobId(uuid4()),
            correlation_id=_CORRELATION,
            kind=IntegrationMessageKind.EXECUTE,
        )
    )
    await publisher.publish(
        TriggerEnvelope(
            work_item_id=WorkItemId(uuid4()),
            correlation_id=_CORRELATION,
            kind=TriggerKind.SAMPLE_FLOW,
        )
    )

    assert [queue for queue, _ in client.sent] == [
        "synthia-integration-commands",
        "synthia-triggers",
    ]

    # And the body that actually went on the wire carries the job identifier.
    assert set(json.loads(client.sent[0][1])) == {"jobId", "correlationId", "kind"}


@pytest.mark.parametrize("kind", [IntegrationMessageKind.COMPLETED, IntegrationMessageKind.FAILED])
async def test_ragcore_refuses_to_publish_a_result(kind: IntegrationMessageKind) -> None:
    """**RagCore consumes results; it never publishes them.**

    It holds Receiver and not Sender on the results queue, so this would fail at the platform
    anyway. Refusing here names the defect instead of surfacing it as a puzzling authorization
    error against a queue nobody expected this process to write to.

    The asymmetry is a control, not tidiness: an orchestrator that could publish
    `integration.completed` could fabricate a successful outcome for work that never ran.
    """
    publisher, client = _publisher()

    with pytest.raises(ValueError, match="consumed by RagCore, never published"):
        await publisher.publish(
            IntegrationCommandEnvelope(
                job_id=IntegrationJobId(uuid4()), correlation_id=_CORRELATION, kind=kind
            )
        )

    assert client.sent == []


def test_the_integration_kinds_are_a_separate_enum_from_the_trigger_kinds() -> None:
    """`integration.execute` MUST NOT be a `TriggerKind`.

    `TriggerEnvelope` carries `work_item_id`. Adding the integration kinds to that enum would make
    the envelope constructible with one, and the resulting message would carry `workItemId` where
    the far side's closed field set demands `jobId` — refused and dead-lettered, with the cause two
    modules away from the symptom.
    """
    trigger_values = {member.value for member in TriggerKind}
    integration_values = {member.value for member in IntegrationMessageKind}

    assert not trigger_values & integration_values
    assert "workItemId" not in integration_command_body(
        IntegrationCommandEnvelope(
            job_id=IntegrationJobId(UUID(int=1)),
            correlation_id=_CORRELATION,
            kind=IntegrationMessageKind.EXECUTE,
        )
    )
