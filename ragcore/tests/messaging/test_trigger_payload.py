"""A published trigger carries **three fields and nothing else**.

This is the test that makes ``contracts/triggers.md`` enforceable rather than aspirational. The rule
it guards is the reason a forged or replayed trigger cannot authorize anything: the message names
*which* work, and the durable record says what may happen to it.

The negative half matters more than the positive one. "It contains workItemId" would pass just as
happily on a payload that also contained the tenant and the approval state — so the assertions below
are written as *exact* comparisons and explicit absences, not as containment checks.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from ragcore.domain.envelopes import TriggerEnvelope, TriggerKind
from ragcore.domain.identifiers import CorrelationId, WorkItemId
from ragcore.messaging.publisher import (
    PAYLOAD_FIELDS,
    TRACEPARENT_PROPERTY,
    build_message,
    trigger_body,
)

FORBIDDEN_IN_A_TRIGGER = (
    "tenant",
    "tenantId",
    "organisation",
    "requester",
    "requestedBy",
    "role",
    "roles",
    "action",
    "governedAction",
    "target",
    "approval",
    "approvalState",
    "verdict",
    "expiry",
    "expiresAt",
    "command",
    "parameters",
    "credential",
    "token",
)
"""Explicitly forbidden by the contract. Named individually so a failure says which one leaked."""


@pytest.fixture(name="envelope")
def envelope_fixture() -> TriggerEnvelope:
    return TriggerEnvelope(
        work_item_id=WorkItemId(uuid4()),
        correlation_id=CorrelationId("corr-abc-123"),
        kind=TriggerKind.SAMPLE_FLOW,
    )


class TestTheBodyIsExactlyThreeFields:
    """Exact, not 'at least'."""

    def test_the_body_has_the_three_contract_fields_and_no_others(
        self, envelope: TriggerEnvelope
    ) -> None:
        assert set(trigger_body(envelope)) == {"workItemId", "correlationId", "kind"}
        assert set(trigger_body(envelope)) == set(PAYLOAD_FIELDS)

    def test_the_values_are_the_envelopes_own(self, envelope: TriggerEnvelope) -> None:
        body = trigger_body(envelope)
        assert body["workItemId"] == str(envelope.work_item_id)
        assert body["correlationId"] == str(envelope.correlation_id)
        assert body["kind"] == "sample.flow"

    @pytest.mark.parametrize("forbidden", FORBIDDEN_IN_A_TRIGGER)
    def test_no_authority_bearing_field_appears(
        self, envelope: TriggerEnvelope, forbidden: str
    ) -> None:
        """Checked against the serialised body, so a nested value cannot hide from a key check."""
        serialised = json.dumps(trigger_body(envelope)).lower()
        assert forbidden.lower() not in serialised

    @pytest.mark.parametrize("kind", list(TriggerKind))
    def test_every_kind_in_the_closed_set_produces_the_same_shape(self, kind: TriggerKind) -> None:
        """A kind is a routing hint. It may not bring fields of its own.

        Parametrised over the whole enum rather than over the one kind the scaffold wires, because
        the property must already hold for the handlers that land later.
        """
        envelope = TriggerEnvelope(
            work_item_id=WorkItemId(uuid4()),
            correlation_id=CorrelationId("corr-1"),
            kind=kind,
        )
        assert set(trigger_body(envelope)) == set(PAYLOAD_FIELDS)


class TestTraceContextTravelsAsMetadata:
    """Correlation is followable across the hop without widening the body."""

    def test_the_traceparent_is_an_application_property_not_a_body_field(
        self, envelope: TriggerEnvelope
    ) -> None:
        """Putting it in the body would make the body something other than the three fields."""
        message = build_message(envelope, traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01")

        assert TRACEPARENT_PROPERTY in message.application_properties
        assert "traceparent" not in json.loads(b"".join(message.body).decode())

    def test_the_correlation_id_is_also_on_the_message_for_filtering(
        self, envelope: TriggerEnvelope
    ) -> None:
        """So an operator can filter the queue without deserializing every body."""
        message = build_message(envelope)
        assert message.correlation_id == str(envelope.correlation_id)

    def test_a_message_without_a_trace_still_publishes(self, envelope: TriggerEnvelope) -> None:
        """No tracer configured is normal on a developer machine and never fatal.

        Telemetry must not be able to stop a trigger being published — that would be observability
        outranking the work it observes.
        """
        message = build_message(envelope)
        assert not message.application_properties

    def test_expiry_is_set_so_a_stale_trigger_dead_letters(self, envelope: TriggerEnvelope) -> None:
        """A trigger that outlives the execution window can no longer lead to a valid execution."""
        message = build_message(envelope, time_to_live_seconds=900)
        assert message.time_to_live is not None
        assert message.time_to_live.total_seconds() == 900
