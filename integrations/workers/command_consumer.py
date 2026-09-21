"""Worker entry point: consumes `integration.execute` from the command queue.

**The behaviour is in :mod:`integrations.messaging.consumer`; this module is the process that runs
it.** The split is the same one RagCore makes in ``ragcore/workers/resume_worker.py``, and for the
same reason: the decision logic must be testable without a Service Bus namespace, a credential or a
network, because those are exactly what CI does not have.

**Every command is untrusted.** The message carried three fields — a job identifier, a correlation
identifier and a routing hint — and *none of them is authority*. The organisation, the capability,
its version, its parameters and its approval all come from the durable ``integration_job`` row that
identifier names. A consumer that read authority from a message would be defective regardless of
where the message came from (`FR-INTEG-014`, `FR-INTEG-018`).

``kind`` is a **routing hint only**. It says which handler to dispatch to; it never says what may
happen. A forged `integration.execute` reaches a handler that then loads the row, finds no
authorized work inside its window, and refuses.

**Settlement is the retry policy.** The three dispositions below are not an implementation detail of
this loop — they *are* `FR-INTEG-027`:

* complete — handled, whether executed, refused or recognised as a duplicate;
* dead-letter — uninterpretable or naming nothing; **never auto-replayed**;
* abandon — transient failure *before* any effect, safe to redeliver.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from integrations.messaging.consumer import CommandConsumer, Disposition

if TYPE_CHECKING:  # pragma: no cover — import-time typing only
    from integrations.messaging.consumer import HandledMessage

__all__ = ["SETTLEMENT", "handle_command", "main"]

logger = logging.getLogger(__name__)

SETTLEMENT: Final[dict[Disposition, str]] = {
    Disposition.COMPLETE: "complete_message",
    Disposition.DEAD_LETTER: "dead_letter_message",
    Disposition.ABANDON: "abandon_message",
}
"""Disposition to Service Bus settlement call.

**A table rather than a chain of ``if``s, so the mapping is assertable without a namespace.** The
loop that will use it is not written yet; this is the part a test can pin now, and getting it wrong
is how a dead-letter silently becomes a completion — the failure that makes approved-but-not-
executed work disappear instead of surfacing.

Every member of :class:`~integrations.messaging.consumer.Disposition` appears exactly once, which
``tests/unit/test_command_worker.py`` asserts: a disposition with no settlement is a message that
is received, acted on, and then left to reappear at lock expiry.
"""


async def handle_command(consumer: CommandConsumer, body: str) -> HandledMessage:
    """Handle one delivery and report how it should be settled.

    Thin on purpose. It exists so the worker has one named seam that a test can drive, and so the
    logging below happens for every delivery rather than at whichever call site remembered.

    Args:
        consumer: The command consumer holding the execution leg.
        body: The raw message body.

    Returns:
        The verdict, carrying the disposition and a **non-disclosing** reason.
    """
    handled = await consumer.handle(body)

    if handled.disposition is Disposition.DEAD_LETTER:
        # The one event worth seeing (`FR-DEMO-025`). Logged at warning because a dead-lettered
        # command may mean authorized work never ran, which is a governance failure rather than an
        # operational one — and the reason never carries a fragment of the offending message.
        logger.warning(
            "Integration command dead-lettered and will not be replayed. reason=%s",
            handled.reason,
        )

    return handled


def main() -> None:
    """Worker entry point.

    Composition — engine, session factory, Service Bus receiver, credential resolver and the
    execution leg — belongs to the deployment that runs this and is wired alongside the other
    workers. :func:`handle_command`, :data:`SETTLEMENT` and
    :class:`~integrations.messaging.consumer.CommandConsumer` are the behaviour, and are what the
    tests exercise.

    Raises:
        NotImplementedError: Always, for now. **Deliberately loud rather than a loop that connects
            to nothing**: a worker that started, logged "listening" and consumed no message would
            look healthy while approved work accumulated unexecuted, which is the failure this
            platform is least able to detect.
    """
    raise NotImplementedError(
        "the consumer's parsing, refusal, execution and settlement paths are implemented and "
        "tested; the worker's process wiring lands with the other workers."
    )
