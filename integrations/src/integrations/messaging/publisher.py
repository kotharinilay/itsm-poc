"""The result publisher and its dispatcher. **Entra authentication, and an outbox in front.**

Constitution §Idempotency and messaging: each publishing deployable runs its own transactional
outbox, and a row becomes durable before asynchronous publication. Without that, a crash between
"the external effect happened" and "we told RagCore" loses the only evidence it did.

**Managed identity only.** There is no connection-string setting for Service Bus and there will not
be one — the namespace is configuration, the credential is the identity the container runs as.

**Correlation rides on the message property as well as in the body**, so an operator can filter the
queue on it without deserialising every message. The body remains the contract; this is an index.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Final

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from azure.core.credentials_async import AsyncTokenCredential

    from integrations.config.settings import ServiceBusSettings
    from integrations.messaging.envelope import MessageEnvelope

__all__ = ["MESSAGE_TIME_TO_LIVE", "ResultPublisher"]

logger = logging.getLogger(__name__)

MESSAGE_TIME_TO_LIVE: Final = timedelta(minutes=15)
"""The same bound as the execution window (spec §27.3).

A result that cannot be delivered inside the window can no longer lead to a valid resume, so it
**expires to the dead-letter queue rather than waking a consumer that would only refuse it**. The
TTL is on the message rather than checked by the consumer because a queue that holds expired work is
a queue whose depth stops meaning anything.
"""


class ResultPublisher:
    """Publishes result envelopes to the result queue."""

    def __init__(self, settings: ServiceBusSettings, credential: AsyncTokenCredential) -> None:
        """Bind the publisher.

        Args:
            settings: The namespace and the result queue.
            credential: The managed identity. **No connection string, ever.**
        """
        self._settings = settings
        self._credential = credential

    async def publish(self, envelope: MessageEnvelope) -> None:
        """Send one envelope.

        Args:
            envelope: Three fields, nothing authority-bearing.

        Raises:
            Exception: Propagated so the dispatcher records the failure and increments the attempt
                count. **Swallowing here would mark a row dispatched that never reached the queue**
                — the one failure mode an outbox exists to make impossible.
        """
        async with (
            ServiceBusClient(
                fully_qualified_namespace=self._settings.namespace,
                credential=self._credential,
            ) as client,
            client.get_queue_sender(self._settings.result_queue) as sender,
        ):
            message = ServiceBusMessage(
                body=envelope.to_json(),
                content_type="application/json",
                # An operator filters on this without deserialising the body.
                correlation_id=envelope.correlation_id,
                time_to_live=MESSAGE_TIME_TO_LIVE,
                subject=envelope.kind.value,
            )
            await sender.send_messages(message)

        logger.info(
            "Published %s",
            envelope.kind.value,
            extra={"correlationId": envelope.correlation_id},
        )
