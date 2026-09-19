"""Publication of a durable outbox row to Service Bus.

**The payload is the whole contract, and it is three fields.** For a trigger: ``workItemId``,
``correlationId``, ``kind``. For an integration command: ``jobId``, ``correlationId``, ``kind``.
Nothing else, ever (``contracts/triggers.md``, `FR-INTEG-014`).

**Two envelope types, two bodies, two queues, one dispatcher.** The identifier differs because the
durable row differs — a trigger names a work item, a command names an integration job — and the
queues differ because their dead-letter semantics differ. What does *not* differ is the machinery:
one retry policy and one dead-letter story for every message this deployable publishes, because two
would be two places for "how many attempts before a human sees it" to be answered differently.

No tenant, requester, role, action, target, approval state, expiry or command content travels in
either body. A consumer reads authority from the durable record, which is what makes a forged or
replayed message unable to authorize anything.

**Correlation and trace context travel as message metadata, not as payload.** ``traceparent`` is a
transport concern — it says how to stitch this hop to the last one, not what may happen — so it
goes in the application properties, where a consumer restores it as ambient context. Putting it in
the body would make the body something other than the three fields the contract fixes, and every
guard on that body would then have an exception to carry.

``correlationId`` appears in both, deliberately: in the body because the contract says so, and in
``ServiceBusMessage.correlation_id`` so an operator can filter the queue on it without
deserializing anything.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from ragcore.domain.envelopes import (
    IntegrationCommandEnvelope,
    TriggerEnvelope,
)
from ragcore.messaging.credentials import service_bus_client

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from ragcore.config.settings import MessagingSettings

TRACEPARENT_PROPERTY: Final = "traceparent"
"""W3C Trace Context, as an application property.

The name is the W3C header name rather than a platform one, because the value is a W3C traceparent
and renaming it would mean every reader has to learn that this platform calls it something else.
"""

TRACESTATE_PROPERTY: Final = "tracestate"

PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset({"workItemId", "correlationId", "kind"})
"""Every key a trigger body may carry. Asserted by ``tests/messaging/test_trigger_payload.py``."""

INTEGRATION_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset({"jobId", "correlationId", "kind"})
"""Every key an integration command body may carry.

**A closed set, and the far side enforces it too.** `integrations.messaging.envelope` refuses a
message carrying a field this does not name, and dead-letters rather than sanitising — so a
publisher that added one here would not quietly succeed, it would produce an alert. Both halves are
stated because a contract only one side checks is a contract one deployment change removes.
"""


def trigger_body(envelope: TriggerEnvelope) -> dict[str, str]:
    """The entire message body for one trigger.

    A function rather than inline construction so that exactly one place decides what a trigger
    contains, and so a test can assert on it without a Service Bus client.

    Args:
        envelope: The trigger.

    Returns:
        The three contract fields, and nothing else.
    """
    return {
        "workItemId": str(envelope.work_item_id),
        "correlationId": str(envelope.correlation_id),
        "kind": envelope.kind.value,
    }


def integration_command_body(envelope: IntegrationCommandEnvelope) -> dict[str, str]:
    """The entire message body for one integration command.

    A function rather than inline construction so that exactly one place decides what a command
    contains, and so a test can assert on it without a Service Bus client.

    Args:
        envelope: The command.

    Returns:
        The three contract fields, and nothing else. **No organisation, no capability, no
        parameters** — those live on the durable job row the identifier names.
    """
    return {
        "jobId": str(envelope.job_id),
        "correlationId": str(envelope.correlation_id),
        "kind": envelope.kind.value,
    }


def message_body(envelope: TriggerEnvelope | IntegrationCommandEnvelope) -> dict[str, str]:
    """The body for either envelope type.

    Dispatches on the **type**, not on a flag or a string. A caller cannot ask for the wrong body
    for an envelope because there is no argument with which to ask.

    Args:
        envelope: The trigger or the command.

    Returns:
        That envelope's three contract fields.
    """
    if isinstance(envelope, IntegrationCommandEnvelope):
        return integration_command_body(envelope)
    return trigger_body(envelope)


def build_message(
    envelope: TriggerEnvelope | IntegrationCommandEnvelope,
    *,
    traceparent: str | None = None,
    tracestate: str | None = None,
    time_to_live_seconds: int | None = None,
) -> Any:  # The concrete type needs the SDK imported
    """Build the Service Bus message for one trigger.

    Separated from :meth:`ServiceBusTriggerPublisher.publish` so the message can be constructed and
    asserted on without a namespace, a credential or a network.

    Args:
        envelope: The trigger or the integration command.
        traceparent: The W3C trace context to continue, when there is one.
        tracestate: The accompanying vendor state, when there is one.
        time_to_live_seconds: Message expiry. A trigger that outlives the execution window can no
            longer lead to a valid execution, so it expires to the dead-letter queue rather than
            waking a consumer that would only refuse it.

    Returns:
        An ``azure.servicebus.ServiceBusMessage``.
    """
    from azure.servicebus import ServiceBusMessage

    # Typed as the SDK types it rather than as `dict[str, str]`: application properties accept
    # several scalar types, and narrowing here would make a future non-string property a type
    # error in this module rather than at the call site that introduced it.
    properties: dict[str | bytes, int | float | bytes | bool | str | UUID] = {}
    if traceparent:
        properties[TRACEPARENT_PROPERTY] = traceparent
    if tracestate:
        properties[TRACESTATE_PROPERTY] = tracestate

    message = ServiceBusMessage(
        body=json.dumps(message_body(envelope), sort_keys=True),
        content_type="application/json",
        subject=envelope.kind.value,
        correlation_id=str(envelope.correlation_id),
        application_properties=properties or None,
    )

    if time_to_live_seconds is not None:
        from datetime import timedelta

        message.time_to_live = timedelta(seconds=time_to_live_seconds)

    return message


class ServiceBusTriggerPublisher:
    """Publishes a trigger or an integration command, authenticated by managed identity.

    Satisfies :class:`~ragcore.application.ports.MessagePublisherPort`.

    The client is supplied rather than constructed per publish: it owns a connection, and opening
    one per message would turn the dispatcher's happy path into a connection storm.
    """

    def __init__(self, settings: MessagingSettings, client: Any | None = None) -> None:
        """Bind the publisher to a namespace and queue.

        Args:
            settings: The messaging settings. The namespace is a fully qualified name; there is no
                connection string anywhere in this path.
            client: An open ``ServiceBusClient``. Constructed from settings when omitted.
        """
        self._settings = settings
        self._client = client if client is not None else service_bus_client(settings)

    def _queue_for(self, envelope: TriggerEnvelope | IntegrationCommandEnvelope) -> str:
        """Which queue this envelope goes to.

        Args:
            envelope: The trigger or the command.

        Returns:
            The queue name.

        Raises:
            ValueError: When asked to publish an integration **result** kind. RagCore consumes
                those and holds no Sender role on the results queue, so this would fail at the
                platform anyway — failing here names the defect instead of surfacing it as a
                puzzling authorization error against a queue nobody expected this process to write.
        """
        if not isinstance(envelope, IntegrationCommandEnvelope):
            return self._settings.trigger_queue

        if not envelope.kind.is_outbound:
            raise ValueError(
                f"{envelope.kind.value} is consumed by RagCore, never published by it. Publishing "
                "a result would let this process report an outcome for work it did not perform."
            )

        return self._settings.integration_command_queue

    async def publish(
        self,
        envelope: TriggerEnvelope | IntegrationCommandEnvelope,
        *,
        traceparent: str | None = None,
        tracestate: str | None = None,
    ) -> None:
        """Publish one trigger or integration command.

        Consumers assume at-least-once delivery, so this makes no attempt to be exactly-once. The
        duplicate is absorbed downstream by the atomic claim, which is a property of the durable
        record rather than of the transport — and therefore holds even when the transport
        misbehaves.

        Args:
            envelope: The trigger or the command.
            traceparent: The W3C trace context to continue.
            tracestate: The accompanying vendor state.

        Raises:
            ValueError: When the envelope is an integration result kind. See :meth:`_queue_for`.
        """
        message = build_message(
            envelope,
            traceparent=traceparent,
            tracestate=tracestate,
            time_to_live_seconds=self._settings.message_time_to_live_seconds,
        )

        async with self._client.get_queue_sender(self._queue_for(envelope)) as sender:
            await sender.send_messages(message)
