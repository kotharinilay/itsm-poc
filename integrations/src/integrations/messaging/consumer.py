"""The command consumer. **Decides what to do with a delivery, not what to execute.**

This module owns the message-handling policy — complete, abandon or dead-letter — and delegates the
work itself to the execution leg. Keeping them apart matters because the two answer different
questions: the leg asks *may this run and what happened*, the consumer asks *what should become of
this message*.

**Three dispositions, and the difference between them is the whole retry policy:**

* **Complete** — the command was handled: executed, refused, or recognised as a duplicate. It
  leaves the queue.
* **Dead-letter** — the command cannot be interpreted, or names nothing. It surfaces for a human
  and is **never auto-replayed**.
* **Abandon** — a transient failure *before* any effect. It is redelivered, and the derived key
  protects the far side if the effect somehow did land.

**A refusal completes rather than dead-lettering.** The refusal is itself the durable answer and has
already been announced to RagCore, so redelivering it would produce the same refusal for ever.

**A post-execution failure completes too.** The effect may already have happened; abandoning would
redeliver a command whose external call MAY have landed, and a failed authorized action requires
fresh human authorization rather than an automatic retry (`FR-EXEC-006`).

**Dead-lettered work is not automatically replayed** (spec §27.3). Where the message carried
authorized work, that is a **governance failure** rather than an operational one: it surfaces as
approved-but-not-executed, and recovery is fresh authorization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from integrations.api.middleware.correlation import bind_correlation_id
from integrations.messaging.envelope import EnvelopeError, MessageEnvelope, MessageKind

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.execution.executor import ExecutionLeg

__all__ = ["Disposition", "HandledMessage", "CommandConsumer"]

logger = logging.getLogger(__name__)


class Disposition(Enum):
    """What should become of the message."""

    COMPLETE = "complete"
    DEAD_LETTER = "dead_letter"
    ABANDON = "abandon"


@dataclass(frozen=True, slots=True)
class HandledMessage:
    """The consumer's verdict on one delivery.

    Attributes:
        disposition: What to do with the message.
        reason: A short, **non-disclosing** reason for the dead-letter description. It names the
            class of problem and never a fragment of the message: a message that violated its
            contract is exactly the content not to copy into an operator-visible field.
    """

    disposition: Disposition
    reason: str = ""


class CommandConsumer:
    """Handles one `integration.execute` delivery."""

    def __init__(self, leg: ExecutionLeg) -> None:
        """Bind the consumer.

        Args:
            leg: The execution leg.
        """
        self._leg = leg

    async def handle(self, body: str) -> HandledMessage:
        """Process one message body.

        Args:
            body: The raw message.

        Returns:
            The verdict.
        """
        try:
            envelope = MessageEnvelope.from_json(body)
        except EnvelopeError as error:
            # A MESSAGE THAT DOES NOT MATCH ITS CONTRACT IS REFUSED, NOT REPAIRED. This is where a
            # command carrying a `tenantId`, `parameters` or `treatment` field lands — dead-lettered
            # with an alert rather than stripped and processed, because stripping returns success to
            # whoever sent it and leaves the attempt indistinguishable from an ordinary message.
            logger.warning(
                "Integration command rejected at the envelope boundary: %s",
                error,
            )
            return HandledMessage(Disposition.DEAD_LETTER, "envelope-contract")

        # Bound before anything else, so every log line, span and durable record from here on
        # carries the journey — including the ones written while deciding to refuse.
        bind_correlation_id(envelope.correlation_id)

        if envelope.kind is not MessageKind.EXECUTE:
            # A RESULT KIND ON THE COMMAND QUEUE. Not an authorization to proceed and not something
            # to interpret helpfully: it means a publisher is misconfigured, which a human should
            # see rather than a consumer absorb.
            logger.warning(
                "Unexpected kind on the command queue: %s",
                envelope.kind.value,
                extra={"correlationId": envelope.correlation_id},
            )
            return HandledMessage(Disposition.DEAD_LETTER, "unexpected-kind")

        try:
            report = await self._leg.run(envelope.job_id, envelope.correlation_id)
        except Exception:
            # BEFORE ANY EFFECT, by construction: the leg records its own outcome for everything
            # past invocation, so an exception escaping it is a failure of the machinery rather
            # than of the operation. Abandoned for redelivery — and if the effect somehow did
            # happen, the derived key suppresses the second one.
            logger.exception(
                "Integration command handling failed before an outcome was recorded",
                extra={"correlationId": envelope.correlation_id},
            )
            return HandledMessage(Disposition.ABANDON, "transient")

        if report.dead_letter:
            return HandledMessage(Disposition.DEAD_LETTER, "unknown-job")

        # Executed, refused, or suppressed as a duplicate — all three are handled. The durable
        # record and the result announcement are already written, so redelivering would add nothing
        # and would re-announce an outcome RagCore has already been told about.
        return HandledMessage(Disposition.COMPLETE)
